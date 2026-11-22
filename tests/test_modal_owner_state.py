"""Regression for closing lookup, then closing the enclosing media card."""
import os
from pathlib import Path
import subprocess
import sys
import pytest
from PyQt6 import sip
from PyQt6.QtCore import Qt, QTimer, QEvent, QCoreApplication
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton, QDialogButtonBox


def exercise_nested_close(m, app, folder, is_movie, maximized, method):
    m.set_ui_language('hu')
    m.config['startup_scan_mode'] = 'none'
    m.config['window_geometry'] = ''
    path = folder / ('movie.mkv' if is_movie else 'Series')
    if is_movie:
        path.touch()
    else:
        path.mkdir(exist_ok=True)
        (path / 'Series.S01E01.mkv').touch()
    item = dict(file_path=str(path), title='Test media', is_movie=is_movie)
    main = m.DSVideoWindow()
    if maximized:
        main.showMaximized()
    else:
        main.show()
    app.processEvents()
    original_state = main.windowState()
    errors, stages = [], []
    detail_holder = []

    def visible_dialog(title, owner):
        # Nested windows from earlier tests may still have deferred activation
        # events. Wait for the dialog belonging to this exact owner, not just
        # whichever window happens to be QApplication.activeModalWidget().
        for dialog in app.topLevelWidgets():
            if (dialog.isVisible() and dialog.windowTitle() == title
                    and dialog.parentWidget() == owner):
                bar = app._synostream_chrome.bars.get(sip.unwrapinstance(dialog))
                if bar is not None and not sip.isdeleted(bar.close_button) and bar.close_button.isVisible():
                    return dialog
        return None

    def title_bar(dialog):
        return app._synostream_chrome.bars[sip.unwrapinstance(dialog)]

    def assert_popup(dialog):
        native = app._synostream_chrome.native
        if native:
            style = native.user32.GetWindowLongPtrW(int(dialog.winId()), -16)
            assert style & 0x80000000, 'Modal Qt dialogs must retain their native popup style'

    def close_lookup():
        try:
            lookup = visible_dialog('Videoinformációk lekérése', detail_holder[0])
            if lookup is None:
                QTimer.singleShot(10, close_lookup)
                return
            assert_popup(lookup)
            assert lookup.windowTitle() == 'Videoinformációk lekérése'
            if method == 'x':
                QTest.mouseClick(title_bar(lookup).close_button, Qt.MouseButton.LeftButton)
            elif method == 'escape':
                QTest.keyClick(lookup, Qt.Key.Key_Escape)
            else:
                buttons = lookup.findChild(QDialogButtonBox)
                QTest.mouseClick(buttons.button(QDialogButtonBox.StandardButton.Cancel), Qt.MouseButton.LeftButton)
            stages.append('lookup closed')
        except Exception as error:
            errors.append(str(error))
            if app.activeModalWidget():
                app.activeModalWidget().reject()

    def open_lookup_and_close_detail():
        detail = visible_dialog('Média Részletek', main)
        if detail is None:
            QTimer.singleShot(10, open_lookup_and_close_detail)
            return
        detail_holder[:] = [detail]
        try:
            assert_popup(detail)
            assert detail.windowTitle() == 'Média Részletek'
            info = next(button for button in detail.findChildren(QPushButton)
                        if button.toolTip() == 'Videoinformációk hozzáadása')
            QTimer.singleShot(20, close_lookup)
            QTest.mouseClick(info, Qt.MouseButton.LeftButton)
            assert main.windowState() == original_state
            assert detail.isVisible()
            QTest.mouseClick(title_bar(detail).close_button, Qt.MouseButton.LeftButton)
            stages.append('detail closed')
        except Exception as error:
            errors.append(str(error))
            detail.reject()

    def abort():
        errors.append('Modal close timed out')
        modal = app.activeModalWidget()
        if modal:
            modal.reject()
    watchdog = QTimer()
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(abort)
    watchdog.start(3000)
    QTimer.singleShot(20, open_lookup_and_close_detail)
    main.open_media_detail(item)
    watchdog.stop()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    QTest.qWait(30)
    assert not errors, errors
    assert stages == ['lookup closed', 'detail closed']
    assert main.isVisible() and not main.isMinimized()
    assert main.windowState() == original_state
    assert main._syno_title_bar.isVisible()
    main.close()
    app.processEvents()


@pytest.mark.parametrize('is_movie', [True, False])
@pytest.mark.parametrize('maximized', [False, True])
@pytest.mark.parametrize('method', ['x', 'escape', 'cancel'])
def test_nested_close_preserves_owner(media, app, tmp_path, is_movie, maximized, method):
    exercise_nested_close(media, app, tmp_path, is_movie, maximized, method)


@pytest.mark.skipif(sys.platform != 'win32', reason='Native Windows modal activation')
def test_native_nested_close_and_reopen_preserves_owner(tmp_path):
    source = Path(__file__).resolve().parents[1]
    script = r"""
import sys, importlib.util
from pathlib import Path
source=Path(sys.argv[1]); folder=Path(sys.argv[2]); sys.path[:0]=[str(source),str(source/'tests')]
spec=importlib.util.spec_from_file_location('native_app',source/'SynoStream_1.106.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from test_modal_owner_state import exercise_nested_close
app=m.QApplication([]);m.init_db()
for _ in range(2):
 for is_movie in (True,False):
  for maximized in (False,True):
   for method in ('x','escape','cancel'):
    exercise_nested_close(m,app,folder,is_movie,maximized,method)
app._synostream_chrome.shutdown()
"""
    environment = os.environ.copy()
    environment['QT_QPA_PLATFORM'] = 'windows'
    environment['SYNOSTREAM_DATA_DIR'] = str(tmp_path / 'native-data')
    result = subprocess.run([sys.executable, '-X', 'faulthandler', '-c', script, str(source), str(tmp_path)],
                            # 24 cases retain their individual three-second
                            # watchdog. Allow their total plus Windows startup
                            # and teardown on a slower desktop session.
                            capture_output=True, text=True, env=environment, timeout=120)
    assert result.returncode == 0, result.stderr
