import hashlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

import pytest
import synostream_updates as u
from release_tools import make_manifest


class Response:
    status_code = 200
    headers = {}
    def __init__(self, content): self.content = content; self.closed = False
    def iter_content(self, size):
        for start in range(0, len(self.content), size): yield self.content[start:start+size]
    def close(self): self.closed = True
    def raise_for_status(self): pass
    def __enter__(self): return self
    def __exit__(self, *args): self.close()


def package(tmp_path, extra=None):
    version = '1.96'; payload = b'MZ-test-executable'; stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr(f'SynoStream_{version}_Windows_x64/SynoStream_{version}.exe', payload)
        archive.writestr(f'SynoStream_{version}_Windows_x64/LICENSE', 'license')
        if extra: archive.writestr(extra, b'bad')
    data = stream.getvalue()
    manifest = dict(format=1, version=version, filename=f'SynoStream_{version}_Windows_x64.zip',
        url=f'https://github.com/{u.REPOSITORY}/releases/download/v{version}/SynoStream_{version}_Windows_x64.zip',
        size=len(data), sha256=hashlib.sha256(data).hexdigest(), exe_size=len(payload),
        exe_sha256=hashlib.sha256(payload).hexdigest(), notes='Release notes')
    return manifest, data


@pytest.mark.parametrize('bad',['../1.96','1.96-beta','v1.96','1','01.96',None,196])
def test_version_validation_rejects_unsafe_values(bad):
    with pytest.raises(u.UpdateError): u.version_tuple(bad)


def test_numeric_version_comparison():
    assert u.version_tuple('1.100') > u.version_tuple('1.99')
    assert u.version_tuple('1.95') == u.version_tuple('1.95.0')


@pytest.mark.parametrize('field,value', [('url','https://example.com/update.zip'), ('sha256','x'), ('size',True),
    ('filename','../payload.exe'), ('exe_sha256','0'), ('version','1.96-beta')])
def test_bad_manifest_rejected(tmp_path,field,value):
    m,_=package(tmp_path);m[field]=value
    with pytest.raises(u.UpdateError): u.validate_manifest(m)


def test_check_latest_checks_version_and_bounds(tmp_path,monkeypatch):
    m,_=package(tmp_path);monkeypatch.setattr(u,'_response',lambda *a:Response(json.dumps(m).encode()))
    assert u.check_latest('1.95')['version']=='1.96'
    assert u.check_latest('1.96') is None and u.check_latest('2.0') is None
    monkeypatch.setattr(u,'_response',lambda *a:Response(b'x'*32769))
    with pytest.raises(u.UpdateError):u.check_latest('1.95')


def test_download_stages_verified_bundle_without_touching_old_version(tmp_path,monkeypatch):
    m,data=package(tmp_path);monkeypatch.setattr(u,'_response',lambda *a:Response(data))
    old=tmp_path/'SynoStream v1.54';old.mkdir();(old/'original').write_bytes(b'untouched')
    values=[];result=u.stage_package(m,tmp_path,progress=lambda n,t:values.append((n,t)))
    assert not Path(result['target']).exists()
    assert (Path(result['stage'])/'payload/SynoStream_1.96.exe').read_bytes()==b'MZ-test-executable'
    assert values[-1]==(len(data),len(data)) and (old/'original').read_bytes()==b'untouched'


@pytest.mark.parametrize('mode',['hash','size','cancel','exists'])
def test_download_failure_leaves_no_partial_install(tmp_path,monkeypatch,mode):
    m,data=package(tmp_path);monkeypatch.setattr(u,'_response',lambda *a:Response(data))
    if mode=='hash':m['sha256']='0'*64
    if mode=='size':m['size']+=1
    if mode=='exists':(tmp_path/'SynoStream v1.96').mkdir()
    with pytest.raises(u.UpdateError):u.stage_package(m,tmp_path,cancelled=lambda:mode=='cancel')
    assert not list(tmp_path.glob('.synostream-update-*'))


@pytest.mark.parametrize('extra',['SynoStream_1.96_Windows_x64/../escape.exe','elsewhere.exe',
    'SynoStream_1.96_Windows_x64/assets/../../escape.exe','SynoStream_1.96_Windows_x64/file:stream',
    'SynoStream_1.96_Windows_x64/LICENSE'])
def test_unsafe_zip_is_rejected(tmp_path,monkeypatch,extra):
    m,data=package(tmp_path,extra);monkeypatch.setattr(u,'_response',lambda *a:Response(data))
    with pytest.raises(u.UpdateError):u.stage_package(m,tmp_path)
    assert not list(tmp_path.glob('.synostream-update-*'))


def staged_job(tmp_path,monkeypatch):
    downloads=tmp_path/'Downloads';downloads.mkdir();m,content=package(tmp_path)
    monkeypatch.setattr(u,'_response',lambda *a:Response(content))
    monkeypatch.setattr(u,'downloads_directory',lambda:downloads)
    monkeypatch.setattr(u,'update_shortcut',lambda *a:None)
    staged=u.stage_package(m,downloads);data=tmp_path/'user-data';data.mkdir()
    (data/'config.json').write_text('{"library":"preserved"}')
    (data/'credentials.dat').write_bytes(b'private')
    old=tmp_path/'old.exe';old.write_bytes(b'original')
    job={**staged,'old_exe':str(old),'data_dir':str(data),'parent_pid':123,'token':'a'*32}
    path=Path(staged['stage'])/'job.json';path.write_text(json.dumps(job))
    return path,job,data


def test_installer_acknowledged_startup_preserves_settings(tmp_path,monkeypatch):
    path,job,data=staged_job(tmp_path,monkeypatch);launched=[]
    def launch(args,env):
        launched.append(args)
        assert env['PYINSTALLER_RESET_ENVIRONMENT']=='1'
        u.acknowledge_update(args,'1.96');return SimpleNamespace(poll=lambda:None)
    target=u.install_job(path,wait_parent=lambda pid:None,launch=launch)
    assert (target/'SynoStream_1.96.exe').is_file() and len(launched)==1
    assert (data/'credentials.dat').read_bytes()==b'private'
    assert len(list((data/'upgrade_backups').glob('updater-*')))==1
    assert json.loads((path.parent/'result.json').read_text())['status']=='installed'


def test_failed_startup_restores_settings_before_restarting_old(tmp_path,monkeypatch):
    path,job,data=staged_job(tmp_path,monkeypatch);launched=[]
    def launch(args,env):
        launched.append(args)
        if len(launched)==1:
            (data/'config.json').write_text('changed');(data/'credentials.dat').write_bytes(b'changed')
            (data/'media_library.db-journal').write_bytes(b'failed-process-journal')
        return SimpleNamespace(poll=lambda:1)
    with pytest.raises(u.UpdateError,match='visszaálltak'):u.install_job(path,wait_parent=lambda pid:None,launch=launch)
    assert json.loads((data/'config.json').read_text())['library']=='preserved'
    assert (data/'credentials.dat').read_bytes()==b'private'
    assert not (data/'media_library.db-journal').exists()
    assert launched[-1]==[job['old_exe']]


def test_unconfirmed_running_app_never_has_data_restored(tmp_path,monkeypatch):
    path,job,data=staged_job(tmp_path,monkeypatch)
    def launch(args,env):
        (data/'config.json').write_text('live');return SimpleNamespace(poll=lambda:None)
    with pytest.raises(u.UpdateError,match='még fut'):u.install_job(path,wait_parent=lambda pid:None,launch=launch,health_timeout=0)
    assert (data/'config.json').read_text()=='live'


def test_helper_does_not_install_while_parent_is_alive(tmp_path,monkeypatch):
    path,job,data=staged_job(tmp_path,monkeypatch)
    def wait(pid):raise u.UpdateError('parent alive')
    with pytest.raises(u.UpdateError,match='parent alive'):u.install_job(path,wait_parent=wait)
    assert not Path(job['target']).exists()


def test_release_manifest_uses_actual_files(tmp_path):
    (tmp_path/'SynoStream_1.95.exe').write_bytes(b'exe')
    (tmp_path/'SynoStream_1.95_Windows_x64.zip').write_bytes(b'zip')
    m=make_manifest(tmp_path,'1.95','Changes')
    assert u.validate_manifest(m)==m and m['exe_sha256']==hashlib.sha256(b'exe').hexdigest()


def test_update_controls_keep_parent_and_reject_active_playback(media,app,monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    window=media.DSVideoWindow();controller=window.updater
    controller.manifest=package(Path(media.BASE_DIR))[0]
    window.settings_dialog.show();controller.show_offer();app.processEvents()
    assert controller.dialog.parentWidget() is window.settings_dialog
    controller.staged={'stage':'unused'}
    monkeypatch.setattr(window,'running_threads',lambda:[SimpleNamespace(process=SimpleNamespace(poll=lambda:None))])
    controller.install();assert not controller.installing
    assert 'lejátszást' in controller.status.text()
    controller.dialog.reject();window.settings_dialog.reject();window.close();app.processEvents()


def test_disabling_update_checks_rolls_back_failed_save(media,app,monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    window=media.DSVideoWindow();controller=window.updater
    controller.save=lambda:(False,'write error');monkeypatch.setattr(QMessageBox,'warning',lambda *a:None)
    controller.set_automatic(False)
    assert controller.config['check_updates'] is True and controller.automatic.isChecked()
    window.close();app.processEvents()
