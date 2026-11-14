from unittest.mock import Mock
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox, QDialog
from synostream_source_folders import SourceFoldersDialog, SourcesBusy
from test_update_sources198 import ROWS


def editor(app,monkeypatch,save):
    monkeypatch.setattr(QMessageBox,'question',Mock(return_value=QMessageBox.StandardButton.Yes))
    return SourceFoldersDialog(None,ROWS,[('movies','Filmek')],save,Mock(),Mock())


def test_busy_save_retries_without_repeating_pair_confirmation(app,monkeypatch):
    save=Mock(side_effect=[SourcesBusy('busy'),None]);dialog=editor(app,monkeypatch,save)
    try:
        dialog.accept()
        assert dialog._save_timer.isActive() and len(dialog.values)==1
        assert dialog._pending_save is not None and not dialog.add.isEnabled()
        dialog._try_save()
        assert dialog.result()==QDialog.DialogCode.Accepted and not dialog._save_timer.isActive()
        assert save.call_count==2 and len(save.call_args.args[0])==1
        QMessageBox.question.assert_called_once()
    finally:dialog.reject();dialog.deleteLater();app.processEvents()


def test_cancel_while_waiting_prevents_later_save(app,monkeypatch):
    save=Mock(side_effect=SourcesBusy('busy'));dialog=editor(app,monkeypatch,save)
    try:
        dialog.accept();dialog.reject();dialog._try_save()
        assert not dialog._save_timer.isActive() and dialog._pending_save is None
        assert save.call_count==1
    finally:dialog.deleteLater();app.processEvents()


def test_waiting_save_completes_from_timer_without_another_click(app,monkeypatch):
    save=Mock(side_effect=[SourcesBusy('busy'),None]);dialog=editor(app,monkeypatch,save)
    watchdog=QTimer(dialog);watchdog.setSingleShot(True);watchdog.timeout.connect(dialog.reject)
    try:
        dialog._save_timer.setInterval(20);dialog.accept();watchdog.start(2000)
        assert dialog.exec()==QDialog.DialogCode.Accepted
        assert save.call_count==2;QMessageBox.question.assert_called_once()
    finally:watchdog.stop();dialog.reject();dialog.deleteLater();app.processEvents()


def test_real_save_error_keeps_approved_pair_for_retry(app,monkeypatch):
    save=Mock(side_effect=[OSError('disk error'),None]);dialog=editor(app,monkeypatch,save)
    try:
        dialog.accept()
        assert len(dialog.values)==1 and not dialog._save_timer.isActive() and dialog.add.isEnabled()
        dialog.accept()
        QMessageBox.question.assert_called_once()
        assert dialog.result()==QDialog.DialogCode.Accepted
    finally:dialog.reject();dialog.deleteLater();app.processEvents()


def test_editor_defers_new_scan_and_sync_and_resumes_after_close(media,app,monkeypatch):
    window=media.DSVideoWindow()
    def execute(dialog):
        assert window._source_editing
        window.start_library_scan(force_remote_refresh=True)
        window.sync_shared_pairings(rescan=True)
        assert window.scanner_thread is None and not window._pairing_sync_running
        assert window._source_scan_deferred and window._source_sync_deferred
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(media.SourceFoldersDialog,'exec',execute)
    # Replace the entry points only after their real deferred paths were checked.
    real_execute=execute;scan=Mock();sync=Mock()
    def execute_and_capture(dialog):
        value=real_execute(dialog)
        monkeypatch.setattr(window,'start_library_scan',scan)
        monkeypatch.setattr(window,'sync_shared_pairings',sync)
        return value
    monkeypatch.setattr(media.SourceFoldersDialog,'exec',execute_and_capture)
    try:
        window.manage_paths()
        app.processEvents()
        assert not window._source_editing
        scan.assert_called_once_with(force_remote_refresh=True);sync.assert_called_once()
    finally:window.close();app.processEvents()

