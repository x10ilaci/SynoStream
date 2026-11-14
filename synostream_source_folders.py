"""One staged editor for local, NAS and paired library folders."""
import copy
import ntpath
import sqlite3
import uuid
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QComboBox, QDialogButtonBox, QFormLayout, QLineEdit, QWidget, QInputDialog, QMessageBox)
from synostream_sources import SourceRouter, parse_pairs, remote_root, expand_mapped_path


class SourcesBusy(RuntimeError):
    """Saving must wait until source-dependent background work has drained."""


class FolderMigrationRouter(SourceRouter):
    """Also preserve history when an existing paired source becomes local-only."""
    def __init__(self, records):
        super().__init__(parse_pairs([r for r in records if r['local_root'] and r['remote_root']]))
        self.local_only = {r['id']: r['local_root'] for r in records if r['local_root'] and not r['remote_root']}

    def rebase(self, path, previous):
        canonical = previous.canonical(path)
        for old in getattr(previous, 'pairs', ()):
            local = self.local_only.get(old.id)
            if local and isinstance(canonical, str) and (canonical == old.remote or canonical.startswith(old.remote + '/')):
                relative = canonical[len(old.remote):].strip('/')
                return ntpath.join(local, *relative.split('/')) if relative else local
        return super().rebase(path, previous)


def clean_records(records):
    result = []
    seen_ids = set()
    for original in records:
        row = {key: str(original.get(key) or '').strip() for key in ('id', 'library_id', 'local_root', 'remote_root')}
        row['id'] = row['id'] or uuid.uuid4().hex
        if row['id'] in seen_ids: raise ValueError('Egy forrásmappa kétszer szerepel a listában.')
        seen_ids.add(row['id'])
        if not row['library_id']: raise ValueError('Válassz médiatárat.')
        local = row['local_root'].strip('"')
        if local and row['remote_root']: local = expand_mapped_path(local)
        if local:
            if not ntpath.isabs(local) or local.startswith(('\\\\?\\', '\\\\.\\')):
                raise ValueError('Teljes helyi vagy hálózati mappaútvonalat adj meg.')
            local = ntpath.normpath(local)
            if local.startswith('\\\\') and len([part for part in local.split('\\') if part]) < 2:
                raise ValueError('Válassz egy megosztott mappát a hálózati gépen.')
        row['local_root'] = local
        if row['remote_root']: row['remote_root'] = remote_root(row['remote_root'])
        if not local and not row['remote_root']: raise ValueError('Válassz legalább egy forrásmappát.')
        result.append(row)
    pairs = parse_pairs([row for row in result if row['local_root'] and row['remote_root']])
    router = SourceRouter(pairs)
    seen = set()
    for row in result:
        root = router.canonical(row['remote_root'] or row['local_root'])
        key = (row['library_id'], root if root.startswith('syno://') else ntpath.normcase(root))
        if key in seen: raise ValueError('Ez a mappa már szerepel ebben a médiatárban.')
        seen.add(key)
    return result


def records_from_settings(settings, libraries):
    pairs = parse_pairs(settings.get('paired_sources', []))
    router = SourceRouter(pairs)
    records = []
    for identifier, _name in libraries:
        if identifier in ('movies', 'shows'):
            paths = settings.get(identifier + '_paths')
            if not isinstance(paths, list): paths = [settings.get(identifier + '_path', '')]
            paths = list(paths)
            if settings.get('remote_' + identifier + '_path'):
                paths.append('syno://' + settings['remote_' + identifier + '_path'])
        else:
            lib = next((lib for lib in settings.get('custom_libraries', []) if lib['id'] == identifier), {})
            paths = list(lib.get('paths', []))
        paths.extend(pair.remote for pair in pairs if pair.library_id == identifier)
        seen = set()
        for path in paths:
            if not isinstance(path, str) or not path.strip(): continue
            canonical = router.canonical(path.strip())
            key = canonical if canonical.startswith('syno://') else ntpath.normcase(ntpath.normpath(canonical))
            if key in seen: continue
            seen.add(key)
            pair = next((p for p in pairs if p.library_id == identifier and p.remote == canonical), None)
            if pair: records.append(pair.to_dict())
            else:
                records.append(dict(id=uuid.uuid4().hex, library_id=identifier,
                    local_root='' if canonical.startswith('syno://') else path,
                    remote_root=canonical if canonical.startswith('syno://') else ''))
    return records


def suggested_pair(records):
    """Suggest only exact SMB share/subfolder matches; confirmation is required."""
    for left, local in enumerate(records):
        if not local.get('local_root') or local.get('remote_root'): continue
        expanded = expand_mapped_path(local['local_root']).replace('\\', '/')
        if not expanded.startswith('//'): continue
        parts = [part for part in expanded.split('/') if part]
        if len(parts) < 2: continue
        suffix = '/'.join(parts[1:]).casefold()
        candidates = [right for right, remote in enumerate(records)
            if remote.get('library_id') == local.get('library_id') and remote.get('remote_root')
            and not remote.get('local_root') and remote['remote_root'][7:].strip('/').casefold() == suffix]
        if len(candidates) == 1: return left, candidates[0]
    return None


def combine_records(records, local_index, remote_index):
    result = copy.deepcopy(records)
    result[remote_index]['local_root'] = result[local_index]['local_root']
    result.pop(local_index)
    return clean_records(result)


class SourceFolderDialog(QDialog):
    def __init__(self, parent, row, browse_local, browse_nas, translate=lambda s:s, edit_menu=lambda w:None, text_prompt=QInputDialog.getText):
        super().__init__(parent)
        self.row = dict(row)
        self.t, self.text_prompt = translate, text_prompt
        self.setWindowTitle(translate('Forrásmappa'))
        self.resize(700, 330)
        layout = QVBoxLayout(self)
        intro = QLabel(translate('Tallózd be a mappát ezen a gépen vagy a NAS-on. Ugyanahhoz a mappához mindkét elérést is megadhatod.'))
        intro.setWordWrap(True); layout.addWidget(intro)
        form = QFormLayout(); layout.addLayout(form)
        self.local = QLineEdit(row.get('local_root', '')); self.local.setReadOnly(True)
        self.remote = QLineEdit(row.get('remote_root', '')); self.remote.setReadOnly(True)
        edit_menu(self.local); edit_menu(self.remote)
        for field, label, button_text, browser in (
            (self.local, 'Ezen a gépen / helyi hálózaton:', 'Helyi mappa tallózása…', browse_local),
            (self.remote, 'A NAS-on:', 'NAS-mappa tallózása…', browse_nas)):
            widget = QWidget(); line = QHBoxLayout(widget); line.setContentsMargins(0,0,0,0)
            line.addWidget(field, 1)
            browse = QPushButton(translate(button_text)); line.addWidget(browse)
            browse.clicked.connect(lambda _=False, f=field, b=browser: self.browse(f, b))
            clear = QPushButton(translate('Törlés')); line.addWidget(clear); clear.clicked.connect(field.clear)
            form.addRow(translate(label), widget)
        note = QLabel(translate('Ha mindkét elérés meg van adva, az elérhető helyi hálózati kapcsolatot használjuk, egyébként a NAS-kapcsolatot. Csak ugyanannak a mappának a két elérését válaszd ki.'))
        note.setWordWrap(True); layout.addWidget(note)
        manual = QPushButton(translate('Útvonal megadása kézzel…')); layout.addWidget(manual)
        manual.clicked.connect(self.manual)
        self.error = QLabel(); self.error.setWordWrap(True); self.error.setStyleSheet('color:#e9a8a8'); layout.addWidget(self.error)
        buttons = QDialogButtonBox()
        buttons.addButton(translate('Kész'), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(translate('Mégse'), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def browse(self, field, browser):
        value = browser(self)
        if value: field.setText(value); self.error.clear()

    def manual(self):
        value, ok = self.text_prompt(self, self.t('Útvonal megadása'), self.t('Helyi, hálózati vagy syno:/// mappaútvonal:'))
        if ok and value.strip():
            field = self.remote if value.strip().startswith(('syno://', '/')) else self.local
            field.setText(value.strip().strip('"'))

    def accept(self):
        try:
            self.row = clean_records([dict(self.row, local_root=self.local.text(), remote_root=self.remote.text())])[0]
        except ValueError as error: self.error.setText(self.t(str(error))); return
        super().accept()


class SourceFoldersDialog(QDialog):
    def __init__(self, parent, records, libraries, save, browse_local, browse_nas, translate=lambda s:s, selected=None, edit_menu=lambda w:None, text_prompt=QInputDialog.getText):
        super().__init__(parent)
        self.values = copy.deepcopy(records)
        self._pending_save = None
        self._save_timer = QTimer(self)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._try_save)
        self.edit_menu, self.text_prompt = edit_menu, text_prompt
        self.save_sources, self.browse_local, self.browse_nas, self.t = save, browse_local, browse_nas, translate
        self.setWindowTitle(translate('Médiatárak – forrásmappák'))
        self.resize(880, 560); self.setMinimumSize(720, 440)
        layout = QVBoxLayout(self)
        intro = QLabel(translate('Válassz médiatárat, majd tallózással adj hozzá forrásmappát. A helyi és a NAS-elérés egy sorban kezelhető.'))
        intro.setWordWrap(True); layout.addWidget(intro)
        self.library = QComboBox()
        for identifier, name in libraries: self.library.addItem(name, identifier)
        if selected: self.library.setCurrentIndex(max(0, self.library.findData(selected)))
        layout.addWidget(self.library)
        self.listing = QListWidget(); layout.addWidget(self.listing, 1)
        row = QHBoxLayout(); layout.addLayout(row)
        self.add = QPushButton(translate('Mappa hozzáadása')); self.edit = QPushButton(translate('Módosítás')); self.remove = QPushButton(translate('Eltávolítás'))
        for button in (self.add, self.edit, self.remove): row.addWidget(button)
        self.add.clicked.connect(lambda:self.edit_folder(False)); self.edit.clicked.connect(lambda:self.edit_folder(True)); self.remove.clicked.connect(self.remove_folder)
        self.listing.itemDoubleClicked.connect(lambda _:self.edit_folder(True))
        self.library.currentIndexChanged.connect(self.refresh)
        self.listing.currentRowChanged.connect(self.selection_changed)
        self.error = QLabel(); self.error.setWordWrap(True); self.error.setStyleSheet('color:#e9a8a8'); layout.addWidget(self.error)
        buttons = QDialogButtonBox()
        buttons.addButton(translate('Mentés'), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(translate('Mégse'), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.buttons = buttons
        self.refresh()

    def selection_changed(self, index):
        self.edit.setEnabled(index >= 0); self.remove.setEnabled(index >= 0)

    def refresh(self):
        self.listing.clear()
        self.indices = [i for i,row in enumerate(self.values) if row['library_id'] == self.library.currentData()]
        for index in self.indices:
            row = self.values[index]
            parts = []
            if row.get('local_root'): parts.append(self.t('Helyi:') + ' ' + row['local_root'])
            if row.get('remote_root'): parts.append(self.t('NAS:') + ' ' + row['remote_root'])
            self.listing.addItem('\n'.join(parts))
        self.selection_changed(-1)

    def edit_folder(self, existing):
        selected = self.listing.currentRow()
        index = self.indices[selected] if existing and selected >= 0 else None
        if existing and index is None: return
        value = self.values[index] if index is not None else dict(id=uuid.uuid4().hex, library_id=self.library.currentData())
        dialog = SourceFolderDialog(self, value, self.browse_local, self.browse_nas, self.t, self.edit_menu, self.text_prompt)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted: return
            proposed = copy.deepcopy(self.values)
            if index is None: proposed.append(dialog.row)
            else: proposed[index] = dialog.row
            self.values = clean_records(proposed)
            self.error.clear(); self.refresh()
        except ValueError as error: self.error.setText(self.t(str(error)))
        finally: dialog.deleteLater()

    def remove_folder(self):
        selected = self.listing.currentRow()
        if selected >= 0: self.values.pop(self.indices[selected]); self.refresh()

    def accept(self):
        if self._pending_save is not None: return
        try:
            proposed = clean_records(self.values)
            while (match := suggested_pair(proposed)) is not None:
                local, remote = (proposed[index] for index in match)
                answer = QMessageBox.question(self, self.t('Ugyanaz a forrásmappa?'),
                    self.t('Ez a helyi hálózati mappa a megadott NAS-mappa másik elérése?') +
                    '\n\n' + local['local_root'] + '\n' + remote['remote_root'] + '\n\n' +
                    self.t('Összerendeléskor egy példányban jelennek meg a műsorok, és az elérhető helyi kapcsolatot használjuk.'),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes)
                if answer == QMessageBox.StandardButton.Cancel: return
                if answer == QMessageBox.StandardButton.No: break
                proposed = combine_records(proposed, *match)
            # Preserve the approved pairing even when the first save is busy.
            self.values = proposed
            self.refresh()
            self._pending_save = proposed
        except (ValueError, OSError, RuntimeError, sqlite3.Error) as error: self.error.setText(self.t(str(error))); return
        self._try_save()

    def _waiting(self, waiting):
        for widget in (self.library, self.listing, self.add): widget.setEnabled(not waiting)
        self.edit.setEnabled(not waiting and self.listing.currentRow() >= 0)
        self.remove.setEnabled(not waiting and self.listing.currentRow() >= 0)
        for button in self.buttons.buttons():
            if self.buttons.buttonRole(button) == QDialogButtonBox.ButtonRole.AcceptRole: button.setEnabled(not waiting)

    def _try_save(self):
        if self._pending_save is None: return
        try:
            self.save_sources(self._pending_save)
        except SourcesBusy:
            self.error.setStyleSheet('color:#c5b1d7')
            self.error.setText(self.t('A háttérművelet befejezésére várunk. A jóváhagyott módosításokat utána automatikusan mentjük. Lejátszás esetén előbb zárd be a lejátszót.'))
            self._waiting(True); self._save_timer.start(); return
        except (ValueError, OSError, RuntimeError, sqlite3.Error) as error:
            self._save_timer.stop(); self._pending_save = None; self._waiting(False)
            self.error.setStyleSheet('color:#e9a8a8'); self.error.setText(self.t(str(error))); return
        self._save_timer.stop(); self._pending_save = None
        super().accept()

    def done(self, result):
        self._save_timer.stop(); self._pending_save = None
        super().done(result)
