"""Poster-based recommendations; every network operation runs in a worker."""
import os
from PyQt6.QtCore import Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabBar, QScrollArea, QWidget, QGridLayout, QPlainTextEdit)
from synostream_recommendations import identity, BATCH_SIZE


class PosterBatch(QThread):
    ready = pyqtSignal(int, object, str)
    def __init__(self, generation, items, fetch):
        super().__init__()
        self.generation, self.items, self.fetch = generation, list(items), fetch
    def run(self):
        for item in self.items:
            if self.isInterruptionRequested(): return
            key = identity(item)
            if not key: continue
            try: path = self.fetch(item.get('poster_url'), key[1], key[0] == 'movie', self.isInterruptionRequested)
            except Exception: path = None
            if path and not self.isInterruptionRequested(): self.ready.emit(self.generation, key, str(path))


class RecommendationsDialog(QDialog):
    def __init__(self, parent, library_id, name, store, context, request, language,
                 run_worker, task_factory, fetch_poster, placeholder, logo_path, translate=lambda s:s, edit_menu=lambda w:None, prefer_hungarian=False):
        super().__init__(parent)
        self.library_id, self.store, self.context = library_id, store, context
        self.request, self.language, self.run_worker, self.task_factory = request, language, run_worker, task_factory
        self.fetch_poster, self.placeholder, self.logo_path, self.t = fetch_poster, placeholder, logo_path, translate
        self.prefer_hungarian = bool(prefer_hungarian)
        self.edit_menu = edit_menu
        self._closing = False; self._worker = None; self._poster_worker = None; self._poster_pending = None
        self._generation = 0; self._poster_labels = {}; self._poster_paths = {}
        self.pool = {}; self.batch = []; self._previous = set(); self._page = 0; self._columns = 0
        self.setWindowTitle(translate('Ajánló') + ' – ' + name)
        self.resize(1040, 780); self.setMinimumSize(740, 560)
        layout = QVBoxLayout(self); layout.setContentsMargins(22, 16, 22, 16)
        title = QLabel(translate('Ajánlatok a médiatárad alapján') + ' – ' + name)
        title.setObjectName('PageTitle'); title.setWordWrap(True); layout.addWidget(title)
        info = QLabel(translate('Médiatáranként külön válogatás. A már meglévő műsorokat az összes médiatárból kiszűrjük.'))
        info.setWordWrap(True); layout.addWidget(info)
        toolbar = QHBoxLayout(); layout.addLayout(toolbar)
        self.tabs = QTabBar()
        for text in ('Fedezz fel', 'Érdekel', 'Elrejtve'): self.tabs.addTab(translate(text))
        self.tabs.currentChanged.connect(self.switch_tab); toolbar.addWidget(self.tabs); toolbar.addStretch()
        self.next_button = QPushButton(translate('Új válogatás')); self.next_button.clicked.connect(self.next_batch)
        toolbar.addWidget(self.next_button)
        self.status = QLabel(); self.status.setWordWrap(True); self.status.setTextFormat(Qt.TextFormat.PlainText); layout.addWidget(self.status)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); layout.addWidget(self.scroll, 1)
        self.content = QWidget(); self.grid = QGridLayout(self.content)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.grid.setSpacing(16); self.scroll.setWidget(self.content)
        bottom = QHBoxLayout(); layout.addLayout(bottom)
        attribution = QPushButton(translate('Adatforrás: TMDB')); attribution.clicked.connect(self.credits)
        bottom.addWidget(attribution); bottom.addStretch()
        close = QPushButton(translate('Bezárás')); close.clicked.connect(self.reject); bottom.addWidget(close)
        self.poll = QTimer(self); self.poll.setInterval(3000); self.poll.timeout.connect(self.filter_owned); self.poll.start()
        self._resize_timer = QTimer(self); self._resize_timer.setSingleShot(True); self._resize_timer.setInterval(100)
        self._resize_timer.timeout.connect(self.reflow)
        QTimer.singleShot(0, self.start)

    def start(self):
        if self._closing: return
        try:
            context = self.context()
            seeds = context['seeds']
            if not seeds:
                self.status.setText(self.t('Ebben a médiatárban még nincs azonosított műsor. Előbb frissítsd a médiatárat vagy add meg a médiainformációkat.'))
                self.next_button.setEnabled(False); return
            self.pool, _ = self.store.pool(self.library_id, seeds, self.language)
            self.batch = self.store.draw(self.library_id, self.pool, context['owned'], prefer_hungarian=self.prefer_hungarian)
            if self.batch: self.store.mark_seen(self.library_id, self.batch)
            self.render()
            self.load()
        except Exception:
            self.status.setText(self.t('Az ajánló helyi adatainak betöltése nem sikerült.'))

    def load(self):
        if self._closing or self._worker is not None: return
        try: context = self.context()
        except Exception:
            self.failed(''); return
        if not context['seeds']: return
        previous = {identity(item) for item in self.batch}
        self.next_button.setEnabled(False)
        self.status.setText(self.t('Ajánlások frissítése… A korábbi válogatás közben is böngészhető.'))
        worker = self.task_factory(lambda stop:self.store.load(self.library_id, context['seeds'], context['owned'],
            self.language, self.request, stop, previous, prefer_hungarian=self.prefer_hungarian))
        self._worker = worker
        worker.succeeded.connect(lambda result:self.loaded(result, previous))
        worker.failed.connect(self.failed)
        worker.finished.connect(self.load_finished)
        self.run_worker(worker)

    def loaded(self, result, previous):
        if self._closing: return
        try:
            self.pool = result['pool']
            owned = self.context()['owned']
            self.batch = self.store.draw(self.library_id, self.pool, owned, previous, prefer_hungarian=self.prefer_hungarian)
            self.store.mark_seen(self.library_id, self.batch)
            self.status.setText(self.t('Ajánlások alapjául szolgáló műsorok: {count}.').format(count=result['seed_count']))
            if result['errors']:
                self.status.setText(self.t('A TMDB-frissítés egy része nem sikerült. A mentett ajánlások továbbra is böngészhetők.'))
            if not self.batch and not result['errors']:
                self.status.setText(self.t('Ebben a válogatásban nincs új találat. Az Új válogatás további műsorokból is kereshet ajánlásokat.'))
            self.render()
        except Exception:
            self.failed('')

    def failed(self, message):
        if not self._closing:
            self.status.setText(self.t('Az ajánlások frissítése nem sikerült. Ellenőrizd a TMDB-kulcsot és az internetkapcsolatot.'))

    def load_finished(self):
        self._worker = None
        if not self._closing: self.next_button.setEnabled(True)

    def next_batch(self):
        if self.tabs.currentIndex() == 0: self.load()
        else: self._page += 1; self.render()

    def switch_tab(self, index):
        self._page = 0
        self.next_button.setText(self.t('Új válogatás' if index == 0 else 'Következő oldal'))
        self.next_button.setEnabled(index != 0 or self._worker is None)
        self.render()

    def visible_items(self):
        owned = self.context()['owned']
        feedback = self.store.feedback(self.library_id)
        mode = self.tabs.currentIndex()
        if mode == 0:
            return [item for item in self.batch if identity(item) not in owned and identity(item) not in feedback]
        state = 'interested' if mode == 1 else 'dismissed'
        items = [item for key, (status, item) in feedback.items() if status == state and key not in owned]
        pages = max(1, (len(items) + BATCH_SIZE - 1) // BATCH_SIZE)
        self._page %= pages
        return items[self._page * BATCH_SIZE:(self._page + 1) * BATCH_SIZE]

    def filter_owned(self):
        if self._closing: return
        try:
            if self.tabs.currentIndex() == 0 and self._worker is None:
                self.next_button.setEnabled(bool(self.context()['seeds']))
            keys = tuple(identity(item) for item in self.visible_items())
            if keys != getattr(self, '_visible_keys', ()): self.render()
        except Exception: pass

    def render(self):
        if self._closing: return
        try: items = self.visible_items()
        except Exception:
            self.status.setText(self.t('Az ajánló helyi adatainak betöltése nem sikerült.')); return
        self._visible_keys = tuple(identity(item) for item in items)
        self._generation += 1; self._poster_labels = {}
        while self.grid.count():
            entry = self.grid.takeAt(0)
            if entry.widget(): entry.widget().deleteLater()
        self._columns = max(1, min(4, (self.scroll.viewport().width() - 16) // 225))
        if not items:
            empty = QLabel(self.t('Itt még nincs megjeleníthető műsor.')); empty.setWordWrap(True)
            self.grid.addWidget(empty, 0, 0)
        for index, item in enumerate(items):
            self.grid.addWidget(self.make_card(item), index // self._columns, index % self._columns)
        self.scroll.verticalScrollBar().setValue(0)
        self._poster_pending = (self._generation, items)
        if self._poster_worker is not None: self._poster_worker.requestInterruption()
        else: self.start_posters()

    def make_card(self, item):
        card = QWidget(); card.setObjectName('RecommendationCard'); card.setFixedWidth(210)
        card.setStyleSheet('QWidget#RecommendationCard { background:#242128; border:1px solid #403a48; border-radius:9px; }')
        layout = QVBoxLayout(card); layout.setContentsMargins(10, 10, 10, 10)
        poster = QLabel(); poster.setAlignment(Qt.AlignmentFlag.AlignCenter); poster.setFixedSize(190, 260)
        key = identity(item); self._poster_labels[key] = poster
        path = self._poster_paths.get(key)
        pixmap = QPixmap(path) if path and os.path.isfile(path) else QPixmap()
        if pixmap.isNull(): pixmap = self.placeholder(str(key), 190, 260)
        poster.setPixmap(pixmap.scaled(190, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)); layout.addWidget(poster)
        title = QLabel(item['title']); title.setTextFormat(Qt.TextFormat.PlainText); title.setWordWrap(True)
        title.setStyleSheet('font-weight:600; font-size:14px;'); layout.addWidget(title)
        kind = self.t('Film' if key[0] == 'movie' else 'Sorozat')
        date = str(item.get('date') or '')[:4]
        layout.addWidget(QLabel(kind + (' · ' + date if date else '')))
        if self.prefer_hungarian and item.get('has_hu_metadata') is True:
            badge = QLabel(self.t('Magyar adatlap'))
            badge.setStyleSheet('color:#c5b1d7; font-size:11px;')
            badge.setToolTip(self.t('Magyar leírás található a TMDB-n. Ez nem igazolja a szinkront.'))
            layout.addWidget(badge)
        reasons = item.get('reasons') or []
        if reasons:
            why = QLabel(self.t('Ez alapján:') + ' ' + ', '.join(reasons[:2]))
            why.setTextFormat(Qt.TextFormat.PlainText); why.setWordWrap(True); why.setStyleSheet('color:#b4a8c0; font-size:11px;')
            layout.addWidget(why)
        layout.addStretch()
        details = QPushButton(self.t('Részletek')); details.clicked.connect(lambda:self.details(item)); layout.addWidget(details)
        mode = self.tabs.currentIndex()
        primary = QPushButton(self.t('Érdekel' if mode == 0 else 'Eltávolítás a listáról' if mode == 1 else 'Visszaállítás'))
        primary.clicked.connect(lambda:self.feedback(item, 'interested' if mode == 0 else 'neutral')); layout.addWidget(primary)
        if mode != 2:
            dismiss = QPushButton(self.t('Nem érdekel')); dismiss.clicked.connect(lambda:self.feedback(item, 'dismissed')); layout.addWidget(dismiss)
        return card

    def feedback(self, item, state):
        try:
            self.store.set_feedback(self.library_id, item, state)
            self.render()
        except Exception:
            self.status.setText(self.t('A visszajelzés mentése nem sikerült.'))

    def details(self, item):
        dialog = QDialog(self); dialog.setWindowTitle(item['title']); dialog.resize(620, 460)
        layout = QVBoxLayout(dialog)
        title = QLabel(item['title']); title.setTextFormat(Qt.TextFormat.PlainText); title.setWordWrap(True); title.setObjectName('PageTitle'); layout.addWidget(title)
        text = QPlainTextEdit(); text.setReadOnly(True); self.edit_menu(text); text.setPlainText(item.get('overview') or self.t('Ehhez a műsorhoz nincs elérhető leírás.')); layout.addWidget(text)
        link = QPushButton(self.t('Megnyitás a TMDB-n'))
        kind, media_id = identity(item)
        link.clicked.connect(lambda:QDesktopServices.openUrl(QUrl(f'https://www.themoviedb.org/{kind}/{media_id}'))); layout.addWidget(link)
        close = QPushButton(self.t('Bezárás')); close.clicked.connect(dialog.reject); layout.addWidget(close)
        dialog.exec(); dialog.deleteLater()

    def credits(self):
        dialog = QDialog(self); dialog.setWindowTitle(self.t('Adatforrás: TMDB')); dialog.resize(540, 230)
        layout = QVBoxLayout(dialog)
        logo = QLabel(); pixmap = QPixmap(self.logo_path)
        if not pixmap.isNull(): logo.setPixmap(pixmap.scaledToWidth(160, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(logo)
        label = QLabel('This product uses the TMDB API but is not endorsed or certified by TMDB.'); label.setWordWrap(True); layout.addWidget(label)
        website = QLabel('<a href="https://www.themoviedb.org">The Movie Database</a>'); website.setOpenExternalLinks(True); layout.addWidget(website)
        close = QPushButton(self.t('Bezárás')); close.clicked.connect(dialog.reject); layout.addWidget(close)
        dialog.exec(); dialog.deleteLater()

    def start_posters(self):
        if self._closing or not self._poster_pending: return
        generation, items = self._poster_pending; self._poster_pending = None
        worker = PosterBatch(generation, items, self.fetch_poster); self._poster_worker = worker
        worker.ready.connect(self.poster_ready); worker.finished.connect(self.posters_finished); self.run_worker(worker)

    def posters_finished(self):
        self._poster_worker = None
        if not self._closing: self.start_posters()

    def poster_ready(self, generation, key, path):
        if self._closing or generation != self._generation: return
        label = self._poster_labels.get(key)
        if label is not None:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self._poster_paths[key] = path
                label.setPixmap(pixmap.scaled(190, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_resize_timer'): self._resize_timer.start()

    def reflow(self):
        columns = max(1, min(4, (self.scroll.viewport().width() - 16) // 225))
        if columns != self._columns: self.render()

    def done(self, result):
        self._closing = True; self.poll.stop(); self._resize_timer.stop(); self._poster_pending = None
        for worker in (self._worker, self._poster_worker):
            if worker is not None: worker.requestInterruption()
        super().done(result)

    def closeEvent(self, event):
        self.done(QDialog.DialogCode.Rejected); event.accept()
