import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import zipfile

import pytest
import synostream_updates as u
from release_guard import UnsafeRelease, check_name, scan_bytes, scan_source_files, scan_zip
from test_updates195 import staged_job, package, Response


def test_failed_start_frees_retry_path_and_keeps_failed_program(tmp_path, monkeypatch):
    path, job, data = staged_job(tmp_path, monkeypatch)
    with pytest.raises(u.UpdateError, match='visszaálltak'):
        u.install_job(path, wait_parent=lambda pid: None, launch=lambda *a, **k: SimpleNamespace(poll=lambda: 1))
    assert not Path(job['target']).exists()
    retired = list(Path(job['target']).parent.glob('SynoStream v1.96 - failed-*'))
    assert len(retired) == 1 and (retired[0]/'SynoStream_1.96.exe').is_file()
    manifest, content = package(tmp_path)
    monkeypatch.setattr(u, '_response', lambda *a: Response(content))
    assert Path(u.stage_package(manifest, Path(job['target']).parent)['stage']).is_dir()


@pytest.mark.parametrize('change', ['missing', 'modified'])
def test_changed_download_is_rejected_before_helper_or_exit(tmp_path, monkeypatch, change):
    path, job, data = staged_job(tmp_path, monkeypatch)
    exe = path.parent/'payload/SynoStream_1.96.exe'
    if change == 'missing': exe.unlink()
    else: exe.write_bytes(b'tampered')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(u.subprocess, 'Popen', lambda *a, **k: pytest.fail('Installer must not start'))
    with pytest.raises(u.UpdateError, match='megváltozott'): u.prepare_install(job, job['old_exe'], data)


@pytest.mark.parametrize('change', ['outside', 'token', 'version'])
def test_startup_acknowledgement_is_confined_to_valid_download_job(tmp_path, monkeypatch, change):
    path, job, data = staged_job(tmp_path, monkeypatch)
    receipt = path.parent/'receipt.json'; token = job['token']; version = '1.96'
    if change == 'outside':
        other = tmp_path/'.synostream-update-outside'; other.mkdir(); receipt = other/'receipt.json'
        (other/'job.json').write_text(json.dumps(job))
    if change == 'token': token = 'b'*32
    if change == 'version': version = '1.97'
    u.acknowledge_update(['app','--updated-from',str(receipt),token], version)
    assert not receipt.exists()


def completed_job(tmp_path, monkeypatch):
    path, job, data = staged_job(tmp_path, monkeypatch)
    (path.parent/'payload').rename(job['target'])
    (path.parent/'result.json').write_text(json.dumps({'status':'installed','version':'1.96'}))
    return path, job, data


def test_completed_cache_cleanup_keeps_install_and_private_data(tmp_path, monkeypatch):
    path, job, data = completed_job(tmp_path, monkeypatch)
    assert u.cleanup_completed_updates() == 1
    assert not path.parent.exists() and Path(job['target']).is_dir()
    assert (data/'credentials.dat').read_bytes() == b'private'


@pytest.mark.parametrize('mode', ['unexpected', 'busy', 'unconfirmed'])
def test_cache_cleanup_does_not_remove_unknown_or_busy_work(tmp_path, monkeypatch, mode):
    path, job, data = completed_job(tmp_path, monkeypatch)
    if mode == 'unexpected': (path.parent/'my-file.txt').write_text('keep')
    if mode == 'unconfirmed': (path.parent/'result.json').write_text('{}')
    if mode == 'busy':
        helper = path.parent/'update-helper.exe'; helper.touch(); original = Path.unlink
        def unlink(candidate, *args, **kwargs):
            if candidate == helper: raise PermissionError('Executing helper')
            return original(candidate, *args, **kwargs)
        monkeypatch.setattr(Path, 'unlink', unlink)
    assert u.cleanup_completed_updates() == 0
    assert path.exists() and (path.parent/'result.json').exists()


@pytest.mark.parametrize('name', ['config.json', 'config.backup.json', 'credentials.dat.unreadable-123',
    'media_library.db.old', '.env.local', 'logs/SynoStream.log', 'upgrade_backups/config.json',
    'keys/signing.key', '../private.txt', 'C:/private.txt', 'library.sqlite3'])
def test_private_artifact_names_are_blocked(name):
    with pytest.raises(UnsafeRelease): check_name(name)


def test_zip_guard_checks_content_and_never_prints_secret(tmp_path):
    secret = 'synthetic-private-value-for-test'
    file = tmp_path/'source.zip'
    with zipfile.ZipFile(file, 'w') as archive: archive.writestr('source/app.py', 'value='+secret)
    with pytest.raises(UnsafeRelease) as error: scan_zip(file, [secret])
    assert secret not in str(error.value)


def test_zip_guard_checks_case_and_backup_variants(tmp_path):
    file = tmp_path/'source.zip'
    with zipfile.ZipFile(file, 'w') as archive: archive.writestr('source/CREDENTIALS.DAT.backup', b'private')
    with pytest.raises(UnsafeRelease): scan_zip(file)


def test_token_scanner_rejects_actual_token_shapes():
    token = b'gh' + b'p_' + b'X'*36
    with pytest.raises(UnsafeRelease) as error: scan_bytes(token, 'source.py')
    assert token.decode() not in str(error.value)


def test_source_guard_rejects_private_file_even_with_ordinary_contents(tmp_path):
    (tmp_path/'credentials.dat.backup').write_bytes(b'ordinary')
    with pytest.raises(UnsafeRelease): scan_source_files(tmp_path, ['credentials.dat.backup'])


def test_publish_guard_still_checks_checksums_under_optimized_python(tmp_path):
    from release_tools import make_manifest
    (tmp_path/'SynoStream_1.96.exe').write_bytes(b'executable')
    (tmp_path/'SynoStream_1.96_Windows_x64.zip').write_bytes(b'zip')
    (tmp_path/'SynoStream_1.96_Source.zip').write_bytes(b'zip')
    (tmp_path/'SynoStream_1.96_SHA256.txt').write_text('')
    m = make_manifest(tmp_path, '1.96', 'Notes'); m['sha256'] = '0'*64
    (tmp_path/'update.json').write_text(json.dumps(m))
    result = subprocess.run([sys.executable,'-O','-c',
        'from publish_release import verify; import sys; verify(sys.argv[1])', str(tmp_path)],
        capture_output=True, text=True, timeout=30, cwd=Path(__file__).resolve().parents[1])
    assert result.returncode != 0 and 'checksum mismatch' in result.stderr


def test_update_settings_follow_live_language_switch(media, app):
    window = media.DSVideoWindow()
    try:
        media.set_ui_language('en'); app.retranslate_all_widgets()
        assert window.updater.group.title() == 'Application updates'
        assert window.updater.check_button.text() == 'Check for updates'
        media.set_ui_language('hu'); app.retranslate_all_widgets()
        assert window.updater.group.title() == 'Programfrissítés'
    finally:
        media.set_ui_language('hu'); window.close(); app.processEvents()
