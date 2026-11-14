"""MPV IPC monitoring; persistence and path handling are injected by the application."""
import contextlib
import json
import os
import time
from PyQt6.QtCore import QThread, pyqtSignal

class MpvPlaybackMonitor(QThread):
    watched_changed = pyqtSignal(str)
    progress_saved = pyqtSignal(str)
    startup_failed = pyqtSignal(str)

    def __init__(self, process, pipe_name, entries, resume_position=0, playlist_file=None, *, save_progress, set_watched, normalize_path, logger, source_paths=None):
        super().__init__()
        self.save_progress = save_progress
        self.set_watched = set_watched
        self.normalize_path = normalize_path
        self.logger = logger
        self.process = process
        self.pipe_name = pipe_name
        self.entries = entries
        self.playlist_file = playlist_file
        self.source_paths = list(source_paths) if source_paths is not None else [entry.get("path", "") for entry in entries]
        self.current_index = -1
        self._generation = 0
        self._pending_requests = {}
        self._next_request = 1000
        self.initial_resume_position = max(0.0, float(resume_position or 0))
        self.position = self.initial_resume_position
        self.duration = 0.0
        self._last_save = 0.0
        self._watched_notified = set()
        self._startup_confirmed = False
        self._startup_error_reported = False

    def _notify_watched_changed(self, entry):
        path = entry.get("path") or ""
        normalized_path = self.normalize_path(path)
        if normalized_path and normalized_path not in self._watched_notified:
            self._watched_notified.add(normalized_path)
            self.watched_changed.emit(path)

    def _current_entry(self):
        if 0 <= self.current_index < len(self.entries):
            return self.entries[self.current_index]
        return None

    def _save_current(self):
        entry = self._current_entry()
        if entry is not None and self.position > 0:
            remaining = [dict(row) for row in self.entries[self.current_index:] if row.get("path")]
            self.save_progress(entry, self.position, self.duration, remaining)
            self.progress_saved.emit(entry.get("path", ""))
            if self.duration > 0 and self.position >= self.duration * 0.9:
                self._notify_watched_changed(entry)

    def _mark_current_watched(self):
        entry = self._current_entry()
        if entry is None:
            return
        self.set_watched(
            entry.get("path", ""), entry.get("media_title", ""),
            entry.get("episode_title", ""), entry.get("poster", ""),
            entry.get("is_movie", True), True,
        )
        self._notify_watched_changed(entry)
        if self.duration > 0:
            self.position = self.duration
        self._save_current()

    def _fail_startup(self, message):
        self._startup_error_reported = True
        self.startup_failed.emit(message)
        if self.process.poll() is None:
            with contextlib.suppress(Exception):
                self.process.terminate()
                self.process.wait(timeout=3)
            if self.process.poll() is None:
                with contextlib.suppress(Exception):
                    self.process.kill()

    def _source_key(self, path):
        # Proxy URLs are opaque; their path/token/query must match exactly.
        if isinstance(path, str) and "://" in path:
            return path
        return self.normalize_path(path) if isinstance(path, str) else ""

    def _bind_source(self, path):
        key = self._source_key(path)
        self.current_index = next((index for index, source in enumerate(self.source_paths)
                                   if key and self._source_key(source) == key), -1)

    def _query_current_source(self, send):
        for name in ("path", "duration", "time-pos"):
            self._next_request += 1
            request_id = self._next_request
            self._pending_requests[request_id] = (self._generation, name)
            send(["get_property", name], request_id)

    def _on_message(self, message):
        pending = self._pending_requests.pop(message.get("request_id"), None)
        if pending is not None:
            generation, name = pending
            if generation != self._generation or message.get("error") != "success":
                return
            value = message.get("data")
            if name == "path":
                self._bind_source(value)
            elif name == "duration" and isinstance(value, (int, float)):
                self.duration = max(0.0, float(value))
            elif name == "time-pos" and isinstance(value, (int, float)):
                self.position = max(0.0, float(value))
            return
        event = message.get("event")
        if event == "start-file":
            self._save_current()
            self.current_index = -1
            self.position = self.duration = self._last_save = 0.0
            self._generation += 1
            self._pending_requests.clear()
        elif event == "property-change":
            name, value = message.get("name"), message.get("data")
            if name == "time-pos" and isinstance(value, (int, float)):
                self.position = max(0.0, float(value))
            elif name == "duration" and isinstance(value, (int, float)):
                self.duration = max(0.0, float(value))
            # playlist-pos is intentionally not an identity: MPV can reorder or
            # replace its list without preserving the application's indices.
        elif event == "end-file":
            if message.get("reason") == "eof":
                self._mark_current_watched()
            else:
                self._save_current()
            self.current_index = -1
            self._generation += 1
            self._pending_requests.clear()

    def run(self):
        if os.name != "nt":
            return
        handle = None
        kernel32 = None
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateFileW.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
            ]
            kernel32.CreateFileW.restype = wintypes.HANDLE
            kernel32.PeekNamedPipe.argtypes = [
                wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                ctypes.POINTER(wintypes.DWORD),
            ]
            kernel32.PeekNamedPipe.restype = wintypes.BOOL
            kernel32.ReadFile.argtypes = [
                wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
            ]
            kernel32.ReadFile.restype = wintypes.BOOL
            kernel32.WriteFile.argtypes = [
                wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
            ]
            kernel32.WriteFile.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL

            invalid_handle = ctypes.c_void_p(-1).value
            pipe_deadline = time.monotonic() + 45
            while (not self.isInterruptionRequested() and self.process.poll() is None
                   and time.monotonic() < pipe_deadline):
                handle = kernel32.CreateFileW(
                    self.pipe_name, 0xC0000000, 0, None, 3, 0x00000080, None,
                )
                if handle and handle != invalid_handle:
                    break
                handle = None
                self.msleep(250)
            if handle is None:
                if self.process.poll() is None and not self.isInterruptionRequested():
                    self._fail_startup(
                        "Az MPV elindult, de a lejátszókapcsolat 45 másodpercen belül nem jött létre."
                    )
                elif not self.isInterruptionRequested() and self.process.poll() not in (None, 0):
                    self._fail_startup("Az MPV hibával leállt, mielőtt létrejött volna a lejátszókapcsolat.")
                return

            def send(command, request_id=None):
                message = {"command": command}
                if request_id is not None:
                    message["request_id"] = request_id
                payload = (json.dumps(message) + "\n").encode("utf-8")
                raw = ctypes.create_string_buffer(payload)
                written = wintypes.DWORD()
                return bool(kernel32.WriteFile(handle, raw, len(payload), ctypes.byref(written), None)) and written.value == len(payload)

            if not all((
                send(["observe_property", 1, "time-pos"]),
                send(["observe_property", 2, "duration"]),
                send(["observe_property", 3, "playlist-pos"]),
            )):
                self._fail_startup("Nem sikerült beállítani az MPV lejátszókapcsolatát.")
                return
            loadlist_request_id = 271
            if self.playlist_file:
                # Load the potentially long episode queue only after IPC is ready.
                if not send(["loadlist", self.playlist_file, "append-play"], loadlist_request_id):
                    self._fail_startup("Nem sikerült elküldeni a lejátszólistát az MPV-nek.")
                    return
            else:
                # Direct NAS-preview playback may have loaded before IPC attached.
                # Query the live source instead of depending on a missed event.
                self._query_current_source(send)
            initial_file_loaded = False
            loadlist_deadline = time.monotonic() + 90

            buffer = b""
            while not self.isInterruptionRequested() and self.process.poll() is None:
                available = wintypes.DWORD()
                if kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None) and available.value:
                    amount = min(available.value, 65536)
                    raw = ctypes.create_string_buffer(amount)
                    read = wintypes.DWORD()
                    if kernel32.ReadFile(handle, raw, amount, ctypes.byref(read), None) and read.value:
                        buffer += raw.raw[:read.value]
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            try:
                                message = json.loads(line.decode("utf-8", errors="replace"))
                                if message.get("request_id") == loadlist_request_id:
                                    if message.get("error") != "success":
                                        self._fail_startup(
                                            "Az MPV nem tudta megnyitni a lejátszólistát."
                                        )
                                        return
                                if message.get("event") == "file-loaded":
                                    self._query_current_source(send)
                                self._on_message(message)
                                if self._current_entry() is not None and not initial_file_loaded:
                                    initial_file_loaded = True
                                    self._startup_confirmed = True
                                    if self.current_index == 0 and self.initial_resume_position > 0:
                                        send(["seek", self.initial_resume_position, "absolute+exact"])
                                    send(["set_property", "pause", False])
                            except (ValueError, TypeError):
                                continue

                now = time.monotonic()
                if self.playlist_file and now >= loadlist_deadline and not initial_file_loaded:
                    self._fail_startup(
                        "Az MPV nem tudta 90 másodpercen belül elindítani a videót."
                    )
                    return
                if now - self._last_save >= 5:
                    self._save_current()
                    self._last_save = now
                self.msleep(200)
        except Exception:
            self.logger.exception("Az MPV lejátszásfigyelése hibával leállt.")
        finally:
            if (not self._startup_confirmed and not self._startup_error_reported
                    and not self.isInterruptionRequested() and self.process.poll() not in (None, 0)):
                self._fail_startup("Az MPV hibával leállt a videó elindítása előtt.")
            self._save_current()
            if handle is not None and kernel32 is not None:
                try:
                    kernel32.CloseHandle(handle)
                except Exception:
                    pass
            if self.playlist_file:
                try:
                    os.remove(self.playlist_file)
                except FileNotFoundError:
                    pass
                except OSError:
                    self.logger.warning("Nem sikerült törölni az ideiglenes MPV-lejátszólistát.", exc_info=True)


