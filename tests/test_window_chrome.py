from pathlib import Path
import pytest
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox, QInputDialog, QLabel, QVBoxLayout
from synostream_download_ui import CreateDownloadDialog, TorrentSitesDialog
from synostream_file_selection_ui import FileSelectionDialog
from synostream_window_chrome import HEIGHT, WindowChrome


@pytest.fixture(autouse=True)
def no_unhandled_chrome_errors(caplog):
    yield
    assert not [record for record in caplog.records if record.levelname == 'CRITICAL']


def assert_chrome(window, app, media):
    window.show()
    app.processEvents()
    bar = window._syno_title_bar
    assert bar is not None
    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert bar.width() == window.width()
    assert window.contentsMargins().top() >= HEIGHT
    expected = QIcon(media.APP_ICON_FILE).pixmap(20,20).toImage()
    assert bar.icon_label.pixmap().toImage() == expected
    window.resize(window.width()+80,window.height()+40)
    app.processEvents()
    assert bar.width() == window.width()
    window.setWindowTitle('Megváltozott cím')
    assert bar.label.text() == 'Megváltozott cím'
    return bar


@pytest.mark.parametrize('kind', ['plain', 'torrent', 'sites', 'files', 'message', 'input', 'picker'])
def test_every_dialog_gets_shared_title_bar_and_close_rejects(media, app, kind):
    main = media.DSVideoWindow()
    page = main.downloads_page
    constructors = {
        'plain': lambda: QDialog(main), 'torrent': lambda: CreateDownloadDialog(page),
        'sites': lambda: TorrentSitesDialog(page),
        'files': lambda: FileSelectionDialog(page, [], str),
        'message': lambda: QMessageBox(QMessageBox.Icon.Information, 'Info', 'Text', parent=main),
        'input': lambda: QInputDialog(main), 'picker': lambda: QFileDialog(main),
    }
    dialog = constructors[kind]()
    if kind == 'input': dialog.setLabelText('Név:')
    if kind == 'picker': dialog.setDirectory(str(Path(media.BASE_DIR)))
    bar = assert_chrome(dialog, app, media)
    assert not bar.minimize.isVisible() and not bar.maximize.isVisible()
    QTest.mouseClick(bar.close_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert not dialog.isVisible()
    if kind != 'message': assert dialog.result() == QDialog.DialogCode.Rejected
    main.close()


def test_main_window_controls_and_resize_edges(media, app):
    main = media.DSVideoWindow()
    main.resize(1000,720)
    bar = assert_chrome(main, app, media)
    assert bar.minimize.isVisible() and bar.maximize.isVisible()
    normal = main.geometry()
    QTest.mouseClick(bar.maximize, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert main.isMaximized()
    assert WindowChrome.resize_edges(main, QPoint(0,0)) == Qt.Edge(0)
    QTest.mouseDClick(bar, Qt.MouseButton.LeftButton, pos=QPoint(150,18))
    app.processEvents()
    assert not main.isMaximized()
    assert main.geometry() == normal
    assert WindowChrome.resize_edges(main, QPoint(0,0)) == Qt.Edge.LeftEdge | Qt.Edge.TopEdge
    assert WindowChrome.resize_edges(main, QPoint(200,100)) == Qt.Edge(0)
    QTest.mouseClick(bar.minimize, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert main.isMinimized()
    main.showNormal()
    app.processEvents()
    main.showFullScreen()
    app.processEvents()
    assert not bar.isVisible() and main.contentsMargins().top() == 0
    main.showNormal()
    app.processEvents()
    assert bar.isVisible() and main.contentsMargins().top() == HEIGHT
    main.close()


def test_native_dialogs_disabled_and_qt_dialog_language_switches(media, app):
    assert app.testAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    media.set_ui_language('hu')
    assert app.translate('QFileDialog', 'Look in:') != 'Look in:'
    media.set_ui_language('en')
    assert app.translate('QFileDialog', 'Look in:') == 'Look in:'
    media.set_ui_language('hu')


def test_cpp_static_file_dialog_close_keeps_wrapper_alive(media, app):
    def close():
        modal = app.activeModalWidget()
        assert modal is not None
        bar = modal._syno_title_bar
        QTest.mouseClick(bar.close_button, Qt.MouseButton.LeftButton)
    QTimer.singleShot(20, close)
    result, _filter = QFileDialog.getOpenFileName(None, 'Fájl', str(Path(media.BASE_DIR)))
    assert result == ''


def test_application_restarts_exit_cleanly(tmp_path):
    import subprocess, sys, os
    source = Path(__file__).resolve().parents[1] / 'SynoStream_1.95.py'
    environment = os.environ.copy()
    environment['SYNOSTREAM_DATA_DIR'] = str(tmp_path / 'restart-data')
    environment['QT_QPA_PLATFORM'] = 'offscreen'
    for _ in range(3):
        result = subprocess.run([sys.executable, '-X', 'faulthandler', str(source), '--smoke-test'],
                                env=environment, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('saved_state', [
    Qt.WindowState.WindowFullScreen,
    Qt.WindowState.WindowFullScreen | Qt.WindowState.WindowMaximized,
    Qt.WindowState.WindowMinimized,
    Qt.WindowState.WindowFullScreen | Qt.WindowState.WindowMaximized | Qt.WindowState.WindowMinimized,
])
def test_saved_immersive_state_never_hides_startup_title_bar(media, app, saved_state):
    from PyQt6.QtWidgets import QMainWindow
    old = QMainWindow()
    old.resize(600, 420)
    old.setWindowState(saved_state)
    media.config['window_geometry'] = bytes(old.saveGeometry().toHex()).decode('ascii')
    old.close()
    window = media.DSVideoWindow()
    window.show()
    app.processEvents()
    assert not window.isFullScreen() and not window.isMinimized()
    assert window.isMaximized() == bool(saved_state & Qt.WindowState.WindowMaximized)
    assert window._syno_title_bar.isVisible()
    assert window._syno_title_bar.close_button.isVisible()
    assert window.contentsMargins().top() == HEIGHT
    window.close()
    again = media.DSVideoWindow()
    again.show()
    app.processEvents()
    assert not again.isFullScreen() and not again.isMinimized()
    assert again._syno_title_bar.isVisible()
    again.close()


@pytest.mark.skipif(__import__('sys').platform != 'win32', reason='Windows native window regression')
def test_native_windows_restored_maximized_is_not_fullscreen(tmp_path):
    import subprocess, sys, os, textwrap
    source = Path(__file__).resolve().parents[1] / 'SynoStream_1.95.py'
    script = r"""
import importlib.util, sys, ctypes
from pathlib import Path
source = Path(sys.argv[1]); sys.path.insert(0,str(source.parent))
spec=importlib.util.spec_from_file_location('native_app',source)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QMainWindow
from ctypes import wintypes
app=m.QApplication([]); m.init_db(); m.config['startup_scan_mode']='none'
old=QMainWindow(); old.resize(600,420)
old.setWindowState(Qt.WindowState.WindowFullScreen | Qt.WindowState.WindowMaximized)
m.config['window_geometry']=bytes(old.saveGeometry().toHex()).decode('ascii')
old.close()
w=m.DSVideoWindow(); w.show(); checks=[]
def check():
    f=app._synostream_chrome.native; hwnd=int(w.winId())
    info=f.MonitorInfo(); info.size=ctypes.sizeof(info)
    f.user32.GetMonitorInfoW(f.user32.MonitorFromWindow(hwnd,2),ctypes.byref(info))
    f.user32.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    f.user32.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
    r=wintypes.RECT(); point=wintypes.POINT()
    f.user32.GetClientRect(hwnd,ctypes.byref(r)); f.user32.ClientToScreen(hwnd,ctypes.byref(point))
    checks.extend([not w.isFullScreen(),w.isMaximized(),w._syno_title_bar.isVisible(),
                   point.x>=info.work.left,point.y>=info.work.top,
                   point.x+r.right<=info.work.right,point.y+r.bottom<=info.work.bottom])
    w.close(); app.quit()
QTimer.singleShot(300,check)
app.exec()
assert checks and all(checks),checks
"""
    environment=os.environ.copy()
    environment['SYNOSTREAM_DATA_DIR']=str(tmp_path/'native-restart')
    environment['QT_QPA_PLATFORM']='windows'
    result=subprocess.run([sys.executable,'-X','faulthandler','-c',textwrap.dedent(script),str(source)],
                          env=environment,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
