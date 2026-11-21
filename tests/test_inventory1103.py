import contextlib
import json
import sqlite3
import time
from unittest.mock import Mock
import pytest
from synostream_downloads import DownloadStationClient,DownloadStationError

@pytest.mark.parametrize('page_size,total_mode',[(100,'page'),(25,'page'),(100,'missing'),(100,'global')])
def test_all_torrents_even_with_page_total(page_size,total_mode):
 c=DownloadStationClient.__new__(DownloadStationClient);rows=[{'id':str(i)} for i in range(235)];calls=[]
 def request(method,**kw):
  calls.append(kw['offset']);batch=rows[kw['offset']:kw['offset']+page_size]
  d={'tasks':batch}
  if total_mode!='missing':d['total']=len(rows) if total_mode=='global' else len(batch)
  return d
 c._task_request=request
 assert len(c.list_tasks())==235 and calls[-1]==235


def test_inventory_previews_precede_every_metadata_lookup(media,tmp_path,monkeypatch):
 root=tmp_path/'movies';root.mkdir();(root/'A.mkv').touch();(root/'B.mkv').touch()
 scanner=media.LibraryScannerThread([str(root)],[],library_key='movies')
 previews=[];inventories=[];resolved=[]
 scanner.preview_ready.connect(lambda item,movie:previews.append(item))
 scanner.inventory_ready.connect(inventories.append)
 def resolve(entry,movie,conn,token):
  assert len(previews)==2 and inventories
  resolved.append(entry.path)
  return scanner.make_item(entry.path,'Identified','Plot',media_id=42)
 monkeypatch.setattr(scanner,'_process_media_item',resolve)
 scanner.run()
 assert len(resolved)==2 and all(isinstance(item['title'],str) for item in previews)
 with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
  assert db.execute('SELECT COUNT(*) FROM library_card_cache').fetchone()[0]==2


def test_inaccessible_root_never_confirms_deletions(media,tmp_path):
 scanner=media.LibraryScannerThread([str(tmp_path/'missing')],[],library_key='movies')
 inventories=[];scanner.inventory_ready.connect(inventories.append);scanner.run()
 assert scanner.errors and inventories==[]


def test_known_display_metadata_is_not_requeried_when_expired(media,monkeypatch):
 scanner=media.LibraryScannerThread([],[])
 payload={'title':'Magyar cím','overview':'Plot','poster_url':'','date':'2020'}
 monkeypatch.setattr(media,'read_tmdb_metadata_cache',lambda key:(payload,False))
 request=Mock(side_effect=AssertionError('No network for known metadata'));monkeypatch.setattr(media,'tmdb_request',request)
 with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
  result=scanner.localized_cached_info(db,'C:/a.mkv',42,True,'Original','Plot','','2020')
 assert result['title']=='Magyar cím';request.assert_not_called()


def test_periodic_reconciliation_skips_busy_and_uses_fast_all_libraries(media,app,monkeypatch):
 window=media.DSVideoWindow();scan=Mock();monkeypatch.setattr(window,'start_library_scan',scan)
 try:
  window._last_inventory_check=time.monotonic()-301
  window.scanner_thread=object();window.check_library_changes();scan.assert_not_called()
  window.scanner_thread=None;window.check_library_changes();scan.assert_called_once_with()
 finally:window.scanner_thread=None;window.close();app.processEvents()


def test_normal_manual_refresh_does_not_force_all_metadata(media,app,monkeypatch):
 window=media.DSVideoWindow();scan=Mock();monkeypatch.setattr(window,'start_library_scan',scan)
 try:window.refresh_library();scan.assert_called_once_with(window.current_library_key)
 finally:window.close();app.processEvents()

@pytest.mark.parametrize('old,expected',[('current','all'),('all','all'),('none','none')])
def test_startup_upgrade_defaults_to_all_but_keeps_explicit_opt_out(media,old,expected):
 from pathlib import Path
 Path(media.CONFIG_FILE).write_text(json.dumps({'startup_scan_mode':old}),encoding='utf-8')
 loaded,_=media.load_config()
 assert loaded['startup_scan_mode']==expected and loaded['inventory_startup_v103'] is True


def test_empty_remote_reply_does_not_publish_mass_deletion(media,monkeypatch):
 from types import SimpleNamespace
 root='syno:///Media/Movies';path=root+'/Old.mkv'
 with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
  db.execute('INSERT INTO media_cache(file_path,tmdb_id,is_movie,status) VALUES (?,?,?,?)',(path,42,1,'success'))
  db.execute('INSERT INTO library_card_cache VALUES (?,?,?)',('movies',path,json.dumps({'file_path':path,'title':'Old'})));db.commit()
 client=SimpleNamespace(list_folder=lambda path:[],close=lambda:None)
 monkeypatch.setattr(media,'RemoteNASClient',lambda **kw:client)
 scanner=media.LibraryScannerThread([root],[],library_key='movies');inventories=[];scanner.inventory_ready.connect(inventories.append)
 scanner.run()
 assert inventories==[]
 with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
  assert db.execute('SELECT COUNT(*) FROM library_card_cache').fetchone()[0]==1
