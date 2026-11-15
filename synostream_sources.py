"""Paired SMB/NAS roots: one identity, bounded local checks, lazy NAS fallback."""
from dataclasses import dataclass
import contextlib
import io
import json
import ntpath
import os
import posixpath
import re
import threading
import time
import uuid

PREFIX = 'syno://'


def _drive_connection(drive):
    """Query the current Windows drive mapping without connecting/reconnecting."""
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL('mpr').WNetGetConnectionW
    api.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    api.restype = wintypes.DWORD
    capacity = 512
    for _ in range(3):
        size = wintypes.DWORD(capacity)
        buffer = ctypes.create_unicode_buffer(capacity)
        status = api(drive, buffer, ctypes.byref(size))
        if status != 234: return status, buffer.value if status == 0 else ''
        if not capacity < size.value <= 32768: break
        capacity = size.value
    return 234, ''


def _remembered_drive_connection(drive):
    """Disconnected persistent drives still have a locally stored UNC target."""
    import ctypes
    import winreg
    from ctypes import wintypes
    drive_type = ctypes.WinDLL('kernel32').GetDriveTypeW
    drive_type.argtypes = (wintypes.LPCWSTR,)
    drive_type.restype = wintypes.UINT
    # Never replace an actual local/removable drive with a stale saved mapping.
    if drive_type(drive + '\\') not in (0, 1, 4): return ''
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Network\\' + drive[0]) as key:
            value, _ = winreg.QueryValueEx(key, 'RemotePath')
            return value if isinstance(value, str) else ''
    except OSError:
        return ''


def expand_mapped_path(value):
    """Turn a mapped Z:\\folder into UNC; leave real local drives untouched."""
    if os.name != 'nt' or not isinstance(value, str): return value
    normalized = ntpath.normpath(value.replace('/', '\\'))
    drive, tail = ntpath.splitdrive(normalized)
    if len(drive) != 2 or drive[1] != ':' or not tail.startswith('\\'): return value
    try:
        status, target = _drive_connection(drive.upper())
        if status in (1201, 1222, 1203, 2250): target = _remembered_drive_connection(drive.upper())
        if not target.startswith('\\\\') or target.startswith(('\\\\?\\', '\\\\.\\')): return value
        target = ntpath.normpath(target)
        if len([part for part in target.split('\\') if part]) < 2: return value
        return ntpath.normpath(ntpath.join(target, tail.lstrip('\\')))
    except (OSError, ValueError, AttributeError):
        return value


def remote_root(value):
    value = str(value or '').strip().strip('"')
    if value.startswith(PREFIX):
        value = value[len(PREFIX):]
    if not value.startswith('/') or any(part == '..' for part in value.replace('\\', '/').split('/')):
        raise ValueError('A NAS-elérés syno:///megosztás/mappa alakú legyen.')
    value = posixpath.normpath('/' + value.replace('\\', '/').lstrip('/'))
    if value == '/':
        raise ValueError('A NAS-on egy médiamappát válassz, ne a megosztások listáját.')
    return PREFIX + value


def local_root(value):
    value = str(value or '').strip().strip('"').replace('/', '\\')
    value = expand_mapped_path(value)
    if not value.startswith('\\\\') or value.startswith(('\\\\?\\', '\\\\.\\')):
        raise ValueError('A helyi elérés \\\\NAS\\megosztás\\mappa alakú SMB-útvonal legyen.')
    if '..' in value.split('\\'):
        raise ValueError('Az SMB-útvonal nem tartalmazhat szülőmappára hivatkozást.')
    value = ntpath.normpath(value)
    if len([part for part in value.split('\\') if part]) < 2:
        raise ValueError('Az SMB-eléréshez a megosztás nevét is meg kell adni.')
    return value.rstrip('\\')


@dataclass(frozen=True)
class SourcePair:
    id: str
    local: str
    remote: str
    library_id: str = 'movies'

    def to_dict(self):
        return dict(id=self.id, local_root=self.local, remote_root=self.remote, library_id=self.library_id)


def parse_pairs(values):
    if not isinstance(values, list) or len(values) > 64:
        raise ValueError('Legfeljebb 64 összerendelt médiamappa állítható be.')
    pairs = []
    for row in values:
        if not isinstance(row, dict):
            raise ValueError('Az összerendelt mappa beállítása nem értelmezhető.')
        pair = SourcePair(str(row.get('id') or uuid.uuid4().hex), local_root(row.get('local_root')), remote_root(row.get('remote_root')), str(row.get('library_id') or 'movies'))
        for previous in pairs:
            local_overlap = _local_relative(pair.local, previous.local) is not None or _local_relative(previous.local, pair.local) is not None
            remote_overlap = _remote_relative(pair.remote, previous.remote) is not None or _remote_relative(previous.remote, pair.remote) is not None
            if pair.id == previous.id or local_overlap or remote_overlap:
                raise ValueError('Az összerendelt mappák azonosítói és gyökerei nem fedhetik át egymást.')
        pairs.append(pair)
    return pairs


def _local_relative(path, root):
    path, root = ntpath.normpath(path), ntpath.normpath(root)
    if ntpath.normcase(path) == ntpath.normcase(root):
        return ''
    if ntpath.normcase(path).startswith(ntpath.normcase(root).rstrip('\\') + '\\'):
        return path[len(root.rstrip('\\')) + 1:].replace('\\', '/')
    return None


def _remote_relative(path, root):
    if path == root:
        return ''
    return path[len(root) + 1:] if path.startswith(root.rstrip('/') + '/') else None


class BoundedIO:
    """A hung Windows SMB operation cannot hold a GUI/scan thread indefinitely."""
    def __init__(self, limit=4):
        self.slots = threading.BoundedSemaphore(limit)
        self.lock = threading.Lock()
        self.pending = {}

    def run(self, key, operation, timeout=1.2):
        with self.lock:
            job = self.pending.get(key)
            if job is None:
                if not self.slots.acquire(blocking=False):
                    raise TimeoutError('A helyi NAS-elérés most nem ellenőrizhető.')
                job = dict(done=threading.Event(), result=None, error=None)
                self.pending[key] = job
                def work():
                    try: job['result'] = operation()
                    except BaseException as error: job['error'] = error
                    finally:
                        job['done'].set()
                        with self.lock: self.pending.pop(key, None)
                        self.slots.release()
                threading.Thread(target=work, name='SynoStream-SMB', daemon=True).start()
        if not job['done'].wait(timeout):
            raise TimeoutError('A helyi NAS-elérés időkorlátja lejárt.')
        if job['error'] is not None:
            raise job['error']
        return job['result']


_shared_io = BoundedIO()


class SourceRouter:
    def __init__(self, pairs=(), *, timeout=1.2):
        self.pairs = tuple(pairs)
        self.timeout = timeout
        self.io = _shared_io
        self.lock = threading.Lock()
        self.health = {}

    def canonical(self, path):
        if not isinstance(path, str):
            return path
        if path.startswith(PREFIX):
            return PREFIX + posixpath.normpath('/' + path[len(PREFIX):].replace('\\', '/').lstrip('/'))
        candidate = expand_mapped_path(path) if self.pairs else path
        if not candidate.startswith(('\\\\', '//')):
            return path
        for pair in self.pairs:
            relative = _local_relative(candidate.replace('/', '\\'), pair.local)
            if relative is not None:
                return pair.remote + ('/' + relative if relative else '')
        return path

    def pair_for(self, path):
        canonical = self.canonical(path)
        for pair in self.pairs:
            if isinstance(canonical, str) and _remote_relative(canonical, pair.remote) is not None:
                return pair
        return None

    def physical(self, path):
        canonical = self.canonical(path)
        pair = self.pair_for(canonical)
        if pair is None:
            return None
        relative = _remote_relative(canonical, pair.remote)
        return ntpath.join(pair.local, *relative.split('/')) if relative else pair.local

    def rebase(self, path, previous):
        canonical = previous.canonical(path)
        current_ids = {pair.id:pair for pair in self.pairs}
        for pair in getattr(previous, 'pairs', ()):
            relative = _remote_relative(canonical, pair.remote) if isinstance(canonical,str) else None
            replacement = current_ids.get(pair.id)
            if replacement and relative is not None:
                return replacement.remote + ('/' + relative if relative else '')
        return self.canonical(canonical)

    def invalidate(self, pair):
        with self.lock: self.health[pair.id] = (False, time.monotonic() + 5)

    def available(self, pair, *, refresh=False, timeout=None):
        with self.lock: previous = self.health.get(pair.id)
        if not refresh and previous and previous[1] > time.monotonic():
            return previous[0]
        def probe():
            # A successful ping/192.168 address alone is not evidence of access.
            with os.scandir(pair.local) as entries: next(entries, None)
            return True
        try:
            result = self.io.run(('probe', pair.local), probe, self.timeout if timeout is None else timeout)
        except (OSError, TimeoutError):
            result = False
        with self.lock: self.health[pair.id] = (result, time.monotonic() + 5)
        return result

    def local_operation(self, path, operation, *, refresh=False, timeout=None):
        pair = self.pair_for(path)
        if pair is None or not self.available(pair, refresh=refresh, timeout=timeout):
            raise OSError('A helyi elérés nem áll rendelkezésre.')
        try:
            return self.io.run(('operation', operation.__name__, self.physical(path)), lambda: operation(self.physical(path)), self.timeout if timeout is None else timeout)
        except (OSError, TimeoutError):
            self.invalidate(pair)
            raise

    def playback_path(self, path, *, recheck=False):
        canonical = self.canonical(path)
        if self.pair_for(canonical) is None:
            return canonical
        try:
            exists = self.local_operation(canonical, os.path.isfile, refresh=recheck,
                timeout=max(3.0, self.timeout) if recheck else None)
            return self.physical(canonical) if exists else canonical
        except (OSError, TimeoutError):
            return canonical


class LocalResponse:
    """Small bounded reads (NFO/pairing), using the existing response interface."""
    status_code = 200
    def __init__(self, content):
        self.content = content
        self.headers = {'Content-Length': str(len(content))}
    def raise_for_status(self): pass
    def iter_content(self, chunk_size=16384):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset:offset + chunk_size]
    def close(self): pass


class RoutedNASClient:
    def __init__(self, router, remote_factory):
        self.router, self.remote_factory = router, remote_factory
        self.remote = None
        self.lock = threading.RLock()
        self._case_listings = {}

    def _nas(self):
        with self.lock:
            if self.remote is None: self.remote = self.remote_factory()
            return self.remote

    def __getattr__(self, name):
        return getattr(self._nas(), name)

    def list_folder(self, path):
        canonical = self.router.canonical(PREFIX + path)
        def listing(local):
            result = []
            with os.scandir(local) as entries:
                for entry in entries:
                    if entry.is_symlink(): continue
                    stat = entry.stat()
                    result.append(dict(name=entry.name, path=canonical[len(PREFIX):].rstrip('/') + '/' + entry.name,
                                       isdir=entry.is_dir(), additional={'time': {'mtime': int(stat.st_mtime)}, 'size': stat.st_size}))
            return result
        try: return self.router.local_operation(canonical, listing)
        except (OSError, TimeoutError): return self._nas().list_folder(path)

    def resolve_case(self, path):
        """Recover case lost in legacy Windows keys before publishing pairings."""
        canonical = self.router.canonical(path)
        pair = self.router.pair_for(canonical)
        if pair is None: return canonical
        relative = _remote_relative(canonical, pair.remote)
        current = pair.remote
        cache = self._case_listings
        for part in relative.split('/') if relative else []:
            if current not in cache: cache[current] = self.list_folder(current[len(PREFIX):])
            matches = [entry['name'] for entry in cache[current] if str(entry.get('name','')).casefold() == part.casefold()]
            if not matches:
                raise FileNotFoundError('A korábbi fájl most nem található a NAS-on.')
            if len(matches) != 1:
                raise ValueError('A korábbi fájlnév nem azonosítható egyértelműen a NAS-on.')
            current += '/' + matches[0]
        return current

    def open_stream(self, path, headers=None):
        canonical = self.router.canonical(PREFIX + path)
        def read(local):
            with open(local, 'rb') as source: return source.read(2 * 1024 * 1024 + 1)
        # Playback is routed before it enters the NAS HTTP proxy. Other streams
        # here are bounded NFO reads; do not substitute a truncated video stream.
        if headers is None:
            try:
                content = self.router.local_operation(canonical, read)
                if len(content) <= 2 * 1024 * 1024: return LocalResponse(content)
            except (OSError, TimeoutError): pass
        return self._nas().open_stream(path, headers=headers)

    def read_pairing(self, path):
        canonical = self.router.canonical(PREFIX + path)
        def read(local):
            with open(local, 'rb') as source: return source.read(16385)
        try: return self.router.local_operation(canonical, read)
        except (OSError, TimeoutError): return self._nas().read_pairing(path)

    def upload_pairing(self, directory, name, payload):
        if not re.fullmatch(r'[0-9a-f]{32}\.json', name) or not directory.endswith('/.synostream/parositasok') or len(payload) > 16384:
            raise ValueError('Érvénytelen párosítási cél.')
        canonical = self.router.canonical(PREFIX + directory)
        def write(local):
            import tempfile
            os.makedirs(local, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix='.pair-', dir=local)
            try:
                with os.fdopen(fd, 'wb') as target:
                    target.write(payload); target.flush(); os.fsync(target.fileno())
                os.replace(temporary, os.path.join(local, name))
            finally:
                with contextlib.suppress(OSError): os.remove(temporary)
        try: return self.router.local_operation(canonical, write)
        except (OSError, TimeoutError): return self._nas().upload_pairing(directory, name, payload)

    def close(self):
        with self.lock:
            if self.remote is not None: self.remote.close()


def nas_root_from_local(path, settings):
    """Infer a File Station path only for the configured NAS host, never by title."""
    from synostream_connections import local_nas_host
    host = local_nas_host(settings)
    if not host:
        return None
    expanded = expand_mapped_path(str(path or '')).replace('\\', '/')
    if not expanded.startswith('//'):
        return None
    parts = [part for part in expanded.split('/') if part]
    if len(parts) < 2 or parts[0].casefold() != host.casefold():
        return None
    return remote_root('/' + '/'.join(parts[1:]))


def automatic_pairs(settings):
    """SMB is an optional optimization of a NAS source, not a second source."""
    import hashlib
    from synostream_connections import local_nas_host
    pairs = parse_pairs(settings.get('paired_sources', []))
    host = local_nas_host(settings)
    # Windows UNC does not support colon-separated IPv6 literals directly.
    if not host or ':' in host:
        return pairs
    roots = []
    for kind in ('movies', 'shows'):
        paths = settings.get(kind + '_paths')
        if not isinstance(paths, list): paths = [settings.get(kind + '_path', '')]
        paths = list(paths)
        if settings.get('remote_' + kind + '_path'):
            paths.append(PREFIX + settings['remote_' + kind + '_path'])
        roots.extend((kind, value) for value in paths)
    for library in settings.get('custom_libraries', []):
        roots.extend((library.get('id'), value) for value in library.get('paths', []))
    for library_id, value in roots:
        if not isinstance(value, str): continue
        remote = remote_root(value) if value.startswith(PREFIX) else nas_root_from_local(value, settings)
        if not remote: continue
        local = '\\\\' + host + '\\' + remote[len(PREFIX):].strip('/').replace('/', '\\')
        identifier = 'auto-' + hashlib.sha256((str(library_id) + '\0' + remote).encode()).hexdigest()[:24]
        candidate = dict(id=identifier, library_id=library_id, local_root=local, remote_root=remote)
        # Parent mappings already route their child folders. Explicit legacy
        # aliases win; never reinterpret a user-confirmed mapping.
        try: pairs = parse_pairs([*(p.to_dict() for p in pairs), candidate])
        except ValueError: continue
    return pairs
