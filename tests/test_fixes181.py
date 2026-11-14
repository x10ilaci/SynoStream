import sqlite3
from contextlib import closing
from unittest.mock import Mock
from types import SimpleNamespace
import pytest
from synostream_nas import RemoteNASClient
from synostream_downloads import DownloadStationClient,DownloadStationError
from synostream_performance import PosterPixmapCache

def test_unreadable_image_outside_managed_cache_is_not_deleted(app,tmp_path):
    file=tmp_path/'important.mkv';file.write_bytes(b'not an image')
    assert PosterPixmapCache().load(str(file),100,100) is None
    assert file.read_bytes()==b'not an image'

@pytest.mark.parametrize('inside',[False,True])
def test_only_owned_poster_files_in_managed_directory_can_be_removed(app,tmp_path,inside):
    cache=tmp_path/'cache';cache.mkdir()
    file=(cache/'personal.jpg') if inside else (tmp_path/'movie_123.jpg')
    file.write_bytes(b'not an image')
    assert PosterPixmapCache(managed_directory=cache).load(str(file),100,100) is None
    assert file.read_bytes()==b'not an image'

def test_incomplete_nested_scope_must_keep_cached_descendants(media,tmp_path):
    root=tmp_path/'Library';nested=root/'Offline';nested.mkdir(parents=True)
    path=media.normalize_media_path(str(nested/'Film.mkv'))
    scanner=media.LibraryScannerThread([],[]);scanner.failed_libraries.add('nested')
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO media_cache(file_path,is_movie) VALUES (?,1)',(path,));db.commit()
        scanner.cleanup_stale_media_cache(db,[('parent',str(root),True),('nested',str(nested),True)],False)
        assert db.execute('SELECT COUNT(*) FROM media_cache').fetchone()[0]==1

def test_repeated_nas_page_is_not_complete_listing():
    client=RemoteNASClient.__new__(RemoteNASClient);client.should_stop=lambda:False;client.list_version=2
    page=[dict(name='a.mkv',path='/Movies/a.mkv')]
    client.api_get=Mock(side_effect=[dict(files=page,total=2),dict(files=page,total=2)])
    with pytest.raises(RuntimeError):client.list_folder('/Movies')

def test_repeated_download_page_is_rejected():
    client=DownloadStationClient.__new__(DownloadStationClient)
    client._task_request=Mock(side_effect=[dict(tasks=[dict(id='same')],total=2)]*2)
    with pytest.raises(DownloadStationError):client.list_tasks()

def test_negative_lookup_is_retried_after_one_day(media,tmp_path,monkeypatch):
    film=tmp_path/'Unknown.mkv';film.touch();path=media.normalize_media_path(str(film))
    entry=SimpleNamespace(path=str(film),name=film.name,stat=film.stat)
    scanner=media.LibraryScannerThread([],[]);scanner.get_poster=Mock(return_value=None)
    lookup=Mock(return_value=dict(status='no_result'));monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        scanner.process_media_item(entry,True,db)
        before=lookup.call_count
        scanner.process_media_item(entry,True,db)
        assert lookup.call_count==before
        now=media.time.time();monkeypatch.setattr(media.time,'time',lambda:now+90000)
        scanner.process_media_item(entry,True,db)
        assert lookup.call_count>before

def test_backup_rejects_integer_primary_key_for_media_path(media):
    with closing(sqlite3.connect(':memory:')) as db:
        media.initialize_database_connection(db)
        cols=db.execute('PRAGMA table_info(media_cache)').fetchall()
        db.execute('DROP TABLE media_cache')
        definitions=','.join('file_path INTEGER PRIMARY KEY' if row[1]=='file_path' else '"'+row[1]+'" '+row[2] for row in cols)
        db.execute('CREATE TABLE media_cache('+definitions+')');db.commit()
        with pytest.raises(ValueError):media.validate_backup_database(db)

def test_manual_refresh_retries_fresh_negative_cache(media,tmp_path,monkeypatch):
    file=tmp_path/'Retry.mkv';file.touch();entry=SimpleNamespace(path=str(file),name=file.name,stat=file.stat)
    lookup=Mock(return_value=dict(status='no_result'));monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        media.LibraryScannerThread([],[]).process_media_item(entry,True,db)
        before=lookup.call_count
        media.LibraryScannerThread([],[],force_remote_refresh=True).process_media_item(entry,True,db)
        assert lookup.call_count>before

def test_backup_accepts_equivalent_text_key_type(media):
    with closing(sqlite3.connect(':memory:')) as db:
        media.initialize_database_connection(db)
        cols=db.execute('PRAGMA table_info(media_cache)').fetchall();db.execute('DROP TABLE media_cache')
        definitions=','.join('file_path VARCHAR(2048) PRIMARY KEY' if row[1]=='file_path' else '"'+row[1]+'" '+row[2] for row in cols)
        db.execute('CREATE TABLE media_cache('+definitions+')');db.commit()
        media.validate_backup_database(db)
