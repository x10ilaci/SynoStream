import concurrent.futures as futures
import json,threading,time,sqlite3,contextlib
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import requests
from synostream_nas import RemoteNASClient,clear_route_cache
from synostream_sessions import NasSessionPool
from synostream_diagnostics import snapshot,measure
from test_upgrade import bare_client,response

@pytest.fixture(autouse=True)
def isolated_routes():
 clear_route_cache();yield;clear_route_cache()

def test_directory_request_is_one_filtered_page():
 c=bare_client();c.api_get=Mock(return_value={'files':[{'name':'Folder','path':'/downloads/Folder','isdir':True}],'total':1})
 t=time.perf_counter();data=c.list_directories('/downloads')
 assert len(data['entries'])==1 and not data['more']
 kwargs=c.api_get.call_args.kwargs
 assert kwargs==dict(offset=0,limit=200,sort_by='name',folder_path='/downloads',filetype='dir')
 c.api_get.return_value={'shares':[],'total':0};c.list_directories('')
 assert 'additional' not in c.api_get.call_args.kwargs and c.api_get.call_args.kwargs['onlywritable']=='true'

def test_scan_fields_and_deletion_fields():
 c=bare_client();c.api_get=Mock(return_value={'files':[]})
 c.list_folder('/video');assert json.loads(c.api_get.call_args.kwargs['additional'])==['size','time']
 c.list_for_deletion('/video');assert json.loads(c.api_get.call_args.kwargs['additional'])==['real_path','size','time']

def test_pool_four_concurrent_reads_one_login_and_single_renewal():
 pool=NasSessionPool();logins=[];barrier=threading.Barrier(4)
 def factory(stop):
  logins.append(1);c=bare_client();c.should_stop=stop
  def get(*a,**k):
   if k['params']['_sid']=='old-session':barrier.wait(timeout=3);return response({'success':False,'error':{'code':106}})
   time.sleep(.08);return response({'success':True,'data':{'files':[]}})
  c._get=get;return c
 def read(n):
  lease=pool.acquire({'quickconnect_id':'fixture'},lambda:False,factory)
  try:lease.api_get('SYNO.FileStation.List',2,'list')
  finally:lease.close()
 try:
  t=time.perf_counter()
  with futures.ThreadPoolExecutor(4) as executor:list(executor.map(read,range(4)))
  assert len(logins)==1
  entry=next(iter(pool.entries.values()));entry['client'].connect.assert_called_once()
  assert time.perf_counter()-t<.3
 finally:pool.close()

def test_pool_cancellation_is_borrower_local_and_idle_closes():
 pool=NasSessionPool(idle=.01);stopped=[False];created=[]
 def make(stop):
  c=bare_client();c.close=Mock();c.should_stop=stop;created.append(c);return c
 a=pool.acquire({},lambda:stopped[0],make);b=pool.acquire({},lambda:False,make)
 stopped[0]=True
 with pytest.raises(InterruptedError):a._check_cancelled()
 b._check_cancelled();a.close();b.close();time.sleep(.02);pool.reap();assert not pool.entries
 pool.close()

def test_route_cache_avoids_failed_lan_and_reuses_relay(monkeypatch):
 attempts=[];info={k:{'path':'entry.cgi'} for k in ('SYNO.API.Auth','SYNO.FileStation.List','SYNO.FileStation.Download')}
 def get(c,url,**kwargs):attempts.append(c.transport);raise requests.ConnectionError()
 def discover(c,address):attempts.append('discover');c.base_url='https://fixture.eu.quickconnect.to';return info
 def login(c,*args):c.sid='fixture'
 monkeypatch.setattr(RemoteNASClient,'_get',get);monkeypatch.setattr(RemoteNASClient,'_discover_quickconnect',discover);monkeypatch.setattr(RemoteNASClient,'_login_from_info',login)
 monkeypatch.setattr(RemoteNASClient,'_connect_request',lambda *a,**k:response({'data':info}))
 profile={'nas_local_url':'192.168.1.2','quickconnect_id':'fixture','nas_username':'fixture','nas_password':'fixture'}
 a=RemoteNASClient(profile);assert attempts==['local','discover'];attempts.clear()
 b=RemoteNASClient(profile);assert attempts==[] and b.transport=='quickconnect'
 # Cached endpoint fails: full normal route order is attempted again.
 monkeypatch.setattr(RemoteNASClient,'_connect_request',Mock(side_effect=requests.ConnectionError()))
 c=RemoteNASClient(profile);assert attempts==['local','discover']
 for client in (a,b,c):client.sid='';client.close()

def test_anonymous_metrics_never_retain_arguments(caplog):
 import logging
 snapshot(True)
 with caplog.at_level(logging.DEBUG,logger='SynoStream'):
  with measure('https://private-secret.invalid/?sid=private-secret','private-secret'):pass
 assert 'private-secret' not in caplog.text
 assert set(snapshot())=={('NAS','request')}

def test_movie_tree_parallel_listing_preserves_results(media,monkeypatch):
 scanner=media.LibraryScannerThread([],[]);scanner.remote_client=object();seen=[];calls=[]
 def row(path,directory):return dict(name=path.rsplit('/',1)[-1],path=path,isdir=directory,additional={'size':100,'time':{'mtime':1}})
 tree={'/video':[row('/video/Movie'+str(i),True) for i in range(40)]}
 tree.update({'/video/Movie'+str(i):[row('/video/Movie'+str(i)+'/Film.mkv',False)] for i in range(40)})
 def listing(path):time.sleep(.08);calls.append(path);return tree[path]
 monkeypatch.setattr(scanner,'portable_remote_listing',listing)
 monkeypatch.setattr(scanner,'_process_media_item',lambda entry,*args:(seen.append(entry.path) or scanner.make_item(entry.path,'Fixture','',media_id=42)))
 started=time.perf_counter()
 with contextlib.closing(sqlite3.connect(media.DB_FILE)) as conn:scanner.scan_remote_folder(conn,'syno:///video',True,'Movie')
 elapsed=time.perf_counter()-started
 assert not scanner.errors and set(seen)=={'syno:///video/Movie'+str(i)+'/Film.mkv' for i in range(40)}
 assert len(calls)==41 and elapsed<41*.08*.35
 print('BENCHMARK Windows 40 folders: seconds=%.3f calls=%d'%(elapsed,len(calls)))

def test_directory_cache_queue_profile_and_token(media,app,monkeypatch):
 w=media.DSVideoWindow();page=w.downloads_page;page.timer.stop();jobs=[];result=[];dialog=SimpleNamespace(closed=False)
 media.config['nas_device_tokens']='fixture-token';assert page.credentials()['nas_device_tokens']=='fixture-token'
 client=SimpleNamespace(list_directories=Mock(return_value={'entries':[],'more':False}))
 def start(op,success,failure):jobs.append(op);success(op(client));return True
 monkeypatch.setattr(page,'start_operation',start)
 page.busy=True;page.directory_operation(dialog,'/video',0,result.append,pytest.fail);assert not jobs
 page.operation_finished();assert len(jobs)==1
 page.directory_operation(dialog,'/video',0,result.append,pytest.fail);assert len(jobs)==1
 page.folder_cache[('/video',0)]=(time.monotonic()-61,{'entries':[],'more':False})
 page.directory_operation(dialog,'/video',0,result.append,pytest.fail);assert len(jobs)==2
 media.config['nas_username']='changed';page.directory_operation(dialog,'/video',0,result.append,pytest.fail);assert len(jobs)==3
 page.client=None;w.close()


def test_scanner_episode_and_proxy_factory_share_authenticated_profile(media,monkeypatch):
 pool=NasSessionPool();created=[];calls=[]
 class Client:
  def __init__(self,credentials,stop,extra_apis=()):
   time.sleep(.08);created.append(self);self.credentials=credentials;self.should_stop=stop;self.close=Mock()
  def list_folder(self,path):
   if self.should_stop():raise InterruptedError()
   calls.append(path);return [{'name':'S01E01.mkv','path':path+'/S01E01.mkv','isdir':False}]
 monkeypatch.setattr(media,'nas_session_pool',pool);monkeypatch.setattr(media,'_RemoteNASClient',Client);monkeypatch.setattr(media,'source_router',lambda:SimpleNamespace(pairs=[],canonical=lambda path:path))
 try:
  a=media.RemoteNASClient();a.list_folder('/show');a.close()
  b=media.RemoteNASClient(dict(media.config));b.close()
  result=[];worker=media.EpisodeScanWorker('syno:///show');worker.episodes_found.connect(lambda entries,error:result.append((entries,error)));worker.run()
  assert len(created)==1 and len(calls)==2 and result[0][1]=='' and len(result[0][0])==1
  print('BENCHMARK Windows scan/reopen/episode: logins=1; episode additional logins=0')
 finally:pool.close()

def test_unchanged_leaf_scan_does_not_prefetch_cached_directories(media,monkeypatch):
 scanner=media.LibraryScannerThread([],[]);scanner.remote_client=object();scanner.directory_scan_token='fixture';calls=[];emitted=[]
 for i in range(40):scanner._record_directory_snapshot('/video/Film'+str(i),1,False,1)
 monkeypatch.setattr(scanner,'_cached_rows_for_movie_directory',lambda path:[{'file_mtime':1}])
 monkeypatch.setattr(scanner,'emit_cached_media_row',lambda row,*args:emitted.append(row))
 def listing(path):
  calls.append(path);assert path=='/video'
  return [dict(name='Film'+str(i),path='/video/Film'+str(i),isdir=True,additional={'time':{'mtime':1}}) for i in range(40)]
 monkeypatch.setattr(scanner,'portable_remote_listing',listing)
 with contextlib.closing(sqlite3.connect(media.DB_FILE)) as conn:scanner.scan_remote_folder(conn,'syno:///video',True,'Movie')
 assert not scanner.errors and calls==['/video'] and len(emitted)==40
 print('BENCHMARK Windows unchanged 40 leaf folders: lists=1')

def test_folder_initial_destination_is_canonical(media,app,monkeypatch):
 from synostream_download_ui import FolderDialog
 w=media.DSVideoWindow();page=w.downloads_page;page.timer.stop();calls=[]
 monkeypatch.setattr(page,'directory_operation',lambda dialog,path,offset,success,failure:calls.append(path))
 dialog=FolderDialog(page,'video/Movies');dialog.show();app.processEvents();assert calls==['/video/Movies'];dialog.reject();w.close()


def test_folder_parent_is_cached_and_pages_appear_incrementally(media,app,monkeypatch):
 from synostream_download_ui import FolderDialog
 w=media.DSVideoWindow();page=w.downloads_page;page.timer.stop();calls=[]
 def directories(path,offset=0,limit=200):
  calls.append((path,offset));return {'entries':[{'name':'Folder'+str(i),'path':path+'/Folder'+str(i),'isdir':True} for i in range(offset,offset+(200 if offset==0 else 3))],'more':offset==0}
 client=SimpleNamespace(list_directories=directories)
 def start(op,success,failure):success(op(client));return True
 monkeypatch.setattr(page,'start_operation',start)
 dialog=FolderDialog(page,'/video');dialog.show();app.processEvents();assert dialog.items.count()==200 and dialog.more_button.isVisible()
 dialog.more_button.click();assert dialog.items.count()==203 and not dialog.more_button.isVisible()
 dialog.load('/video/Folder0');assert len(calls)==3
 dialog.parent_button.click();assert dialog.path=='/video' and len(calls)==3
 dialog.reject();w.close()

def test_closed_queued_folder_does_not_contact_nas(media,app,monkeypatch):
 w=media.DSVideoWindow();page=w.downloads_page;page.timer.stop();dialog=SimpleNamespace(closed=False);start=Mock();monkeypatch.setattr(page,'start_operation',start)
 page.busy=True;page.directory_operation(dialog,'/video',0,Mock(),Mock());dialog.closed=True;page.operation_finished();start.assert_not_called();w.close()
