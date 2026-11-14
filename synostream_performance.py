"""Bounded GUI image cache and synchronized playback display snapshots."""
from collections import OrderedDict
from contextlib import closing, suppress
import os
import re
import sqlite3
import threading

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QImageReader, QPixmap


class PosterPixmapCache:
    # GUI-thread only. Keys include the file generation and requested display size.
    def __init__(self, max_bytes=64 * 1024 * 1024, managed_directory=None):
        self.managed_directory = managed_directory
        self.max_bytes = max_bytes
        self.entries = OrderedDict()
        self.bytes_used = 0
        self.decodes = 0

    def clear(self):
        self.entries.clear()
        self.bytes_used = 0

    def load(self, path, width, height):
        if not path:
            return None
        try:
            info = os.stat(path)
        except OSError:
            return None
        key = (path, info.st_mtime_ns, info.st_size, width, height)
        if key in self.entries:
            pixmap, cost = self.entries.pop(key)
            self.entries[key] = pixmap, cost
            return pixmap
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid():
            reader.setScaledSize(size.scaled(QSize(width, height), Qt.AspectRatioMode.KeepAspectRatio))
        image = reader.read()
        self.decodes += 1
        if image.isNull():
            del reader  # Release Qt's file handle before removing a corrupt image on Windows.
            with suppress(OSError, ValueError):
                target = os.path.realpath(path)
                directory = os.path.realpath(self.managed_directory) if self.managed_directory else None
                if (directory and os.path.commonpath([directory, target]) == directory
                        and re.fullmatch(r"(?:movie|tv)_\d+\.jpg", os.path.basename(path), re.I)):
                    os.remove(path)
            return None
        pixmap = QPixmap.fromImage(image).scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation)
        cost = pixmap.width() * pixmap.height() * max(1, pixmap.depth() // 8)
        if cost <= self.max_bytes:
            while self.entries and self.bytes_used + cost > self.max_bytes:
                _, (_, old_cost) = self.entries.popitem(last=False)
                self.bytes_used -= old_cost
            self.entries[key] = pixmap, cost
            self.bytes_used += cost
        return pixmap


class PlaybackDisplaySnapshot:
    def __init__(self):
        self.lock = threading.RLock()
        self.database = None
        self.states = {}
        self.loads = 0

    def clear(self):
        with self.lock:
            self.database = None
            self.states = {}

    @staticmethod
    def _state(row):
        return dict(position=float(row[0] or 0), duration=float(row[1] or 0), watched=bool(row[2]))

    def get(self, database, path):
        with self.lock:
            if self.database != database:
                with closing(sqlite3.connect(database, timeout=10)) as conn:
                    rows = conn.execute('SELECT file_path,position,duration,watched FROM playback_state').fetchall()
                self.states = {row[0]: self._state(row[1:]) for row in rows}
                self.database = database
                self.loads += 1
            return dict(self.states.get(path, {}))

    def update(self, database, path, connection):
        with self.lock:
            if self.database != database:
                return
            row = connection.execute('SELECT position,duration,watched FROM playback_state WHERE file_path=?',
                                     (path,)).fetchone()
            if row:
                self.states[path] = self._state(row)
            else:
                self.states.pop(path, None)


# Three shared, code-drawn placeholders; no per-title image files or downloads.
from functools import lru_cache
import hashlib
from PyQt6.QtCore import QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QLinearGradient, QPen, QPolygonF

POSTER_PALETTES = (
    ('#66506E', '#281C31'),  # dusty purple
    ('#356066', '#10292D'),  # petrol teal
    ('#68394D', '#301623'),  # muted burgundy
)


def placeholder_variant(identity):
    # Stable pseudo-random choice: independent of Python's per-process hash seed.
    digest = hashlib.sha256(str(identity or '').encode('utf-8')).digest()
    return int.from_bytes(digest[:8], 'big') % len(POSTER_PALETTES)


@lru_cache(maxsize=36)
def _paint_placeholder(variant, width, height):
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        bounds = QRectF(0, 0, width, height)
        radius = min(width, height) * .038
        clip = QPainterPath()
        clip.addRoundedRect(bounds, radius, radius)
        painter.setClipPath(clip)
        gradient = QLinearGradient(0, 0, width, height)
        gradient.setColorAt(0, QColor(POSTER_PALETTES[variant][0]))
        gradient.setColorAt(1, QColor(POSTER_PALETTES[variant][1]))
        painter.fillRect(bounds, gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 15))
        painter.drawPolygon(QPolygonF([QPointF(0, height*.67), QPointF(width, height*.12),
                                       QPointF(width, height*.65), QPointF(width*.35, height)]))
        painter.setBrush(QColor(255, 255, 255, 5))
        painter.drawPolygon(QPolygonF([QPointF(0, height*.94), QPointF(width, height*.44),
                                       QPointF(width, height*.52), QPointF(0, height)]))
        # Small translucent film-frame symbol, matching the approved concept.
        icon_width = width * .28
        icon_height = icon_width * .74
        left, top = (width-icon_width)/2, (height-icon_height)/2
        stroke = max(1.2, width*.012)
        painter.setPen(QPen(QColor(235, 226, 240, 63), stroke))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(left, top, icon_width, icon_height), stroke, stroke)
        rail = icon_width * .16
        painter.drawLine(QPointF(left+rail, top), QPointF(left+rail, top+icon_height))
        painter.drawLine(QPointF(left+icon_width-rail, top), QPointF(left+icon_width-rail, top+icon_height))
        for i in range(1, 4):
            y = top + icon_height*i/4
            painter.drawLine(QPointF(left, y), QPointF(left+rail, y))
            painter.drawLine(QPointF(left+icon_width-rail, y), QPointF(left+icon_width, y))
    finally:
        painter.end()
    return pixmap


def placeholder_pixmap(identity, width, height):
    return _paint_placeholder(placeholder_variant(identity), max(1, int(width)), max(1, int(height)))
