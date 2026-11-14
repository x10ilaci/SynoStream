import json
from pathlib import Path
import shutil
import sqlite3
from contextlib import closing
from unittest.mock import Mock
from types import SimpleNamespace
import pytest
import synostream_pairings as p


def database(path):
    conn=sqlite3.connect(path)
    conn.execute('CREATE TABLE manual_overrides(file_path TEXT PRIMARY KEY,tmdb_id INTEGER,custom_title TEXT,is_movie INTEGER)')
    conn.execute('CREATE TABLE media_cache(file_path TEXT PRIMARY KEY,signature TEXT)')
    p.init_tables(conn);conn.commit()
    return conn


def manual(conn,root,path,identifier=603,title='The Matrix',movie=True):
    with conn:
        conn.execute('INSERT OR REPLACE INTO manual_overrides VALUES (?,?,?,?)',(p.normalize_root(path),identifier,title,int(movie)))
        return p.enqueue(conn,[str(root)],str(path),movie,identifier,title)


def test_root_only_storage_and_mounted_elsewhere(tmp_path):
    a=tmp_path/'A';a.mkdir();film=a/'Release'/'Movie.mkv';film.parent.mkdir();film.touch()
    with closing(database(tmp_path/'a.db')) as db:
        manual(db,a,film)
        stats=p.synchronize(db,str(a),p.LocalBackend(a))
        assert stats['written']==1 and not stats['pending']
    assert list(film.parent.iterdir())==[film]
    files=list((a/p.SUBDIR).glob('*.json'));assert len(files)==1
    event=json.loads(files[0].read_text(encoding='utf-8'))
    assert event['relative_path']=='Release/Movie.mkv'
    assert str(tmp_path) not in files[0].read_text(encoding='utf-8')
    b=tmp_path/'B';shutil.copytree(a,b)
    with closing(database(tmp_path/'b.db')) as db:
        stats=p.synchronize(db,str(b),p.LocalBackend(b))
        assert stats['imported']==1
        row=db.execute('SELECT file_path,tmdb_id FROM manual_overrides').fetchone()
        assert row==(p.normalize_root(b/'Release'/'Movie.mkv'),603)


def test_standalone_movie_and_series(tmp_path):
    root=tmp_path/'Library';root.mkdir();(root/'Movie.mkv').touch();(root/'Series').mkdir()
    with closing(database(tmp_path/'a.db')) as a:
        manual(a,root,root/'Movie.mkv')
        manual(a,root,root/'Series',100,'Series',False)
        p.synchronize(a,str(root),p.LocalBackend(root))
    with closing(database(tmp_path/'b.db')) as b:
        p.synchronize(b,str(root),p.LocalBackend(root))
        assert b.execute('SELECT COUNT(*) FROM manual_overrides').fetchone()[0]==2
        assert {r[0] for r in b.execute('SELECT is_movie FROM manual_overrides')}=={0,1}


def test_two_offline_pcs_keep_both_choices(tmp_path):
    root=tmp_path/'Library';root.mkdir()
    with closing(database(tmp_path/'a.db')) as a,closing(database(tmp_path/'b.db')) as b:
        manual(a,root,root/'A.mkv',1,'A');manual(b,root,root/'B.mkv',2,'B')
        p.synchronize(a,str(root),p.LocalBackend(root))
        p.synchronize(b,str(root),p.LocalBackend(root))
        p.synchronize(a,str(root),p.LocalBackend(root))
        assert a.execute('SELECT COUNT(*) FROM manual_overrides').fetchone()[0]==2
        assert b.execute('SELECT COUNT(*) FROM manual_overrides').fetchone()[0]==2
        assert len(list((root/p.SUBDIR).glob('*.json')))==2


def test_same_file_concurrent_changes_converge_and_history_survives(tmp_path):
    root=tmp_path/'Library';root.mkdir();path=root/'A.mkv'
    with closing(database(tmp_path/'a.db')) as a,closing(database(tmp_path/'b.db')) as b:
        manual(a,root,path,1,'A');manual(b,root,path,2,'B')
        p.synchronize(a,str(root),p.LocalBackend(root));p.synchronize(b,str(root),p.LocalBackend(root));p.synchronize(a,str(root),p.LocalBackend(root))
        assert a.execute('SELECT tmdb_id FROM manual_overrides').fetchone()==b.execute('SELECT tmdb_id FROM manual_overrides').fetchone()
        assert len(list((root/p.SUBDIR).glob('*.json')))==2


def test_remove_propagates_without_resurrection(tmp_path):
    root=tmp_path/'Library';root.mkdir();path=root/'A.mkv'
    with closing(database(tmp_path/'a.db')) as a,closing(database(tmp_path/'b.db')) as b:
        manual(a,root,path)
        p.synchronize(a,str(root),p.LocalBackend(root));p.synchronize(b,str(root),p.LocalBackend(root))
        with a:
            p.enqueue(a,[str(root)],str(path),True,deleted=True)
            a.execute('DELETE FROM manual_overrides')
        p.synchronize(a,str(root),p.LocalBackend(root));p.synchronize(b,str(root),p.LocalBackend(root));p.synchronize(a,str(root),p.LocalBackend(root))
        assert not a.execute('SELECT * FROM manual_overrides').fetchall()
        assert not b.execute('SELECT * FROM manual_overrides').fetchall()


def test_readonly_retains_local_and_retry(tmp_path):
    root=tmp_path/'Library';root.mkdir();backend=p.LocalBackend(root)
    with closing(database(tmp_path/'a.db')) as db:
        manual(db,root,root/'A.mkv')
        original=backend.write;backend.write=Mock(side_effect=PermissionError('readonly'))
        result=p.synchronize(db,str(root),backend)
        assert result['pending']==1 and result['warnings']
        assert db.execute('SELECT tmdb_id FROM manual_overrides').fetchone()[0]==603
        backend.write=original
        assert p.synchronize(db,str(root),backend)['pending']==0


def test_legacy_manuals_migrate_once(tmp_path):
    root=tmp_path/'Library';root.mkdir();path=p.normalize_root(root/'A.mkv')
    with closing(database(tmp_path/'a.db')) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(path,603,'Legacy'));db.commit()
        assert p.synchronize(db,str(root),p.LocalBackend(root))['written']==1
        assert p.synchronize(db,str(root),p.LocalBackend(root))['written']==0
        assert len(list((root/p.SUBDIR).glob('*.json')))==1


def test_shared_match_replaces_wrong_automatic_cache(tmp_path):
    root=tmp_path/'Library';root.mkdir();path=p.normalize_root(root/'A.mkv')
    with closing(database(tmp_path/'a.db')) as a,closing(database(tmp_path/'b.db')) as b:
        manual(a,root,path);p.synchronize(a,str(root),p.LocalBackend(root))
        b.execute('INSERT INTO media_cache VALUES (?,?)',(path,'language:wrong'));b.commit()
        p.synchronize(b,str(root),p.LocalBackend(root))
        assert not b.execute('SELECT * FROM media_cache').fetchall()
        assert b.execute('SELECT tmdb_id FROM manual_overrides').fetchone()[0]==603


@pytest.mark.parametrize('bad',['../A.mkv','/A.mkv','C:/A.mkv','folder/../../A.mkv','.synostream/A.mkv','a\\b.mkv','x\x00.mkv'])
def test_bad_relative_paths_rejected(tmp_path,bad):
    root=tmp_path/'Library';root.mkdir()
    with closing(database(tmp_path/'a.db')) as a:
        event=manual(a,root,root/'A.mkv')
    event['relative_path']=bad
    with pytest.raises(ValueError):p.decode_event(json.dumps(event).encode())


def test_no_secrets_and_size_limit(tmp_path):
    root=tmp_path/'Library';root.mkdir()
    with closing(database(tmp_path/'a.db')) as a:event=manual(a,root,root/'A.mkv')
    event['nas_password']='secret'
    with pytest.raises(ValueError):p.decode_event(json.dumps(event).encode())
    with pytest.raises(ValueError):p.decode_event(b' '*(p.MAX_BYTES+1))


def test_nas_backend_protocol_and_readback(tmp_path):
    root='syno:///Movies';client=Mock();client.list_folder.side_effect=[[dict(name='parositasok',isdir=True)],[]]
    backend=p.NASBackend(root,client,[dict(name='.synostream',isdir=True)])
    assert backend.list_names()==[]
    with closing(database(tmp_path/'a.db')) as a:event=manual(a,root,root+'/A.mkv')
    payload=p.encode_event(event)
    client.read_pairing.return_value=payload
    backend.write(event['event_id']+'.json',payload)
    client.upload_pairing.assert_called_once_with('/Movies/.synostream/parositasok',event['event_id']+'.json',payload)
    client.read_pairing.assert_called_once_with('/Movies/.synostream/parositasok/'+event['event_id']+'.json')


def test_real_scanner_imports_shared_before_automatic_match(media,tmp_path,monkeypatch):
    root=tmp_path/'Library';root.mkdir();path=root/'Opaque.mkv';path.touch()
    with closing(database(tmp_path/'other.db')) as other:
        manual(other,root,path,603,'Shared');p.synchronize(other,str(root),p.LocalBackend(root))
    fetch=Mock(return_value=dict(status='success',id=603,title='The Matrix',overview='Description',poster_url='',date='1999',complete=True))
    monkeypatch.setattr(media,'fetch_tmdb_data',fetch)
    scanner=media.LibraryScannerThread([str(root)],[],library_key='movies');scanner.get_poster=Mock(return_value=None)
    items=[];scanner.item_ready.connect(lambda item,movie:items.append(item));scanner.run()
    assert not scanner.failed_libraries,scanner.errors
    assert len(items)==1 and items[0]['id']==603
    fetch.assert_called_once_with(None,is_movie=True,tmdb_id=603)
    assert media.is_ignored('.synostream')


def test_actual_gui_manual_save_queues_same_transaction(media,app,tmp_path,monkeypatch):
    root=tmp_path/'Library';root.mkdir();film=root/'Film.mkv';film.touch()
    media.config['movies_paths']=[str(root)];media.config['movies_path']=str(root)
    window=media.DSVideoWindow();window.start_library_scan=Mock()
    window.sync_shared_pairings=Mock()
    selected=dict(id=603,title='The Matrix')
    choice=Mock();choice.exec.return_value=media.QDialog.DialogCode.Accepted;choice.selected_result.return_value=selected
    monkeypatch.setattr(media,'TmdbChoiceDialog',Mock(return_value=choice))
    monkeypatch.setattr(media.QMessageBox,'information',Mock())
    monkeypatch.setattr(media,'run_worker',Mock())
    window.pending_override=dict(fpath=media.normalize_media_path(str(film)),fpath_raw=str(film),is_movie=True,library_id='movies')
    try:
        window.on_override_search_done(dict(status='success',results=[selected]))
        with closing(sqlite3.connect(media.DB_FILE)) as db:
            assert db.execute('SELECT tmdb_id FROM manual_overrides').fetchone()[0]==603
            event=json.loads(db.execute('SELECT payload FROM portable_outbox').fetchone()[0])
            assert event['relative_path']=='Film.mkv' and event['tmdb_id']==603
        window.sync_shared_pairings.assert_called_once()
    finally:window.close();app.processEvents()


def test_settings_sync_button_exports_existing_manuals(media,app,tmp_path):
    import time
    root=tmp_path/'Library';root.mkdir();film=root/'Film.mkv';film.touch()
    media.config['movies_paths']=[str(root)];media.config['movies_path']=str(root)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(media.normalize_media_path(str(film)),603,'The Matrix'));db.commit()
    window=media.DSVideoWindow();window.start_library_scan=Mock()
    try:
        window.portable_sync_button.click()
        deadline=time.monotonic()+8
        while window._pairing_sync_running and time.monotonic()<deadline:
            app.processEvents();time.sleep(.01)
        assert not window._pairing_sync_running
        assert len(list((root/p.SUBDIR).glob('*.json')))==1
        assert window.portable_sync_button.isEnabled()
        window.start_library_scan.assert_called_once()
    finally:window.close();app.processEvents()


def test_nas_file_station_http_roundtrip(tmp_path):
    import threading
    import requests
    from email.parser import BytesParser
    from email.policy import default
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    from urllib.parse import urlsplit,parse_qs
    from synostream_nas import RemoteNASClient
    store={};uploads=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,data):
            payload=json.dumps(data).encode() if not isinstance(data,bytes) else data
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
        def do_GET(self):
            params={k:v[0] for k,v in parse_qs(urlsplit(self.path).query).items()}
            if params['api']=='SYNO.FileStation.Download':
                payload=store.get(params['path'])
                self.reply(payload if payload is not None else {'success':False,'error':{'code':407}});return
            folder=params.get('folder_path','')
            if folder=='/Movies':items=[dict(name='.synostream',isdir=True)] if store else []
            elif folder=='/Movies/.synostream':items=[dict(name='parositasok',isdir=True)]
            elif folder=='/Movies/'+p.SUBDIR:items=[dict(name=Path(path).name,isdir=False) for path in store]
            else:raise AssertionError(folder)
            self.reply({'success':True,'data':{'files':items,'total':len(items)}})
        def do_POST(self):
            raw=self.rfile.read(int(self.headers['Content-Length']))
            message=BytesParser(policy=default).parsebytes(('Content-Type: '+self.headers['Content-Type']+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+raw)
            fields={};file=None;order=[]
            for part in message.iter_parts():
                name=part.get_param('name',header='content-disposition');order.append(name)
                if name=='file':file=(part.get_filename(),part.get_payload(decode=True))
                else:fields[name]=part.get_payload(decode=True).decode()
            assert order[-1]=='file'
            assert fields['create_parents']=='true' and fields['version']=='2'
            assert fields['path']=='/Movies/'+p.SUBDIR
            store[fields['path']+'/'+file[0]]=file[1];uploads.append(file[0]);self.reply({'success':True})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    client=RemoteNASClient.__new__(RemoteNASClient);client.lock=threading.RLock();client.should_stop=lambda:False;client.session=requests.Session()
    client.base_url=f'http://127.0.0.1:{server.server_port}';client.sid='test-session';client.list_url=client.base_url+'/webapi/entry.cgi';client.list_version=2;client.download_url=client.list_url;client.download_version=2
    client.api_info={'SYNO.FileStation.Upload':dict(path='entry.cgi',minVersion=2,maxVersion=3)}
    root='syno:///Movies'
    try:
        with closing(database(tmp_path/'a.db')) as a,closing(database(tmp_path/'b.db')) as b:
            manual(a,root,root+'/Film.mkv')
            assert p.synchronize(a,root,p.NASBackend(root,client))['written']==1
            assert p.synchronize(b,root,p.NASBackend(root,client))['imported']==1
            assert b.execute('SELECT tmdb_id FROM manual_overrides').fetchone()[0]==603
            assert len(uploads)==len(store)==1
    finally:client.session.close();server.shutdown();server.server_close();thread.join()


def test_upload_renews_endpoint_and_closes_responses():
    import threading
    from synostream_nas import RemoteNASClient
    client=RemoteNASClient.__new__(RemoteNASClient);client.lock=threading.RLock();client.should_stop=lambda:False
    client.base_url='https://old.invalid';client.sid='old';client.api_info={'SYNO.FileStation.Upload':dict(path='old.cgi',maxVersion=2)}
    first,second=Mock(),Mock();first.json.return_value={'success':False,'error':{'code':106}};second.json.return_value={'success':True}
    client.session=Mock();client.session.post.side_effect=[first,second]
    def renew():
        client.base_url='https://new.invalid';client.sid='new';client.api_info={'SYNO.FileStation.Upload':dict(path='new.cgi',maxVersion=3)}
    client.connect=Mock(side_effect=renew)
    client.upload_pairing('/Movies/'+p.SUBDIR,'a'*32+'.json',b'{}')
    assert client.session.post.call_args_list[1].args[0]=='https://new.invalid/webapi/new.cgi'
    assert client.session.post.call_args_list[1].kwargs['data']['_sid']=='new'
    first.close.assert_called_once();second.close.assert_called_once()


def test_nested_root_legacy_export_chooses_deepest(tmp_path):
    root=tmp_path/'Library';nested=root/'Sub';nested.mkdir(parents=True);film=nested/'A.mkv';film.touch()
    with closing(database(tmp_path/'a.db')) as a:
        a.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(p.normalize_root(film),603,'The Matrix'));a.commit()
        assert p.synchronize(a,str(root),p.LocalBackend(root),all_roots=[str(root),str(nested)])['written']==0
        assert p.synchronize(a,str(nested),p.LocalBackend(nested),all_roots=[str(root),str(nested)])['written']==1
    assert not (root/p.SUBDIR).exists()


def test_corrupt_record_does_not_block_good_records(tmp_path):
    root=tmp_path/'Library';root.mkdir()
    with closing(database(tmp_path/'a.db')) as a:
        manual(a,root,root/'A.mkv');p.synchronize(a,str(root),p.LocalBackend(root))
    (root/p.SUBDIR/('b'*32+'.json')).write_text('{')
    with closing(database(tmp_path/'b.db')) as b:
        result=p.synchronize(b,str(root),p.LocalBackend(root))
        assert result['imported']==1 and result['invalid']==1


def test_remote_root_absolute_path():
    assert p.absolute_path('syno:///','Movie.mkv')=='syno:///Movie.mkv'
    assert p.relative_path('syno:///Movies','C:/Movies/A.mkv') is None


def test_two_real_processes_publish_without_lost_events(tmp_path):
    import os,sys,subprocess,time
    root=tmp_path/'Library';root.mkdir()
    (root/'A.mkv').touch();(root/'B.mkv').touch()
    code="""import sys,time,sqlite3
from pathlib import Path
import synostream_pairings as p
root=Path(sys.argv[1]);db=sqlite3.connect(sys.argv[2]);name=sys.argv[3]
db.execute('CREATE TABLE manual_overrides(file_path TEXT PRIMARY KEY,tmdb_id INTEGER,custom_title TEXT,is_movie INTEGER)')
db.execute('CREATE TABLE media_cache(file_path TEXT PRIMARY KEY,signature TEXT)');p.init_tables(db);db.commit()
with db:
 db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(p.normalize_root(root/(name+'.mkv')),603,name))
 p.enqueue(db,[str(root)],str(root/(name+'.mkv')),True,603,name)
Path(sys.argv[4]).touch()
while not Path(sys.argv[5]).exists():time.sleep(.01)
p.synchronize(db,str(root),p.LocalBackend(root));db.close()
"""
    children=[]
    try:
        for name in ('A','B'):
            children.append(subprocess.Popen([sys.executable,'-c',code,str(root),str(tmp_path/(name+'.db')),name,str(tmp_path/('ready-'+name)),str(tmp_path/'go')]))
        deadline=time.monotonic()+10
        while not all((tmp_path/('ready-'+n)).exists() for n in ('A','B')):
            assert time.monotonic()<deadline
            assert all(child.poll() is None for child in children)
            time.sleep(.01)
        (tmp_path/'go').touch()
        assert all(child.wait(timeout=10)==0 for child in children)
        assert len(list((root/p.SUBDIR).glob('*.json')))==2
        with closing(database(tmp_path/'c.db')) as c:
            assert p.synchronize(c,str(root),p.LocalBackend(root))['imported']==2
    finally:
        for child in children:
            if child.poll() is None:child.kill();child.wait()


def test_uncertain_upload_is_not_replayed_in_transport():
    import requests,threading
    from synostream_nas import RemoteNASClient
    client=RemoteNASClient.__new__(RemoteNASClient);client.lock=threading.RLock();client.should_stop=lambda:False
    client.base_url='https://example.invalid';client.sid='test';client.api_info={'SYNO.FileStation.Upload':dict(path='entry.cgi',maxVersion=2)}
    client.session=Mock();client.session.post.side_effect=requests.Timeout('uncertain')
    with pytest.raises(requests.Timeout):client.upload_pairing('/Movies/'+p.SUBDIR,'a'*32+'.json',b'{}')
    assert client.session.post.call_count==1


def test_interrupted_local_publish_keeps_outbox_for_retry(tmp_path,monkeypatch):
    root=tmp_path/'Library';root.mkdir()
    with closing(database(tmp_path/'a.db')) as a:
        manual(a,root,root/'A.mkv')
        with monkeypatch.context() as m:
            m.setattr(p.os,'rename',Mock(side_effect=OSError('interrupted publish')))
            assert p.synchronize(a,str(root),p.LocalBackend(root))['pending']==1
        assert not list((root/p.SUBDIR).glob('*.json'))
        assert not list((root/p.SUBDIR).glob('*.tmp'))
        assert p.synchronize(a,str(root),p.LocalBackend(root))['pending']==0


def test_redirected_metadata_folder_is_rejected(tmp_path,monkeypatch):
    root=tmp_path/'Library';root.mkdir();backend=p.LocalBackend(root)
    original=Path.is_junction
    monkeypatch.setattr(Path,'is_junction',lambda path: True if path==root/'.synostream' else original(path))
    with pytest.raises(OSError):backend.list_names()


def test_local_legacy_choice_not_silently_replaced_during_first_migration(tmp_path):
    root=tmp_path/'Library';root.mkdir();file=root/'A.mkv';file.touch()
    with closing(database(tmp_path/'a.db')) as a,closing(database(tmp_path/'b.db')) as b:
        manual(a,root,file,1,'Other PC');p.synchronize(a,str(root),p.LocalBackend(root))
        b.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(p.normalize_root(file),2,'Existing local choice'));b.commit()
        p.synchronize(b,str(root),p.LocalBackend(root));p.synchronize(a,str(root),p.LocalBackend(root))
        assert b.execute('SELECT tmdb_id FROM manual_overrides').fetchone()[0]==2
        assert a.execute('SELECT tmdb_id FROM manual_overrides').fetchone()[0]==2


def test_missing_shared_directory_can_be_restored_from_local_history(tmp_path):
    root=tmp_path/'Library';root.mkdir()
    with closing(database(tmp_path/'a.db')) as a:
        manual(a,root,root/'A.mkv')
        p.synchronize(a,str(root),p.LocalBackend(root))
        shared=root/p.SUBDIR
        for file in shared.glob('*.json'):file.unlink()
        assert p.synchronize(a,str(root),p.LocalBackend(root))['written']==1
    with closing(database(tmp_path/'b.db')) as b:
        assert p.synchronize(b,str(root),p.LocalBackend(root))['imported']==1


def test_series_scanner_uses_shared_match_and_ignores_metadata_folder(media,tmp_path,monkeypatch):
    root=tmp_path/'Shows';root.mkdir();series=root/'Opaque';series.mkdir();(series/'Show.S01E01.mkv').touch()
    with closing(database(tmp_path/'other.db')) as other:
        manual(other,root,series,1399,'Shared series',False);p.synchronize(other,str(root),p.LocalBackend(root))
    fetch=Mock(return_value=dict(status='success',id=1399,title='Shared series',overview='Description',poster_url='',date='2011',complete=True))
    monkeypatch.setattr(media,'fetch_tmdb_data',fetch)
    scanner=media.LibraryScannerThread([],[str(root)],library_key='shows');scanner.get_poster=Mock(return_value=None)
    items=[];scanner.item_ready.connect(lambda item,movie:items.append(item));scanner.run()
    assert not scanner.failed_libraries,scanner.errors
    assert len(items)==1 and items[0]['id']==1399
    fetch.assert_called_once_with(None,is_movie=False,tmdb_id=1399)


def test_custom_library_has_its_own_root(media,tmp_path):
    root=tmp_path/'Animation';root.mkdir();file=root/'Film.mkv';file.touch()
    media.config['custom_libraries']=[dict(id='animation',name='Animation',media_type='movies',paths=[str(root)])]
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        event=media.record_portable_edit(db,str(file),True,603,'Film');db.commit()
        assert event['relative_path']=='Film.mkv'
        assert db.execute('SELECT root FROM portable_outbox').fetchone()[0]==p.normalize_root(root)


def test_outside_library_remains_local_only(media,tmp_path):
    root=tmp_path/'Library';root.mkdir();file=tmp_path/'Outside.mkv';file.touch()
    media.config['movies_paths']=[str(root)]
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(p.normalize_root(file),603,'Local'))
        assert media.record_portable_edit(db,str(file),True,603,'Local') is None
        db.commit()
        assert db.execute('SELECT COUNT(*) FROM portable_outbox').fetchone()[0]==0
        assert db.execute('SELECT tmdb_id FROM manual_overrides').fetchone()[0]==603
    assert not (root/p.SUBDIR).exists()


def test_repeated_read_failure_is_bounded(tmp_path):
    root=tmp_path/'Library';root.mkdir()
    backend=Mock();backend.list_names.return_value=[f'{index:032x}.json' for index in range(50)]
    backend.read.side_effect=OSError('connection lost')
    with closing(database(tmp_path/'a.db')) as a:
        result=p.synchronize(a,str(root),backend)
    assert backend.read.call_count==3
    assert result['warnings'] and result['invalid']==3
