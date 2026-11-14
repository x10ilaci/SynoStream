from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from contextlib import closing
import json
import sqlite3
import threading
import zipfile
import pytest
import synostream_storage as storage
from synostream_nas import RemoteNASClient


def test_repaired_movie_reloads_open_detail_and_ignores_old_worker(media,app,tmp_path,monkeypatch):
    path=str(tmp_path/'Film.mkv')
    window=media.DSVideoWindow();page=window.movies_page
    old=dict(file_path=path,title='Wrong movie',overview='Old plot',date='1965',id=111,is_movie=True,library_id='movies')
    page.add_item(old)
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(media.normalize_media_path(path),222,'Correct animation'))
    item=dict(file_path=path,title='Correct animation',overview='New plot',date='2016',id=222,_pairing_token=(222,'Correct animation',1))
    monkeypatch.setattr(media,'run_worker',Mock())
    old_metadata=dict(certification='18',certification_country='HU',certification_checked=True,runtime=180,cast=['Old Actor'])
    monkeypatch.setattr(media,'read_tmdb_metadata_cache',lambda key:(old_metadata,True) if key=='media:movie:111' else (None,False))
    seen=[]
    def inspect_actual_dialog(dialog):
        metadata=dialog.findChild(media.QLabel,'DetailMetadata')
        assert 'Old Actor' in metadata.text() and '180' in metadata.text()
        before=metadata.text()
        window.on_override_refresh_done(item,True,'',{'library_id':'movies','detail_dialog':dialog})
        assert dialog.findChild(media.QLabel,'DetailTitle').text()=='Correct animation'
        assert dialog.findChild(media.QLabel,'DetailOverview').text()=='New plot'
        assert metadata.text()!=before and 'Old Actor' not in metadata.text()
        workers=[call.args[0] for call in media.run_worker.call_args_list if isinstance(call.args[0],media.TmdbMediaMetadataWorker)]
        assert len(workers)==2
        workers[0].metadata_ready.emit(dict(status='success',**old_metadata))
        assert 'Old Actor' not in metadata.text()
        workers[1].metadata_ready.emit(dict(status='success',certification='6',certification_checked=True,runtime=101,cast=['New Actor']))
        assert 'New Actor' in metadata.text() and '101' in metadata.text() and 'Old Actor' not in metadata.text()
        assert old['id']==222 and old['title']=='Correct animation'
        assert page.cards[0][1].item['certification']=='6' 
        assert page.cards[0][1].item['id']==222
        seen.append(True);dialog.reject()
        return media.QDialog.DialogCode.Rejected
    monkeypatch.setattr(media.QDialog,'exec',inspect_actual_dialog)
    try:
        window.open_media_detail(old)
        assert seen==[True]
    finally:
        window.close();app.processEvents()


def test_truncated_nas_listing_preserves_cache(media):
    client=RemoteNASClient.__new__(RemoteNASClient);client.should_stop=lambda:False;client.list_version=2
    files=[dict(name=f'{i}.mkv',path=f'/Movies/{i}.mkv',isdir=False) for i in range(500)]
    client.api_get=Mock(side_effect=[dict(files=files,total=501),dict(files=[],total=501)])
    scanner=media.LibraryScannerThread([],[]);scanner.remote_client=client;scanner.current_scan_library_id='movies'
    with sqlite3.connect(media.DB_FILE) as db:
        db.executemany('INSERT INTO media_cache(file_path,is_movie,title) VALUES (?,1,?)',[(f'syno:///Movies/{i}.mkv',str(i)) for i in range(501)]);db.commit()
        scanner.scan_folder(db,'syno:///Movies',True)
        assert 'movies' in scanner.failed_libraries
        scanner.cleanup_stale_media_cache(db,[('movies','syno:///Movies',True)],False)
        assert db.execute('SELECT COUNT(*) FROM media_cache').fetchone()[0]==501
    assert scanner.errors


def test_simultaneous_first_start_adopts_published_data_directory(tmp_path,monkeypatch):
    appdir=tmp_path/'App';appdir.mkdir();(appdir/'config.json').write_text('{}')
    userdir=tmp_path/'UserLocal';monkeypatch.setenv('LOCALAPPDATA',str(userdir));monkeypatch.delenv('SYNOSTREAM_DATA_DIR',raising=False)
    target=userdir/'SynoStream'/'data'
    barrier=threading.Barrier(2);original=storage.os.replace
    def replace(source,destination):
        if Path(destination)==target:barrier.wait(timeout=10)
        return original(source,destination)
    monkeypatch.setattr(storage.os,'replace',replace)
    results=[];errors=[]
    def start():
        try:results.append(storage.data_directory(appdir))
        except BaseException as error:errors.append(error)
    threads=[threading.Thread(target=start) for _ in range(2)]
    for t in threads:t.start()
    for t in threads:t.join(15)
    assert not any(t.is_alive() for t in threads)
    assert len(results)==2 and not errors
    assert results[0]==results[1]
    assert (target/'config.json').read_text()=='{}'


def test_restore_rejects_missing_media_path_before_replacing_live_data(media,tmp_path):
    assert media.save_config()[0]
    original=tmp_path/'original.zip';media.create_backup_archive(str(original))
    broken=tmp_path/'bad-schema.db'
    with zipfile.ZipFile(original) as archive:broken.write_bytes(archive.read('media_library.db'))
    with sqlite3.connect(broken) as db:
        db.execute('DROP TABLE media_cache');db.execute('CREATE TABLE media_cache(unrelated TEXT)')
        db.execute('DROP TABLE manual_overrides');db.execute('CREATE TABLE manual_overrides(unrelated TEXT)')
        db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    archive_path=tmp_path/'bad-schema.zip'
    with zipfile.ZipFile(original) as src,zipfile.ZipFile(archive_path,'w') as dst:
        for name in src.namelist():dst.writestr(name,broken.read_bytes() if name=='media_library.db' else src.read(name))
    with closing(sqlite3.connect(media.DB_FILE)) as db:before=list(db.iterdump())
    with pytest.raises(ValueError):media.restore_backup_archive(str(archive_path))
    with sqlite3.connect(media.DB_FILE) as db:
        assert list(db.iterdump())==before
        for table in ('manual_overrides','media_cache'):
            assert 'file_path' in {row[1] for row in db.execute(f'PRAGMA table_info({table})')}


@pytest.mark.parametrize('total,batches',[(0,[[]]),(1,[[dict(name='a')]]),(2,[[dict(name='a')],[dict(name='b')]])])
def test_complete_nas_pages_are_accepted(total,batches):
    client=RemoteNASClient.__new__(RemoteNASClient);client.should_stop=lambda:False;client.list_version=2
    client.api_get=Mock(side_effect=[dict(files=batch,total=total) for batch in batches])
    assert len(client.list_folder('/Movies'))==total


def test_truncated_download_station_list_is_rejected():
    from synostream_downloads import DownloadStationClient,DownloadStationError
    client=DownloadStationClient.__new__(DownloadStationClient)
    client._task_request=Mock(side_effect=[dict(tasks=[dict(id='a')],total=2),dict(tasks=[],total=2)])
    with pytest.raises(DownloadStationError,match='hiányos'):client.list_tasks()


def test_first_start_does_not_hide_real_publication_failure(tmp_path,monkeypatch):
    appdir=tmp_path/'App';appdir.mkdir()
    monkeypatch.delenv('SYNOSTREAM_DATA_DIR',raising=False);monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'User'))
    monkeypatch.setattr(storage.os,'replace',Mock(side_effect=PermissionError('denied')))
    with pytest.raises(PermissionError):storage.data_directory(appdir)


@pytest.mark.parametrize('table',['media_cache','manual_overrides','playback_state','library_card_cache','portable_outbox'])
def test_backup_rejects_missing_primary_key(media,table):
    with sqlite3.connect(':memory:') as db:
        media.initialize_database_connection(db)
        columns=db.execute(f'PRAGMA table_info({table})').fetchall()
        db.execute(f'DROP TABLE {table}')
        defs=','.join('"'+row[1]+'" '+(row[2] or 'TEXT') for row in columns)
        db.execute(f'CREATE TABLE {table}({defs})');db.commit()
        with pytest.raises(ValueError):media.validate_backup_database(db)


def test_legacy_backup_can_upgrade_on_staging_connection(media):
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE manual_overrides(file_path TEXT PRIMARY KEY,tmdb_id INTEGER)')
        db.execute('CREATE TABLE media_cache(file_path TEXT PRIMARY KEY,tmdb_id INTEGER)')
        media.initialize_database_connection(db)
        db.execute("INSERT INTO manual_overrides(file_path,tmdb_id) VALUES ('legacy',222)");db.commit()
        media.validate_backup_database(db)
        assert db.execute("SELECT tmdb_id FROM manual_overrides WHERE file_path='legacy'").fetchone()==(222,)


def test_two_first_start_processes_reach_normal_instance_handling(media,tmp_path):
    import os,subprocess,sys,time
    appdir=tmp_path/'LegacyApp';appdir.mkdir();(appdir/'config.json').write_text('{}')
    gates=tmp_path/'gates';gates.mkdir()
    code='''import os,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import synostream_storage as storage
app=Path(sys.argv[2]);gates=Path(sys.argv[3]);identifier=sys.argv[4]
target=Path(os.environ['LOCALAPPDATA'])/'SynoStream'/'data'
original=storage.os.replace
def publish(source,destination):
 if Path(destination)==target:
  (gates/identifier).touch()
  deadline=time.monotonic()+10
  while not all((gates/key).exists() for key in ('a','b')):
   if time.monotonic()>deadline:raise TimeoutError('publication barrier')
   time.sleep(.01)
 return original(source,destination)
storage.os.replace=publish
data=storage.data_directory(app)
try:
 with storage.acquire_application_lock(data):
  (gates/'owner').touch()
  deadline=time.monotonic()+15
  while not (gates/'release').exists():
   if time.monotonic()>deadline:raise TimeoutError('owner release')
   time.sleep(.01)
except storage.DataDirectoryInUse:sys.exit(2)
'''
    env=os.environ.copy();env.pop('SYNOSTREAM_DATA_DIR',None);env['LOCALAPPDATA']=str(tmp_path/'UserLocal')
    processes=[subprocess.Popen([sys.executable,'-c',code,str(Path(media.__file__).parent),str(appdir),str(gates),key],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for key in ('a','b')]
    try:
        deadline=time.monotonic()+15
        while not any(p.poll() is not None for p in processes) and time.monotonic()<deadline:time.sleep(.02)
        assert (gates/'owner').exists()
        assert any(p.poll()==2 for p in processes)
    finally:
        (gates/'release').touch()
        outputs=[p.communicate(timeout=20) for p in processes]
    assert sorted(p.returncode for p in processes)==[0,2],outputs
    assert (tmp_path/'UserLocal/SynoStream/data/config.json').read_text()=='{}'
