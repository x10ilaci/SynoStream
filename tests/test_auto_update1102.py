import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import sys
from PyQt6.QtCore import QObject,pyqtSignal
from PyQt6.QtWidgets import QMessageBox
import synostream_updates as updates
import synostream_update_ui as ui
from synostream_connections import normalize_local_url
from synostream_nas import normalize_direct_url
from test_updates195 import package,Response
from test_download_station import dsm_server


@pytest.mark.parametrize('given,expected',[
 ('192.168.1.2','http://192.168.1.2:5000'),('192.168.1.2:5050','http://192.168.1.2:5050'),
 ('https://nas.local','https://nas.local:5001'),('nas.local','http://nas.local:5000')])
def test_local_short_address(given,expected):assert normalize_local_url(given)==expected

@pytest.mark.parametrize('url',['http://nas.example:5001','https://nas.example:5001'])
def test_ddns_accepts_explicit_transport(url):assert normalize_direct_url(url)==url

def test_bare_ddns_remains_https():assert normalize_direct_url('nas.example:5001')=='https://nas.example:5001'

@pytest.fixture
def staged(tmp_path,monkeypatch):
 manifest,content=package(tmp_path);downloads=tmp_path/'downloads';downloads.mkdir();data=tmp_path/'data';data.mkdir()
 monkeypatch.setattr(updates,'downloads_directory',lambda:downloads)
 monkeypatch.setattr(updates,'_response',lambda *a:Response(content))
 value=updates.stage_package(manifest)
 return value,data,downloads


def test_queue_survives_restart_and_launches_only_when_enabled(staged,monkeypatch):
 value,data,_=staged;updates.queue_update(value,data,'1.95')
 assert updates.pending_update(data,'1.95')==value
 monkeypatch.setattr(sys,'frozen',True,raising=False);prepare=Mock();monkeypatch.setattr(updates,'prepare_install',prepare)
 (data/'config.json').write_text(json.dumps({'auto_update':False}))
 assert not updates.launch_pending_update('1.95','old.exe',data);prepare.assert_not_called()
 (data/'config.json').write_text(json.dumps({'auto_update':True}))
 assert updates.launch_pending_update('1.95','old.exe',data)
 prepare.assert_called_once_with(value,'old.exe',data)
 assert not (data/'pending_update.json').exists()
 assert not updates.launch_pending_update('1.95','old.exe',data)


def test_changed_download_is_never_installed(staged,monkeypatch):
 value,data,_=staged;updates.queue_update(value,data,'1.95')
 Path(value['stage'],'payload','SynoStream_1.96.exe').write_bytes(b'MZ-corrupt')
 (data/'config.json').write_text(json.dumps({'auto_update':True}));monkeypatch.setattr(sys,'frozen',True,raising=False)
 prepare=Mock();monkeypatch.setattr(updates,'prepare_install',prepare)
 assert not updates.launch_pending_update('1.95','old.exe',data)
 prepare.assert_not_called();assert (data/'pending_update_error.json').exists()


def test_old_version_cannot_be_queued(staged):
 value,data,_=staged
 with pytest.raises(updates.UpdateError):updates.queue_update(value,data,'1.97')


def test_pending_path_outside_downloads_rejected(staged):
 value,data,_=staged;value['stage']=str(data)
 (data/'pending_update.json').write_text(json.dumps(value))
 with pytest.raises(updates.UpdateError):updates.pending_update(data,'1.95')


def test_failed_helper_launch_keeps_existing_program_available(staged,monkeypatch):
 value,data,_=staged;updates.queue_update(value,data,'1.95')
 (data/'config.json').write_text(json.dumps({'auto_update':True}));monkeypatch.setattr(sys,'frozen',True,raising=False)
 monkeypatch.setattr(updates,'prepare_install',Mock(side_effect=OSError('cannot launch')))
 assert not updates.launch_pending_update('1.95','old.exe',data)
 assert (data/'pending_update.json').exists()


class Worker(QObject):
 done=pyqtSignal(object);failed=pyqtSignal(str);finished=pyqtSignal();progress=pyqtSignal(int)
 def __init__(self,version,manifest=None):super().__init__();self.manifest=manifest;self.running=False;self.cancelled=False
 def isRunning(self):return self.running
 def requestInterruption(self):self.cancelled=True


def controller(media,monkeypatch):
 window=media.DSVideoWindow();c=window.updater;c.version='1.95'
 monkeypatch.setattr(sys,'frozen',True,raising=False);monkeypatch.setattr(ui,'UpdateWorker',Worker)
 c.run_worker=lambda worker:setattr(worker,'running',True)
 c.config['auto_update']=True;c.config['update_last_check']=0
 return window,c


@pytest.mark.parametrize('manual',[False,True])
def test_background_check_downloads_and_queues_without_install(media,app,monkeypatch,staged,manual):
 value,data,_=staged;window,c=controller(media,monkeypatch);c.data_dir=data
 install=Mock();monkeypatch.setattr(updates,'prepare_install',install)
 try:
  c.check(manual);check=c.worker;check.done.emit(value['manifest']);check.running=False;check.finished.emit()
  download=c.worker;assert download is not check and download.manifest==value['manifest']
  assert c.dialog is None
  download.done.emit(value);download.running=False;download.finished.emit()
  assert (data/'pending_update.json').exists();assert c.staged==value
  install.assert_not_called();assert not c.installing
 finally:window.close();app.processEvents()


def test_disabling_background_update_cancels_and_does_not_queue(media,app,monkeypatch,staged):
 value,data,_=staged;window,c=controller(media,monkeypatch);c.data_dir=data;c.manifest=value['manifest']
 try:
  c._download_automatic();worker=c.worker
  c.set_auto_install(False);assert worker.cancelled
  worker.done.emit(value);worker.running=False;worker.finished.emit()
  assert not (data/'pending_update.json').exists()
 finally:window.close();app.processEvents()


def test_toggle_failure_preserves_preference(media,app,monkeypatch):
 window=media.DSVideoWindow();c=window.updater;c.save=lambda:(False,'disk error')
 monkeypatch.setattr(QMessageBox,'warning',lambda *a:None)
 try:
  c.set_auto_install(True)
  assert c.config['auto_update'] is False and not c.auto_install.isChecked()
 finally:window.close();app.processEvents()


def test_controller_follows_replaced_settings(media,app):
 window=media.DSVideoWindow();c=window.updater
 try:
  replacement=dict(media.config,auto_update=True);media.config=replacement
  assert c.config is replacement
 finally:window.close();app.processEvents()


def test_queued_update_installer_handoff_preserves_user_data(staged,monkeypatch,tmp_path):
 value,data,_=staged;updates.queue_update(value,data,'1.95')
 config={'auto_update':True,'library':'preserved'}
 (data/'config.json').write_text(json.dumps(config));(data/'credentials.dat').write_bytes(b'synthetic-private')
 old=tmp_path/'old.exe';old.write_bytes(b'old-executable')
 monkeypatch.setattr(sys,'frozen',True,raising=False)
 spawn=Mock();monkeypatch.setattr(updates.subprocess,'Popen',spawn)
 assert updates.launch_pending_update('1.95',old,data)
 args=spawn.call_args.args[0];assert args[1]=='--install-update'
 job=Path(args[2]);assert job.exists() and Path(args[0]).read_bytes()==b'old-executable'
 monkeypatch.setattr(updates,'update_shortcut',lambda *a:None)
 def launch(args,env):
  updates.acknowledge_update(args,'1.96')
  return SimpleNamespace(poll=lambda:None)
 target=updates.install_job(job,wait_parent=lambda pid:None,launch=launch)
 assert (target/'SynoStream_1.96.exe').is_file()
 assert json.loads((data/'config.json').read_text())==config
 assert (data/'credentials.dat').read_bytes()==b'synthetic-private'
 assert old.read_bytes()==b'old-executable'
 assert not (data/'pending_update.json').exists()


def test_explicit_http_direct_download_station(dsm_server):
 from synostream_downloads import DownloadStationClient
 state,factory=dsm_server
 bootstrap=factory(dict(quickconnect_id='synthetic',nas_username='synthetic',nas_password='synthetic'))
 base=bootstrap.base_url;bootstrap.close()
 client=DownloadStationClient(dict(nas_direct_url=base,nas_username='synthetic',nas_password='synthetic'))
 try:
  assert client.transport=='direct' and len(client.list_tasks())==1
 finally:client.close()

@pytest.mark.parametrize('config',[[],None,'invalid'])
def test_malformed_config_never_blocks_existing_application(tmp_path,monkeypatch,config):
 monkeypatch.setattr(sys,'frozen',True,raising=False)
 (tmp_path/'config.json').write_text(json.dumps(config))
 assert updates.launch_pending_update('1.95','old.exe',tmp_path) is False
