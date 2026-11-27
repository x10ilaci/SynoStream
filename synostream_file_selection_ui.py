"""Explicit, fail-closed file selection for metadata-only prepared torrents."""
from pathlib import PurePosixPath

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
                            QTreeWidgetItem, QHeaderView, QPushButton, QDialogButtonBox)
from synostream_torrent_selection import default_file_selected
from synostream_logic import torrent_root, largest_video_sizes


class FileSelectionDialog(QDialog):
    def __init__(self, page, previews, format_size):
        super().__init__(page)
        self.page, self.previews, self.format_size = page, previews, format_size
        self.torrent_roots = {p["list_id"]: torrent_root(f["name"] for f in p["files"]) for p in self.previews}
        self.video_sizes = {p["list_id"]: largest_video_sizes((f["name"], f.get("size")) for f in p["files"]) for p in self.previews}
        self.file_items = []
        self.setWindowTitle(page.tr('Letöltendő fájlok kiválasztása'))
        self.resize(820, 560)
        self.setMinimumSize(620, 420)
        layout = QVBoxLayout(self)
        intro = QLabel(page.tr('A letöltés csak a kijelölés jóváhagyása után indul. Az NFO fájlok alapból kijelölve, a sample fájlok kihagyva.'))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([page.tr('Fájl / mappa'), page.tr('Méret')])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setAlternatingRowColors(False)
        self.tree.setUniformRowHeights(True)
        layout.addWidget(self.tree, 1)
        controls = QHBoxLayout()
        for text, mode in (('Mind kijelölése', 'all'), ('Kijelölés törlése', 'none'), ('Ajánlott kijelölés', 'recommended')):
            button = QPushButton(page.tr(text))
            button.clicked.connect(lambda _checked=False, selected_mode=mode: self.set_selection(selected_mode))
            controls.addWidget(button)
        controls.addStretch()
        layout.addLayout(controls)
        self.summary = QLabel()
        layout.addWidget(self.summary)
        destinations = list(dict.fromkeys('/' + p['destination'] for p in previews))
        target = QLabel(page.tr('Célmappa') + ': ' + ', '.join(destinations))
        target.setTextFormat(Qt.TextFormat.PlainText)
        target.setWordWrap(True)
        layout.addWidget(target)
        buttons = QDialogButtonBox()
        self.start_button = buttons.addButton(page.tr('Kijelöltek letöltése'), QDialogButtonBox.ButtonRole.AcceptRole)
        self.start_button.setObjectName('DownloadPrimary')
        buttons.addButton(page.tr('Mégse'), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.summary_timer = QTimer(self)
        self.summary_timer.setSingleShot(True)
        self.summary_timer.timeout.connect(self.update_summary)
        self.tree.itemChanged.connect(lambda *_args: self.summary_timer.start(0))
        self.tree.blockSignals(True)
        for preview in previews:
            list_id = preview['list_id']
            root = QTreeWidgetItem(self.tree, [preview['title'], ''])
            root.setFlags(root.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
            folders = {(): root}
            for file in preview['files']:
                path = [part for part in PurePosixPath(file['name'].replace('\\', '/')).parts if part not in ('/', '.', '..')]
                if path and path[0] == preview['title']:
                    path = path[1:]
                path = path or [file['name']]
                for depth in range(1, len(path)):
                    prefix = tuple(path[:depth])
                    if prefix not in folders:
                        folder = QTreeWidgetItem(folders[prefix[:-1]], [prefix[-1], ''])
                        folder.setFlags(folder.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
                        folders[prefix] = folder
                item = QTreeWidgetItem(folders[tuple(path[:-1])], [path[-1], format_size(file.get('size'))])
                item.setToolTip(0, file['name'])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked if self.recommended(file, list_id) else Qt.CheckState.Unchecked)
                self.file_items.append((item, preview['list_id'], file))
            root.setExpanded(True)
        self.tree.blockSignals(False)
        self.setStyleSheet('''QTreeWidget {background:#141317; color:#EEEAF3; border:1px solid #302B36; border-radius:7px;}
            QTreeWidget::indicator:unchecked {border:1px solid #756A80; background:#211D26; border-radius:2px;}
            QTreeWidget::item {padding:5px;} QTreeWidget::item:selected {background:#30263C;}
            QHeaderView::section {background:#1B191F; color:#A49CAE; border:0; padding:8px;}
            QPushButton#DownloadPrimary {background:#30263C; color:#EEEAF3; border:1px solid #645077;}''')
        self.update_summary()

    def recommended(self, file, list_id):
        parent = file['name'].replace('\\', '/').rpartition('/')[0]
        return default_file_selected(file['name'], self.torrent_roots.get(list_id, ''), file.get('size'), self.video_sizes[list_id].get(parent))

    def selected_files(self):
        selected = {preview['list_id']: [] for preview in self.previews}
        for item, list_id, file in self.file_items:
            if item.checkState(0) == Qt.CheckState.Checked:
                selected[list_id].append(file['index'])
        return selected

    def set_selection(self, mode):
        self.tree.blockSignals(True)
        try:
            for item, list_id, file in self.file_items:
                checked = mode == 'all' or mode == 'recommended' and self.recommended(file, list_id)
                item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        finally:
            self.tree.blockSignals(False)
        self.update_summary()

    def update_summary(self):
        selected = [(item, file) for item, _list_id, file in self.file_items if item.checkState(0) == Qt.CheckState.Checked]
        total = 0
        for _item, file in selected:
            try:
                total += max(0, int(file.get('size') or 0))
            except (TypeError, ValueError):
                pass
        self.summary.setText(self.page.tr('Kijelölve: {count} fájl · {size}').format(count=len(selected), size=self.format_size(total)))
        self.start_button.setEnabled(bool(selected))

    def accept(self):
        if any(self.selected_files().values()):
            super().accept()

