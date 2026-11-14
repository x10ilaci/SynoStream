from unittest.mock import Mock
from types import SimpleNamespace
from contextlib import closing
import sqlite3
import pytest

def test_offline_queue_uses_only_one_final_probe(media,tmp_path,monkeypatch):
    scanner=media.LibraryScannerThread([],[]);scanner.read_nfo_hint=Mock(return_value={})
    lookup=Mock(return_value=dict(status='error',message='offline'));monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        for i in range(8):
            file=tmp_path/f'Offline{i}.mkv';file.touch()
            scanner.process_media_item(SimpleNamespace(path=str(file),name=file.name,stat=file.stat),True,db)
        assert lookup.call_count==3
        scanner._tmdb_probe_at=0;scanner.retry_deferred_metadata(db)
        assert lookup.call_count==4 and len(scanner._deferred_metadata)==8

@pytest.mark.parametrize('cancelled,code',[(False,0),(True,1)])
def test_normal_player_close_and_cancellation_are_not_startup_errors(media,cancelled,code,monkeypatch):
    process=Mock();process.poll.return_value=code
    monitor=media.MpvPlaybackMonitor(process,r'\\.\pipe\unused-test',[])
    if cancelled:monkeypatch.setattr(monitor,'isInterruptionRequested',lambda:True)
    failures=[];monitor.startup_failed.connect(failures.append);monitor.run()
    assert failures==[]

def test_manual_search_can_recover_after_first_request_fails(media,monkeypatch):
    monkeypatch.setattr(media,'UI_LANGUAGE','hu')
    hit=dict(id=222,title='Film',original_title='Film')
    monkeypatch.setattr(media,'search_tmdb',Mock(side_effect=[media.TmdbError('temporary'),[hit]]))
    result=media.search_tmdb_multiple('Film')
    assert result['status']=='success' and result['results'][0]['id']==222 and result['partial']

def test_manual_search_reports_total_network_failure(media,monkeypatch):
    monkeypatch.setattr(media,'search_tmdb',Mock(side_effect=media.TmdbError('offline')))
    assert media.search_tmdb_multiple('Film')['status']=='error'

def test_full_scan_recovered_items_replace_placeholders_in_saved_snapshot(media,tmp_path,monkeypatch):
    import json
    for i in range(8):(tmp_path/f'Film{i}.mkv').touch()
    scanner=media.LibraryScannerThread([str(tmp_path)],[],library_key='movies')
    scanner.sync_portable_roots=Mock();scanner.read_nfo_hint=Mock(return_value={});scanner.get_poster=Mock(return_value=None)
    good=dict(status='success',id=222,title='Recovered',overview='',date='',poster_url='')
    lookup=Mock(side_effect=[dict(status='error',message='temporary')]*3+[good]*8)
    monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    scanner.run()
    assert not scanner._deferred_metadata and 'movies' not in scanner.metadata_failed_libraries
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        rows=db.execute("SELECT payload FROM library_card_cache WHERE library_id='movies'").fetchall()
    assert len(rows)==8 and all(json.loads(row[0])['id']==222 for row in rows)

def test_reproduce_recovered_network_is_never_probed_after_three_errors(media,tmp_path,monkeypatch):
    scanner=media.LibraryScannerThread([],[]);scanner.read_nfo_hint=Mock(return_value={});scanner.get_poster=Mock(return_value=None)
    good=dict(status='success',id=222,title='Recovered',overview='',date='',poster_url='')
    lookup=Mock(side_effect=[dict(status='error',message='temporary')]*3+[good]*5)
    monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    items=[]
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        for i in range(8):
            file=tmp_path/f'Film{i}.mkv';file.touch()
            items.append(scanner.process_media_item(SimpleNamespace(path=str(file),name=file.name,stat=file.stat),True,db))
    assert lookup.call_count==3
    scanner._tmdb_probe_at=0
    lookup.side_effect=None;lookup.return_value=good
    with closing(sqlite3.connect(media.DB_FILE)) as db:scanner.retry_deferred_metadata(db)
    assert not scanner._deferred_metadata and lookup.call_count==11

def test_reproduce_manual_search_discards_existing_results_after_later_error(media,monkeypatch):
    monkeypatch.setattr(media,'UI_LANGUAGE','hu')
    hit=dict(id=222,title='Film',original_title='Film',release_date='2001-01-01')
    search=Mock(side_effect=[[hit],media.TmdbError('temporary')]);monkeypatch.setattr(media,'search_tmdb',search)
    result=media.search_tmdb_multiple('Film',True)
    assert search.call_count==2 and result['status']=='success' and result['results'][0]['id']==222 and result['partial']

def test_reproduce_failed_player_exit_before_ipc_has_no_error_signal(media):
    process=Mock();process.poll.return_value=1
    monitor=media.MpvPlaybackMonitor(process,r'\\.\pipe\synostream-audit-no-player',[])
    failures=[];monitor.startup_failed.connect(failures.append)
    monitor.run()
    assert len(failures)==1 and process.poll.call_count>0
