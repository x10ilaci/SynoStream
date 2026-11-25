import json,os,time
from pathlib import Path
from unittest.mock import Mock
import pytest,requests
from test_upgrade import bare_client,response
from synostream_logic import parse_episode_position,is_sample_video,is_sample_path,torrent_root
from synostream_torrent_selection import default_file_selected
from synostream_nas import nas_device_key,trusted_device_id
import synostream_mpv_install as mpv

@pytest.mark.parametrize('name,result',[
 ('Show/Show - 05 [720x480].mkv',(1,5)),('Show.05.720x576.mkv',(1,5)),('Movie.720x480.mkv',(1,None)),
 ('Show/Show - 05 [640x480].mkv',(1,5)),('Show 2x05.mkv',(2,5)),('Show 10x12.mkv',(10,12)),('Show [2x05].mkv',(2,5)),('Show S100E01.mkv',(100,1)),('Show.05.1920x1080i.mkv',(1,5)),('Show 2x05p.mkv',(1,None))])
def test_resolution_and_episode_markers(name,result):assert parse_episode_position(name)[:2]==result

@pytest.mark.parametrize('otp,calls',[('',3),('fixture-code',1)])
@pytest.mark.parametrize('status',[429,502,503,504])
def test_last_login_http_failure_never_returns_none(otp,calls,status):
 c=bare_client();c.session.post.return_value=response(status=status)
 with pytest.raises(requests.HTTPError):c._connect_request('post','https://fixture.invalid',data={'otp_code':otp})
 assert c.session.post.call_count==calls

@pytest.mark.parametrize('path,selected',[
 ('Sample.Size.2019.1080p/Sample.Size.2019.mkv',True),('Movie/Resampled.Audio.Pack/track.flac',True),
 ('The.Sample.Show.S01/E01.mkv',True),('Movie/Samples/clip.mkv',False),('Movie/Show.sample.mkv',False),('Movie/release.nfo',True)])
def test_shared_sample_rules(path,selected):assert default_file_selected(path)==selected

def test_real_torrent_root_is_derived_from_all_files():
 assert torrent_root(['Movie.mkv','Samples/clip.mkv'])==''
 assert not default_file_selected('Samples/clip.mkv',torrent_root(['Movie.mkv','Samples/clip.mkv']))
 names=['Samples/S01E01.mkv','Samples/S01E02.mkv'];root=torrent_root(names)
 assert root=='Samples' and all(default_file_selected(n,root) for n in names)
 assert not is_sample_video('Sample Size.mkv') and not is_sample_video('Resampled.Audio.Pack.mkv')
 assert is_sample_path('/Samples/Show/Samples/clip.mkv','/Samples/Show')
 assert not is_sample_path('/Samples/Show/S01E01.mkv','/Samples/Show')

def test_trusted_nas_device_can_authenticate_later_clients():
 credentials={'nas_local_url':'http://127.0.0.1:5000','nas_username':'fixture','otp_code':'123456','remember_device':True}
 c=bare_client();c.credentials=dict(credentials);c.base_url='http://127.0.0.1:5000';c.session_name='FileStation';c._connect_request=Mock(return_value=response({'success':True,'data':{'sid':'one','did':'fixture-device-token'}}))
 info={'SYNO.API.Auth':{'path':'auth.cgi','maxVersion':7}}
 c._login_from_info(info,'fixture','fixture-password');params=c._connect_request.call_args.kwargs['data'];assert params['enable_device_token']=='yes' and params['device_name']=='SynoStream Windows' and params['version']==6
 assert c.device_id=='fixture-device-token' and 'otp_code' not in c.credentials
 later=bare_client();later.base_url=c.base_url;later.session_name='FileStation';later.credentials={k:v for k,v in credentials.items() if k not in ('otp_code','remember_device')};later.credentials['nas_device_tokens']=json.dumps({nas_device_key(credentials):c.device_id});later._connect_request=Mock(return_value=response({'success':True,'data':{'sid':'two'}}));later._login_from_info(info,'fixture','fixture-password')
 params=later._connect_request.call_args.kwargs['data'];assert params['device_id']==c.device_id and 'otp_code' not in params
 wrong=dict(later.credentials,nas_username='other');assert trusted_device_id(wrong)==''
 assert trusted_device_id(dict(later.credentials,use_device_token=False))==''

def test_device_tokens_are_dpapi_only(media):
 m=media;m.config['nas_device_tokens']=json.dumps({'fixture-profile':'fixture-device-token'})
 assert m.save_config()[0];public=Path(m.CONFIG_FILE).read_text();assert 'fixture-device-token' not in public and 'nas_device_tokens' not in json.loads(public)
 cfg,_=m.load_config();assert json.loads(cfg['nas_device_tokens'])=={'fixture-profile':'fixture-device-token'}

def test_invalid_relay_does_not_hide_valid_candidate():
 c=bare_client();c.extra_apis=();c._connect_request=Mock(side_effect=[response([{'errno':0,'env':{'relay_region':'evil.example/x?'}},{'errno':0,'env':{'relay_region':'us1'}}]),response({}),response({'success':True,'data':{'fixture':{}}})]);c._discover_quickconnect('safe-id')
 assert c.base_url=='https://safe-id.us1.quickconnect.to' and c._connect_request.call_count==3

@pytest.mark.parametrize('text',['Kétlépcsős azonosítás','A NAS egyszer használatos kódja:','A NAS nem értelmezhető JSON-választ adott.','Mentési figyelmeztetés','Megbízható eszköz megjegyzése a kétlépcsős belépéshez'])
def test_new_ui_text_has_english_translation(media,monkeypatch,text):
 monkeypatch.setattr(media,'UI_LANGUAGE','en');assert media.translate_text(text)!=text

def test_user_cancelled_mpv_is_not_an_error(media,monkeypatch):
 monkeypatch.setattr(media,'resolve_mpv_path',lambda p:None);monkeypatch.setattr(media.os.path,'isfile',lambda p:False);monkeypatch.setattr(media.sys,'platform','win32');monkeypatch.setattr(media.ensure_mpv,'_cleanup_started',True,raising=False)
 def cancel(*args):raise InterruptedError('fixture')
 monkeypatch.setattr(mpv,'bootstrap',cancel);warning=Mock();monkeypatch.setattr(media.QMessageBox,'warning',warning)
 assert media.ensure_mpv() is None;warning.assert_not_called()

def test_mpv_labels_translate_on_gui_thread(media,monkeypatch):
 from PyQt6.QtWidgets import QProgressDialog
 seen=[]
 class Progress(QProgressDialog):
  def setLabelText(self,value):seen.append(value);return super().setLabelText(value)
 monkeypatch.setattr(media,'UI_LANGUAGE','en');monkeypatch.setattr(media,'resolve_mpv_path',lambda p:None);monkeypatch.setattr(media.os.path,'isfile',lambda p:False);monkeypatch.setattr(media.sys,'platform','win32');monkeypatch.setattr(media,'save_config',lambda:(True,''));monkeypatch.setattr(media.ensure_mpv,'_cleanup_started',True,raising=False)
 def work(*args):args[-1].setLabelText('MPV kicsomagolása…');return 'fixture.exe'
 monkeypatch.setattr(mpv,'bootstrap',work);monkeypatch.setattr('PyQt6.QtWidgets.QProgressDialog',Progress)
 assert media.ensure_mpv()=='fixture.exe';assert media.translate_text('MPV kicsomagolása…') in seen and 'MPV kicsomagolása…' not in seen

def test_stale_mpv_cleanup_is_strictly_scoped(tmp_path):
 install=tmp_path/'mpv';old=tmp_path/('mpv.old-'+'a'*32);new=tmp_path/('mpv.new-'+'b'*32);foreign=tmp_path/'other.old-folder';fresh=tmp_path/('mpv.old-'+'c'*32)
 for d in [old,new,foreign,fresh]:d.mkdir();(d/'fixture').write_text('x')
 now=time.time()
 for d in [old,new,foreign]:os.utime(d,(now-90000,now-90000))
 mpv.cleanup_stale(install,now);assert not old.exists() and not new.exists() and foreign.exists() and fresh.exists()

def test_diagnostics_keep_exception_class_but_no_private_message(media,monkeypatch,caplog):
 def fail(*a,**kw):raise media.sqlite3.OperationalError('secret-password-and-private-path')
 monkeypatch.setattr(media.sqlite3,'connect',fail);media.write_tmdb_metadata_cache('fixture',{})
 assert 'OperationalError' in caplog.text and 'secret-password-and-private-path' not in caplog.text
