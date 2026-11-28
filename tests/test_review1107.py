import json,threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from synostream_logic import parse_episode_position,is_sample_video,largest_video_sizes,SAMPLE_MAX_BYTES
from synostream_torrent_selection import default_file_selected
from synostream_deletion import Inventory
from test_deletion1104 import Files,ROOT
from test_upgrade import bare_client,response

@pytest.mark.parametrize('name',['Show/Show.2x05HDTV.mkv','Show/Show.2x05v2.mkv','Show/Show.2x05x264.mkv','Show [2x05].mkv'])
def test_nxm_release_suffixes(name):assert parse_episode_position(name)==(2,5,True)

@pytest.mark.parametrize('name',['Show 2x05p.mkv','Show 2x05i.mkv','Movie.720x480.mkv'])
def test_nxm_resolution_suffix_is_still_not_an_episode(name):assert parse_episode_position(name)==(1,None,False)

@pytest.mark.parametrize('size,largest,wanted',[(None,None,False),(-1,9999999999,False),(SAMPLE_MAX_BYTES,None,False),(SAMPLE_MAX_BYTES+1,None,False),(200_000_000,2_000_000_001,True),(200_000_000,2_000_000_000,False)])
@pytest.mark.parametrize('name',['Sample-The.Movie.2019.1080p.mkv','sample_movie.mkv'])
def test_ambiguous_sample_size_evidence(name,size,largest,wanted):
 assert is_sample_video(name,size,largest)==wanted
 assert default_file_selected('Movie/'+name,'Movie',size,largest)==(not wanted)

def test_large_sample_title_and_unknown_size_are_preserved():
 assert not is_sample_video('Sample Size.mkv',2_000_000_000,2_000_000_000)
 assert not is_sample_video('sample_movie.mkv',None,10_000_000_000)
 assert is_sample_video('Movie.sample.mkv')
 assert largest_video_sizes([('A/main.mkv',5_000_000_000),('B/sample_x.mkv',200_000_000),('B/main.nfo',9_000_000_000)])=={'A':5_000_000_000,'B':200_000_000}

def test_size_aware_scan_and_episode_inventory(media,tmp_path,monkeypatch):
 folder=tmp_path/'Movie';folder.mkdir()
 sizes={'Movie.mkv':2_000_000_001,'sample_movie.mkv':200_000_000,'Sample Size.mkv':300_000_000}
 for name in sizes:(folder/name).write_bytes(b'x')
 real_stat=media.os.stat
 def stat(path,*a,**k):
  result=real_stat(path,*a,**k)
  if str(path) in {str(folder/name) for name in sizes}:
   fields=list(result);fields[6]=sizes[Path(path).name];return media.os.stat_result(fields)
  return result
 monkeypatch.setattr(media.os,'stat',stat)
 files=media.local_file_listing(str(folder),['Movie.mkv','sample_movie.mkv','Sample Size.mkv'])
 assert media.sample_names_in_listing(files)=={'sample_movie.mkv'}
 episodes,error=media.find_episodes(str(folder));assert not error and {Path(p).name for _,p in episodes}=={'Movie.mkv','Sample Size.mkv'}
 assert media.sample_names_in_listing([{'name':'sample_x.mkv'},{'name':'main.mkv','size':3_000_000_000}])==set()

def test_size_sample_cleanup_does_not_keep_orphan_folder():
 main=ROOT+'/Movie/Main.mkv';sample=ROOT+'/Movie/Sample-Movie.mkv';nfo=ROOT+'/Movie/release.nfo'
 fs=Files([main,sample,nfo]);fs.rows[main]['size']=3_000_000_000;fs.rows[sample]['size']=100_000_000
 inv=Inventory([main],[ROOT],True,fs.list);plan=inv.plan();assert sample in plan.files and nfo in plan.files
 result=inv.execute(plan,fs.delete);assert ROOT+'/Movie' in result['folders']

def test_torrent_recommendation_uses_sizes_and_keeps_manual_override(media,app):
 from synostream_file_selection_ui import FileSelectionDialog
 from test_selection_and_menus import size_text
 window=media.DSVideoWindow();files=[{'index':0,'name':'Movie/main.mkv','size':3_000_000_000},{'index':1,'name':'Movie/sample_movie.mkv','size':200_000_000},{'index':2,'name':'Movie/release.nfo','size':123}]
 d=FileSelectionDialog(window.downloads_page,[{'list_id':'fixture','title':'Movie','destination':'video/Movies','files':files}],size_text)
 assert d.selected_files()=={'fixture':[0,2]};d.set_selection('all');assert d.selected_files()=={'fixture':[0,1,2]};d.set_selection('recommended');assert d.selected_files()=={'fixture':[0,2]};d.close();window.close()

@pytest.mark.parametrize('parameter',['device_id','did','otp_code','sid','password','api_key'])
def test_credentials_redacted(media,parameter):
 assert 'private-value' not in media.redact_credentials('https://fixture.invalid/?'+parameter+'=private-value&safe=ok')

@pytest.mark.parametrize('version,did,wanted',[(5,'',True),(5,'unexpected',True),(6,'',True),(6,'fixture-token',False)])
def test_trust_request_warns_if_not_remembered(version,did,wanted):
 c=bare_client();c.base_url='https://fixture.invalid';c.session_name='fixture';c.credentials={'remember_device':True,'otp_code':'fixture-otp'};c._connect_request=Mock(return_value=response({'success':True,'data':{'sid':'fixture','did':did}}))
 c._login_from_info({'SYNO.API.Auth':{'maxVersion':version}},'fixture','fixture')
 assert bool(c.device_trust_warning)==wanted

def profile(media,monkeypatch):
 p={'credentials':{'fixture':True},'client':None,'paths':{'/video/a.mkv':1}}
 monkeypatch.setattr(media,'_remote_playback_profiles',{'fixture':p});return p

def test_proxy_login_does_not_hold_global_lock(media,monkeypatch):
 p=profile(media,monkeypatch)
 def make(*args):
  acquired=[]
  def probe():
   ok=media._remote_playback_lock.acquire(timeout=.5);acquired.append(ok)
   if ok:media._remote_playback_lock.release()
  t=threading.Thread(target=probe);t.start();t.join(1);assert acquired==[True]
  return SimpleNamespace(sid='fixture',close=Mock())
 monkeypatch.setattr(media,'RemoteNASClient',make)
 assert media._remote_profile_client('fixture',p,'/video/a.mkv') is p['client']

def test_proxy_login_race_closes_unused_client(media,monkeypatch):
 p=profile(media,monkeypatch);barrier=threading.Barrier(2);created=[];answers=[]
 def make(*args):
  c=SimpleNamespace(sid='fixture',close=Mock());created.append(c);barrier.wait(timeout=2);return c
 monkeypatch.setattr(media,'RemoteNASClient',make)
 ts=[threading.Thread(target=lambda:answers.append(media._remote_profile_client('fixture',p,'/video/a.mkv'))) for _ in range(2)]
 for t in ts:t.start()
 for t in ts:t.join(3);assert not t.is_alive()
 assert len(answers)==2 and answers[0] is answers[1] and sum(c.close.call_count for c in created)==1

def test_proxy_release_during_login_closes_candidate(media,monkeypatch):
 p=profile(media,monkeypatch);c=SimpleNamespace(sid='fixture',close=Mock())
 def make(*args):media._remote_playback_profiles.clear();return c
 monkeypatch.setattr(media,'RemoteNASClient',make)
 assert media._remote_profile_client('fixture',p,'/video/a.mkv') is None;c.close.assert_called_once()

def test_diagnostic_type_is_logged_once(media,monkeypatch,caplog):
 def fail(*a,**k):raise media.sqlite3.OperationalError('private-details')
 monkeypatch.setattr(media.sqlite3,'connect',fail);media.write_tmdb_metadata_cache('fixture',{})
 assert caplog.text.count('OperationalError')==1 and 'private-details' not in caplog.text


def test_trusted_device_warning_is_visible_and_translatable(media,app,monkeypatch):
 dialog=media.RemoteQuickConnectDialog(None,connection_only=True)
 dialog.id_edit.setText('fixture');dialog.user_edit.setText('fixture');dialog.pass_edit.setText('fixture');dialog.remember_device.setChecked(True)
 message='A NAS nem jegyezte meg ezt az eszközt. A következő belépésnél ismét kétlépcsős kódot kérhet. Ellenőrizd a DSM megbízhatóeszköz-beállításait.'
 client=SimpleNamespace(**{name:'fixture' for name in ('base_url','sid','auth_url','auth_version','list_url','list_version','download_url','download_version')},session=Mock(),device_id='',device_trust_warning=message,transport='direct',close=Mock())
 monkeypatch.setattr(dialog,'_start_task',lambda work,done,cleanup:done(client));warning=Mock();monkeypatch.setattr(media.QMessageBox,'warning',warning);monkeypatch.setattr(media,'save_config',lambda:(True,''));monkeypatch.setattr(media,'UI_LANGUAGE','en')
 dialog.connect_nas();warning.assert_called_once();assert message not in warning.call_args.args and 'two-step' in warning.call_args.args[2]
 dialog._cleanup_connection()
