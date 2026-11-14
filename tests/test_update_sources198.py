import contextlib
import json
import sqlite3
import sys
import time
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QPushButton, QMessageBox
import synostream_update_ui as update_ui
from synostream_source_folders import SourceFoldersDialog, suggested_pair, combine_records
from synostream_sources import SourceRouter, parse_pairs
from test_updates195 import package

LOCAL = r'\\NAS\Share\Film'
REMOTE = 'syno:///Share/Film'
ROWS = [dict(id='nas',library_id='movies',local_root='',remote_root=REMOTE),
        dict(id='local',library_id='movies',local_root=LOCAL,remote_root='')]


class DownloadWorker(QObject):
    done=pyqtSignal(object);failed=pyqtSignal(str);progress=pyqtSignal(int)
    def __init__(self, version, manifest=None):super().__init__();self.manifest=manifest;self.cancelled=False
    def isRunning(self):return True
    def requestInterruption(self):self.cancelled=True


@pytest.mark.parametrize('outcome',['success','failure','later'])
def test_two_button_update_downloads_then_installs_without_extra_click(media,app,monkeypatch,tmp_path,outcome):
    window=media.DSVideoWindow();controller=window.updater;controller.manifest=package(tmp_path)[0]
    monkeypatch.setattr(sys,'frozen',True,raising=False);monkeypatch.setattr(update_ui,'UpdateWorker',DownloadWorker)
    controller.run_worker=lambda worker:None
    prepare=Mock();monkeypatch.setattr(update_ui.updates,'prepare_install',prepare)
    original_close=window.close;close=Mock();monkeypatch.setattr(window,'close',close)
    try:
        controller.show_offer();app.processEvents()
        buttons=[b.text() for b in controller.dialog.findChildren(QPushButton) if b.text() in ('Letöltés','Frissítés és újraindítás','Később')]
        assert sorted(buttons)==sorted(['Frissítés és újraindítás','Később'])
        assert controller.install_button.isEnabled()
        controller.install_button.click();worker=controller.worker
        assert not controller.install_button.isEnabled();prepare.assert_not_called()
        if outcome=='failure':
            worker.failed.emit('offline');assert controller.install_button.isEnabled();close.assert_not_called()
        elif outcome=='later':
            controller.dialog.reject();assert worker.cancelled
            stage=tmp_path/'stage';stage.mkdir();worker.done.emit({'stage':str(stage)})
            prepare.assert_not_called();close.assert_not_called()
        else:
            staged={'stage':str(tmp_path/'stage'),'manifest':controller.manifest};worker.done.emit(staged)
            assert controller.installing;prepare.assert_called_once();close.assert_called_once()
    finally:controller.dialog.reject();original_close();app.processEvents()


@pytest.mark.parametrize('answer',[QMessageBox.StandardButton.Yes,QMessageBox.StandardButton.No,QMessageBox.StandardButton.Cancel])
def test_source_editor_links_only_after_confirmation(app,monkeypatch,answer):
    assert suggested_pair(ROWS)==(1,0)
    save=Mock();monkeypatch.setattr(QMessageBox,'question',lambda *args:answer)
    dialog=SourceFoldersDialog(None,ROWS,[('movies','Filmek')],save,Mock(),Mock())
    try:
        dialog.accept()
        if answer==QMessageBox.StandardButton.Cancel:save.assert_not_called()
        elif answer==QMessageBox.StandardButton.No:assert len(save.call_args.args[0])==2
        else:
            linked=save.call_args.args[0];assert len(linked)==1
            assert linked[0]['local_root']==LOCAL and linked[0]['remote_root']==REMOTE
    finally:dialog.reject();dialog.deleteLater();app.processEvents()


def test_pair_suggestion_does_not_merge_different_folders():
    rows=[dict(ROWS[0],remote_root='syno:///Other/Film'),ROWS[1]]
    assert suggested_pair(rows) is None


def test_source_link_collapses_existing_local_and_nas_cards(media,app):
    media.config.update(movies_paths=[LOCAL,REMOTE],paired_sources=[])
    local=LOCAL+r'\Title.mkv';remote=REMOTE+'/Title.mkv'
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        for path in (local,remote):
            db.execute('INSERT INTO media_cache(file_path,tmdb_id,is_movie,status) VALUES (?,?,?,?)',
                (media.normalize_media_path(path),603,1,'success'))
            db.execute('INSERT INTO library_card_cache VALUES (?,?,?)',('movies',media.normalize_media_path(path),
                json.dumps(dict(file_path=path,title='Film',id=603,is_movie=True))))
        db.commit()
    window=media.DSVideoWindow()
    try:
        assert window.movies_page.count()==2
        window.save_library_sources(combine_records(ROWS,1,0))
        assert window.movies_page.count()==1 and len(media.config['paired_sources'])==1
        assert media.configured_paths('movies')==[REMOTE]
        with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
            assert db.execute('SELECT COUNT(*) FROM library_card_cache WHERE library_id=?',('movies',)).fetchone()[0]==1
    finally:window.close();app.processEvents()


def test_playback_rechecks_local_connection_after_cached_failure(monkeypatch):
    router=SourceRouter(parse_pairs([dict(ROWS[0],local_root=LOCAL)]));pair=router.pairs[0]
    router.health[pair.id]=(False,time.monotonic()+5)
    monkeypatch.setattr('synostream_sources.os.scandir',lambda path:contextlib.nullcontext(iter(())))
    monkeypatch.setattr('synostream_sources.os.path.isfile',lambda path:True)
    assert router.playback_path(REMOTE+'/Title.mkv',recheck=True)==LOCAL+r'\Title.mkv'


def test_playlist_rechecks_each_source_only_once(media,app):
    router=SourceRouter(parse_pairs([dict(ROWS[0],local_root=LOCAL)]))
    router.playback_path=Mock(side_effect=lambda path,**kwargs:path)
    worker=media.SourceResolutionWorker(router,[REMOTE+'/A.mkv',REMOTE+'/B.mkv']);worker.run()
    assert [call.kwargs['recheck'] for call in router.playback_path.call_args_list]==[True,False]


def test_playback_source_indicator_describes_actual_selected_route(media,monkeypatch):
    assert media.playback_source_text([LOCAL+r'\Title.mkv'])=='Lejátszás: helyi hálózat'
    assert media.playback_source_text([REMOTE+'/Title.mkv'])=='Lejátszás: NAS / QuickConnect'
    assert media.playback_source_text(['C:/Film.mkv'])=='Lejátszás: helyi fájl'
    monkeypatch.setattr(media,'expand_mapped_path',lambda path:LOCAL+r'\Title.mkv')
    assert media.playback_source_text(['Z:/Title.mkv'])=='Lejátszás: helyi hálózat'
