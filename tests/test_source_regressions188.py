import contextlib
import copy
import json
import sqlite3
from unittest.mock import Mock
import pytest
from synostream_sources import SourceRouter,parse_pairs
from synostream_source_migration import canonicalize_config,migrate_database
from test_sources187 import values,REMOTE,LOCAL

@pytest.mark.parametrize('old_library',['movies','custom-a'])
def test_move_pair_removes_old_roots_and_cached_cards(media,old_library):
    old_values=values();old_values[0]['library_id']=old_library
    new_values=values();new_values[0]['library_id']='shows'
    old=SourceRouter(parse_pairs(old_values));new=SourceRouter(parse_pairs(new_values))
    settings=dict(movies_paths=[REMOTE,'C:/Other'],movies_path=LOCAL,remote_movies_path=REMOTE[7:],shows_paths=[],custom_libraries=[dict(id='custom-a',paths=[REMOTE,'C:/Keep'])])
    updated=canonicalize_config(settings,new,old)
    assert updated['shows_paths']==[REMOTE]
    if old_library=='movies':
        assert updated['movies_paths']==['C:/Other']
        assert updated['movies_path']==updated['remote_movies_path']==''
    else:assert updated['custom_libraries'][0]['paths']==['C:/Keep']
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO library_card_cache VALUES (?,?,?)',(old_library,REMOTE+'/Film.mkv',json.dumps(dict(file_path=REMOTE+'/Film.mkv',title='Film'))));db.commit()
        with db:migrate_database(db,old,new)
        assert db.execute('SELECT library_id,file_path FROM library_card_cache').fetchall()==[('shows',REMOTE+'/Film.mkv')]

@pytest.mark.parametrize('save_ok',[True,False])
def test_delete_library_removes_pair_and_failed_save_restores_it(media,app,monkeypatch,save_ok):
    pair=values()[0];pair['library_id']='custom-a'
    media.config.update(custom_libraries=[dict(id='custom-a',name='Test',paths=[REMOTE],is_movie=True)],paired_sources=[pair])
    before=copy.deepcopy(media.config)
    window=media.DSVideoWindow()
    monkeypatch.setattr(media.QMessageBox,'question',lambda *a:media.QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(media.QMessageBox,'critical',Mock())
    monkeypatch.setattr(media,'save_config',lambda:(save_ok,'test'))
    try:
        window.delete_custom_library('custom-a')
        if save_ok:
            assert media.config['paired_sources']==[]
            assert media.config['custom_libraries']==[]
            canonicalize_config(media.config,media.source_router(),media.source_router())
        else:assert media.config==before
    finally:window.close();app.processEvents()

@pytest.mark.parametrize('activity',['sync','resolution'])
def test_reconfigure_waits_for_background_source_users(media,app,monkeypatch,activity):
    window=media.DSVideoWindow();original=copy.deepcopy(media.config)
    saved_workers=media._background_workers
    class FakeResolver:
        def isRunning(self): return True
    worker=FakeResolver()
    try:
        if activity=='sync':window._pairing_sync_running=True
        else:
            monkeypatch.setattr(media,'SourceResolutionWorker',FakeResolver)
            monkeypatch.setattr(media,'_background_workers',[worker])
        with pytest.raises(RuntimeError):window.save_source_pairs(values())
        assert media.config==original
        with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
            assert db.execute('SELECT COUNT(*) FROM manual_overrides').fetchone()[0]==0
    finally:
        window._pairing_sync_running=False
        media._background_workers=saved_workers
        window.close();app.processEvents()
