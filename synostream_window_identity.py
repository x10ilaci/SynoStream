"""Stable Windows identity and application-owned icon handles, independent of HWND lifetime."""
import os
import struct
from pathlib import Path
from PyQt6.QtGui import QIcon

APP_USER_MODEL_ID = 'SynoStream.Desktop'


def configure_windows_identity():
    # Must run before QApplication creates any native windows. No version in
    # the identity: releases belong to the same application/taskbar group.
    if os.name != 'nt': return False
    try:
        import ctypes
        api = ctypes.WinDLL('shell32').SetCurrentProcessExplicitAppUserModelID
        api.argtypes = [ctypes.c_wchar_p]
        api.restype = ctypes.c_long
        return api(APP_USER_MODEL_ID) == 0
    except (OSError, AttributeError):
        return False


def load_application_icon(path):
    source = QIcon(str(path))
    icon = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256):
        pixmap = source.pixmap(size, size)
        if not pixmap.isNull(): icon.addPixmap(pixmap)
    return icon if not icon.isNull() else source


def icon_frames(data):
    if len(data) < 6: return []
    reserved, kind, count = struct.unpack_from('<HHH', data)
    if reserved or kind != 1 or not 0 < count <= 64 or len(data) < 6 + count * 16: return []
    frames = []
    for index in range(count):
        width, height, _colors, _reserved, _planes, depth, length, offset = struct.unpack_from('<BBBBHHII', data, 6 + index * 16)
        if length and offset >= 6 + count * 16 and offset + length <= len(data):
            frames.append((max(width or 256, height or 256), depth, data[offset:offset + length]))
    return frames


class WindowsWindowIcons:
    def __init__(self, icon_path):
        import ctypes
        from ctypes import wintypes
        self.ctypes = ctypes
        try: self.frames = icon_frames(Path(icon_path).read_bytes())
        except (OSError, TypeError): self.frames = []
        self.handles = {}; self.closed = False
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.user32.CreateIconFromResourceEx.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.BOOL,
                                                        wintypes.DWORD, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.user32.CreateIconFromResourceEx.restype = wintypes.HANDLE
        self.user32.DestroyIcon.argtypes = [wintypes.HANDLE]
        self.user32.DestroyIcon.restype = wintypes.BOOL
        self.user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.SendMessageW.restype = ctypes.c_ssize_t
        self.user32.IsWindow.argtypes = [wintypes.HWND]; self.user32.IsWindow.restype = wintypes.BOOL
        self.user32.GetSystemMetrics.argtypes = [ctypes.c_int]; self.user32.GetSystemMetrics.restype = ctypes.c_int
        if hasattr(self.user32, 'GetDpiForWindow'):
            self.user32.GetDpiForWindow.argtypes = [wintypes.HWND]; self.user32.GetDpiForWindow.restype = wintypes.UINT
        if hasattr(self.user32, 'GetSystemMetricsForDpi'):
            self.user32.GetSystemMetricsForDpi.argtypes = [ctypes.c_int, wintypes.UINT]
            self.user32.GetSystemMetricsForDpi.restype = ctypes.c_int

    def handle(self, size):
        if self.closed or not self.frames: return 0
        size = max(16, min(256, int(size)))
        if size not in self.handles:
            _width, _depth, data = min(self.frames, key=lambda f:(f[0] < size, abs(f[0] - size), -f[1]))
            buffer = self.ctypes.create_string_buffer(data)
            handle = self.user32.CreateIconFromResourceEx(buffer, len(data), True, 0x00030000, size, size, 0)
            if handle: self.handles[size] = int(handle)
        return self.handles.get(size, 0)

    def expected(self, hwnd):
        dpi = (self.user32.GetDpiForWindow(hwnd) or 96) if hasattr(self.user32, 'GetDpiForWindow') else 96
        def metric(index):
            value = self.user32.GetSystemMetricsForDpi(index, dpi) if hasattr(self.user32, 'GetSystemMetricsForDpi') else self.user32.GetSystemMetrics(index)
            return value or (16 if index == 49 else 32)
        return self.handle(metric(49)), self.handle(metric(11))

    def ensure(self, hwnd):
        if self.closed or not hwnd or not self.user32.IsWindow(hwnd): return
        small, big = self.expected(hwnd)
        for kind, handle in ((0, small), (1, big)):
            if handle and self.user32.SendMessageW(hwnd, 0x007F, kind, 0) != handle:
                self.user32.SendMessageW(hwnd, 0x0080, kind, handle)

    def close(self):
        if self.closed: return
        self.closed = True
        # Qt owns its own icon handles. Only these application-created handles
        # are destroyed, once all managed native windows have been destroyed.
        for handle in set(self.handles.values()): self.user32.DestroyIcon(handle)
        self.handles.clear()
