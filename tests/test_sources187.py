import contextlib
import json
import ntpath
import os
import sqlite3
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import synostream_sources as routing
from synostream_sources import SourceRouter, RoutedNASClient, parse_pairs
from synostream_source_migration import canonicalize_config, migrate_database

LOCAL = r'\\192.168.1.2\Media\Film'
REMOTE = 'syno:///Media/Film'


def values(**changes):
    return [dict(id='test-pair', local_root=LOCAL, remote_root=REMOTE, library_id='movies', **changes)]


def router():
    return SourceRouter(parse_pairs(values()), timeout=.04)


@pytest.mark.parametrize('path,expected', [
    (LOCAL,REMOTE),(LOCAL+r'\Title\Film.mkv',REMOTE+'/Title/Film.mkv'),
    (LOCAL.lower()+r'\Title\Film.mkv',REMOTE+'/Title/Film.mkv'),
    (LOCAL+'s\\Other.mkv',LOCAL+'s\\Other.mkv'),
    ('syno:///usbshare2/Film/a.mkv','syno:///usbshare2/Film/a.mkv'),
])
def test_alias_boundaries_and_canonical_identity(path,expected):
    assert router().canonical(path)==expected


@pytest.mark.parametrize('local,remote', [
    ('C:\\Films',REMOTE),(r'\\NAS',REMOTE),(LOCAL,'https://example.com'),
    (LOCAL,'syno:///'),(LOCAL,'syno:///Media/../Other'),(LOCAL+r'\..\Other',REMOTE),
])
def test_invalid_or_escaping_root_is_rejected(local,remote):
    with pytest.raises(ValueError):parse_pairs([dict(local_root=local,remote_root=remote)])


def test_overlapping_roots_rejected():
    with pytest.raises(ValueError):parse_pairs(values()+[dict(id='other',local_root=LOCAL+r'\Nested',remote_root='syno:///Other')])
    with pytest.raises(ValueError):parse_pairs(values()+[dict(id='other',local_root=r'\\OTHER\Share',remote_root=REMOTE+'/Nested')])


def test_offline_smb_uses_nas_without_replaying_mutations(monkeypatch):
    r=router();nas=Mock();nas.list_folder.return_value=[dict(name='NAS entry')]
    factory=Mock(return_value=nas)
    monkeypatch.setattr(routing.os,'scandir',Mock(side_effect=OSError('offline')))
    client=RoutedNASClient(r,factory)
    assert factory.call_count==0
    assert client.list_folder('/Media/Film')==[dict(name='NAS entry')]
    assert factory.call_count==1
    assert r.playback_path(REMOTE+'/Film.mkv')==REMOTE+'/Film.mkv'
    client.close();nas.close.assert_called_once()


def test_hung_smb_probe_has_deadline_and_does_not_create_threads_per_file(monkeypatch):
    r=router();r.io=routing.BoundedIO();release=threading.Event();calls=[]
    def hung(path):
        calls.append(path);release.wait(4);raise OSError('offline')
    monkeypatch.setattr(routing.os,'scandir',hung)
    nas=Mock();nas.list_folder.return_value=[];client=RoutedNASClient(r,lambda:nas)
    start=time.perf_counter()
    try:
        for _ in range(8):assert client.list_folder('/Media/Film')==[]
        assert time.perf_counter()-start<.6
        assert len(calls)==1
    finally:release.set();client.close()


def local_files(monkeypatch,tmp_path):
    (tmp_path/'Title').mkdir();(tmp_path/'Title'/'Film.mkv').write_bytes(b'video')
    (tmp_path/'Title'/'Film.nfo').write_bytes(b'<movie><title>Title</title></movie>')
    real_scan=os.scandir;real_open=open;real_isfile=os.path.isfile
    def path(value):
        relative=routing._local_relative(str(value),LOCAL)
        return tmp_path.joinpath(*relative.split('/')) if relative is not None else value
    monkeypatch.setattr(routing.os,'scandir',lambda value:real_scan(path(value)))
    monkeypatch.setattr(routing,'open',lambda value,*a,**kw:real_open(path(value),*a,**kw),raising=False)
    monkeypatch.setattr(routing.os.path,'isfile',lambda value:real_isfile(path(value)))
    return path


def test_online_smb_scan_and_nfo_need_no_quickconnect_login(monkeypatch,tmp_path):
    local_files(monkeypatch,tmp_path);r=router();factory=Mock(side_effect=AssertionError('NAS login not needed'))
    client=RoutedNASClient(r,factory)
    entries=client.list_folder('/Media/Film/Title')
    assert {entry['name'] for entry in entries}=={'Film.mkv','Film.nfo'}
    assert all(entry['path'].startswith('/Media/Film/Title/') for entry in entries)
    assert all(type(entry['additional']['time']['mtime']) is int for entry in entries)
    response=client.open_stream('/Media/Film/Title/Film.nfo')
    assert b'<title>Title</title>' in b''.join(response.iter_content())
    assert r.playback_path(REMOTE+'/Title/Film.mkv')==LOCAL+r'\Title\Film.mkv'
    factory.assert_not_called();client.close()


def test_missing_local_file_uses_remote_file_even_when_share_is_online(monkeypatch,tmp_path):
    local_files(monkeypatch,tmp_path);r=router()
    assert r.playback_path(REMOTE+'/Title/Missing.mkv')==REMOTE+'/Title/Missing.mkv'


def test_unsupported_usb_root_remains_quickconnect_only():
    r=router()
    assert r.pair_for('syno:///usbshare1/Films/a.mkv') is None
    assert r.playback_path('syno:///usbshare1/Films/a.mkv')=='syno:///usbshare1/Films/a.mkv'


def test_configured_roots_and_scanner_collapse_both_aliases(media):
    media.config.update(paired_sources=values(),movies_paths=[LOCAL,REMOTE],remote_movies_path='/Media/Film')
    assert media.configured_paths('movies')==[REMOTE]
    assert media.normalize_media_path(LOCAL+r'\Title\Film.mkv')==REMOTE+'/Title/Film.mkv'
    assert media.media_path_is_within(LOCAL+r'\Title\Film.mkv',REMOTE)
    scanner=media.LibraryScannerThread([LOCAL,REMOTE],[])
    assert scanner.movies_paths==[REMOTE]


def test_shared_manual_event_uses_same_relative_path_from_smb(media):
    media.config.update(paired_sources=values(),movies_paths=[LOCAL,REMOTE])
    with sqlite3.connect(media.DB_FILE) as db:
        event=media.record_portable_edit(db,LOCAL+r'\Title\Film.mkv',True,77,'Chosen',library_id='movies')
        assert event is not None
        payload=json.loads(db.execute('SELECT payload FROM portable_events').fetchone()[0])
        assert payload['relative_path']=='Title/Film.mkv'


def test_migration_preserves_manual_metadata_latest_progress_and_case(media):
    path=LOCAL+r'\CamelTitle\Film.mkv';old=media.normalize_media_path(path);canonical=REMOTE+'/CamelTitle/Film.mkv'
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,?)',(old,77,'Chosen',1))
        db.execute('INSERT INTO playback_state(file_path,position,last_played) VALUES (?,?,?)',(old,80,10))
        db.execute('INSERT INTO playback_state(file_path,position,last_played) VALUES (?,?,?)',(canonical,20,20))
        db.execute('INSERT INTO library_card_cache VALUES (?,?,?)',('movies',old,json.dumps(dict(file_path=path,title='Chosen',id=77))))
        migrate_database(db,SourceRouter(),router())
        assert db.execute('SELECT file_path,tmdb_id FROM manual_overrides').fetchall()==[(canonical,77)]
        assert db.execute('SELECT file_path,position FROM playback_state').fetchall()==[(canonical,20)]
        row=db.execute('SELECT file_path,payload FROM library_card_cache').fetchone()
        assert row[0]==canonical and json.loads(row[1])['file_path']==canonical


def test_conflicting_manual_matches_abort_without_data_loss(media):
    old=media.normalize_media_path(LOCAL+r'\Film.mkv');canonical=REMOTE+'/Film.mkv'
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,?)',(old,77,'A',1))
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,?)',(canonical,88,'B',1))
        before=db.execute('SELECT * FROM manual_overrides ORDER BY file_path').fetchall()
        with pytest.raises(ValueError):migrate_database(db,SourceRouter(),router())
        assert db.execute('SELECT * FROM manual_overrides ORDER BY file_path').fetchall()==before


def test_config_keeps_unpaired_smb_and_usb_roots_and_canonicalizes_pairs():
    settings=dict(movies_paths=[LOCAL,REMOTE,r'\\OTHER\Films'],shows_paths=['syno:///usbshare1/Shows'],custom_libraries=[],manual_show_groups=[],excluded_media_paths=[LOCAL+r'\Ignore.mkv'])
    updated=canonicalize_config(settings,router())
    assert updated['movies_paths']==[REMOTE,r'\\OTHER\Films']
    assert updated['shows_paths']==settings['shows_paths']
    assert updated['excluded_media_paths']==[REMOTE+'/Ignore.mkv']
    assert settings['movies_paths'][0]==LOCAL


def test_pair_configuration_survives_save_and_reload(media):
    media.config['paired_sources']=values()
    assert media.save_config()[0]
    loaded,warning=media.load_config()
    assert loaded['paired_sources']==values() and not warning


def test_save_failure_rolls_back_database_and_settings(media,app,monkeypatch):
    old=media.normalize_media_path(LOCAL+r'\Film.mkv')
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,?)',(old,77,'Chosen',1));db.commit()
    window=media.DSVideoWindow();save=media.write_config_atomic
    monkeypatch.setattr(media,'write_config_atomic',Mock(side_effect=OSError('test write failure')))
    try:
        with pytest.raises(OSError):window.save_source_pairs(values())
        with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:assert db.execute('SELECT file_path FROM manual_overrides').fetchone()[0]==old
        assert media.config.get('paired_sources',[])==[]
    finally:monkeypatch.setattr(media,'write_config_atomic',save);window.close();app.processEvents()


def test_same_card_and_progress_after_online_offline_switch(media,monkeypatch,tmp_path):
    local_files(monkeypatch,tmp_path)
    media.config.update(paired_sources=values(),movies_paths=[LOCAL,REMOTE],remote_movies_path='')
    nas=Mock()
    directory=dict(name='Title',path='/Media/Film/Title',isdir=True,additional={'time':{'mtime':int((tmp_path/'Title').stat().st_mtime)}})
    file=dict(name='Film.mkv',path='/Media/Film/Title/Film.mkv',isdir=False,additional={'time':{'mtime':int((tmp_path/'Title'/'Film.mkv').stat().st_mtime)},'size':5})
    nfo=dict(name='Film.nfo',path='/Media/Film/Title/Film.nfo',isdir=False,additional={'time':{'mtime':1}})
    nas.list_folder.side_effect=lambda path:[directory] if path=='/Media/Film' else [file,nfo]
    nas.open_stream.return_value=routing.LocalResponse(b'<movie><title>Title</title></movie>')
    factory=Mock(return_value=nas);monkeypatch.setattr(media,'_RemoteNASClient',factory)
    monkeypatch.setattr(media,'fetch_tmdb_data',Mock(return_value=dict(status='success',id=77,title='Chosen',overview='Plot',poster_url='',date='2020',complete=True)))
    monkeypatch.setattr(media.LibraryScannerThread,'get_poster',lambda *a:None)
    first=media.LibraryScannerThread([LOCAL,REMOTE],[],library_key='movies',force_remote_refresh=True)
    items=[];first.item_ready.connect(lambda item,movie:items.append(item));first.run()
    assert len(items)==1 and items[0]['file_path']==REMOTE+'/Title/Film.mkv'
    factory.assert_not_called()
    media.save_playback_progress(dict(path=items[0]['file_path'],media_title='Chosen',is_movie=True),42,100,[])
    real_scan=routing.os.scandir
    def disconnected(path):
        if str(path).startswith('\\\\'):raise OSError('SMB disconnected')
        return real_scan(path)
    monkeypatch.setattr(routing.os,'scandir',disconnected)
    media.source_router().health.clear()
    second=media.LibraryScannerThread([LOCAL,REMOTE],[],library_key='movies',force_remote_refresh=True)
    received=[];second.item_ready.connect(lambda item,movie:received.append(item));second.run()
    assert len(received)==1 and received[0]['file_path']==items[0]['file_path']
    assert media.get_playback_state(LOCAL+r'\Title\Film.mkv')['position']==42
    assert factory.called
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        assert db.execute("SELECT COUNT(*) FROM library_card_cache WHERE library_id='movies'").fetchone()[0]==1


def test_migration_rejects_case_colliding_nas_files(media):
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,?)',(REMOTE+'/Film.mkv',77,'A',1))
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,?)',(REMOTE+'/film.mkv',88,'B',1));db.commit()
        with pytest.raises(ValueError):migrate_database(db,SourceRouter(),router())
        assert db.execute('SELECT COUNT(*) FROM manual_overrides').fetchone()[0]==2


def test_source_editor_validates_pending_input_and_adds_pairs(media,app):
    from synostream_source_ui import SourcePairsDialog
    save=Mock();dialog=SourcePairsDialog(None,media.config,[('movies','Filmek')],save)
    try:
        dialog.local.setText(LOCAL);dialog.remote.setText(REMOTE)
        dialog.accept();save.assert_not_called()
        assert dialog.error.text()
        dialog.add_pair();assert len(dialog.values)==1
        dialog.accept();save.assert_called_once()
        assert save.call_args.args[0][0]['remote_root']==REMOTE
    finally:dialog.close();app.processEvents()


def test_source_configuration_success_has_one_card_and_keeps_original_source_only_settings(media,app):
    media.config.update(movies_paths=[LOCAL,REMOTE],remote_movies_path='/Media/Film')
    path=LOCAL+r'\Title\Film.mkv';old=media.normalize_media_path(path)
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO library_card_cache VALUES (?,?,?)',('movies',old,json.dumps(dict(file_path=path,title='Chosen',id=77))))
        db.execute('INSERT INTO library_card_cache VALUES (?,?,?)',('movies',REMOTE+'/Title/Film.mkv',json.dumps(dict(file_path=REMOTE+'/Title/Film.mkv',title='Chosen',id=77))))
        db.commit()
    window=media.DSVideoWindow()
    try:
        window.save_source_pairs(values())
        assert media.configured_paths('movies')==[REMOTE]
        assert len(window._cached_page_items('movies'))==1
        loaded,warning=media.load_config()
        assert loaded['paired_sources']==values()
        assert media.config['remote_movies_path']=='/Media/Film'
    finally:window.close();app.processEvents()


def test_legacy_unknown_case_is_resolved_before_publishing(media,monkeypatch,tmp_path):
    local_files(monkeypatch,tmp_path)
    old=media.normalize_media_path(LOCAL+r'\Title\Film.mkv')
    r=router();client=RoutedNASClient(r,Mock(side_effect=AssertionError('No NAS needed')))
    from synostream_source_migration import resolve_pending_cases
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,?)',(old,77,'Chosen',1));db.commit()
        with db:migrate_database(db,SourceRouter(),r)
        assert db.execute('SELECT COUNT(*) FROM source_route_pending').fetchone()[0]==1
        resolve_pending_cases(db,REMOTE,client,r)
        assert db.execute('SELECT file_path FROM manual_overrides').fetchone()[0]==REMOTE+'/Title/Film.mkv'
        assert db.execute('SELECT COUNT(*) FROM source_route_pending').fetchone()[0]==0
    client.close()


def test_legacy_unknown_missing_file_keeps_pending_metadata(media,monkeypatch):
    r=router();client=Mock();client.resolve_case.side_effect=OSError('offline')
    from synostream_source_migration import resolve_pending_cases
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,?)',(media.normalize_media_path(LOCAL+r'\Missing.mkv'),77,'Chosen',1));db.commit()
        with db:migrate_database(db,SourceRouter(),r)
        with pytest.raises(OSError):resolve_pending_cases(db,REMOTE,client,r)
        assert db.execute('SELECT tmdb_id FROM manual_overrides').fetchone()[0]==77
        assert db.execute('SELECT COUNT(*) FROM source_route_pending').fetchone()[0]==1


def test_editing_existing_pair_rebases_history_and_config(media):
    old=router();updated_values=values();updated_values[0]['remote_root']='syno:///Renamed/Film'
    new=SourceRouter(parse_pairs(updated_values))
    settings=canonicalize_config(dict(movies_paths=[REMOTE],remote_movies_path='/Media/Film'),new,old)
    assert settings['movies_paths']==['syno:///Renamed/Film']
    assert settings['remote_movies_path']=='/Renamed/Film'
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO playback_state(file_path,position) VALUES (?,?)',(REMOTE+'/Title/Film.mkv',42));db.commit()
        with db:migrate_database(db,old,new)
        assert db.execute('SELECT file_path,position FROM playback_state').fetchone()==('syno:///Renamed/Film/Title/Film.mkv',42)


def test_removing_pair_keeps_quickconnect_and_history(media):
    old=router();new=SourceRouter()
    settings=canonicalize_config(dict(movies_paths=[REMOTE],paired_sources=values()),new,old)
    assert settings['movies_paths']==[REMOTE] and settings['paired_sources']==[]
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO playback_state(file_path,position) VALUES (?,?)',(REMOTE+'/Film.mkv',42));db.commit()
        with db:migrate_database(db,old,new)
        assert db.execute('SELECT file_path,position FROM playback_state').fetchone()==(REMOTE+'/Film.mkv',42)


def test_smb_returns_after_connection_recovery(monkeypatch,tmp_path):
    local_files(monkeypatch,tmp_path);r=router();client=RoutedNASClient(r,Mock())
    assert r.playback_path(REMOTE+'/Title/Film.mkv')==LOCAL+r'\Title\Film.mkv'
    r.invalidate(r.pairs[0])
    assert r.playback_path(REMOTE+'/Title/Film.mkv')==REMOTE+'/Title/Film.mkv'
    r.health[r.pairs[0].id]=(False,0)
    assert r.playback_path(REMOTE+'/Title/Film.mkv')==LOCAL+r'\Title\Film.mkv'


def test_one_removed_legacy_file_does_not_block_other_pairings(media,monkeypatch,tmp_path):
    local_files(monkeypatch,tmp_path)
    r=router();client=RoutedNASClient(r,Mock(side_effect=AssertionError('SMB is available')))
    from synostream_source_migration import resolve_pending_cases
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        for file in ('Title\\Film.mkv','Missing.mkv'):
            db.execute('INSERT INTO manual_overrides VALUES (?,?,?,?)',(media.normalize_media_path(LOCAL+'\\'+file),77,'Chosen',1))
        db.commit()
        with db:migrate_database(db,SourceRouter(),r)
        resolve_pending_cases(db,REMOTE,client,r)
        assert db.execute('SELECT COUNT(*) FROM source_route_pending').fetchone()[0]==1
        assert db.execute('SELECT tmdb_id FROM manual_overrides WHERE file_path=?',(REMOTE+'/Title/Film.mkv',)).fetchone()[0]==77
        backend=Mock();backend.list_names.return_value=[];backend.fingerprints={};backend.write=Mock()
        media.synchronize_portable_root(db,REMOTE,backend,lambda:False,[REMOTE],False)
        assert backend.write.call_count==1
        assert db.execute('SELECT COUNT(*) FROM manual_overrides').fetchone()[0]==2
    client.close()


def test_pending_case_resolution_also_works_after_unpairing(media):
    from synostream_source_migration import resolve_pending_cases
    client=SimpleNamespace(list_folder=lambda path:[dict(name='Film.mkv')])
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,?)',(REMOTE+'/film.mkv',77,'Chosen',1))
        db.execute('INSERT INTO source_route_pending VALUES (?,?)',(REMOTE+'/film.mkv',REMOTE));db.commit()
        resolve_pending_cases(db,REMOTE,client,SourceRouter())
        assert db.execute('SELECT file_path FROM manual_overrides').fetchone()[0]==REMOTE+'/Film.mkv'
        assert db.execute('SELECT COUNT(*) FROM source_route_pending').fetchone()[0]==0


@pytest.mark.parametrize('local',[True,False])
def test_playback_route_is_asynchronous_but_progress_identity_is_shared(media,app,monkeypatch,local):
    from pathlib import Path
    media.config.update(paired_sources=values(),movies_paths=[REMOTE],mpv_path='mpv.exe')
    monkeypatch.setattr(media,'resolve_mpv_path',lambda value:'mpv.exe')
    monkeypatch.setattr(media,'mpv_localized_context_menu_args',lambda *a:[])
    process=Mock();monkeypatch.setattr(media.subprocess,'Popen',Mock(return_value=process))
    monkeypatch.setattr(media,'run_worker',Mock())
    monitor=Mock();monkeypatch.setattr(media,'MpvPlaybackMonitor',Mock(return_value=monitor))
    proxy=Mock(return_value='http://127.0.0.1/stream');monkeypatch.setattr(media,'_remote_stream_url',proxy)
    parent=media.QWidget();parent.show();app.processEvents();playlist=None
    try:
        media.play_with_mpv(parent,LOCAL+r'\Title\Film.mkv','Chosen',resume_position=33)
        media.subprocess.Popen.assert_not_called()
        resolver=media.run_worker.call_args.args[0]
        assert isinstance(resolver,media.SourceResolutionWorker)
        resolver.resolved.emit([LOCAL+r'\Title\Film.mkv' if local else REMOTE+'/Title/Film.mkv'])
        assert media.subprocess.Popen.called
        entries=media.MpvPlaybackMonitor.call_args.args[2]
        assert entries[0]['path']==REMOTE+'/Title/Film.mkv'
        playlist=Path(media.MpvPlaybackMonitor.call_args.args[4])
        assert (LOCAL+r'\Title\Film.mkv' if local else 'http://127.0.0.1/stream') in playlist.read_text(encoding='utf-8')
        assert media.get_playback_state(REMOTE+'/Title/Film.mkv')['position']==33
        assert media.get_playback_state(LOCAL+r'\Title\Film.mkv')['position']==33
    finally:
        if playlist is not None:playlist.unlink(missing_ok=True)
        parent.close();app.processEvents()
