"""The source-pair editor inherits SynoStream's window chrome and theme."""
import copy
import uuid
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QFormLayout, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QDialogButtonBox, QMessageBox
from synostream_sources import parse_pairs


class SourcePairsDialog(QDialog):
    def __init__(self, parent, settings, libraries, save, translate=lambda value:value):
        super().__init__(parent)
        self.translate, self.save_pairs = translate, save
        initial_error = ''
        try:self.values = [pair.to_dict() for pair in parse_pairs(settings.get('paired_sources', []))]
        except ValueError as error:self.values = []; initial_error = str(error)
        self.setWindowTitle(translate('Helyi és távoli elérések összerendelése'))
        self.resize(880, 590)
        self.setMinimumSize(680, 500)
        layout = QVBoxLayout(self)
        description = QLabel(translate('Egy médiamappa, két elérés. A program beolvasáskor és lejátszás indításakor az elérhető SMB-kapcsolatot használja, egyébként QuickConnectre vált. A kártyák, párosítások és lejátszási előzmények közösek.'))
        description.setWordWrap(True); layout.addWidget(description)
        self.listing = QListWidget(); layout.addWidget(self.listing, 1)
        self.library = QComboBox()
        for identifier, name in libraries: self.library.addItem(name, identifier)
        self.local = QLineEdit(); self.local.setPlaceholderText(r'\\192.168.1.2\megosztás\Film')
        self.remote = QLineEdit(); self.remote.setPlaceholderText('syno:///megosztás/Film')
        form = QFormLayout()
        form.addRow(translate('Médiatár:'), self.library)
        form.addRow(translate('Helyi SMB-elérés:'), self.local)
        form.addRow(translate('QuickConnect-elérés:'), self.remote)
        layout.addLayout(form)
        note = QLabel(translate('Csak ugyanannak a mappának a két elérését rendeld össze. A kizárólag SMB-vel vagy QuickConnecttel használt mappákat nem kell itt felvenni. Összerendelés megszüntetésekor a QuickConnect-elérés megmarad.'))
        note.setWordWrap(True); layout.addWidget(note)
        controls = QHBoxLayout()
        self.add = QPushButton(translate('Hozzáadás / módosítás')); self.add.clicked.connect(self.add_pair)
        self.new = QPushButton(translate('Új összerendelés')); self.new.clicked.connect(self.clear_editor)
        self.remove = QPushButton(translate('Kijelölt összerendelés megszüntetése')); self.remove.clicked.connect(self.remove_pair)
        for button in (self.add, self.new, self.remove): controls.addWidget(button)
        layout.addLayout(controls)
        self.error = QLabel(initial_error); self.error.setWordWrap(True); self.error.setStyleSheet('color:#E9A8A8;'); layout.addWidget(self.error)
        buttons = QDialogButtonBox()
        buttons.addButton(translate('Mentés'), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(translate('Mégse'), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.listing.currentRowChanged.connect(self.select_pair)
        self.refresh()

    def refresh(self):
        self.listing.blockSignals(True); self.listing.clear()
        names = {self.library.itemData(i):self.library.itemText(i) for i in range(self.library.count())}
        for pair in self.values:
            self.listing.addItem(f"{names.get(pair.get('library_id'), pair.get('library_id',''))}\n{pair.get('local_root','')}  ↔  {pair.get('remote_root','')}")
        self.listing.blockSignals(False)

    def select_pair(self, index):
        if not 0 <= index < len(self.values): return
        pair = self.values[index]
        self.local.setText(pair['local_root']); self.remote.setText(pair['remote_root'])
        self.library.setCurrentIndex(max(0, self.library.findData(pair.get('library_id','movies'))))

    def clear_editor(self):
        self.listing.setCurrentRow(-1); self.local.clear(); self.remote.clear(); self.error.clear()

    def add_pair(self):
        index = self.listing.currentRow()
        value = dict(id=self.values[index]['id'] if 0 <= index < len(self.values) else uuid.uuid4().hex,
                     library_id=self.library.currentData(), local_root=self.local.text(), remote_root=self.remote.text())
        staged = copy.deepcopy(self.values)
        if 0 <= index < len(staged): staged[index] = value
        else: staged.append(value)
        try: self.values = [pair.to_dict() for pair in parse_pairs(staged)]
        except ValueError as error: self.error.setText(str(error)); return
        self.error.clear(); self.refresh(); self.clear_editor()

    def remove_pair(self):
        index = self.listing.currentRow()
        if 0 <= index < len(self.values):
            self.values.pop(index); self.refresh(); self.clear_editor()

    def accept(self):
        if self.local.text().strip() or self.remote.text().strip():
            index = self.listing.currentRow()
            current = self.values[index] if 0 <= index < len(self.values) else None
            unchanged = current and current.get('local_root') == self.local.text() and current.get('remote_root') == self.remote.text() and current.get('library_id') == self.library.currentData()
            if not unchanged:
                self.error.setText(self.translate('Előbb a Hozzáadás / módosítás gombbal vedd fel a kitöltött összerendelést.'))
                return
        try:
            values = [pair.to_dict() for pair in parse_pairs(self.values)]
            self.save_pairs(values)
        except (ValueError, OSError, RuntimeError) as error:
            self.error.setText(str(error)); return
        super().accept()
