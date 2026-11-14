from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import hashlib
import json
import os
import sqlite3
import pytest
import synostream_pairings as p
from test_portable_pairings import database,manual


def localized(identifier=603,movie=True):
    return {'id':identifier,'title':'Magyar filmcím','original_title':'Original Movie','release_date':'2016-01-01','overview':'Magyar leírás.'} if movie else {'id':identifier,'name':'Magyar sorozatcím','original_name':'Original Show','first_air_date':'2016-01-01','overview':'Magyar leírás.'}


@pytest.mark.parametrize('movie',[True,False],ids=['film','series'])
def test_english_search_result_is_displayed_from_hungarian_details(media,monkeypatch,movie):
    monkeypatch.setattr(media,'UI_LANGUAGE','hu')
    english={'id':603,'title':'Original Movie','original_title':'Original Movie','name':'Original Show','original_name':'Original Show','release_date':'2016-01-01','first_air_date':'2016-01-01','overview':'English synopsis'}
    query='Original Movie' if movie else 'Original Show'
    search=Mock(side_effect=lambda *a,**kw:[] if kw.get('language')=='hu-HU' else [english])
    monkeypatch.setattr(media,'search_tmdb',search)
    request=Mock(return_value=localized(movie=movie));monkeypatch.setattr(media,'tmdb_request',request)
    result=media.fetch_tmdb_data(query,'2016',movie)
    assert result['status']=='success' and result['title']==('Magyar filmcím' if movie else 'Magyar sorozatcím')
    assert result['overview']=='Magyar leírás.'
    request.assert_called_once_with(('movie' if movie else 'tv')+'/603',{'language':'hu-HU'})


@pytest.mark.parametrize('mode',['automatic','manual','nfo'])
def test_old_english_cache_is_corrected_without_rematching(media,tmp_path,monkeypatch,mode):
    monkeypatch.setattr(media,'UI_LANGUAGE','hu')
    film=tmp_path/'opaque.mkv';film.touch();path=media.normalize_media_path(str(film))
    scanner=media.LibraryScannerThread([],[]);scanner.get_poster=Mock(return_value=None)
    signature='language:match_v185:hu-HU'
    if mode=='manual':signature='override:603:hu-HU'
    if mode=='nfo':
        nfo={'tmdb_id':603};scanner.read_nfo_hint=Mock(return_value=nfo)
        signature='nfo:'+hashlib.sha256(json.dumps(nfo,sort_keys=True,ensure_ascii=False).encode()).hexdigest()+':hu-HU'
    request=Mock(return_value=localized());monkeypatch.setattr(media,'tmdb_request',request)
    monkeypatch.setattr(media,'search_tmdb',Mock(side_effect=AssertionError('must preserve known TMDB ID')))
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        if mode=='manual':db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(path,603,'Original Movie'));db.commit()
        scanner.save_cache(db,path,1,603,'Original Movie','English synopsis','','2016-01-01',film.stat().st_mtime,'success',signature)
        entry=SimpleNamespace(path=str(film),name=film.name,stat=film.stat)
        assert scanner.process_media_item(entry,True,db)['title']=='Magyar filmcím'
        assert db.execute('SELECT title,overview,tmdb_id FROM media_cache').fetchone()==('Magyar filmcím','Magyar leírás.',603)
        assert scanner.process_media_item(entry,True,db)['title']=='Magyar filmcím'
    request.assert_called_once_with('movie/603',{'language':'hu-HU'})


def test_english_overview_fallback_never_replaces_hungarian_title(media,monkeypatch):
    monkeypatch.setattr(media,'UI_LANGUAGE','hu')
    hu=localized();hu['overview']=''
    request=Mock(side_effect=[hu,dict(id=603,title='Original Movie',overview='English synopsis')])
    monkeypatch.setattr(media,'tmdb_request',request)
    result=media.fetch_tmdb_data(None,tmdb_id=603)
    assert result['title']=='Magyar filmcím' and result['overview']=='English synopsis'
    assert request.call_args.kwargs=={} and request.call_args.args[1]['language']=='en-US'


def test_missing_hungarian_translation_keeps_available_title(media,monkeypatch):
    monkeypatch.setattr(media,'UI_LANGUAGE','hu')
    response=localized();response['title']='Original Movie';response['overview']=''
    monkeypatch.setattr(media,'tmdb_request',Mock(return_value=response))
    assert media.fetch_tmdb_data(None,tmdb_id=603)['title']=='Original Movie'


def test_cached_localization_network_failure_keeps_old_data_and_retries(media,tmp_path,monkeypatch):
    monkeypatch.setattr(media,'UI_LANGUAGE','hu')
    request=Mock(side_effect=media.TmdbError('offline'));monkeypatch.setattr(media,'tmdb_request',request)
    scanner=media.LibraryScannerThread([],[])
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        result=scanner.localized_cached_info(db,'C:/movie.mkv',603,True,'Original Movie','Old text','','2016')
        assert result['title']=='Original Movie'
        assert media.read_tmdb_metadata_cache(media.display_info_cache_key(603,True))[0] is None
        request.side_effect=None;request.return_value=localized()
        fresh=media.LibraryScannerThread([],[])
        assert fresh.localized_cached_info(db,'C:/movie.mkv',603,True,'Original Movie','Old text','','2016')['title']=='Magyar filmcím'


def test_localization_failures_are_bounded_per_scan(media,monkeypatch):
    monkeypatch.setattr(media,'tmdb_request',Mock(side_effect=media.TmdbError('offline')))
    scanner=media.LibraryScannerThread([],[])
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        for identifier in range(1,20):scanner.localized_cached_info(db,'C:/movie.mkv',identifier,True,'Old','Text','','2016')
    assert media.tmdb_request.call_count==3


def test_incremental_cached_row_is_emitted_with_hungarian_title(media,monkeypatch):
    monkeypatch.setattr(media,'UI_LANGUAGE','hu');monkeypatch.setattr(media,'tmdb_request',Mock(return_value=localized()))
    scanner=media.LibraryScannerThread([],[]);scanner.get_poster=Mock(return_value=None)
    items=[];scanner.item_ready.connect(lambda item,movie:items.append(item))
    scanner.emit_cached_media_row(dict(file_path='syno:///Movies/opaque.mkv',title='Original Movie',overview='English',tmdb_id=603,poster_url='',release_date='2016',file_mtime=1),True)
    assert items[0]['title']=='Magyar filmcím' and items[0]['id']==603


def test_junction_media_exports_logical_path_without_blocking_other_pairs(tmp_path):
    import _winapi
    root=tmp_path/'Library';target=tmp_path/'Elsewhere';root.mkdir();target.mkdir();link=root/'Linked'
    _winapi.CreateJunction(str(target),str(link));(target/'Film.mkv').touch();(root/'Good.mkv').touch()
    assert link.is_junction() and p.relative_path(str(root),str(link/'Film.mkv'))=='Linked/Film.mkv'
    with closing(database(tmp_path/'a.db')) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(p.normalize_root(link/'Film.mkv'),603,'Linked'))
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(p.normalize_root(root/'Good.mkv'),604,'Good'));db.commit()
        result=p.synchronize(db,str(root),p.LocalBackend(root))
        assert result['written']==2 and not result['warnings']
    assert set(target.iterdir())=={target/'Film.mkv'}
    events=[p.decode_event(path.read_bytes(),path.name) for path in (root/p.SUBDIR).glob('*.json')]
    assert {e['relative_path'] for e in events}=={'Linked/Film.mkv','Good.mkv'}


def test_one_invalid_legacy_pair_does_not_abort_other_exports(tmp_path):
    root=tmp_path/'Library';root.mkdir()
    with closing(database(tmp_path/'a.db')) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(p.normalize_root(root/'Bad.mkv'),603,'x'*1001))
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,1)',(p.normalize_root(root/'Good.mkv'),604,'Good'));db.commit()
        result=p.synchronize(db,str(root),p.LocalBackend(root))
        assert result['written']==1 and result['invalid']==1
        assert db.execute('SELECT COUNT(*) FROM manual_overrides').fetchone()[0]==2


def test_mixed_movie_library_series_manual_save_is_queued(media,app,tmp_path,monkeypatch):
    root=tmp_path/'Library';root.mkdir();series=root/'Numbered Show';series.mkdir()
    media.config.update(movies_paths=[str(root)],movies_path=str(root),shows_paths=[],shows_path='',custom_libraries=[])
    window=media.DSVideoWindow();window.start_library_scan=Mock();window.sync_shared_pairings=Mock()
    choice=Mock();choice.exec.return_value=media.QDialog.DialogCode.Accepted;choice.selected_result.return_value=dict(id=1399,title='Series')
    monkeypatch.setattr(media,'TmdbChoiceDialog',Mock(return_value=choice));monkeypatch.setattr(media.QMessageBox,'information',Mock());monkeypatch.setattr(media,'run_worker',Mock())
    window.pending_override=dict(fpath=media.normalize_media_path(str(series)),fpath_raw=str(series),is_movie=False,library_id='movies')
    try:
        window.on_override_search_done(dict(status='success',results=[dict(id=1399,title='Series')]))
        with closing(sqlite3.connect(media.DB_FILE)) as db:
            event=json.loads(db.execute('SELECT payload FROM portable_outbox').fetchone()[0])
            assert event['media_type']=='tv' and event['relative_path']=='Numbered Show'
        window.sync_shared_pairings.assert_called_once()
    finally:window.close();app.processEvents()


def test_corrupt_known_record_is_repaired_and_received_by_second_pc(tmp_path):
    root=tmp_path/'Library';root.mkdir();(root/'Film.mkv').touch()
    with closing(database(tmp_path/'a.db')) as a,closing(database(tmp_path/'b.db')) as b:
        event=manual(a,root,root/'Film.mkv');p.synchronize(a,str(root),p.LocalBackend(root))
        p.synchronize(a,str(root),p.LocalBackend(root)) # record the healthy fingerprint
        file=root/p.SUBDIR/(event['event_id']+'.json');file.write_bytes(b'{')
        result=p.synchronize(a,str(root),p.LocalBackend(root))
        assert result['invalid']==result['repaired']==1 and not result['pending'] and not result['warnings']
        assert p.decode_event(file.read_bytes(),file.name)==event
        assert list((root/p.SUBDIR).glob('.corrupt-*.bak'))
        assert p.synchronize(b,str(root),p.LocalBackend(root))['imported']==1


def test_explicit_verification_detects_same_size_same_stamp_corruption(tmp_path):
    root=tmp_path/'Library';root.mkdir()
    with closing(database(tmp_path/'a.db')) as a:
        event=manual(a,root,root/'Film.mkv');p.synchronize(a,str(root),p.LocalBackend(root));p.synchronize(a,str(root),p.LocalBackend(root))
        file=root/p.SUBDIR/(event['event_id']+'.json');info=file.stat();size=info.st_size
        file.write_bytes(b' '*(size-1)+b'{');os.utime(file,ns=(info.st_atime_ns,info.st_mtime_ns))
        assert p.synchronize(a,str(root),p.LocalBackend(root),verify=True)['repaired']==1


def test_valid_changed_event_is_reported_not_silently_overwritten(tmp_path):
    root=tmp_path/'Library';root.mkdir()
    with closing(database(tmp_path/'a.db')) as a:
        event=manual(a,root,root/'Film.mkv');p.synchronize(a,str(root),p.LocalBackend(root))
        file=root/p.SUBDIR/(event['event_id']+'.json');changed=dict(event,tmdb_id=604);file.write_bytes(p.encode_event(changed))
        result=p.synchronize(a,str(root),p.LocalBackend(root),verify=True)
        assert result['invalid']==1 and result['warnings'] and result['repaired']==0
        assert p.decode_event(file.read_bytes(),file.name)['tmdb_id']==604
        assert a.execute('SELECT tmdb_id FROM manual_overrides').fetchone()[0]==603


def test_unchanged_fingerprinted_records_stay_fast(tmp_path):
    root=tmp_path/'Library';root.mkdir()
    with closing(database(tmp_path/'a.db')) as a:
        manual(a,root,root/'Film.mkv');p.synchronize(a,str(root),p.LocalBackend(root));p.synchronize(a,str(root),p.LocalBackend(root))
        backend=p.LocalBackend(root);backend.read=Mock(side_effect=AssertionError('unnecessary read'))
        assert not p.synchronize(a,str(root),backend)['warnings']


def test_imdb_nfo_identifier_uses_hungarian_display_details(media,monkeypatch):
    monkeypatch.setattr(media,'UI_LANGUAGE','hu')
    def response(path,params):
        assert params.get('language')=='hu-HU'
        if path=='find/tt0133093':return {'movie_results':[{'id':603}]}
        if path=='movie/603':return localized()
        raise AssertionError(path)
    monkeypatch.setattr(media,'tmdb_request',Mock(side_effect=response))
    result=media.fetch_tmdb_by_imdb('tt0133093',True)
    assert result['title']=='Magyar filmcím' and result['id']==603


def test_full_scan_updates_old_english_card_snapshot(media,tmp_path,monkeypatch):
    monkeypatch.setattr(media,'UI_LANGUAGE','hu')
    folder=tmp_path/'Library';folder.mkdir();film=folder/'opaque.mkv';film.touch()
    scanner=media.LibraryScannerThread([str(folder)],[],library_key='movies');scanner.get_poster=Mock(return_value=None)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        scanner.save_cache(db,media.normalize_media_path(str(film)),1,603,'Original Movie','English','','2016',film.stat().st_mtime,'success','language:match_v185:hu-HU')
    monkeypatch.setattr(media,'tmdb_request',Mock(return_value=localized()))
    monkeypatch.setattr(media,'search_tmdb',Mock(side_effect=AssertionError('no new search needed')))
    items=[];scanner.item_ready.connect(lambda item,movie:items.append(item));scanner.run()
    assert not scanner.failed_libraries,scanner.errors
    assert items[0]['title']=='Magyar filmcím'
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        snapshot=json.loads(db.execute("SELECT payload FROM library_card_cache WHERE library_id='movies'").fetchone()[0])
        assert snapshot['title']=='Magyar filmcím' and snapshot['id']==603


def test_known_corrupt_nas_record_is_restored_by_readback(tmp_path):
    root='syno:///Movies'
    client=Mock();store={}
    def listing(path):
        if path=='/Movies/.synostream':return [dict(name='parositasok',isdir=True)]
        if path=='/Movies/'+p.SUBDIR:return [dict(name=name,isdir=False) for name in store]
        raise AssertionError(path)
    client.list_folder.side_effect=listing
    client.read_pairing.side_effect=lambda path:store[path.rsplit('/',1)[-1]]
    client.upload_pairing.side_effect=lambda directory,name,payload:store.__setitem__(name,payload)
    backend=lambda:p.NASBackend(root,client,[dict(name='.synostream',isdir=True)])
    with closing(database(tmp_path/'a.db')) as a,closing(database(tmp_path/'b.db')) as b:
        event=manual(a,root,root+'/Film.mkv');assert p.synchronize(a,root,backend())['written']==1
        store[event['event_id']+'.json']=b'{' 
        result=p.synchronize(a,root,backend())
        assert result['repaired']==1 and not result['warnings']
        assert p.synchronize(b,root,backend())['imported']==1


def test_unicode_filenames_with_different_spelling_are_not_collapsed(tmp_path):
    root=tmp_path/'Library';root.mkdir()
    for name in ('Masse.mkv','Maße.mkv'):(root/name).touch()
    assert len(list(root.glob('*.mkv')))==2
    assert p.relative_path(str(root),str(root/'Masse.mkv'))=='Masse.mkv'
    assert p.relative_path(str(root),str(root/'Maße.mkv'))=='Maße.mkv'


def test_valid_changed_nas_event_is_not_overwritten_by_old_retry(tmp_path):
    root='syno:///Movies';client=Mock();store={}
    def listing(path):
        if path=='/Movies/.synostream':return [dict(name='parositasok',isdir=True)]
        return [dict(name=name,isdir=False) for name in store]
    client.list_folder.side_effect=listing
    client.read_pairing.side_effect=lambda path:store[path.rsplit('/',1)[-1]]
    backend=p.NASBackend(root,client,[dict(name='.synostream',isdir=True)])
    with closing(database(tmp_path/'a.db')) as a:
        event=manual(a,root,root+'/Film.mkv')
        changed=dict(event,tmdb_id=604);store[event['event_id']+'.json']=p.encode_event(changed)
        result=p.synchronize(a,root,backend,verify=True)
        assert result['invalid']==1 and result['pending']==1
        client.upload_pairing.assert_not_called()
        assert p.decode_event(store[event['event_id']+'.json'])['tmdb_id']==604


def test_verified_localized_info_is_reused_during_remote_refresh(media,monkeypatch):
    monkeypatch.setattr(media,'UI_LANGUAGE','hu')
    media.cache_localized_display_info(localized(),True)
    monkeypatch.setattr(media,'tmdb_request',Mock(side_effect=AssertionError('do not re-download a verified title')))
    scanner=media.LibraryScannerThread([],[],force_remote_refresh=True)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        info=scanner.localized_cached_info(db,'syno:///Movies/opaque.mkv',603,True,'Original Movie','English','','2016')
        assert info['title']=='Magyar filmcím'
    media.tmdb_request.assert_not_called()
