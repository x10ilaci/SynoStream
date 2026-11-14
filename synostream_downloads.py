"""Download Station transport. Read retries and state-changing requests are separate."""
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

import requests
from synostream_nas import RemoteNASClient
from synostream_torrent_selection import TorrentSelectionMixin, SELECTION_APIS

TASK_API = 'SYNO.DownloadStation.Task'
MAX_TORRENT_BYTES = 32 * 1024 * 1024
COMPLETE_STATUSES = {'finished', 'seeding'}
ERRORS = {
    105: 'A NAS-fióknak nincs Download Station jogosultsága.',
    106: 'A NAS-munkamenet lejárt.',
    107: 'A NAS-munkamenet megszakadt.',
    119: 'A NAS-munkamenet érvénytelen.',
    400: 'A Download Station feladata nem hajtható végre.',
    401: 'A feladat vagy a fájl célmappája nem érhető el.',
    402: 'Érvénytelen torrentfájl vagy letöltési hivatkozás.',
    403: 'Elérted a Download Station feladatkorlátját.',
    404: 'Érvénytelen feladatazonosító.',
    405: 'A Download Station nem tudta szüneteltetni a feladatot.',
    406: 'Nincs beállítva alapértelmezett letöltési célmappa a NAS-on.',
    407: 'A NAS nem tudja használni a kiválasztott célmappát.',
    408: 'A megadott fájl nem található a NAS-on.',
}


class DownloadStationError(RuntimeError):
    pass


def normalize_destination(path):
    path = (path or '').strip().removeprefix('syno://').replace('\\', '/')
    pieces = [part for part in path.split('/') if part]
    if any(part in ('.', '..') or '\x00' in part for part in pieces):
        raise ValueError('A célmappa nem tartalmazhat relatív útvonalelemet.')
    return '/'.join(pieces)


def validate_uri(uri):
    uri = (uri or '').strip()
    if any(c in uri for c in ('\r', '\n', '\x00')):
        raise ValueError('Egyszerre egy letöltési hivatkozást adj meg.')
    parsed = urlsplit(uri)
    if parsed.scheme.lower() == 'magnet':
        if not any(value.lower().startswith('urn:btih:') for value in parse_qs(parsed.query).get('xt', [])):
            raise ValueError('A magnetlinkből hiányzik a torrent azonosítója.')
    elif parsed.scheme.lower() in ('http', 'https') and parsed.hostname:
        pass
    else:
        raise ValueError('Magnet-, HTTP- vagy HTTPS-hivatkozást adj meg.')
    return uri


def is_complete(task):
    return task.get('status') in COMPLETE_STATUSES


class DownloadStationClient(TorrentSelectionMixin, RemoteNASClient):
    def __init__(self, credentials, should_stop=None):
        super().__init__(credentials, should_stop, session_name='DownloadStation',
                         extra_apis=(TASK_API, 'SYNO.DownloadStation.Info') + SELECTION_APIS)

    def connect(self):
        super().connect()
        info = self.api_info.get(TASK_API)
        if not info:
            raise DownloadStationError('A Download Station nem érhető el. Telepítsd a NAS-on, és ellenőrizd a fiók jogosultságát.')
        self.task_version = min(3, int(info.get('maxVersion') or 1))
        self.task_url = self.base_url.rstrip('/') + '/webapi/' + (info.get('path') or 'DownloadStation/task.cgi').lstrip('/')

    def _task_request(self, method, *, readonly=False, file_payload=None, **parameters):
        with self.lock:
            renewed = False
            attempts = 3 if readonly else 2  # The second write attempt is only for explicit session rejection.
            for attempt in range(attempts):
                self._check_cancelled()
                data = dict(api=TASK_API, version=self.task_version, method=method, _sid=self.sid, **parameters)
                try:
                    if readonly:
                        response = self.session.get(self.task_url, params=data, timeout=(8, 25))
                    elif file_payload:
                        name, content = file_payload
                        # Requests serializes regular form parameters before the multipart file, as DSM requires.
                        response = self.session.post(self.task_url, data=data,
                            files={'file': (name, content, 'application/x-bittorrent')}, timeout=(8, 45))
                    else:
                        response = self.session.post(self.task_url, data=data, timeout=(8, 30))
                    try:
                        if readonly and response.status_code in (429, 502, 503, 504) and attempt < attempts - 1:
                            self._pause(0.5 * 2 ** attempt)
                            continue
                        response.raise_for_status()
                        payload = response.json()
                    finally:
                        response.close()
                except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
                    if readonly and not isinstance(exc, requests.HTTPError) and attempt < attempts - 1:
                        self._pause(0.5 * 2 ** attempt)
                        continue
                    if not readonly:
                        raise DownloadStationError('Nem érkezett biztos visszaigazolás. Frissítsd a feladatlistát, mielőtt újra elküldöd a műveletet.') from None
                    raise DownloadStationError('A Download Station most nem érhető el. Próbáld újra a frissítést.') from None
                except (ValueError, TypeError):
                    if not readonly:
                        raise DownloadStationError('Nem érkezett biztos visszaigazolás. Frissítsd a feladatlistát, mielőtt újra elküldöd a műveletet.') from None
                    raise DownloadStationError('A NAS nem értelmezhető Download Station-választ adott.') from None
                if not isinstance(payload, dict):
                    raise DownloadStationError('A NAS válaszformátuma nem támogatott.')
                if payload.get('success'):
                    result = payload.get('data') or {}
                    if isinstance(result, list):
                        failures = [row for row in result if int(row.get('error') or 0)]
                        if failures:
                            raise DownloadStationError('Néhány feladat művelete nem sikerült. Frissítsd a listát, és ellenőrizd az állapotokat.')
                    return result
                code = (payload.get('error') or {}).get('code')
                if code in (106, 107, 119) and not renewed:
                    self.connect()
                    renewed = True
                    continue
                raise DownloadStationError(ERRORS.get(code, f'Download Station-hiba (DSM: {code}).'))
            raise DownloadStationError('A Download Station munkamenetét nem sikerült helyreállítani.')

    def list_tasks(self):
        tasks = []
        seen = set()
        offset = 0
        while True:
            data = self._task_request('list', readonly=True, offset=offset, limit=100,
                                      additional='detail,transfer')
            batch = data.get('tasks') or []
            if not isinstance(batch, list):
                raise DownloadStationError('A NAS feladatlistája nem értelmezhető.')
            for task in batch:
                if not isinstance(task, dict):
                    raise DownloadStationError('A NAS feladatlistája nem értelmezhető.')
                identity = task.get('id')
                if not isinstance(identity, str) or not identity or identity in seen:
                    raise DownloadStationError('A NAS ismétlődő vagy érvénytelen feladatlistát adott.')
                seen.add(identity)
            tasks.extend(batch)
            offset += len(batch)
            total = int(data.get('total', offset))
            if not batch and offset < total:
                raise DownloadStationError('A NAS hiányos feladatlistát adott; a korábbi lista megmarad.')
            if not batch or offset >= total:
                return tasks
            if offset >= 10000:
                raise DownloadStationError('A NAS több mint 10 000 feladatot adott vissza; szűkítsd a feladatlistát a NAS-on.')

    def create(self, *, uri=None, torrent_file=None, destination=''):
        if bool(uri) == bool(torrent_file):
            raise ValueError('Egy torrentfájlt vagy egy hivatkozást válassz.')
        destination = normalize_destination(destination)
        options = {}
        if destination:
            if self.task_version < 2:
                raise DownloadStationError('Ez a Download Station nem támogat feladatonkénti célmappát.')
            options['destination'] = destination
        file_payload = None
        if torrent_file:
            path = Path(torrent_file)
            if path.suffix.lower() != '.torrent' or not path.is_file():
                raise ValueError('Létező .torrent fájlt válassz.')
            if path.stat().st_size > MAX_TORRENT_BYTES:
                raise ValueError('A torrentfájl legfeljebb 32 MiB lehet.')
            with path.open('rb') as source:
                content = source.read(MAX_TORRENT_BYTES + 1)
            if not content or len(content) > MAX_TORRENT_BYTES:
                raise ValueError('A torrentfájl üres vagy túl nagy.')
            file_payload = path.name, content
        else:
            if self.task_version < 3:
                raise DownloadStationError('A hivatkozásos hozzáadáshoz újabb Download Station API szükséges.')
            options['uri'] = validate_uri(uri)
        return self._task_request('create', file_payload=file_payload, **options)

    def task_action(self, action, ids):
        if action not in ('pause', 'resume', 'delete'):
            raise ValueError('Ismeretlen feladatművelet.')
        if not ids or any(not isinstance(value, str) or not value or ',' in value for value in ids):
            raise ValueError('Válassz érvényes letöltési feladatot.')
        options = {'id': ','.join(ids)}
        if action == 'delete':
            options['force_complete'] = 'false'
        return self._task_request(action, **options)
