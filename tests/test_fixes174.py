import sqlite3
import threading
from types import SimpleNamespace
from unittest.mock import Mock
import sys
from pathlib import Path
import synostream_pairings as p
from test_portable_pairings import database, manual


def test_late_scanner_preserves_new_manual_match(media,tmp_path,monkeypatch):
    film=tmp_path/'Film.mkv';film.touch();path=media.normalize_media_path(str(film))
    scanner=media.LibraryScannerThread([],[]);scanner.get_poster=Mock(return_value=None)
    scanner.read_nfo_hint=Mock(return_value={})
    entered=threading.Event();release=threading.Event();result=[];errors=[]
    def fetch(*a,**kw):
        if kw.get('tmdb_id')==222:
            return dict(status='success',id=222,title='Correct manual match',overview='Correct',poster_url='',date='2016')
        entered.set()
        assert release.wait(10)
        return dict(status='success',id=111,title='Old automatic match',overview='Old',poster_url='',date='2016')
    monkeypatch.setattr(media,'fetch_tmdb_data',fetch)
    def scan():
        try:
            with sqlite3.connect(media.DB_FILE) as db:
                result.append(scanner.process_media_item(SimpleNamespace(path=str(film),name=film.name,stat=film.stat),True,db))
        except BaseException as e:errors.append(e)
    thread=threading.Thread(target=scan);thread.start();assert entered.wait(10)
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(path,222,'Correct manual match'))
        scanner.save_cache(db,path,1,222,'Correct manual match','Correct','','2016',film.stat().st_mtime,'success','override:222:hu-HU')
    release.set();thread.join(10)
    assert not thread.is_alive() and not errors
    with sqlite3.connect(media.DB_FILE) as db:
        assert db.execute('SELECT tmdb_id FROM manual_overrides WHERE file_path=?',(path,)).fetchone()==(222,)
        assert db.execute('SELECT tmdb_id FROM media_cache WHERE file_path=?',(path,)).fetchone()==(222,)
    assert result[0]['id']==222
    page=media.MediaPage('Race test')
    page.add_item(dict(file_path=str(film),title='Correct manual match',overview='',date='2016',id=222,is_movie=True))
    window=SimpleNamespace(is_closing=False,library_pages={},movies_page=page,shows_page=None,scan_seen_paths={'movies':set()})
    media.DSVideoWindow._apply_scan_item(window,result[0],True)
    assert page.cards[0][1].item['id']==222
    assert media.normalize_media_path(str(film)) in window.scan_seen_paths['movies']
    page.close();page.deleteLater()


def test_all_published_events_remain_readable(tmp_path):
    root=tmp_path/'Library';root.mkdir()
    with database(tmp_path/'a.db') as db:
        for i in range(3):manual(db,root,root/f'{i}.mkv',i+1,str(i))
        assert p.synchronize(db,str(root),p.LocalBackend(root))['written']==3
        assert not p.synchronize(db,str(root),p.LocalBackend(root))['warnings']
    with database(tmp_path/'b.db') as db:
        assert p.synchronize(db,str(root),p.LocalBackend(root))['imported']==3


def test_rematched_card_discards_old_certification(media,app,monkeypatch,tmp_path):
    page=media.MediaPage('Test')
    path=str(tmp_path/'Film.mkv')
    old=dict(file_path=path,title='Old',overview='',date='',id=111,is_movie=True,
             certification='18',certification_order=18,certification_checked=True,original_language='en')
    page.add_item(old)
    updated=page.add_item(dict(file_path=path,title='New family film',overview='',date='',id=222,is_movie=True))
    assert updated['id']==222
    assert not {'certification','certification_checked','original_language'} & updated.keys()
    worker=Mock();monkeypatch.setattr(media,'TmdbCertificationSortWorker',worker)
    monkeypatch.setattr(media,'run_worker',Mock())
    page.sort_criterion.blockSignals(True)
    page.sort_criterion.setCurrentIndex(page.sort_criterion.findData('certification'))
    page.sort_criterion.blockSignals(False)
    page.request_certification_data()
    worker.assert_called_once_with([(222,True)])
    page.close();page.deleteLater()


def test_scan_cleanup_preserves_manual_refresh_poster(media,app,tmp_path,monkeypatch):
    film=tmp_path/'Film.mkv';film.touch()
    monkeypatch.setattr(media,'fetch_tmdb_data',Mock(return_value=dict(status='success',id=333,title='Film',overview='',date='2016',poster_url='https://invalid.test/poster.jpg')))
    downloaded=threading.Event();cleaned=threading.Event();result=[];errors=[]
    poster=Path(media.CACHE_DIR)/'movie_333.jpg'
    def get_poster(*a):
        poster.write_bytes(b'poster')
        downloaded.set();assert cleaned.wait(10)
        return str(poster)
    monkeypatch.setattr(media,'download_and_cache_poster',get_poster)
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(media.normalize_media_path(str(film)),333,'Film'))
    worker=media.ManualOverrideRefreshWorker(str(film),True,333)
    worker.refresh_done.connect(lambda item,movie,error:result.append((item,error)),media.Qt.ConnectionType.DirectConnection)
    def scan():
        try:
            worker.run()
        except BaseException as e:errors.append(e)
    thread=threading.Thread(target=scan);thread.start();assert downloaded.wait(10)
    with sqlite3.connect(media.DB_FILE) as db:
        assert media.cleanup_orphaned_poster_files(db)==[]
    cleaned.set();thread.join(10)
    assert not thread.is_alive() and not errors
    assert result[0][1]=='' and result[0][0]['poster']==str(poster) and poster.exists()
    with sqlite3.connect(media.DB_FILE) as db:
        assert db.execute('SELECT tmdb_id,poster_url FROM media_cache').fetchone()==(333,'https://invalid.test/poster.jpg')


def test_nas_lists_more_than_former_event_limit():
    names=[f'{i:032x}.json' for i in range(20001)]
    client=Mock()
    client.list_folder.side_effect=[
        [dict(name='.synostream',isdir=True)],
        [dict(name='parositasok',isdir=True)],
        [dict(name=name,isdir=False,additional=dict(time=dict(mtime=1),size=100)) for name in names],
    ]
    backend=p.NASBackend('syno:///Movies',client)
    assert backend.list_names()==names
    assert len(backend.fingerprints)==20001


def test_local_lists_more_than_former_event_limit(tmp_path,monkeypatch):
    root=tmp_path/'Library';directory=root/p.SUBDIR;directory.mkdir(parents=True)
    names=[f'{i:032x}.json' for i in range(20001)]
    entries=[SimpleNamespace(name=name,is_file=lambda **kw:True,stat=lambda **kw:SimpleNamespace(st_mtime_ns=1,st_size=100)) for name in names]
    listing=Mock();listing.__enter__=Mock(return_value=iter(entries));listing.__exit__=Mock(return_value=False)
    monkeypatch.setattr(p.os,'scandir',Mock(return_value=listing))
    backend=p.LocalBackend(root)
    assert backend.list_names()==names and len(backend.fingerprints)==20001


def test_queued_old_scanner_item_cannot_replace_new_pairing(media,tmp_path):
    path=str(tmp_path/'Film.mkv')
    page=media.MediaPage('Queued race')
    page.add_item(dict(file_path=path,title='Correct',overview='',id=222,is_movie=True))
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(media.normalize_media_path(path),222,'Correct'))
    window=SimpleNamespace(is_closing=False,library_pages={},movies_page=page,shows_page=None,scan_seen_paths={})
    stale=dict(file_path=path,title='Old',overview='',id=111,_pairing_token=None)
    media.DSVideoWindow._apply_scan_item(window,stale,True)
    assert page.cards[0][1].item['id']==222
    page.close();page.deleteLater()


def test_same_media_keeps_verified_certification(media,tmp_path):
    page=media.MediaPage('Stable')
    path=str(tmp_path/'Film.mkv')
    page.add_item(dict(file_path=path,title='Film',overview='',id=222,is_movie=True,certification='12',certification_checked=True))
    updated=page.add_item(dict(file_path=path,title='Magyar cím',overview='',id=222,is_movie=True))
    assert updated['certification']=='12' and updated['certification_checked'] is True
    page.close();page.deleteLater()


def test_guarded_cache_save_rejects_superseded_pairing(media,tmp_path):
    path=media.normalize_media_path(str(tmp_path/'Film.mkv'))
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(path,222,'Correct'));db.commit()
        assert media.LibraryScannerThread.save_cache(db,path,1,111,'Old','','','',0,'success','language:hu-HU',pairing_token=None) is False
        assert db.execute('SELECT COUNT(*) FROM media_cache').fetchone()[0]==0


def test_finished_manual_request_cannot_replace_later_pairing(media,tmp_path):
    path=str(tmp_path/'Film.mkv')
    page=media.MediaPage('Manual queue');page.add_item(dict(file_path=path,title='Correct',overview='',id=222,is_movie=True))
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(media.normalize_media_path(path),222,'Correct'))
    window=SimpleNamespace(is_closing=False,library_pages={},movies_page=page,shows_page=None)
    stale=dict(file_path=path,title='Old',overview='',id=111,_pairing_token=(111,'Old',1))
    media.DSVideoWindow.on_override_refresh_done(window,stale,True,'',{})
    assert page.cards[0][1].item['id']==222
    page.close();page.deleteLater()


def test_superseded_manual_worker_does_not_start_network_request(media,tmp_path,monkeypatch):
    film=tmp_path/'Film.mkv';film.touch()
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(media.normalize_media_path(str(film)),222,'Correct'))
    request=Mock();monkeypatch.setattr(media,'fetch_tmdb_data',request)
    media.ManualOverrideRefreshWorker(str(film),True,111).run()
    request.assert_not_called()
    assert media.POSTER_CACHE_WRITERS==0


def test_changed_media_retains_explicit_new_metadata(media,tmp_path):
    page=media.MediaPage('New metadata');path=str(tmp_path/'Film.mkv')
    page.add_item(dict(file_path=path,title='Old',overview='',id=111,is_movie=True,certification='18',certification_checked=True))
    updated=page.add_item(dict(file_path=path,title='New',overview='',id=222,is_movie=True,certification='6',certification_checked=True))
    assert updated['certification']=='6' and updated['certification_checked'] is True
    page.close();page.deleteLater()


def test_completed_manual_card_survives_older_scan_snapshot(media,tmp_path):
    path=str(tmp_path/'Film.mkv');normalized=media.normalize_media_path(path)
    page=media.MediaPage('Snapshot');page.add_item(dict(file_path=path,title='Old',overview='',id=111,is_movie=True))
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(normalized,222,'Correct'))
    window=SimpleNamespace(is_closing=False,library_pages={'movies':page},movies_page=page,shows_page=None)
    correct=dict(file_path=path,title='Correct',overview='',id=222,_pairing_token=(222,'Correct',1))
    media.DSVideoWindow.on_override_refresh_done(window,correct,True,'',{'library_id':'movies'})
    scanner=media.LibraryScannerThread([],[])
    scanner.emitted_card_items={'movies':[dict(file_path=path,title='Old',id=111,_pairing_token=None)]}
    scanner.persist_card_cache([('movies',[str(tmp_path)],True)])
    import json
    with sqlite3.connect(media.DB_FILE) as db:
        payload=json.loads(db.execute('SELECT payload FROM library_card_cache WHERE library_id=? AND file_path=?',('movies',normalized)).fetchone()[0])
    assert payload['id']==222 and payload['title']=='Correct'
    page.close();page.deleteLater()


def test_null_legacy_custom_title_uses_consistent_token(media,tmp_path):
    path=media.normalize_media_path(str(tmp_path/'Film.mkv'))
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,NULL,1)',(path,222))
        assert media.read_pairing_token(db,path)==(222,'',1)
        assert media.pairing_item_is_current(db,dict(file_path=path,_pairing_token=[222,'',1]))
