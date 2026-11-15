"""Metadata-only Download Station preparation, followed by an explicit selected-file start."""
import json
import logging
from pathlib import Path, PurePosixPath
import time

import requests

TASK2 = 'SYNO.DownloadStation2.Task'
LIST_API = 'SYNO.DownloadStation2.Task.List'
POLL_API = 'SYNO.DownloadStation2.Task.List.Polling'
LOCATION_API = 'SYNO.DownloadStation2.Settings.Location'
SELECTION_APIS = (TASK2, LIST_API, POLL_API, LOCATION_API)


def default_file_selected(name):
    path = str(name or '').replace('\\', '/')
    return 'sample' not in path.casefold()


def validate_files(metadata):
    files = metadata.get('files')
    if not isinstance(files, list) or not files or len(files) > 50000:
        raise ValueError('A NAS még nem adott használható fájllistát. A letöltés nem indult el.')
    seen = set()
    result = []
    for file in files:
        index = file.get('index')
        if type(index) is not int or index < 0 or index in seen:
            raise ValueError('A NAS fájllistájának azonosítói nem érvényesek. A letöltés nem indult el.')
        seen.add(index)
        name = file.get('name')
        if not isinstance(name, str) or not name:
            raise ValueError('A NAS fájllistája hiányos. A letöltés nem indult el.')
        result.append(dict(index=index, name=name, size=file.get('size', 0)))
    return result


class TorrentSelectionMixin:
    def _selection_request(self, api, method, *, readonly=False, upload=None, **params):
        from synostream_downloads import DownloadStationError
        attempts = 3 if readonly else 2
        renewed = False
        for attempt in range(attempts):
            self._check_cancelled()
            info = self.api_info.get(api) or {}
            if not info or int(info.get('maxVersion', 0)) < (1 if api == LOCATION_API else 2):
                raise DownloadStationError('A NAS ezen a kapcsolaton nem támogatja az indulás előtti fájlválasztást. A letöltés nem indult el.')
            version = 1 if api == LOCATION_API else 2
            endpoint = self.base_url.rstrip('/') + '/webapi/' + info['path'].lstrip('/')
            data = dict(api=api, method=method, version=version, _sid=self.sid)
            data.update({key: json.dumps(value, ensure_ascii=False, separators=(',', ':')) for key, value in params.items()})
            try:
                if readonly:
                    response = self._get(endpoint, params=data, timeout=(8, 30))
                elif upload:
                    response = self._post(endpoint, data=data,
                        files={'torrent': (upload[0], upload[1], 'application/x-bittorrent')}, timeout=(8, 60))
                else:
                    response = self._post(endpoint, data=data, timeout=(8, 60))
                try:
                    response.raise_for_status()
                    payload = response.json()
                finally:
                    response.close()
            except (requests.RequestException, ValueError):
                if readonly and attempt < attempts - 1:
                    self._pause(.5 * 2 ** attempt)
                    continue
                raise DownloadStationError('Nem érkezett biztos NAS-visszaigazolás. Ellenőrizd a feladatlistát; a műveletet nem ismételtem meg automatikusan.') from None
            if not isinstance(payload, dict):
                raise DownloadStationError('A NAS fájlválasztási válasza nem értelmezhető.')
            if payload.get('success'):
                return payload.get('data') or {}
            code = (payload.get('error') or {}).get('code')
            if code in (106, 107, 119) and not renewed:
                self.connect()
                renewed = True
                continue
            raise DownloadStationError(f'A NAS fájlválasztási művelete nem sikerült (DSM: {code}). Letöltés kijelölés nélkül nem indul.')
        raise DownloadStationError('A NAS-munkamenetet nem sikerült helyreállítani.')

    def prepare(self, *, uri=None, torrent_file=None, destination=''):
        from synostream_downloads import DownloadStationError, normalize_destination, validate_uri, MAX_TORRENT_BYTES
        if bool(uri) == bool(torrent_file):
            raise ValueError('Egy torrentfájlt vagy egy hivatkozást válassz.')
        with self.lock:
            destination = normalize_destination(destination)
            if not destination:
                location = self._selection_request(LOCATION_API, 'get', readonly=True)
                destination = normalize_destination(location.get('default_destination', ''))
            if not destination:
                raise DownloadStationError('Válassz célmappát a NAS-on. A letöltés nem indult el.')
            params = dict(type='file' if torrent_file else 'url', destination=destination, create_list=True)
            upload = None
            if torrent_file:
                path = Path(torrent_file)
                if path.suffix.lower() != '.torrent' or not path.is_file():
                    raise ValueError('Létező .torrent fájlt válassz.')
                with path.open('rb') as source:
                    content = source.read(MAX_TORRENT_BYTES + 1)
                if not content or len(content) > MAX_TORRENT_BYTES:
                    raise ValueError('A torrentfájl üres vagy túl nagy.')
                upload = path.name, content
                params['file'] = ['torrent']
                params['size'] = len(content)
            else:
                params['url'] = [validate_uri(uri)]
            result = self._selection_request(TASK2, 'create', upload=upload, **params)
            ids = result.get('list_id')
            ids = [ids] if isinstance(ids, str) else ids
            if not isinstance(ids, list) or not ids or any(not isinstance(value, str) or not value for value in ids):
                raise DownloadStationError('A NAS nem igazolta vissza a fájllista előkészítését. A letöltést nem indítom el.')
            prepared = getattr(self, 'prepared_lists', {})
            self.prepared_lists = prepared
            for identifier in ids:
                prepared[identifier] = {'list_id': identifier, 'destination': destination, 'files': [], 'submitted': False}
            try:
                results = []
                for identifier in ids:
                    # The NAS resolves torrent/magnet metadata before returning this file list.
                    metadata = self._selection_request(LIST_API, 'get', readonly=True, list_id=identifier)
                    files = validate_files(metadata)
                    preview = dict(list_id=identifier, title=str(metadata.get('title') or 'Torrent'),
                                   destination=destination, files=files, submitted=False)
                    prepared[identifier] = preview
                    results.append(dict(preview))
                return results
            except Exception:
                for identifier in ids:
                    try:
                        self.discard_prepared(identifier)
                    except Exception:
                        pass
                raise

    def discard_prepared(self, list_id):
        with self.lock:
            prepared = getattr(self, 'prepared_lists', {})
            entry = prepared.get(list_id)
            if entry is None or entry.get('submitted'):
                return
            self._selection_request(LIST_API, 'delete', list_id=list_id)
            prepared.pop(list_id, None)

    def start_prepared(self, list_id, selected):
        from synostream_downloads import DownloadStationError
        with self.lock:
            prepared = getattr(self, 'prepared_lists', {})
            entry = prepared.get(list_id)
            if entry is None or entry.get('submitted'):
                raise DownloadStationError('Ez a fájllista már elküldött vagy lejárt. Frissítsd a letöltési feladatokat.')
            available = {file['index'] for file in entry['files']}
            if not selected or any(type(value) is not int or value not in available for value in selected):
                raise ValueError('Legalább egy érvényes fájlt jelölj ki. Kijelölés nélkül nem indul letöltés.')
            selected = sorted(set(selected))
            entry['submitted'] = True  # Never replay an uncertain start.
            result = self._selection_request(POLL_API, 'download', list_id=list_id, selected=selected,
                                             destination=entry['destination'], create_subfolder=True)
            ticket = result.get('task_id')
            if not isinstance(ticket, str) or not ticket:
                raise DownloadStationError('A NAS nem adott biztos indítási visszaigazolást. Ellenőrizd a feladatlistát, mielőtt újra hozzáadod.')
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                self._check_cancelled()
                status = self._selection_request(POLL_API, 'download_status', readonly=True, task_id=ticket)
                if status.get('finish'):
                    try:
                        self._selection_request(POLL_API, 'download_stop', task_id=ticket)
                    except Exception:
                        logging.getLogger('SynoStream').warning('A Download Station lezárási kérése nem sikerült; a visszaigazolt indítási eredmény megmaradt.')
                    if not status.get('success'):
                        raise DownloadStationError('A NAS nem tudta elindítani a kijelölt fájlokat. Ellenőrizd a feladatlistát.')
                    prepared.pop(list_id, None)
                    return status.get('data') or {}
                self._pause(.5)
            raise DownloadStationError('A kijelölt fájlok indításának visszaigazolása lejárt. Ellenőrizd a feladatlistát; automatikus ismétlés nem történt.')
