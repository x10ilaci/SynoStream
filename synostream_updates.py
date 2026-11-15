"""Public GitHub updates; verified staging and an out-of-process installer.

No NAS/API credentials are used by this module. Installation never overwrites
an existing version and always retains the previous executable.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
import uuid
import zipfile

import requests

REPOSITORY = 'x10ilaci/SynoStream'
MANIFEST_URL = f'https://github.com/{REPOSITORY}/releases/latest/download/update.json'
MAX_PACKAGE = 256 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024


class UpdateError(ValueError):
    pass


class Cancelled(UpdateError):
    pass


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'[1-9]\d{0,3}\.\d{1,4}(?:\.\d{1,4})?', value):
        raise UpdateError('Érvénytelen verziószám.')
    parts = tuple(map(int, value.split('.')))
    return parts + (0,) * (3 - len(parts))


def release_url(url, version=None, filename=None):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != 'github.com' or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise UpdateError('Érvénytelen frissítési hivatkozás.')
    if version is not None and parsed.path != f'/{REPOSITORY}/releases/download/v{version}/{filename}':
        raise UpdateError('A frissítési hivatkozás nem a SynoStream kiadására mutat.')
    if parsed.query or parsed.fragment:
        raise UpdateError('Érvénytelen frissítési hivatkozás.')
    return url


def validate_manifest(data):
    if not isinstance(data, dict) or data.get('format') != 1:
        raise UpdateError('Ismeretlen frissítési formátum.')
    version = data.get('version'); version_tuple(version)
    name = f'SynoStream_{version}_Windows_x64.zip'
    if data.get('filename') != name:
        raise UpdateError('Érvénytelen frissítési fájlnév.')
    if not re.fullmatch('[0-9a-f]{64}', str(data.get('sha256', ''))):
        raise UpdateError('Hiányzó ellenőrzőösszeg.')
    if type(data.get('size')) is not int or not 0 < data['size'] <= MAX_PACKAGE:
        raise UpdateError('Érvénytelen frissítési méret.')
    if type(data.get('exe_size')) is not int or not 0 < data['exe_size'] <= MAX_PACKAGE:
        raise UpdateError('Érvénytelen programméret.')
    if not re.fullmatch('[0-9a-f]{64}', str(data.get('exe_sha256', ''))):
        raise UpdateError('Hiányzó program-ellenőrzőösszeg.')
    release_url(data.get('url', ''), version, name)
    return {**data, 'notes': str(data.get('notes', ''))[:12000]}


def _response(url, session=None):
    session = session or requests.Session()
    # Explicit redirect validation avoids following a changed manifest to an
    # unrelated host. The session has no application credentials or auth.
    allowed = {'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}
    for _ in range(6):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname not in allowed or parsed.username or parsed.password:
            raise UpdateError('Nem engedélyezett letöltési kiszolgáló.')
        response = session.get(url, headers={'User-Agent': 'SynoStream-Updater', 'Accept-Encoding': 'identity'},
                               timeout=(10, 20), stream=True, allow_redirects=False)
        if response.status_code in (301, 302, 303, 307, 308):
            from urllib.parse import urljoin
            url = urljoin(url, response.headers.get('Location', '')); response.close()
            continue
        try: response.raise_for_status()
        except Exception:
            response.close(); raise
        return response
    raise UpdateError('Túl sok letöltési átirányítás.')


def check_latest(current, session=None):
    with _response(MANIFEST_URL, session) as response:
        content = bytearray()
        for block in response.iter_content(16384):
            content.extend(block)
            if len(content) > 32768: raise UpdateError('Túl nagy frissítési leíró.')
    data = validate_manifest(json.loads(content))
    return data if version_tuple(data['version']) > version_tuple(current) else None


def downloads_directory():
    if os.name != 'nt': return Path.home() / 'Downloads'
    import ctypes
    import ctypes.wintypes as wt
    # FOLDERID_Downloads, including user-redirected Downloads directories.
    class GUID(ctypes.Structure):
        _fields_ = [('a', wt.DWORD), ('b', wt.WORD), ('c', wt.WORD), ('d', ctypes.c_ubyte * 8)]
    guid = GUID.from_buffer_copy(uuid.UUID('374de290-123f-4565-9164-39c4925e467b').bytes_le)
    shell = ctypes.WinDLL('shell32'); ole = ctypes.WinDLL('ole32')
    shell.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(GUID), wt.DWORD, wt.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)]
    shell.SHGetKnownFolderPath.restype = ctypes.c_long
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    result = ctypes.c_wchar_p()
    if shell.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(result)) != 0:
        raise UpdateError('A Letöltések mappa nem található.')
    try: return Path(result.value)
    finally: ole.CoTaskMemFree(ctypes.cast(result, ctypes.c_void_p))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''): digest.update(block)
    return digest.hexdigest()


def stage_package(manifest, downloads=None, cancelled=lambda: False, progress=lambda n, total: None, session=None):
    m = validate_manifest(manifest)
    root = Path(downloads or downloads_directory()).resolve(); root.mkdir(parents=True, exist_ok=True)
    target = root / ('SynoStream v' + m['version'])
    if target.exists(): raise UpdateError('Az új verzió mappája már létezik. Nem írjuk felül.')
    stage = Path(tempfile.mkdtemp(prefix='.synostream-update-', dir=root))
    try:
        package = stage / 'package.zip'; digest = hashlib.sha256(); size = 0
        with _response(m['url'], session) as response, package.open('xb') as output:
            for block in response.iter_content(256 * 1024):
                if cancelled(): raise Cancelled('A letöltés megszakítva.')
                size += len(block)
                if size > m['size']: raise UpdateError('A letöltés mérete eltér.')
                output.write(block); digest.update(block); progress(size, m['size'])
        if cancelled(): raise Cancelled('A letöltés megszakítva.')
        if size != m['size'] or digest.hexdigest() != m['sha256']:
            raise UpdateError('A letöltött csomag ellenőrzése sikertelen.')
        payload = stage / 'payload'; payload.mkdir()
        prefix = f'SynoStream_{m["version"]}_Windows_x64/'
        total = 0; seen = set()
        with zipfile.ZipFile(package) as archive:
            if len(archive.infolist()) > 2000: raise UpdateError('Túl sok fájl a frissítésben.')
            for item in archive.infolist():
                if cancelled(): raise Cancelled('A letöltés megszakítva.')
                if not item.filename.startswith(prefix): raise UpdateError('Hibás frissítési csomagszerkezet.')
                relative = item.filename[len(prefix):]; path = PurePosixPath(relative)
                if not relative: continue
                if '\\' in relative or ':' in relative or path.is_absolute() or '..' in path.parts:
                    raise UpdateError('Érvénytelen csomagútvonal.')
                key = str(path).casefold()
                if key in seen: raise UpdateError('Ismétlődő csomagfájl.')
                seen.add(key)
                # Release bundles contain the EXE, notices, icon and licenses.
                if any(part.rstrip(' .') != part for part in path.parts): raise UpdateError('Érvénytelen csomagfájlnév.')
                if (item.external_attr >> 16) & 0o170000 == 0o120000: raise UpdateError('Átirányított csomagfájl.')
                total += item.file_size
                if total > MAX_EXPANDED: raise UpdateError('Túl nagy kibontott frissítés.')
                destination = payload.joinpath(*path.parts)
                if item.is_dir(): destination.mkdir(parents=True, exist_ok=True); continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as src, destination.open('xb') as dst: shutil.copyfileobj(src, dst)
        exe = payload / f'SynoStream_{m["version"]}.exe'
        if not exe.is_file() or exe.stat().st_size != m['exe_size'] or sha256(exe) != m['exe_sha256']:
            raise UpdateError('A programfájl ellenőrzése sikertelen.')
        package.unlink()
        return {'stage': str(stage), 'target': str(target), 'manifest': m}
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _validate_staged(staged):
    manifest = validate_manifest(staged['manifest'])
    stage = Path(staged['stage']).resolve(); target = Path(staged['target']).resolve()
    if (stage.parent != downloads_directory().resolve() or not stage.name.startswith('.synostream-update-')
            or target != stage.parent / ('SynoStream v' + manifest['version']) or target.exists()):
        raise UpdateError('Érvénytelen vagy már létező frissítési célmappa.')
    payload = stage / 'payload'; exe = payload / f'SynoStream_{manifest["version"]}.exe'
    if (stage.is_symlink() or stage.is_junction() or payload.is_symlink() or payload.is_junction()
            or exe.is_symlink() or not exe.is_file() or exe.stat().st_size != manifest['exe_size']
            or sha256(exe) != manifest['exe_sha256']):
        raise UpdateError('A letöltött program megváltozott vagy hiányzik. Töltsd le újra.')
    return manifest, stage, target


def queue_update(staged, data_dir, current_version):
    manifest, stage, target = _validate_staged(staged)
    if version_tuple(manifest['version']) <= version_tuple(current_version):
        raise UpdateError('A várakozó frissítés nem újabb a jelenlegi verziónál.')
    marker = Path(data_dir) / 'pending_update.json'
    _atomic_json(marker, {'stage':str(stage), 'target':str(target), 'manifest':manifest})
    return marker


def pending_update(data_dir, current_version):
    marker = Path(data_dir) / 'pending_update.json'
    if not marker.exists(): return None
    if marker.is_symlink() or marker.stat().st_size > 262144:
        raise UpdateError('Érvénytelen várakozó frissítés.')
    try:
        staged = json.loads(marker.read_text(encoding='utf-8'))
        manifest, stage, target = _validate_staged(staged)
        if version_tuple(manifest['version']) <= version_tuple(current_version):
            marker.unlink(); return None
        return {'stage':str(stage), 'target':str(target), 'manifest':manifest}
    except (ValueError, KeyError, TypeError) as exc:
        raise UpdateError('A várakozó frissítés leírója sérült.') from exc


def clear_pending_update(data_dir, staged=None):
    marker = Path(data_dir) / 'pending_update.json'
    if staged is not None and marker.exists():
        saved = json.loads(marker.read_text(encoding='utf-8'))
        if saved.get('stage') != staged.get('stage'): return
    marker.unlink(missing_ok=True)


def launch_pending_update(current_version, current_exe, data_dir):
    """Called on next startup while holding the data lock, before DB migration/GUI."""
    if not getattr(sys, 'frozen', False): return False
    config_file = Path(data_dir) / 'config.json'
    try:
        config = json.loads(config_file.read_text(encoding='utf-8-sig'))
        if not isinstance(config, dict) or config.get('auto_update') is not True: return False
        staged = pending_update(data_dir, current_version)
        if staged is None: return False
        # Consume before launch so rollback cannot repeatedly retry this update.
        clear_pending_update(data_dir, staged)
        try:
            prepare_install(staged, current_exe, data_dir)
        except Exception:
            _atomic_json(Path(data_dir) / 'pending_update.json', staged)
            raise
        return True
    except (OSError, ValueError, KeyError, TypeError, UpdateError) as error:
        # Updating must never prevent the existing application from opening.
        try: _atomic_json(Path(data_dir) / 'pending_update_error.json', {'error':str(error)})
        except OSError: pass
        return False


def prepare_install(staged, current_exe, data_dir):
    if not getattr(sys, 'frozen', False): raise UpdateError('Az automatikus telepítés az EXE-változatban használható.')
    manifest, stage, target = _validate_staged(staged)
    job = {**staged, 'old_exe': str(Path(current_exe).resolve()), 'data_dir': str(Path(data_dir).resolve()),
           'parent_pid': os.getpid(), 'token': uuid.uuid4().hex}
    helper = stage / 'update-helper.exe'
    shutil.copy2(current_exe, helper)
    job_path = stage / 'job.json'; job_path.write_text(json.dumps(job), encoding='utf-8')
    env = os.environ.copy(); env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    return subprocess.Popen([str(helper), '--install-update', str(job_path)], env=env,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def update_shortcut(target_exe, old_exe):
    """Maintain only our own launcher in Downloads; leave user shortcuts alone."""
    if os.name != 'nt': return
    import base64
    def quote(value): return "'" + str(value).replace("'", "''") + "'"
    shortcut = downloads_directory() / 'SynoStream.lnk'
    script = "$w=New-Object -ComObject WScript.Shell\n$s=$w.CreateShortcut(" + quote(shortcut) + ")\n"
    script += "if ($s.TargetPath -and $s.TargetPath -ne " + quote(old_exe) + " -and $s.TargetPath -ne " + quote(target_exe) + ") { exit 0 }\n"
    script += "$s.TargetPath=" + quote(target_exe) + "\n$s.WorkingDirectory=" + quote(Path(target_exe).parent) + "\n$s.IconLocation=" + quote(str(target_exe) + ',0') + "\n$s.Save()"
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand',
        base64.b64encode(script.encode('utf-16le')).decode('ascii')], timeout=20,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=True, capture_output=True)


def _wait_parent(pid, timeout=120):
    import ctypes
    from ctypes import wintypes as wt
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]; api.OpenProcess.restype = wt.HANDLE
    api.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]; api.WaitForSingleObject.restype = wt.DWORD
    api.CloseHandle.argtypes = [wt.HANDLE]
    handle = api.OpenProcess(0x00100000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87: return
        raise UpdateError('Nem ellenőrizhető a korábbi program kilépése.')
    try:
        if api.WaitForSingleObject(handle, timeout * 1000) != 0: raise UpdateError('A SynoStream még fut. A frissítés nem történt meg.')
    finally: api.CloseHandle(handle)


def _atomic_json(path, data):
    path = Path(path); tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data), encoding='utf-8'); os.replace(tmp, path)


def acknowledge_update(args, version):
    if '--updated-from' not in args: return
    try:
        index = args.index('--updated-from'); receipt = Path(args[index + 1]); token = args[index + 2]
        receipt = receipt.resolve(); stage = receipt.parent
        if (receipt.name != 'receipt.json' or not stage.name.startswith('.synostream-update-')
                or stage.parent != downloads_directory().resolve() or stage.is_symlink() or stage.is_junction()):
            return
        if not re.fullmatch('[0-9a-f]{32}', token): return
        job = json.loads((stage / 'job.json').read_text(encoding='utf-8'))
        if job.get('token') != token or job.get('manifest', {}).get('version') != version:
            return
        _atomic_json(receipt, {'version': version, 'token': token})
    except (ValueError, IndexError, OSError, TypeError, AttributeError): pass


def cleanup_completed_updates():
    """Remove only validated, completed updater caches, never user data/backups."""
    root = downloads_directory().resolve(); count = 0
    for stage in root.glob('.synostream-update-*'):
        try:
            if stage.is_symlink() or stage.is_junction() or not stage.is_dir(): continue
            allowed = {'job.json', 'receipt.json', 'result.json', 'update-helper.exe'}
            if any(path.name not in allowed or path.is_symlink() or path.is_junction() or path.is_dir() for path in stage.iterdir()): continue
            job = json.loads((stage / 'job.json').read_text(encoding='utf-8'))
            result = json.loads((stage / 'result.json').read_text(encoding='utf-8'))
            m = validate_manifest(job['manifest'])
            target = root / ('SynoStream v' + m['version'])
            if (Path(job['stage']).resolve() != stage.resolve() or Path(job['target']).resolve() != target
                    or result != {'status':'installed', 'version':m['version']}): continue
            if not target.is_dir() or target.is_symlink() or target.is_junction(): continue
            if sha256(target / f'SynoStream_{m["version"]}.exe') != m['exe_sha256']: continue
            # Windows denies deleting an executing helper. Try this first so
            # a busy helper leaves its diagnostic/validation files intact.
            helper = stage / 'update-helper.exe'
            if helper.exists(): helper.unlink()
            shutil.rmtree(stage); count += 1
        except (OSError, ValueError, TypeError, KeyError): continue
    return count


def _retire_failed_install(target):
    """Keep the failed program for diagnosis, freeing the canonical retry path."""
    if target.is_symlink() or target.is_junction(): return
    try: target.rename(target.with_name(target.name + ' - failed-' + uuid.uuid4().hex[:8]))
    except OSError: pass


def _snapshot(data, folder):
    import sqlite3
    from contextlib import closing
    folder.mkdir(parents=True, exist_ok=False)
    present = {}
    for name in ('config.json', 'credentials.dat', 'media_library.db', 'data_version.json'):
        path = data / name; present[name] = path.exists()
        if not present[name]: continue
        if name.endswith('.db'):
            with closing(sqlite3.connect(path)) as src, closing(sqlite3.connect(folder / name)) as dst: src.backup(dst)
        else: shutil.copy2(path, folder / name)
    _atomic_json(folder / 'snapshot.json', present)


def _restore(data, folder):
    present = json.loads((folder / 'snapshot.json').read_text(encoding='utf-8'))
    # Only called after the failed process exited and our data lock was acquired.
    # Its hot SQLite journal must not replay onto the restored database.
    for suffix in ('-journal', '-wal', '-shm'):
        sidecar = data / ('media_library.db' + suffix)
        if sidecar.exists(): sidecar.unlink()
    for name, existed in present.items():
        if name not in ('config.json', 'credentials.dat', 'media_library.db', 'data_version.json'): raise UpdateError('Hibás mentés.')
        target = data / name
        if existed:
            temporary = data / ('.updater-restore-' + uuid.uuid4().hex)
            shutil.copy2(folder / name, temporary); os.replace(temporary, target)
        elif target.exists(): target.unlink()


def install_job(job_path, *, wait_parent=_wait_parent, launch=subprocess.Popen, health_timeout=120):
    """Called before Qt imports/data locks by a copied executable after exit."""
    from synostream_storage import acquire_application_lock
    job_path = Path(job_path).resolve(); stage = job_path.parent
    job = json.loads(job_path.read_text(encoding='utf-8')); m = validate_manifest(job['manifest'])
    if not re.fullmatch('[0-9a-f]{32}', str(job.get('token', ''))): raise UpdateError('Érvénytelen frissítési azonosító.')
    root = stage.parent.resolve(); target = root / ('SynoStream v' + m['version'])
    if root != downloads_directory().resolve() or version_tuple(m['version']) <= version_tuple('1.54'):
        raise UpdateError('A frissítés célja csak az új verzió Letöltések mappája lehet.')
    if not stage.name.startswith('.synostream-update-') or Path(job['stage']).resolve() != stage or Path(job['target']).resolve() != target:
        raise UpdateError('Érvénytelen frissítési munkamappa.')
    if stage.is_symlink() or stage.is_junction(): raise UpdateError('Átirányított frissítési munkamappa.')
    if target.exists(): raise UpdateError('A célverzió már létezik.')
    payload = stage / 'payload'; exe = payload / f'SynoStream_{m["version"]}.exe'
    if payload.is_symlink() or payload.is_junction() or exe.is_symlink() or sha256(exe) != m['exe_sha256']:
        raise UpdateError('A telepítendő program ellenőrzése sikertelen.')
    old = Path(job['old_exe']); data = Path(job['data_dir']); receipt = stage / 'receipt.json'
    wait_parent(int(job['parent_pid']))
    lock = acquire_application_lock(data, timeout=10)
    snapshot = data / 'upgrade_backups' / ('updater-' + uuid.uuid4().hex)
    try:
        _snapshot(data, snapshot)
        os.rename(payload, target)
        lock.close()
        env = os.environ.copy(); env['SYNOSTREAM_DATA_DIR'] = str(data); env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
        try:
            process = launch([str(target / exe.name), '--updated-from', str(receipt), job['token']], env=env)
        except OSError:
            lock = acquire_application_lock(data, timeout=10); _restore(data, snapshot); lock.close()
            _retire_failed_install(target)
            if old.is_file(): launch([str(old)], env=env)
            raise UpdateError('Az új verzió nem indítható el. A korábbi verzió megmaradt.')
        deadline = time.monotonic() + health_timeout
        while time.monotonic() < deadline:
            if receipt.exists():
                ack = json.loads(receipt.read_text(encoding='utf-8'))
                if ack == {'version': m['version'], 'token': job['token']}:
                    _atomic_json(stage / 'result.json', {'status': 'installed', 'version': m['version']})
                    try: update_shortcut(target / exe.name, old)
                    except (OSError, subprocess.SubprocessError): pass
                    return target
            if process.poll() is not None:
                lock = acquire_application_lock(data, timeout=10); _restore(data, snapshot); lock.close()
                _retire_failed_install(target)
                if old.is_file(): launch([str(old)], env=env)
                raise UpdateError('Az új verzió nem indult el. A korábbi adatok és verzió visszaálltak.')
            time.sleep(.2)
        # Never restore an active process's database or terminate playback.
        _atomic_json(stage / 'result.json', {'status': 'startup-unconfirmed', 'version': m['version']})
        raise UpdateError('Az új verzió még fut, de indulása nem igazolható. Az adatait nem módosítottuk.')
    finally:
        lock.close()


def helper_main(job_path):
    try:
        install_job(job_path); return 0
    except Exception as error:
        try: _atomic_json(Path(job_path).parent / 'error.json', {'error': str(error)})
        except OSError: pass
        if os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), 'SynoStream – frissítés', 0x10)
        return 1
