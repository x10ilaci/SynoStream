"""Non-blocking update controls sharing the application's Qt theme/chrome."""
import os
from pathlib import Path
import shutil
import sys
import time

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import QCheckBox, QDialog, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QTextEdit, QVBoxLayout
import synostream_updates as updates


class UpdateWorker(QThread):
    done = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, version, manifest=None):
        super().__init__(); self.version = version; self.manifest = manifest

    def run(self):
        try:
            if self.manifest is None: result = updates.check_latest(self.version)
            else:
                result = updates.stage_package(self.manifest, cancelled=self.isInterruptionRequested,
                    progress=lambda value, total: self.progress.emit(int(value * 100 / total)))
            if self.isInterruptionRequested() and isinstance(result, dict) and 'stage' in result:
                shutil.rmtree(result['stage'], ignore_errors=True); return
            self.done.emit(result)
        except updates.Cancelled: self.failed.emit('')
        except Exception as error: self.failed.emit(str(error))


class UpdateSettingsGroup(QGroupBox):
    def __init__(self, controller):
        super().__init__(); self.controller = controller

    def retranslate_texts(self):
        self.controller.refresh_settings_texts()


class UpdateController(QObject):
    def __init__(self, window, version, config, save, run_worker, data_dir, language=lambda:'hu'):
        super().__init__(window)
        self.window = window; self.version = version; self.config = config; self.save = save
        self.run_worker = run_worker; self.data_dir = data_dir; self.language = language
        self.worker = None; self.manifest = None; self.staged = None; self.dialog = None
        self.check_button = None; self.installing = False

    def tr(self, hu, en): return en if self.language() == 'en' else hu

    def settings_group(self):
        group = UpdateSettingsGroup(self); self.group = group; layout = QVBoxLayout(group)
        self.automatic = QCheckBox(self.tr('Frissítések automatikus keresése', 'Check for updates automatically'))
        self.automatic.setChecked(bool(self.config.get('check_updates', True)))
        self.automatic.toggled.connect(self.set_automatic); layout.addWidget(self.automatic)
        self.check_button = QPushButton(self.tr('Frissítések keresése', 'Check for updates'))
        self.check_button.clicked.connect(lambda: self.check(True)); layout.addWidget(self.check_button)
        self.note = QLabel(); self.note.setWordWrap(True)
        layout.addWidget(self.note); self.refresh_settings_texts(); return group

    def refresh_settings_texts(self):
        if not hasattr(self, 'group') or self.check_button is None: return
        self.group.setTitle(self.tr('Programfrissítés', 'Application updates'))
        self.automatic.setText(self.tr('Frissítések automatikus keresése', 'Check for updates automatically'))
        self.note.setText(self.tr('Az új verzió a Letöltések mappába kerül. A beállítások megmaradnak.',
            'New versions are saved to Downloads. Your settings are retained.'))
        self.check_button.setText(self.tr('Új verzió elérhető: ', 'Update available: ') + self.manifest['version']
            if self.manifest else self.tr('Frissítések keresése', 'Check for updates'))

    def set_automatic(self, value):
        previous = self.config.get('check_updates', True); self.config['check_updates'] = value
        ok, error = self.save()
        if not ok:
            self.config['check_updates'] = previous
            self.automatic.blockSignals(True); self.automatic.setChecked(previous); self.automatic.blockSignals(False)
            QMessageBox.warning(self.window, self.tr('Mentési hiba', 'Save error'), str(error))

    def check(self, manual=False):
        if self.window.is_closing or self.installing: return
        if self.worker and self.worker.isRunning(): return
        if manual and self.staged: self.show_offer(); return
        if not manual:
            if not self.config.get('check_updates', True): return
            try: last = float(self.config.get('update_last_check', 0))
            except (ValueError, TypeError): last = 0
            if 0 <= time.time() - last < 86400: return
        worker = UpdateWorker(self.version); self.worker = worker
        self.config['update_last_check'] = time.time(); self.save()
        if self.check_button: self.check_button.setEnabled(False)
        def ready(result):
            self.config['update_last_check'] = time.time(); self.save(); self.manifest = result
            if self.window.is_closing: return
            if result:
                # Automatic discovery never interrupts playback or opens a modal.
                self.check_button.setText(self.tr('Új verzió elérhető: ', 'Update available: ') + result['version'])
                if manual: self.show_offer()
                else: self.window.statusBar().showMessage(self.tr('Új SynoStream-verzió érhető el a Beállításokban.',
                    'A SynoStream update is available in Settings.'), 15000)
            elif manual: QMessageBox.information(self.window, 'SynoStream', self.tr('A legújabb verziót használod.', 'You are using the latest version.'))
        def failed(error):
            if manual and error and not self.window.is_closing:
                QMessageBox.warning(self.window, self.tr('Frissítés', 'Update'), self.tr('A frissítés ellenőrzése nem sikerült.\n', 'Could not check for updates.\n') + error)
        worker.done.connect(ready); worker.failed.connect(failed)
        worker.finished.connect(lambda: self.check_button.setEnabled(True) if self.check_button else None)
        self.run_worker(worker)

    def show_offer(self):
        if self.dialog and self.dialog.isVisible(): self.dialog.raise_(); return
        settings = getattr(self.window, 'settings_dialog', None)
        dialog = QDialog(settings if settings and settings.isVisible() else self.window); self.dialog = dialog
        dialog.setWindowTitle(self.tr('SynoStream frissítése', 'Update SynoStream')); dialog.resize(540, 420)
        layout = QVBoxLayout(dialog); m = self.manifest or self.staged['manifest']
        layout.addWidget(QLabel(self.tr('Elérhető verzió: ', 'Available version: ') + m['version']))
        notes = QTextEdit(); notes.setReadOnly(True); notes.setPlainText(m['notes']); layout.addWidget(notes)
        self.status = QLabel(self.tr('A korábbi verzió és a beállítások megmaradnak.', 'Your previous version and settings are retained.'))
        self.status.setWordWrap(True); layout.addWidget(self.status)
        self.progress_bar = QProgressBar(); self.progress_bar.setValue(100 if self.staged else 0); layout.addWidget(self.progress_bar)
        row = QHBoxLayout(); layout.addLayout(row)
        self.download_button = QPushButton(self.tr('Letöltés', 'Download')); row.addWidget(self.download_button)
        self.download_button.clicked.connect(self.download)
        self.install_button = QPushButton(self.tr('Frissítés és újraindítás', 'Update and restart')); row.addWidget(self.install_button)
        self.install_button.setEnabled(bool(self.staged) and bool(getattr(sys, 'frozen', False)))
        self.install_button.clicked.connect(self.install)
        later = QPushButton(self.tr('Később', 'Later')); later.clicked.connect(dialog.reject); row.addWidget(later)
        dialog.finished.connect(self.cancel_download)
        if self.staged: self.download_button.setEnabled(False)
        if not getattr(sys, 'frozen', False): self.status.setText(self.tr('Az automatikus telepítés az EXE-változatban használható.', 'Automatic installation is available in the EXE build.'))
        dialog.show()

    def download(self):
        if self.worker and self.worker.isRunning(): return
        self.download_button.setEnabled(False); self.status.setText(self.tr('Letöltés és ellenőrzés…', 'Downloading and verifying…'))
        worker = UpdateWorker(self.version, self.manifest); self.worker = worker
        worker.progress.connect(self.progress_bar.setValue)
        def ready(result):
            if self.window.is_closing or not self.dialog.isVisible():
                shutil.rmtree(result['stage'], ignore_errors=True); return
            self.staged = result; self.progress_bar.setValue(100)
            self.status.setText(self.tr('A csomag ellenőrizve. Telepítésre kész.', 'Package verified. Ready to install.'))
            self.install_button.setEnabled(bool(getattr(sys, 'frozen', False)))
        def failed(error):
            self.download_button.setEnabled(True)
            if self.dialog.isVisible(): self.status.setText(error or self.tr('Letöltés megszakítva.', 'Download cancelled.'))
        worker.done.connect(ready); worker.failed.connect(failed); self.run_worker(worker)

    def cancel_download(self):
        if self.worker and self.worker.manifest is not None and self.worker.isRunning(): self.worker.requestInterruption()

    def install(self):
        if not self.staged or self.installing: return
        if any(getattr(thread, 'process', None) is not None and thread.process.poll() is None for thread in self.window.running_threads()):
            self.status.setText(self.tr('Előbb állítsd le a lejátszást.', 'Stop playback before updating.')); return
        try:
            updates.prepare_install(self.staged, sys.executable, self.data_dir)
        except Exception as error:
            self.status.setText(str(error)); return
        self.installing = True; self.dialog.accept()
        settings = getattr(self.window, 'settings_dialog', None)
        if settings and settings.isVisible(): settings.accept()
        self.window.close()
