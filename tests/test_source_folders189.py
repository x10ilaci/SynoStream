import contextlib
import copy
import json
import sqlite3
from unittest.mock import Mock
import pytest
from PyQt6.QtWidgets import QPushButton,QDialog
from synostream_source_folders import clean_records,records_from_settings,SourceFolderDialog,SourceFoldersDialog
from synostream_sources import SourceRouter,parse_pairs
from test_sources187 import values,REMOTE,LOCAL

LIBRARIES=[('movies','Filmek'),('shows','TV')]

def row(local='',remote='',id='source',library='movies'):
    return dict(id=id,library_id=library,local_root=local,remote_root=remote)

def test_existing_settings_are_combined_without_duplicates():
    settings=dict(movies_paths=[LOCAL,REMOTE],remote_movies_path=REMOTE[7:],shows_paths=['C:/TV'],paired_sources=values())
    result=records_from_settings(settings,LIBRARIES)
    assert len(result)==2 and result[0]==values()[0]
    assert result[1]['local_root']=='C:/TV'

@pytest.mark.parametrize('local,remote',[(LOCAL,''),('',REMOTE),('C:/Films',''),(LOCAL,REMOTE)])
def test_local_remote_and_paired_sources_are_valid(local,remote):
    result=clean_records([row(local,remote)])[0]
    assert result['remote_root']==remote
    assert bool(result['local_root'])==bool(local)

@pytest.mark.parametrize('records',[[row()],[row('relative')],[row('C:relative')],[row('\\\\NAS')],[row('C:/Films',REMOTE)],[row(LOCAL,REMOTE),row('',REMOTE,id='another')]])
def test_invalid_or_duplicate_sources_are_rejected(records):
    with pytest.raises(ValueError):clean_records(records)

def test_browse_buttons_fill_fields_without_saving(app):
    local=Mock(return_value=LOCAL);nas=Mock(return_value=REMOTE)
    dialog=SourceFolderDialog(None,row(),local,nas)
    try:
        next(b for b in dialog.findChildren(QPushButton) if b.text()=='Helyi mappa tallózása…').click()
        next(b for b in dialog.findChildren(QPushButton) if b.text()=='NAS-mappa tallózása…').click()
        assert dialog.local.text()==LOCAL and dialog.remote.text()==REMOTE
        local.assert_called_once_with(dialog);nas.assert_called_once_with(dialog)
        dialog.accept();assert dialog.result()==QDialog.DialogCode.Accepted
    finally:dialog.close();dialog.deleteLater();app.processEvents()

def test_cancelled_browse_preserves_current_selection(app):
    dialog=SourceFolderDialog(None,row(LOCAL),lambda _:None,lambda _:None)
    try:
        dialog.browse(dialog.local,lambda _:None)
        assert dialog.local.text()==LOCAL
    finally:dialog.close();dialog.deleteLater();app.processEvents()

def test_cancel_main_editor_never_saves(app):
    save=Mock();original=[row(LOCAL)]
    dialog=SourceFoldersDialog(None,original,LIBRARIES,save,Mock(),Mock())
    try:
        dialog.listing.setCurrentRow(0);dialog.remove_folder();dialog.reject()
        save.assert_not_called();assert original==[row(LOCAL)]
    finally:dialog.close();dialog.deleteLater();app.processEvents()

def test_save_failure_keeps_editor_open_and_preserves_rows(app):
    dialog=SourceFoldersDialog(None,[row(LOCAL)],LIBRARIES,Mock(side_effect=OSError('test')),Mock(),Mock())
    try:
        dialog.accept();assert dialog.result()!=QDialog.DialogCode.Accepted
        assert dialog.values==[row(LOCAL)] and dialog.error.text()=='test'
    finally:dialog.close();dialog.deleteLater();app.processEvents()

def test_unified_save_preserves_history_and_collapses_old_configuration(media,app):
    media.config.update(movies_paths=[LOCAL],remote_movies_path=REMOTE[7:])
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        path=media.normalize_media_path(LOCAL+r'\Film.mkv')
        db.execute('INSERT INTO playback_state(file_path,position) VALUES (?,?)',(path,42))
        db.execute('INSERT INTO library_card_cache VALUES (?,?,?)',('movies',path,json.dumps(dict(file_path=LOCAL+r'\Film.mkv'))));db.commit()
    window=media.DSVideoWindow()
    try:
        window.save_library_sources([row(LOCAL,REMOTE)])
        assert media.configured_paths('movies')==[REMOTE]
        assert media.config['remote_movies_path']==''
        assert media.get_playback_state(REMOTE+'/Film.mkv')['position']==42
        assert len(records_from_settings(media.config,LIBRARIES))==1
        loaded,_=media.load_config();assert loaded['paired_sources']==[row(LOCAL,REMOTE)]
    finally:window.close();app.processEvents()

def test_removing_nas_access_keeps_local_history(media,app):
    media.config.update(paired_sources=values(),movies_paths=[REMOTE])
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO playback_state(file_path,position) VALUES (?,?)',(REMOTE+'/Title/Film.mkv',42))
        db.execute('INSERT INTO source_route_pending VALUES (?,?)',(REMOTE+'/Title/Film.mkv',REMOTE));db.commit()
    window=media.DSVideoWindow()
    try:
        window.save_library_sources([row(LOCAL,id='test-pair')])
        assert media.config['paired_sources']==[]
        assert media.configured_paths('movies')==[LOCAL]
        assert media.get_playback_state(LOCAL+r'\Title\Film.mkv')['position']==42
        with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
            assert db.execute('SELECT COUNT(*) FROM source_route_pending').fetchone()[0]==0
    finally:window.close();app.processEvents()

def test_new_custom_library_uses_same_save_and_empty_library_is_rejected(media,app):
    window=media.DSVideoWindow();library=dict(id='new',name='Test',media_type='movies',paths=[])
    try:
        window.save_library_sources([row('',REMOTE,library='new')],library)
        assert media.configured_paths('custom:new')==[REMOTE]
        assert len(media.config['custom_libraries'])==1
    finally:window.close();app.processEvents()

def test_failed_atomic_save_restores_old_sources(media,app,monkeypatch):
    media.config['movies_paths']=[LOCAL];window=media.DSVideoWindow();before=copy.deepcopy(media.config)
    monkeypatch.setattr(media,'write_config_atomic',Mock(side_effect=OSError('test')))
    try:
        with pytest.raises(OSError):window.save_library_sources([row(LOCAL,REMOTE)])
        assert media.config==before
    finally:window.close();app.processEvents()

def test_nas_picker_returns_selection_without_assigning_library(media,app,monkeypatch):
    dialog=media.RemoteQuickConnectDialog(folder_picker=True)
    save=Mock();monkeypatch.setattr(media,'save_config',save)
    monkeypatch.setattr(dialog,'_cleanup_connection',Mock())
    try:
        dialog.sid='test';dialog.current_path='/Media/Film'
        dialog.choose_remote_folder()
        assert dialog.selected_folder==REMOTE
        assert dialog.result()==QDialog.DialogCode.Accepted
        save.assert_not_called()
    finally:dialog.close();dialog.deleteLater();app.processEvents()

def test_only_one_folder_management_entry_is_visible(media,app):
    window=media.DSVideoWindow()
    try:
        group=window.btn_paths.parentWidget()
        assert isinstance(group,media.QGroupBox)
        assert group.title()=='Médiatár és adatok'
        assert window.settings_dialog.isAncestorOf(window.btn_paths)
        assert window.library_nav_layout.indexOf(window.btn_paths)==-1
        assert window.btn_paths.text()=='Forrásmappák'
        texts=[b.text() for b in window.settings_dialog.findChildren(QPushButton)]
        assert 'Helyi médiamappák' not in texts
        assert 'Helyi és távoli elérések összerendelése' not in texts
    finally:window.close();app.processEvents()
