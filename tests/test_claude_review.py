import io,json,threading,zipfile,hashlib,time
from datetime import date
from pathlib import Path
from unittest.mock import Mock
import pytest
from test_upgrade import bare_client,response
from test_deletion1104 import Files as BaseFiles
import copy,posixpath
class Files(BaseFiles):
 def list(self,root):
  if root=="":return [copy.deepcopy(e) for p,e in self.rows.items() if posixpath.dirname(p)=="/"]
  return super().list(root)
from synostream_nas import RemoteNASClient,quickconnect_url,NASOtpRequired
from synostream_deletion import Inventory,sample
from synostream_logic import clean_name,parse_episode_position
import synostream_mpv_install as mpv

@pytest.mark.parametrize('identifier',['a@evil.example/','a/b','x'*65,'a:443','a?b'])
def test_quickconnect_identifier_rejected_before_io(identifier):
 c=bare_client();c._connect_request=Mock()
 with pytest.raises(ValueError):c._discover_quickconnect(identifier)
 c._connect_request.assert_not_called()

@pytest.mark.parametrize('region',['evil.example/x?','us@evil.example','us:443','/us','US'])
def test_quickconnect_region_rejected_before_endpoint_io(region):
 c=bare_client();c._connect_request=Mock(return_value=response([{'errno':0,'env':{'relay_region':region}}]))
 with pytest.raises(RuntimeError):c._discover_quickconnect('safe-id')
 assert c._connect_request.call_count==1
 assert quickconnect_url('safe-id','us1')=='https://safe-id.us1.quickconnect.to'

def test_config_rejects_invalid_identifier(media):
 m=media;m.config['quickconnect_id']='a@evil.example/'
 assert m.save_config()[0] is False
 Path(m.CONFIG_FILE).write_text(json.dumps({'quickconnect_id':'a@evil.example/'}))
 cfg,warning=m.load_config();assert cfg['quickconnect_id']=='' and warning

@pytest.mark.parametrize('root,seed,file',[('/video/Samples','/video/Samples/Show','/video/Samples/Show/S01E01.mkv'),('/video','/video/Sample Size (2019)','/video/Sample Size (2019)/Sample Size (2019).mkv'),('/video','/video/Samples','/video/Samples/S01E01.mkv')])
def test_sample_titles_and_roots_are_not_release_samples(root,seed,file):
 fs=Files([file]);inv=Inventory([file] if '2019' in file else [seed],[root],'2019' in file,fs.list)
 assert file in inv.plan().files

def test_sample_subfolders_and_filename_markers():
 root='/video/Show'
 assert sample(root+'/Sample/x.mkv',[root])
 assert sample(root+'/Samples/x.mkv',[root])
 assert sample(root+'/Show.sample.mkv',[root])
 assert not sample(root+'/Sample Size (2019).mkv',[root])
 inv=Inventory([root],['/video'],False,Files([root+'/S01E01.mkv',root+'/Samples/S02E01.mkv']).list)
 assert inv.seasons==(1,)

@pytest.mark.parametrize('filename,season,episode',[('Show/Show.S02.720p.mkv',2,None),('Show/Show.S100E01.mkv',100,1),('Show/Show.x264.mkv',1,None),('Show/S.W.A.T.mkv',1,None)])
def test_season_tokens(filename,season,episode):
 result=parse_episode_position(filename);assert result[:2]==(season,episode)

def test_dynamic_years_and_numeric_titles():
 year=date.today().year
 assert clean_name(f'Movie ({year+1}).mkv')==('Movie',str(year+1))
 assert clean_name(f'Movie ({year+5}).mkv')[1] is None
 assert clean_name('Blade Runner 2049.mkv')[0]=='Blade Runner 2049'

def test_api_endpoint_and_invalid_json():
 c=bare_client();c.base_url='https://nas.invalid';c.api_info={'Other.API':{'path':'other.cgi'}}
 c.session.get.return_value=response({'success':True,'data':{'ok':1}})
 assert c.api_get('Other.API',1,'get')=={'ok':1}
 assert c.session.get.call_args.args[0]=='https://nas.invalid/webapi/other.cgi'
 c.session.get.return_value.json.side_effect=ValueError('proxy HTML')
 with pytest.raises(RuntimeError,match='JSON'):c.api_get('Other.API',1,'get')

def test_stream_wait_does_not_block_listing():
 c=bare_client();entered=threading.Event();release=threading.Event()
 def get(url,**kw):
  if kw['params']['api']=='SYNO.FileStation.Download':entered.set();assert release.wait(3);return response(status=206)
  return response({'success':True,'data':{'ok':True}})
 c.session.get.side_effect=get
 thread=threading.Thread(target=lambda:c.open_stream('/video/a.mkv'));thread.start()
 try:
  assert entered.wait(1);started=time.monotonic();assert c.api_get('api',1,'get')['ok'];assert time.monotonic()-started<1
 finally:release.set();thread.join(3)
 assert not thread.is_alive()

def test_otp_is_required_and_used_once():
 c=bare_client();c.base_url='https://nas.invalid';c.session_name='FileStation';c.credentials={'otp_code':'123456'}
 c._connect_request=Mock(side_effect=[response({'success':True,'data':{'sid':'one'}}),response({'success':False,'error':{'code':403}})])
 info={'SYNO.API.Auth':{'path':'auth.cgi'}}
 c._login_from_info(info,'fixture','fixture');assert c._connect_request.call_args.kwargs['data']['otp_code']=='123456'
 assert 'otp_code' not in c.credentials
 with pytest.raises(NASOtpRequired):c._login_from_info(info,'fixture','fixture')
 assert 'otp_code' not in c._connect_request.call_args.kwargs['data']

def test_probe_invalid_identifier_has_no_network(media,monkeypatch):
 post=Mock();monkeypatch.setattr(media.requests,'post',post)
 worker=media.QuickConnectProbeWorker('a@evil.example/','fixture','fixture');results=[];worker.finished_with_result.connect(results.append);worker.run()
 post.assert_not_called();assert results and 'Érvénytelen' in results[0]

def test_mpv_replaces_tree_without_stale_dlls_and_rolls_back(tmp_path,monkeypatch):
 old=tmp_path/'mpv';old.mkdir();(old/'mpv.exe').write_bytes(b'old');(old/'stale.dll').write_bytes(b'old')
 source=tmp_path/'source';source.mkdir();(source/'mpv.exe').write_bytes(b'new')
 replace=mpv.os.replace
 def fail(source,dest):
  if '.new-' in str(source):raise PermissionError('fixture locked')
  return replace(source,dest)
 monkeypatch.setattr(mpv.os,'replace',fail)
 with pytest.raises(PermissionError):mpv.replace_install(source,old)
 assert (old/'mpv.exe').read_bytes()==b'old' and (old/'stale.dll').exists()
 monkeypatch.setattr(mpv.os,'replace',replace);mpv.replace_install(source,old)
 assert (old/'mpv.exe').read_bytes()==b'new' and not (old/'stale.dll').exists()

@pytest.mark.parametrize('member',['../escape','x:ads','/absolute','C:/evil'])
def test_mpv_rejects_unsafe_archive_members(tmp_path,monkeypatch,member):
 buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w') as z:z.writestr('mpv.exe',b'fixture');z.writestr(member,b'x')
 data=buf.getvalue();asset={'name':'mpv-x86_64-w64-mingw32.zip','size':len(data),'browser_download_url':'https://github.com/mpv-player/mpv/releases/download/fixture/mpv.zip','digest':'sha256:'+hashlib.sha256(data).hexdigest()}
 meta=response({'assets':[asset]});archive=response();archive.iter_content.return_value=[data];archive.__enter__=Mock(return_value=archive);archive.__exit__=Mock(return_value=False)
 monkeypatch.setattr(mpv.requests,'get',Mock(side_effect=[meta,archive]))
 with pytest.raises(RuntimeError,match='biztonságos|célmapp'):mpv.bootstrap(tmp_path/'install','https://api.github.com/fixture',100000,lambda:False,Mock())
 assert not (tmp_path/'install').exists()

def test_mpv_worker_keeps_gui_responsive_and_reports_save_failure(media,monkeypatch):
 from PyQt6.QtCore import QTimer,QThread
 ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(1));timer.start(5)
 def bootstrap(*args):assert QThread.currentThread()!=media.QApplication.instance().thread();time.sleep(.08);return 'fixture-mpv.exe'
 monkeypatch.setattr(mpv,'bootstrap',bootstrap);monkeypatch.setattr(media,'resolve_mpv_path',lambda p:None);monkeypatch.setattr(media.os.path,'isfile',lambda p:False);monkeypatch.setattr(media.sys,'platform','win32');monkeypatch.setattr(media,'save_config',lambda:(False,'fixture save failed'));warning=Mock();monkeypatch.setattr(media.QMessageBox,'warning',warning)
 try:assert media.ensure_mpv()=='fixture-mpv.exe'
 finally:timer.stop()
 assert ticks and warning.called

def test_database_cache_failure_is_logged(media,monkeypatch,caplog):
 def fail(*a,**kw):raise media.sqlite3.OperationalError('fixture')
 monkeypatch.setattr(media.sqlite3,'connect',fail)
 media.write_tmdb_metadata_cache('fixture',{'title':'fixture'})
 assert 'write_tmdb_metadata_cache' in caplog.text


def test_probe_rejects_bad_region_before_nas_request(media,monkeypatch):
 resolver=response([{'errno':0,'env':{'relay_region':'evil.example/x?'}}]);post=Mock(return_value=resolver);session=Mock()
 monkeypatch.setattr(media.requests,'post',post);monkeypatch.setattr(media.requests,'Session',session)
 worker=media.QuickConnectProbeWorker('safe-id','fixture','fixture');result=[];worker.finished_with_result.connect(result.append);worker.run()
 session.assert_not_called();assert result and 'régió' in result[0]

def test_probe_never_lists_or_logs_out_without_session(media,monkeypatch):
 resolver=response([]);session=Mock();session.headers={};session.cookies=[];session.get.return_value=response();session.post.return_value=response({'success':True,'data':{}})
 monkeypatch.setattr(media.requests,'post',Mock(return_value=resolver));monkeypatch.setattr(media.requests,'Session',Mock(return_value=session))
 worker=media.QuickConnectProbeWorker('safe-id','fixture','fixture');worker._api_info=lambda *a:({'SYNO.API.Auth':{'path':'auth.cgi'}},[]);results=[];worker.finished_with_result.connect(results.append);worker.run()
 assert session.get.call_count==1 and 'munkamenet' in results[0]

def test_bootstrap_success_replaces_existing_mpv(tmp_path,monkeypatch):
 buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w') as z:z.writestr('build/mpv.exe',b'new');z.writestr('build/new.dll',b'dll')
 data=buf.getvalue();asset={'name':'mpv-x86_64-w64-mingw32.zip','size':len(data),'browser_download_url':'https://github.com/mpv-player/mpv/releases/download/fixture/mpv.zip','digest':'sha256:'+hashlib.sha256(data).hexdigest()}
 meta=response({'assets':[asset]});archive=response();archive.iter_content.return_value=[data];archive.__enter__=Mock(return_value=archive);archive.__exit__=Mock(return_value=False)
 monkeypatch.setattr(mpv.requests,'get',Mock(side_effect=[meta,archive]));target=tmp_path/'install';target.mkdir();(target/'old.dll').write_bytes(b'old')
 assert Path(mpv.bootstrap(target,'https://api.github.com/fixture',100000,lambda:False,Mock())).read_bytes()==b'new'
 assert (target/'new.dll').exists() and not (target/'old.dll').exists()


def test_otp_network_failure_is_not_replayed():
 import requests
 c=bare_client();c.transport='quickconnect';c.session.post.side_effect=requests.Timeout('fixture')
 with pytest.raises(RuntimeError):c._connect_request('post','https://safe.quickconnect.to/webapi/auth.cgi',data={'otp_code':'123456'})
 assert c.session.post.call_count==1
