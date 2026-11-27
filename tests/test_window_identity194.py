from pathlib import Path
import os
import struct
import subprocess
import sys
import pytest
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDialog
from synostream_window_identity import icon_frames,load_application_icon,APP_USER_MODEL_ID


def test_icon_frames_are_complete_and_invalid_payloads_are_ignored(media):
    data=Path(media.APP_ICON_FILE).read_bytes()
    frames=icon_frames(data)
    assert {frame[0] for frame in frames}=={16,24,32,48,64,128,256}
    assert icon_frames(data[:20])==[]
    bad=bytearray(data);struct.pack_into('<I',bad,18,len(data)+100)
    assert len(icon_frames(bad))==len(frames)-1


def test_materialized_icon_survives_source_file_removal(media,app,tmp_path):
    path=tmp_path/'icon.ico';path.write_bytes(Path(media.APP_ICON_FILE).read_bytes())
    icon=load_application_icon(path);expected=icon.pixmap(64,64).toImage();path.unlink()
    assert not icon.isNull() and icon.pixmap(64,64).toImage()==expected
    for size in (16,32,48,128,256):assert not icon.pixmap(size,size).isNull()


def test_window_icon_loss_is_repaired_without_changing_owner_state(media,app):
    main=media.DSVideoWindow();main.show();app.processEvents()
    dialog=QDialog(main);dialog.show();app.processEvents()
    state=main.windowState();geometry=main.geometry();chrome=app._synostream_chrome
    try:
        dialog.setWindowIcon(QIcon());main.setWindowIcon(QIcon());app.setWindowIcon(QIcon())
        chrome.repair_icons();app.processEvents()
        assert main.windowIcon().cacheKey()==chrome.icon.cacheKey()
        assert dialog.windowIcon().cacheKey()==chrome.icon.cacheKey()
        assert app.windowIcon().cacheKey()==chrome.icon.cacheKey()
        assert main.windowState()==state and main.geometry()==geometry
        assert chrome.icon_timer.isActive() and chrome.icon_timer.interval()==5000
    finally:dialog.close();dialog.deleteLater();main.close();app.processEvents()


@pytest.mark.skipif(sys.platform!='win32',reason='Windows native icon lifecycle')
def test_native_icon_handles_survive_dialogs_state_changes_and_loss(tmp_path):
    source=Path(__file__).resolve().parents[1]/'SynoStream_1.109.py'
    script=r'''
import ctypes,importlib.util,sys,json
from pathlib import Path
from ctypes import wintypes
source=Path(sys.argv[1]);sys.path.insert(0,str(source.parent))
spec=importlib.util.spec_from_file_location('native_app',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from PyQt6.QtCore import QEvent,Qt,QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDialog
from synostream_window_identity import APP_USER_MODEL_ID
app=m.QApplication([]);m.init_db();m.config['startup_scan_mode']='none'
w=m.DSVideoWindow();w.show();app.processEvents()
chrome=app._synostream_chrome;icons=chrome.native_icons;u=icons.user32
assert app._synostream_app_id_set
shell=ctypes.WinDLL('shell32');shell.GetCurrentProcessExplicitAppUserModelID.argtypes=[ctypes.POINTER(ctypes.c_wchar_p)];shell.GetCurrentProcessExplicitAppUserModelID.restype=ctypes.c_long
name=ctypes.c_wchar_p();assert shell.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(name))==0
assert name.value==APP_USER_MODEL_ID
ole=ctypes.WinDLL('ole32');ole.CoTaskMemFree.argtypes=[ctypes.c_void_p];ole.CoTaskMemFree(ctypes.cast(name,ctypes.c_void_p))
def check(window):
 app.processEvents();chrome.ensure_icon(window)
 hwnd=int(window.winId());small,big=icons.expected(hwnd)
 assert small and big
 assert u.SendMessageW(hwnd,0x007F,0,0)==small
 assert u.SendMessageW(hwnd,0x007F,1,0)==big
check(w)
for _ in range(12):
 dialog=QDialog(w);dialog.show();check(dialog)
 dialog.reject();dialog.deleteLater();app.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
 check(w)
for action in (w.showMaximized,w.showMinimized,w.showNormal,w.showMaximized,w.showNormal):
 action();app.processEvents();check(w)
w.hide();w.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,True);w.show();check(w)
w.hide();w.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,False);w.show();check(w)
state=w.windowState();geometry=w.geometry();hwnd=int(w.winId())
u.SendMessageW(hwnd,0x0080,0,0);u.SendMessageW(hwnd,0x0080,1,0)
assert not u.SendMessageW(hwnd,0x007F,0,0) and not u.SendMessageW(hwnd,0x007F,1,0)
# Exercise the actual periodic repair, not only a direct method call.
chrome.icon_timer.setInterval(30)
loop=m.QEventLoop() if hasattr(m,'QEventLoop') else None
from PyQt6.QtCore import QEventLoop
loop=QEventLoop();QTimer.singleShot(90,loop.quit);loop.exec()
small,big=icons.expected(hwnd)
assert u.SendMessageW(hwnd,0x007F,0,0)==small
assert u.SendMessageW(hwnd,0x007F,1,0)==big
check(w);assert w.windowState()==state and w.geometry()==geometry
class IconInfo(ctypes.Structure):
 _fields_=[('icon',wintypes.BOOL),('x',wintypes.DWORD),('y',wintypes.DWORD),('mask',wintypes.HANDLE),('color',wintypes.HANDLE)]
u.GetIconInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(IconInfo)];u.GetIconInfo.restype=wintypes.BOOL
gdi=ctypes.WinDLL('gdi32');gdi.DeleteObject.argtypes=[wintypes.HANDLE]
for size in (16,24,32,48,64,128,256):
 handle=icons.handle(size);info=IconInfo();assert u.GetIconInfo(handle,ctypes.byref(info))
 for bitmap in (info.mask,info.color):
  if bitmap:gdi.DeleteObject(bitmap)
assert len(icons.handles)<=10
print(json.dumps({'dialog_cycles':12,'state_changes':5,'forced_icon_loss_repaired':True,'app_id':APP_USER_MODEL_ID,'cached_icon_sizes':len(icons.handles)}),flush=True)
w.close();chrome.shutdown();assert icons.closed and not icons.handles;icons.close()
'''
    env=os.environ.copy();env.update(SYNOSTREAM_DATA_DIR=str(tmp_path/'native-icons'),QT_QPA_PLATFORM='windows')
    result=subprocess.run([sys.executable,'-X','faulthandler','-c',script,str(source)],env=env,capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'forced_icon_loss_repaired' in result.stdout
