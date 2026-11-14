import contextlib
import ctypes
import json
import os
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import synostream_sources as routing
from synostream_sources import expand_mapped_path,parse_pairs,SourceRouter
from synostream_source_folders import clean_records
from test_sources187 import LOCAL,REMOTE

@pytest.fixture
def mapped(monkeypatch):
    def connection(drive):
        return (0,LOCAL) if drive=='Z:' else (2250,'')
    monkeypatch.setattr(routing,'_drive_connection',connection)
    monkeypatch.setattr(routing,'_remembered_drive_connection',lambda drive:'')

@pytest.mark.parametrize('path,expected',[(r'Z:\Title\Film.mkv',LOCAL+r'\Title\Film.mkv'),('z:/Title/Film.mkv',LOCAL+r'\Title\Film.mkv'),('Z:/',LOCAL),(r'C:\Films',r'C:\Films'),(LOCAL,LOCAL),('syno:///Media/Film','syno:///Media/Film'),('Z:relative','Z:relative'),('Z:/../Film',LOCAL+r'\Film'),('Z:/Title/../Film',LOCAL+r'\Film')])
def test_windows_mapped_drive_resolution(mapped,path,expected):
    assert expand_mapped_path(path).rstrip('\\')==expected.rstrip('\\')

@pytest.mark.parametrize('status',[1201,1222,1203,2250])
def test_disconnected_persistent_drive_uses_saved_target(monkeypatch,status):
    monkeypatch.setattr(routing,'_drive_connection',lambda drive:(status,''))
    monkeypatch.setattr(routing,'_remembered_drive_connection',lambda drive:LOCAL)
    assert expand_mapped_path(r'Z:\Title')==LOCAL+r'\Title'


def test_lookup_failure_preserves_input(monkeypatch):
    monkeypatch.setattr(routing,'_drive_connection',Mock(side_effect=OSError('unavailable')))
    assert expand_mapped_path(r'Z:\Title')==r'Z:\Title'


def test_paired_browsed_drive_is_accepted_and_canonical(mapped):
    record=dict(id='mapped',library_id='movies',local_root='Z:/',remote_root=REMOTE)
    cleaned=clean_records([record])[0]
    assert cleaned['local_root'].rstrip('\\')==LOCAL
    router=SourceRouter(parse_pairs([cleaned]))
    assert router.canonical(r'Z:\Title\Film.mkv')==REMOTE+'/Title/Film.mkv'
    assert router.physical(REMOTE+'/Title/Film.mkv')==LOCAL+r'\Title\Film.mkv'


def test_unpaired_drive_keeps_its_existing_identity(mapped):
    record=dict(id='mapped',library_id='movies',local_root=r'Z:\Title',remote_root='')
    assert clean_records([record])[0]['local_root']==r'Z:\Title'
    assert SourceRouter().canonical(r'Z:\Title')==r'Z:\Title'
    other=SourceRouter(parse_pairs([dict(id='other',local_root=r'\\Elsewhere\Media',remote_root=REMOTE)]))
    assert other.canonical(r'Z:\Title')==r'Z:\Title'


def test_save_preserves_mapped_drive_history_and_manual_match(media,app,mapped):
    media.config.update(movies_paths=['Z:/'],remote_movies_path=REMOTE[7:])
    path=media.normalize_media_path(r'Z:\Title\Film.mkv')
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO playback_state(file_path,position) VALUES (?,?)',(path,42))
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,?)',(path,77,'Chosen',1))
        db.execute('INSERT INTO library_card_cache VALUES (?,?,?)',('movies',path,json.dumps(dict(file_path=r'Z:\Title\Film.mkv',title='Chosen',id=77))))
        db.commit()
    window=media.DSVideoWindow()
    try:
        window.save_library_sources([dict(id='mapped',library_id='movies',local_root='Z:/',remote_root=REMOTE)])
        assert media.configured_paths('movies')==[REMOTE]
        assert media.get_playback_state(r'Z:\Title\Film.mkv')['position']==42
        assert media.get_playback_state(REMOTE+'/Title/Film.mkv')['position']==42
        with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
            assert db.execute('SELECT file_path,tmdb_id FROM manual_overrides').fetchone()==(REMOTE+'/Title/Film.mkv',77)
            assert db.execute('SELECT COUNT(*) FROM source_route_pending').fetchone()[0]==0
    finally:window.close();app.processEvents()


def test_case_lost_mapped_history_waits_for_nas_spelling(media,app,mapped):
    media.config['movies_paths']=['Z:/']
    path=media.normalize_media_path(r'Z:\Film.mkv')
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,?)',(path,77,'Chosen',1));db.commit()
    window=media.DSVideoWindow()
    try:
        window.save_library_sources([dict(id='mapped',library_id='movies',local_root='Z:/',remote_root=REMOTE)])
        with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
            assert db.execute('SELECT file_path FROM source_route_pending').fetchone()[0]==REMOTE+'/film.mkv'
    finally:window.close();app.processEvents()


class Api:
    def __init__(self,operation):self.operation=operation
    def __call__(self,*args):return self.operation(*args)


def test_windows_api_retries_long_unc_buffer(monkeypatch):
    calls=[];target='\\\\NAS\\share\\'+'a'*700
    def connection(drive,buffer,size):
        calls.append(size._obj.value)
        if size._obj.value<len(target)+1:
            size._obj.value=len(target)+1;return 234
        buffer.value=target;return 0
    monkeypatch.setattr(ctypes,'WinDLL',lambda name:SimpleNamespace(WNetGetConnectionW=Api(connection)))
    assert routing._drive_connection('Z:')==(0,target)
    assert len(calls)==2


def test_saved_mapping_never_replaces_a_real_local_drive(monkeypatch):
    import winreg
    query=Mock();monkeypatch.setattr(winreg,'OpenKey',query)
    monkeypatch.setattr(ctypes,'WinDLL',lambda name:SimpleNamespace(GetDriveTypeW=Api(lambda path:3)))
    assert routing._remembered_drive_connection('C:')==''
    query.assert_not_called()
