"""Shared custom title bars for application-owned Qt windows and dialogs."""
from PyQt6.QtCore import QObject, QEvent, Qt, QRectF, QTimer, QAbstractNativeEventFilter
import weakref
from PyQt6 import sip
from PyQt6.QtGui import QColor, QPainter, QPen, QIcon
from synostream_window_identity import WindowsWindowIcons
from PyQt6.QtWidgets import (QWidget, QMainWindow, QDialog, QLabel, QPushButton,
                             QHBoxLayout, QApplication, QFileDialog, QSizePolicy)

HEIGHT = 38


class CaptionButton(QPushButton):
    def __init__(self, kind, bar):
        super().__init__(bar)
        self.kind, self.bar = kind, bar
        self.setObjectName('CaptionClose' if kind == 'close' else 'CaptionButton')
        self.setFixedSize(46, HEIGHT - 1)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#EEEAF3'), 1.2))
        x, y = self.width()/2, self.height()/2
        if self.kind == 'close':
            painter.drawLine(int(x-5), int(y-5), int(x+5), int(y+5))
            painter.drawLine(int(x+5), int(y-5), int(x-5), int(y+5))
        elif self.kind == 'minimize':
            painter.drawLine(int(x-5), int(y), int(x+5), int(y))
        elif self.bar.target.isMaximized():
            painter.drawRect(QRectF(x-3, y-5, 8, 8))
            painter.fillRect(QRectF(x-6, y-2, 8, 8), QColor('#201B27'))
            painter.drawRect(QRectF(x-6, y-2, 8, 8))
        else:
            painter.drawRect(QRectF(x-5, y-5, 10, 10))
        painter.end()


class TitleBar(QWidget):
    def __init__(self, target, icon, language):
        super().__init__(target)
        self.default_icon, self.language = icon, language
        self.setObjectName('SynoTitleBar')
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            QWidget#SynoTitleBar {background:#201B27; border:0; border-bottom:1px solid #38303F;}
            QLabel {background:transparent; border:0; color:#EEEAF3; font-size:13px;}
            QPushButton#CaptionButton, QPushButton#CaptionClose {background:transparent; border:0; border-radius:0; padding:0; margin:0;}
            QPushButton#CaptionButton:hover {background:#39303F;}
            QPushButton#CaptionClose:hover {background:#B43A50;}
        """)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 0, 1)
        row.setSpacing(9)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(20, 20)
        self.label = QLabel()
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setMinimumWidth(0)
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        for label in (self.icon_label, self.label):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(self.icon_label)
        row.addWidget(self.label, 1)
        row.setStretch(1, 1)
        self.minimize = CaptionButton('minimize', self)
        self.maximize = CaptionButton('maximize', self)
        self.close_button = CaptionButton('close', self)
        for button in (self.minimize, self.maximize, self.close_button):
            row.addWidget(button)
        self.minimize.clicked.connect(lambda: self.target.showMinimized())
        self.maximize.clicked.connect(self.toggle_maximized)
        self.close_button.clicked.connect(self.close_window)
        self.refresh()

    @property
    def target(self):
        # Resolve through Qt ownership, including C++-created static dialogs
        # whose temporary Python window wrappers need not stay alive.
        return self.parentWidget()

    def refresh(self, *_args):
        if self.target is None or sip.isdeleted(self.target):
            return
        self.label.setText(self.target.windowTitle() or 'SynoStream')
        self.label.setToolTip(self.target.windowTitle() or 'SynoStream')
        icon = self.target.windowIcon()
        self.icon_label.setPixmap((icon if not icon.isNull() else self.default_icon).pixmap(20, 20))
        main = isinstance(self.target, QMainWindow)
        self.minimize.setVisible(main)
        self.maximize.setVisible(main and self.target.minimumSize() != self.target.maximumSize())
        english = self.language() == 'en'
        for button, hu, en in ((self.minimize, 'Kis méret', 'Minimize'),
                               (self.maximize, 'Visszaállítás' if self.target.isMaximized() else 'Teljes méret',
                                'Restore' if self.target.isMaximized() else 'Maximize'),
                               (self.close_button, 'Bezárás', 'Close')):
            button.setToolTip(en if english else hu)
            button.setAccessibleName(en if english else hu)
        self.maximize.update()

    def close_window(self):
        target = self.target
        if isinstance(target, QDialog):
            # End the modal Qt dialog as Cancel. A general window-close request
            # must not propagate native owner-window state changes.
            target.reject()
        else:
            target.close()

    def toggle_maximized(self):
        if not isinstance(self.target, QMainWindow):
            return
        if self.target.isMaximized():
            self.target.showNormal()
        else:
            self.target.showMaximized()
        self.refresh()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.target.windowHandle()
            if handle and handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class WindowChrome(QObject):
    def __init__(self, application, icon, language, icon_path=None):
        super().__init__(application)
        self.icon, self.language = icon, language
        # Keep Python subclass wrappers alive without retaining their target windows.
        self.bars = {}
        self.native = WindowsDesktopFrame(application) if application.platformName() == 'windows' else None
        self.native_icons = WindowsWindowIcons(icon_path) if self.native is not None else None
        self._icon_applying = False
        self._shutting_down = False
        self.icon_timer = QTimer(self)
        self.icon_timer.setInterval(5000)
        self.icon_timer.timeout.connect(self.repair_icons)
        self.icon_timer.start()
        application.installEventFilter(self)
        self.application = weakref.proxy(application)
        application.aboutToQuit.connect(self.shutdown)

    def shutdown(self):
        self._shutting_down = True
        self.icon_timer.stop()
        self.application.removeEventFilter(self)
        if self.native is not None:
            self.application.removeNativeEventFilter(self.native)
        # Destroy managed C++ windows while Python callbacks are still available,
        # rather than leaving subclass widgets to interpreter finalization.
        for bar in list(self.bars.values()):
            if sip.isdeleted(bar):
                continue
            target = bar.target
            if target is not None and not sip.isdeleted(target):
                sip.delete(target)
        self.bars.clear()
        if self.native_icons is not None: self.native_icons.close()

    def ensure_icon(self, window):
        if self._shutting_down or self._icon_applying or sip.isdeleted(window) or self.icon.isNull(): return
        # WinId/close events may queue a callback while the native window is being torn down.
        if not window.isVisible() or window.windowHandle() is None: return
        self._icon_applying = True
        try:
            if self.application.windowIcon().cacheKey() != self.icon.cacheKey():
                self.application.setWindowIcon(self.icon)
            if window.windowIcon().cacheKey() != self.icon.cacheKey(): window.setWindowIcon(self.icon)
            if self.native_icons is not None:
                handle = window.effectiveWinId()
                self.native_icons.ensure(int(handle) if handle else 0)
        finally:
            self._icon_applying = False

    def repair_icons(self):
        if self._shutting_down: return
        for bar in list(self.bars.values()):
            if sip.isdeleted(bar): continue
            window = bar.target
            if window is not None and not sip.isdeleted(window): self.ensure_icon(window)

    def apply(self, window):
        key = sip.unwrapinstance(window)
        existing = self.bars.get(key)
        if existing is not None and not sip.isdeleted(existing):
            # Qt can expose another Python wrapper for the same live window.
            window._syno_title_bar = existing
            self.sync_window(window)
            return
        # A destroyed Qt child's wrapper can outlive the native address. Never
        # let that stale entry suppress chrome for a newly allocated window.
        self.bars.pop(key, None)
        window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        window.setWindowIcon(self.icon)
        margins = window.contentsMargins()
        window.setProperty('_syno_base_margins', (margins.left(), margins.top(), margins.right(), margins.bottom()))
        if window.minimumHeight() == window.maximumHeight():
            window.setFixedHeight(window.height()+HEIGHT)
        window.setContentsMargins(margins.left(), margins.top()+HEIGHT,
                                  margins.right(), margins.bottom())
        bar = TitleBar(window, self.icon, self.language)
        window._syno_title_bar = bar
        self.bars[key] = bar
        window.setProperty('_syno_chrome', True)
        window.destroyed.connect(lambda _object=None, key=key: self.bars.pop(key, None))
        bar.setGeometry(0, 0, window.width(), HEIGHT)
        bar.raise_()
        bar.show()
        window.setMouseTracking(True)
        if self.native is not None:
            self.native.attach(window)
        self.ensure_icon(window)

    @staticmethod
    def resize_edges(window, point):
        if window.isMaximized() or window.isFullScreen() or window.minimumSize() == window.maximumSize():
            return Qt.Edge(0)
        edges = Qt.Edge(0)
        if window.minimumWidth() != window.maximumWidth():
            if point.x() < 5: edges |= Qt.Edge.LeftEdge
            elif point.x() >= window.width()-5: edges |= Qt.Edge.RightEdge
        if window.minimumHeight() != window.maximumHeight():
            if point.y() < 5: edges |= Qt.Edge.TopEdge
            elif point.y() >= window.height()-5: edges |= Qt.Edge.BottomEdge
        return edges

    def sync_window(self, window):
        if sip.isdeleted(window):
            return
        bar = self.bars.get(sip.unwrapinstance(window))
        if bar is None or sip.isdeleted(bar):
            return
        window._syno_title_bar = bar
        base = window.property('_syno_base_margins')
        top = (base[1] if base else 0) + (0 if window.isFullScreen() else HEIGHT)
        if window.contentsMargins().top() != top:
            margins = window.contentsMargins()
            window.setContentsMargins(margins.left(), top, margins.right(), margins.bottom())
        bar.setGeometry(0, 0, window.width(), HEIGHT)
        bar.setVisible(not window.isFullScreen())
        bar.raise_()
        bar.refresh()

    def eventFilter(self, watched, event):
        kind = event.type()
        # Never inspect widget properties during Destroy/DeferredDelete: Qt may
        # already be tearing down the C++ object while its wrapper still exists.
        if kind not in (QEvent.Type.Polish, QEvent.Type.Resize, QEvent.Type.Show,
                        QEvent.Type.WindowStateChange, QEvent.Type.WindowTitleChange,
                        QEvent.Type.WindowIconChange, QEvent.Type.MouseMove,
                        QEvent.Type.MouseButtonPress, QEvent.Type.WinIdChange, QEvent.Type.WindowActivate):
            return False
        if not isinstance(watched, QWidget) or sip.isdeleted(watched):
            return False
        if kind == QEvent.Type.Polish and watched.isWindow() and isinstance(watched, (QMainWindow, QDialog)):
            self.apply(watched)
        bar = self.bars.get(sip.unwrapinstance(watched))
        if bar is not None and self.native is not None and kind in (QEvent.Type.WinIdChange, QEvent.Type.Show):
            self.native.attach(watched)
        if bar is not None and kind in (QEvent.Type.WinIdChange, QEvent.Type.Show, QEvent.Type.WindowStateChange,
                                        QEvent.Type.WindowIconChange, QEvent.Type.WindowActivate):
            self.ensure_icon(watched)
            QTimer.singleShot(0, lambda window=watched: self.ensure_icon(window))
        if kind == QEvent.Type.Show and isinstance(watched, QFileDialog):
            english = self.language() == 'en'
            labels = ((QFileDialog.DialogLabel.LookIn, 'Hely:', 'Look in:'),
                      (QFileDialog.DialogLabel.FileName, 'Fájlnév:', 'File name:'),
                      (QFileDialog.DialogLabel.FileType, 'Fájltípus:', 'Files of type:'),
                      (QFileDialog.DialogLabel.Reject, 'Mégse', 'Cancel'))
            for label, hu, en in labels:
                watched.setLabelText(label, en if english else hu)
        if bar is not None and kind in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.WindowStateChange,
                                         QEvent.Type.WindowTitleChange, QEvent.Type.WindowIconChange):
            self.sync_window(watched)
            if kind in (QEvent.Type.Show, QEvent.Type.WindowStateChange):
                QTimer.singleShot(0, lambda window=watched: self.sync_window(window))
        if kind in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress):
            window = watched.window()
            if sip.unwrapinstance(window) in self.bars:
                point = window.mapFromGlobal(event.globalPosition().toPoint())
                edges = self.resize_edges(window, point)
                if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton and edges:
                    handle = window.windowHandle()
                    if handle and handle.startSystemResize(edges):
                        return True
                if watched is window:
                    cursors = {Qt.Edge.LeftEdge: Qt.CursorShape.SizeHorCursor,
                               Qt.Edge.RightEdge: Qt.CursorShape.SizeHorCursor,
                               Qt.Edge.TopEdge: Qt.CursorShape.SizeVerCursor,
                               Qt.Edge.BottomEdge: Qt.CursorShape.SizeVerCursor}
                    if edges:
                        window.setCursor(cursors.get(edges, Qt.CursorShape.SizeFDiagCursor if edges in (
                            Qt.Edge.LeftEdge | Qt.Edge.TopEdge, Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
                            else Qt.CursorShape.SizeBDiagCursor))
                    else:
                        window.unsetCursor()
        return False


def install_window_chrome(application, icon, language, icon_path=None):
    application._synostream_chrome = WindowChrome(application, icon, language, icon_path)


def restore_desktop_geometry(window, geometry):
    """Read saved Qt geometry without applying immersive flags to the real HWND.

    A hidden probe lets Qt validate its own format and monitor coordinates. Only
    the normal rectangle and maximized preference reach the application window.
    """
    probe = QWidget()
    probe.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    try:
        if not probe.restoreGeometry(geometry):
            return False
        normal = probe.normalGeometry()
        maximized = probe.isMaximized()
        if not normal.isValid():
            return False
        window.setGeometry(normal)
        window.setWindowState(Qt.WindowState.WindowMaximized if maximized else Qt.WindowState.WindowNoState)
        return True
    finally:
        sip.delete(probe)


class WindowsDesktopFrame(QAbstractNativeEventFilter):
    """Keep native desktop/maximize semantics while drawing our own caption.

    WS_CAPTION tells Windows/Qt this is a desktop window, not a borderless
    immersive fullscreen surface. WM_NCCALCSIZE removes only its visual frame.
    WM_GETMINMAXINFO constrains maximization to the monitor work area.
    """
    def __init__(self, application):
        super().__init__()
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.types = ctypes, wintypes
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        self.user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        self.user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        self.user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.user32.SetWindowPos.restype = wintypes.BOOL
        self.user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        self.user32.MonitorFromWindow.restype = wintypes.HANDLE
        self.user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        self.user32.GetMonitorInfoW.restype = wintypes.BOOL
        self.user32.IsZoomed.argtypes = [wintypes.HWND]
        self.user32.IsZoomed.restype = wintypes.BOOL
        class MonitorInfo(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT),
                        ('work', wintypes.RECT), ('flags', wintypes.DWORD)]
        class MinMaxInfo(ctypes.Structure):
            _fields_ = [('reserved', wintypes.POINT), ('max_size', wintypes.POINT),
                        ('max_position', wintypes.POINT), ('min_track', wintypes.POINT),
                        ('max_track', wintypes.POINT)]
        self.MonitorInfo, self.MinMaxInfo = MonitorInfo, MinMaxInfo
        self.windows, self.handles = {}, {}
        self.attaching = False
        application.installNativeEventFilter(self)

    def attach(self, window):
        if self.attaching or sip.isdeleted(window):
            return
        self.attaching = True
        try:
            key = sip.unwrapinstance(window)
            hwnd = int(window.winId())
            previous = self.handles.get(key)
            if previous is not None and previous != hwnd:
                self.windows.pop(previous, None)
            if previous is None:
                window.destroyed.connect(lambda _object=None, key=key: self.detach(key))
            self.handles[key] = hwnd
            self.windows[hwnd] = key
            style = self.user32.GetWindowLongPtrW(hwnd, -16)
            # Owned Qt dialogs retain WS_POPUP. Converting them into overlapped
            # desktop windows changes Windows' modal owner/activation behavior.
            desired = style | 0x00C00000 | 0x00080000
            if isinstance(window, QMainWindow):
                desired = (desired & ~0x80000000) | 0x00040000 | 0x00020000 | 0x00010000
            if style != desired:
                self.user32.SetWindowLongPtrW(hwnd, -16, desired)
                self.user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0037)
        finally:
            self.attaching = False

    def detach(self, key):
        hwnd = self.handles.pop(key, None)
        if hwnd is not None:
            self.windows.pop(hwnd, None)

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) not in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
            return False, 0
        msg = self.types.MSG.from_address(int(message))
        if msg.hWnd not in self.windows:
            return False, 0
        if msg.message == 0x0083:  # WM_NCCALCSIZE: retain the work-area client bounds
            if msg.lParam and self.user32.IsZoomed(msg.hWnd):
                monitor = self.user32.MonitorFromWindow(msg.hWnd, 2)
                info = self.MonitorInfo()
                info.size = self.ctypes.sizeof(info)
                if monitor and self.user32.GetMonitorInfoW(monitor, self.ctypes.byref(info)):
                    rectangle = self.types.RECT.from_address(msg.lParam)
                    rectangle.left = max(rectangle.left, info.work.left)
                    rectangle.top = max(rectangle.top, info.work.top)
                    rectangle.right = min(rectangle.right, info.work.right)
                    rectangle.bottom = min(rectangle.bottom, info.work.bottom)
                    # With an auto-hidden/absent taskbar the work area equals the
                    # whole monitor. Qt otherwise classifies that exact client
                    # rectangle as fullscreen (QWindowsWindow::isFullScreen_sys).
                    # Reserve a one-pixel reveal edge instead of entering it.
                    if (rectangle.left == info.monitor.left and rectangle.top == info.monitor.top
                            and rectangle.right == info.monitor.right and rectangle.bottom == info.monitor.bottom):
                        rectangle.bottom -= 1
            return True, 0
        if msg.message == 0x0024 and msg.lParam:  # WM_GETMINMAXINFO
            monitor = self.user32.MonitorFromWindow(msg.hWnd, 2)
            info = self.MonitorInfo()
            info.size = self.ctypes.sizeof(info)
            if monitor and self.user32.GetMonitorInfoW(monitor, self.ctypes.byref(info)):
                limits = self.MinMaxInfo.from_address(msg.lParam)
                limits.max_position.x = info.work.left - info.monitor.left
                limits.max_position.y = info.work.top - info.monitor.top
                limits.max_size.x = info.work.right - info.work.left
                limits.max_size.y = info.work.bottom - info.work.top
                return True, 0
        return False, 0
