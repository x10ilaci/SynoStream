"""SynoStream-styled, asynchronous Download Station page and task creation dialogs."""
import time
import math
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle, QDialog, QDialogButtonBox,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem, QTabWidget, QScrollArea,
)
from synostream_file_selection_ui import FileSelectionDialog
from synostream_downloads import DownloadStationClient, normalize_destination, validate_uri, is_complete


EN = {
    'Továbbiak betöltése':'Load more',
    'A mappa nem olvasható. Lehet, hogy törölték vagy átnevezték. ':'Cannot read this folder. It may have been deleted or renamed. ',
    'Torrentoldalak kezelése': 'Manage torrent sites', 'Torrentoldal hozzáadása': 'Add torrent site',
    'Oldal neve:': 'Site name:', 'Webcím:': 'URL:', 'Kijelölt oldal törlése': 'Delete selected site',
    'Mentés': 'Save', 'Adj meg nevet és érvényes HTTP- vagy HTTPS-webcímet.': 'Enter a name and a valid HTTP or HTTPS URL.',
    'A torrentoldalak mentése nem sikerült.': 'Could not save torrent sites.',

    'Letöltendő fájlok kiválasztása': 'Select files to download',
    'A letöltés csak a kijelölés jóváhagyása után indul. Az NFO fájlok alapból kijelölve, a sample fájlok kihagyva.': 'Downloading starts only after confirmation. NFO files are selected by default; sample files are unchecked.',
    'Fájl / mappa': 'File / folder', 'Méret': 'Size', 'Mind kijelölése': 'Select all',
    'Ajánlott kijelölés': 'Recommended selection', 'Kijelöltek letöltése': 'Download selected',
    'Kijelölve: {count} fájl · {size}': 'Selected: {count} files · {size}',
    'Fájllista előkészítése…': 'Preparing file list…',
    'Kijelölt fájlok indítása…': 'Starting selected files…',
    'A hozzáadás megszakítva. Letöltés nem indult.': 'Addition cancelled. No download started.',
    'Az előkészített fájllista törlése nem sikerült. Letöltés nem indult.': 'Could not remove the prepared file list. No download started.',

    'Letöltések': 'Downloads', 'Download Station a NAS-on': 'Download Station on your NAS',
    'Új letöltés': 'Add download', 'Frissítés': 'Refresh', 'NAS beállítása': 'Configure NAS',
    'nCore megnyitása': 'Open nCore', 'Szüneteltetés': 'Pause', 'Folytatás': 'Resume',
    'Feladat eltávolítása': 'Remove task', 'Összes': 'All', 'Folyamatban': 'Active',
    'Kész / seedel': 'Complete / seeding', 'Hibás': 'Failed', 'Név': 'Name',
    'Állapot': 'Status', 'Haladás': 'Progress', 'Letöltés': 'Download', 'Feltöltés': 'Upload',
    'Hátralévő': 'Remaining', 'Nincs kijelölt feladat.': 'No task selected.',
    'Torrentfájlokat ide is behúzhatsz. A letöltést a NAS végzi.': 'Drop torrent files here. Downloads run on your NAS.',
    'Kapcsolódás a Download Stationhöz…': 'Connecting to Download Station…',
    'Feladatlista frissítése…': 'Refreshing tasks…', 'Művelet folyamatban…': 'Working…',
    'A NAS belépési adatait a Beállítások / Távoli NAS alatt adhatod meg.': 'Configure NAS credentials under Settings / Remote NAS.',
    '{count} feladat · {active} aktív': '{count} tasks · {active} active',
    'Elkészült: {titles}': 'Completed: {titles}',
    'Szünetel': 'Paused', 'Letöltés alatt': 'Downloading', 'Seedel': 'Seeding',
    'Befejezve': 'Finished', 'Várakozik': 'Waiting', 'Ellenőrzés': 'Checking',
    'Kicsomagolás': 'Extracting', 'Befejezés': 'Finishing', 'Hiba': 'Error',
    'Célmappa': 'Destination', 'Feltöltve': 'Uploaded', 'Arány': 'Ratio',
    'Hivatkozás': 'Link', 'Torrentfájlok': 'Torrent files', 'Magnet- vagy torrentlink:': 'Magnet or torrent URL:',
    'Fájlok kiválasztása…': 'Choose files…', 'Kijelölés törlése': 'Clear selection',
    'Típus:': 'Type:', 'Filmek': 'Movies', 'TV-műsorok': 'TV shows', 'Egyéb': 'Other',
    'Célmappa a NAS-on:': 'NAS destination:', 'NAS alapértelmezett mappája': 'NAS default destination',
    'Tallózás…': 'Browse…', 'Médiatár mappája:': 'Library folder:', 'Válassz médiatárat…': 'Choose a library…',
    'Hozzáadás': 'Add', 'Mégse': 'Cancel', 'Letöltési mappa kiválasztása': 'Choose download folder',
    'Szülőmappa': 'Parent folder', 'Kiválasztás': 'Select', 'Mappalista betöltése…': 'Loading folders…',
    'Megosztott mappák': 'Shared folders', 'Hiányzó adat': 'Missing information',
    'Válassz legalább egy torrentfájlt.': 'Choose at least one torrent file.',
    'Várd meg a folyamatban lévő NAS-műveletet.': 'Wait for the current NAS operation.',
    '{count} feladat elküldve a NAS-nak.': '{count} tasks submitted to NAS.',
    'Néhány letöltés hozzáadása nem sikerült.': 'Some downloads could not be added.',
    'A művelet kész.': 'Action completed.', 'Eltávolítás megerősítése': 'Confirm removal',
    '{count} feladatot eltávolítasz a Download Stationből? A befejezetlen adatok kezelését a NAS szabályai határozzák meg.': 'Remove {count} tasks from Download Station? Incomplete data is handled according to NAS settings.',
    'A célmappa mentése nem sikerült.': 'Could not save the default destination.',
}
STATUS = {'downloading': 'Letöltés alatt', 'paused': 'Szünetel', 'seeding': 'Seedel',
          'finished': 'Befejezve', 'waiting': 'Várakozik', 'hash_checking': 'Ellenőrzés',
          'extracting': 'Kicsomagolás', 'finishing': 'Befejezés', 'error': 'Hiba',
          'filehosting_waiting': 'Várakozik'}


def number(value):
    try:
        result = float(value or 0)
        return max(0, result) if math.isfinite(result) else 0
    except (ValueError, TypeError):
        return 0


def size_text(value):
    value = number(value)
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if value < 1024 or unit == 'TiB':
            return f'{value:.1f} {unit}' if unit != 'B' else f'{int(value)} B'
        value /= 1024


def task_values(task):
    extra = task.get('additional') or {}
    transfer = extra.get('transfer') or {}
    total, downloaded = number(task.get('size')), number(transfer.get('size_downloaded'))
    percentage = 100 if is_complete(task) else min(100, int(100 * downloaded / total)) if total else 0
    speed = number(transfer.get('speed_download'))
    eta = '—'
    if task.get('status') == 'downloading' and speed > 0 and total > downloaded:
        seconds = int((total - downloaded) / speed)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        eta = f'{hours}:{minutes:02}:{seconds:02}' if hours else f'{minutes}:{seconds:02}'
    return percentage, size_text(speed) + '/s', size_text(transfer.get('speed_upload')) + '/s', eta


SORT_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class TaskItem(QTableWidgetItem):
    def __lt__(self, other):
        return self.data(SORT_ROLE) < other.data(SORT_ROLE)


def torrent_sites(config):
    # A missing setting retains the previous nCore shortcut; an empty list is intentional.
    values = config.get('torrent_sites', [{'name': 'nCore', 'url': 'https://ncore.pro/'}])
    result = []
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, dict):
            continue
        name, url = str(value.get('name', '')).strip(), str(value.get('url', '')).strip()
        parsed = QUrl(url)
        if name and parsed.isValid() and parsed.scheme().lower() in ('http', 'https') and parsed.host():
            result.append({'name': name, 'url': url})
    return result


class TorrentSitesDialog(QDialog):
    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.sites = torrent_sites(page.services.config())
        self.setWindowTitle(page.tr('Torrentoldalak kezelése'))
        self.resize(600, 400)
        layout = QVBoxLayout(self)
        self.items = QListWidget()
        layout.addWidget(self.items)
        form = QFormLayout()
        self.name = QLineEdit()
        self.url = QLineEdit()
        self.url.setPlaceholderText('https://…')
        form.addRow(page.tr('Oldal neve:'), self.name)
        form.addRow(page.tr('Webcím:'), self.url)
        layout.addLayout(form)
        row = QHBoxLayout()
        add = QPushButton(page.tr('Torrentoldal hozzáadása'))
        self.remove = QPushButton(page.tr('Kijelölt oldal törlése'))
        row.addWidget(add)
        row.addWidget(self.remove)
        layout.addLayout(row)
        add.clicked.connect(self.add_site)
        self.remove.clicked.connect(self.remove_site)
        self.items.currentRowChanged.connect(lambda index: self.remove.setEnabled(index >= 0))
        buttons = QDialogButtonBox()
        buttons.addButton(page.tr('Mentés'), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(page.tr('Mégse'), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh_sites()

    def refresh_sites(self):
        self.items.clear()
        for site in self.sites:
            item = QListWidgetItem(site['name'] + ' · ' + site['url'])
            item.setToolTip(site['url'])
            self.items.addItem(item)
        self.remove.setEnabled(False)

    def add_site(self):
        candidate = {'name': self.name.text().strip(), 'url': self.url.text().strip()}
        if not torrent_sites({'torrent_sites': [candidate]}):
            QMessageBox.warning(self, self.page.tr('Hiányzó adat'),
                                self.page.tr('Adj meg nevet és érvényes HTTP- vagy HTTPS-webcímet.'))
            return
        self.sites.append(candidate)
        self.refresh_sites()
        self.name.clear()
        self.url.clear()

    def remove_site(self):
        row = self.items.currentRow()
        if 0 <= row < len(self.sites):
            del self.sites[row]
            self.refresh_sites()


class ProgressDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ''
        opt.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        rectangle = opt.rect.adjusted(7, 11, -7, -11)
        painter.save()
        painter.fillRect(rectangle, QColor('#38313F'))
        fill = rectangle.adjusted(0, 0, 0, 0)
        fill.setWidth(int(rectangle.width() * number(index.data(Qt.ItemDataRole.UserRole)) / 100))
        painter.fillRect(fill, QColor('#765C91'))
        painter.setPen(QColor('#EEEAF3'))
        painter.drawText(opt.rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class FolderDialog(QDialog):
    def __init__(self, page, initial_path=""):
        super().__init__(page)
        if page.folder_profile!=page.credentials():
            page.folder_cache.clear();page.last_directory="";page.folder_profile=dict(page.credentials())
        initial_path="/"+normalize_destination(initial_path) if initial_path.strip() else ""
        self.page, self.path, self.closed = page, initial_path, False
        self.offset=0;self.generation=0
        self.setWindowTitle(page.tr('Letöltési mappa kiválasztása'))
        self.resize(620, 440)
        layout = QVBoxLayout(self)
        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        self.path_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.path_label)
        self.items = QListWidget()
        layout.addWidget(self.items)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        row = QHBoxLayout()
        self.parent_button = QPushButton(page.tr('Szülőmappa'))
        self.more_button=QPushButton(page.tr('Továbbiak betöltése'));self.more_button.hide()
        self.more_button.clicked.connect(lambda:self.load(self.path,self.offset))
        layout.addWidget(self.more_button)
        self.select_button = QPushButton(page.tr('Kiválasztás'))
        cancel = QPushButton(page.tr('Mégse'))
        for button in (self.parent_button, self.select_button, cancel):
            row.addWidget(button)
        layout.addLayout(row)
        self.parent_button.clicked.connect(lambda: self.load('/'.join(self.path.rstrip('/').split('/')[:-1])))
        self.select_button.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        self.items.itemDoubleClicked.connect(lambda item: self.load(item.data(Qt.ItemDataRole.UserRole)))
        QTimer.singleShot(0, lambda: self.load(initial_path or getattr(page,'last_directory','')))

    def load(self,path,offset=0):
        if self.closed:return
        self.generation+=1;generation=self.generation
        self.path=path
        self.path_label.setText(path or self.page.tr('Megosztott mappák'))
        if not offset:self.items.clear()
        self.items.setEnabled(False);self.more_button.setEnabled(False)
        self.select_button.setEnabled(False);self.parent_button.setEnabled(False)
        self.message.setText(self.page.tr('Mappalista betöltése…'))
        def loaded(data):
            if self.closed or generation!=self.generation:return
            for entry in data['entries']:
                if not entry.get('isdir',not path):continue
                item=QListWidgetItem(entry.get('name',''));item.setData(Qt.ItemDataRole.UserRole,entry.get('path') or path.rstrip('/')+'/'+entry.get('name',''));self.items.addItem(item)
            self.offset=offset+len(data['entries'])
            self.more_button.setVisible(data['more']);self.more_button.setEnabled(True)
            self.items.setEnabled(True);self.select_button.setEnabled(bool(path));self.parent_button.setEnabled(bool(path));self.message.clear()
            self.page.last_directory=path
        def failed(message):
            if not self.closed and generation==self.generation:
                self.page.folder_cache.clear();self.message.setText(self.page.tr('A mappa nem olvasható. Lehet, hogy törölték vagy átnevezték. ')+message);self.parent_button.setEnabled(bool(path))
        self.page.directory_operation(self,path,offset,loaded,failed)

    def done(self,result):
        self.closed=True
        if getattr(self.page,'_folder_current',None) is self and self.page.worker is not None:
            self.page.worker.requestInterruption()
        super().done(result)


class CreateDownloadDialog(QDialog):
    def __init__(self, page, files=None):
        super().__init__(page)
        self.page, self.files = page, list(files or [])
        self.setWindowTitle(page.tr('Új letöltés'))
        self.resize(680, 340)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        link_tab = QWidget()
        link_layout = QVBoxLayout(link_tab)
        link_layout.addWidget(QLabel(page.tr('Magnet- vagy torrentlink:')))
        self.uri = QLineEdit()
        self.uri.setPlaceholderText('magnet:?xt=urn:btih:…')
        self.uri.setClearButtonEnabled(True)
        link_layout.addWidget(self.uri)
        link_layout.addStretch()
        file_tab = QWidget()
        file_layout = QVBoxLayout(file_tab)
        self.file_list = QListWidget()
        file_layout.addWidget(self.file_list)
        row = QHBoxLayout()
        choose = QPushButton(page.tr('Fájlok kiválasztása…'))
        clear = QPushButton(page.tr('Kijelölés törlése'))
        row.addWidget(choose)
        row.addWidget(clear)
        file_layout.addLayout(row)
        choose.clicked.connect(self.choose_files)
        clear.clicked.connect(lambda: self.set_files([]))
        self.tabs.addTab(link_tab, page.tr('Hivatkozás'))
        self.tabs.addTab(file_tab, page.tr('Torrentfájlok'))
        layout.addWidget(self.tabs, 1)
        form = QFormLayout()
        destination_row = QHBoxLayout()
        self.destination = QLineEdit()
        self.destination.setPlaceholderText(page.tr('NAS alapértelmezett mappája'))
        browse = QPushButton(page.tr('Tallózás…'))
        browse.clicked.connect(self.browse)
        destination_row.addWidget(self.destination, 1)
        destination_row.addWidget(browse)
        form.addRow(page.tr('Célmappa a NAS-on:'), destination_row)
        layout.addLayout(form)
        self.default_destination()
        buttons = QDialogButtonBox()
        add = buttons.addButton(page.tr('Hozzáadás'), QDialogButtonBox.ButtonRole.AcceptRole)
        add.setObjectName('DownloadPrimary')
        buttons.addButton(page.tr('Mégse'), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.set_files(self.files)
        if self.files:
            self.tabs.setCurrentIndex(1)

    def default_destination(self):
        config = self.page.services.config()
        value = config.get('download_station_destination', '')
        if not value:
            previous = config.get('download_station_destinations') or {}
            value = previous.get('movies') or previous.get('shows') or previous.get('other') or ''
        self.destination.setText(value)

    def set_files(self, files):
        self.files = list(dict.fromkeys(files))
        self.file_list.clear()
        for path in self.files:
            item = QListWidgetItem(Path(path).name)
            item.setToolTip(path)
            self.file_list.addItem(item)

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, self.page.tr('Fájlok kiválasztása…'), '', 'Torrent (*.torrent)')
        if files:
            self.set_files(self.files + files)

    def browse(self):
        dialog = FolderDialog(self.page,self.destination.text().strip())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.destination.setText(normalize_destination(dialog.path))

    def validate_and_accept(self):
        try:
            if self.page.busy:
                raise ValueError(self.page.tr('Várd meg a folyamatban lévő NAS-műveletet.'))
            normalize_destination(self.destination.text())
            if self.tabs.currentIndex() == 0:
                validate_uri(self.uri.text())
            elif not self.files:
                raise ValueError(self.page.tr('Válassz legalább egy torrentfájlt.'))
        except ValueError as exc:
            QMessageBox.warning(self, self.page.tr('Hiányzó adat'), str(exc))
            return
        self.accept()


class DownloadPage(QWidget):
    completed = pyqtSignal(list)

    def __init__(self, services, parent=None):
        super().__init__(parent)
        self.services = services
        self.client_factory = DownloadStationClient
        self.client = None
        self.worker = None
        self.folder_cache={};self.folder_jobs=[];self.folder_profile=None;self.last_directory="";self._folder_current=None
        self.busy = False
        self.closing = False
        self.dialog_open = False
        self.refresh_after = False
        self._after_operation = None
        self.tasks = []
        self.previous = None
        self._texts = []
        self._success = None
        self._failure = None
        self._status_source = 'A NAS belépési adatait a Beállítások / Távoli NAS alatt adhatod meg.'
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 24)
        layout.setSpacing(14)
        heading = self.label('Letöltések')
        heading.setObjectName('PageTitle')
        layout.addWidget(heading)
        subtitle = self.label('Download Station a NAS-on')
        subtitle.setObjectName('InfoLabel')
        layout.addWidget(subtitle)
        top = QHBoxLayout()
        self.add_button = self.button('Új letöltés', self.add_download)
        self.add_button.setObjectName('DownloadPrimary')
        self.refresh_button = self.button('Frissítés', self.refresh)
        tools = top
        self.pause_button = self.button('Szüneteltetés', lambda: self.action('pause'))
        self.resume_button = self.button('Folytatás', lambda: self.action('resume'))
        self.remove_button = self.button('Feladat eltávolítása', lambda: self.action('delete'))
        for button in (self.add_button, self.refresh_button, self.pause_button, self.resume_button, self.remove_button):
            tools.addWidget(button)
        tools.addStretch()
        self.filter = QComboBox()
        for label, key in (('Összes', 'all'), ('Folyamatban', 'active'), ('Kész / seedel', 'complete'), ('Hibás', 'error')):
            self.filter.addItem(self.tr(label), key)
        self.filter.currentIndexChanged.connect(self.render_tasks)
        layout.addLayout(tools)
        sites_row = QHBoxLayout()
        self.site_scroll = QScrollArea()
        self.site_scroll.setStyleSheet('QScrollArea {border:0; background:transparent;}')
        self.site_scroll.setWidgetResizable(True)
        self.site_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.site_scroll.setFixedHeight(58)
        self.site_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.site_container = QWidget()
        self.site_container.setStyleSheet('QWidget {border:0; background:transparent;} QPushButton {border:1px solid #3A3440; background:#18161C;}')
        self.site_buttons_layout = QHBoxLayout(self.site_container)
        self.site_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.site_scroll.setWidget(self.site_container)
        sites_row.addWidget(self.site_scroll, 1)
        self.manage_sites_button = self.button('Torrentoldalak kezelése', self.manage_sites)
        sites_row.addWidget(self.manage_sites_button)
        layout.addLayout(sites_row)
        self.rebuild_site_buttons()
        filter_row = QHBoxLayout()
        filter_row.addStretch()
        filter_row.addWidget(self.filter)
        layout.addLayout(filter_row)
        self.status = QLabel(self.tr(self._status_source))
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setObjectName('LibraryCount')
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 6)
        self.table.setObjectName('DownloadTable')
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setItemDelegateForColumn(2, ProgressDelegate(self.table))
        self.table.horizontalHeader().setSortIndicator(1, Qt.SortOrder.AscendingOrder)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self.update_controls)
        layout.addWidget(self.table, 1)
        self.detail = self.label('Nincs kijelölt feladat.')
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        self.detail.setObjectName('LibraryCount')
        layout.addWidget(self.detail)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        self.notice.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.notice)
        hint = self.label('Torrentfájlokat ide is behúzhatsz. A letöltést a NAS végzi.')
        hint.setObjectName('LibraryCount')
        layout.addWidget(hint)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.setStyleSheet('''
            QTableWidget#DownloadTable {background:#141317; border:1px solid #302B36; border-radius:7px; selection-background-color:#30263C; color:#EEEAF3;}
            QTableWidget#DownloadTable::item {padding:7px; border-bottom:1px solid #25212B;}
            QHeaderView::section {background:#1B191F; color:#A49CAE; padding:9px 7px; border:0; border-bottom:1px solid #302B36;}
            QPushButton#DownloadPrimary {background:#30263C; color:#EEEAF3; border:1px solid #645077;}
            QPushButton#DownloadPrimary:hover {background:#433250;}
        ''')
        self.retranslate_texts()

    def tr(self, text):
        return EN.get(text, text) if self.services.config().get('language') == 'en' else text

    def label(self, text):
        widget = QLabel(self.tr(text))
        self._texts.append((widget, text))
        return widget

    def button(self, text, callback):
        widget = QPushButton(self.tr(text))
        widget.clicked.connect(callback)
        self._texts.append((widget, text))
        return widget

    def retranslate_texts(self):
        for widget, source in self._texts:
            widget.setText(self.tr(source))
        self.table.setHorizontalHeaderLabels([self.tr(text) for text in ('Név', 'Állapot', 'Haladás', 'Letöltés', 'Feltöltés', 'Hátralévő')])
        for index, source in enumerate(('Összes', 'Folyamatban', 'Kész / seedel', 'Hibás')):
            self.filter.setItemText(index, self.tr(source))
        text = self.tr(self._status_source)
        if self._status_source == '{count} feladat · {active} aktív':
            text = text.format(count=len(self.tasks), active=sum(task.get('status') not in ('finished', 'seeding', 'paused', 'error') for task in self.tasks))
        self.status.setText(text)
        self.render_tasks()

    def rebuild_site_buttons(self):
        while self.site_buttons_layout.count():
            item = self.site_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.site_buttons = []
        for site in torrent_sites(self.services.config()):
            button = QPushButton(site['name'])
            button.setToolTip(site['url'])
            button.clicked.connect(lambda _checked=False, url=site['url']: QDesktopServices.openUrl(QUrl(url)))
            self.site_buttons_layout.addWidget(button)
            self.site_buttons.append(button)
        self.site_buttons_layout.addStretch()

    def manage_sites(self):
        dialog = TorrentSitesDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        config = self.services.config()
        existed, previous = 'torrent_sites' in config, config.get('torrent_sites')
        config['torrent_sites'] = dialog.sites
        saved, _error = self.services.save_config()
        if not saved:
            if existed:
                config['torrent_sites'] = previous
            else:
                config.pop('torrent_sites', None)
            QMessageBox.warning(self, self.tr('Letöltések'), self.tr('A torrentoldalak mentése nem sikerült.'))
            return
        self.rebuild_site_buttons()

    def credentials(self):
        config = self.services.config()
        return {key: config.get(key, '') for key in ('quickconnect_id', 'nas_username', 'nas_password', 'nas_direct_url', 'nas_local_url','nas_device_tokens')}

    def directory_operation(self,dialog,path,offset,success,failure):
        profile=self.credentials()
        if self.folder_profile!=profile:
            self.folder_cache.clear();self.folder_profile=dict(profile);self.last_directory=''
        cached=self.folder_cache.get((path,offset))
        if cached and time.monotonic()-cached[0]<60:
            success(cached[1]);return
        def start():
            if dialog.closed:return
            self._folder_current=dialog
            def operation(client):
                if dialog.closed:raise InterruptedError('Megszakítva')
                return client.list_directories(path,offset=offset,limit=200)
            def ready(data):
                if self.credentials()==profile:self.folder_cache[(path,offset)]=(time.monotonic(),data)
                success(data)
            self.start_operation(operation,ready,failure)
        if self.busy:self.folder_jobs.append(start)
        else:start()

    def start_operation(self, operation, success=None, failure=None):
        if self.busy or self.closing:
            return False
        credentials = self.credentials()
        self.busy = True
        self._operation_credentials = credentials
        self._success, self._failure = success, failure
        self.status.setText(self.tr('Művelet folyamatban…'))
        self.update_controls()
        def execute(stop):
            client = None
            try:
                if self.client is not None and self.client.credentials != credentials:
                    self.client.close()
                    self.client = None
                if self.client is None:
                    self.client = self.client_factory(credentials, stop)
                client = self.client
                client.should_stop = stop
                client._check_cancelled()
                return operation(client)
            finally:
                if self.closing and self.client is not None:
                    closing_client, self.client = self.client, None
                    closing_client.close()
        worker = self.services.task_factory(execute)
        self.worker = worker
        worker.succeeded.connect(self.operation_succeeded)
        worker.failed.connect(self.operation_failed)
        worker.finished.connect(self.operation_finished)
        self.services.run_worker(worker)
        return True

    def operation_succeeded(self, result):
        if self.credentials() != self._operation_credentials:
            self.dialog_open = False
            self._after_operation = None
            self.refresh_after = True
            return
        if not self.closing and self._success:
            self._success(result)

    def operation_failed(self, message):
        if self.credentials() != self._operation_credentials:
            self.dialog_open = False
            self._after_operation = None
            self.refresh_after = True
            return
        if self.closing:
            return
        self._status_source = message
        self.status.setText(self.tr(message))
        self.timer.setInterval(30000)
        if self.client is None:
            self.timer.stop()
        if self._failure:
            self._failure(message)

    def operation_finished(self):
        self.worker = None
        self.busy = False
        self._folder_current=None
        self._success = self._failure = None
        self.update_controls()
        while self.folder_jobs and not self.closing:
            job=self.folder_jobs.pop(0);job()
            if self.busy:return
        if self._after_operation is not None and not self.closing:
            continuation, self._after_operation = self._after_operation, None
            continuation()
            return
        if self.refresh_after and not self.closing:
            self.refresh_after = False
            self.refresh()

    def refresh(self):
        if self.start_operation(lambda client: client.list_tasks(), self.apply_tasks):
            self.status.setText(self.tr('Feladatlista frissítése…'))

    def poll(self):
        if getattr(self, "playback_active", lambda:False)() and not self.window().isActiveWindow():
            return
        if not self.dialog_open and not self.busy and not self.closing:
            self.refresh()

    def apply_tasks(self, tasks):
        profile = tuple(self.credentials().values())
        if getattr(self, '_profile', profile) != profile:
            self.previous = None
        self._profile = profile
        completed = [task for task in tasks if is_complete(task) and self.previous is not None
                     and (task.get('id') not in self.previous or not self.previous[task['id']])]
        self.previous = {task.get('id'): is_complete(task) for task in tasks}
        self.tasks = tasks
        active = sum(task.get('status') not in ('finished', 'seeding', 'paused', 'error') for task in tasks)
        self._status_source = '{count} feladat · {active} aktív'
        self.status.setText(self.tr(self._status_source).format(count=len(tasks), active=active))
        self.render_tasks()
        self.timer.start(5000 if self.isVisible() else 15000)
        if completed:
            titles = ', '.join(str(task.get('title') or '') for task in completed[:3])
            self.notice.setText(self.tr('Elkészült: {titles}').format(titles=titles))
            self.completed.emit(completed)

    def selected_ids(self):
        return [self.table.item(index.row(), 0).data(Qt.ItemDataRole.UserRole)
                for index in self.table.selectionModel().selectedRows() if self.table.item(index.row(), 0)]

    def render_tasks(self, *_args):
        if not hasattr(self, 'table'):
            return
        selected = set(self.selected_ids())
        mode = self.filter.currentData()
        tasks = [task for task in self.tasks if mode == 'all'
                 or mode == 'complete' and is_complete(task)
                 or mode == 'error' and task.get('status') == 'error'
                 or mode == 'active' and task.get('status') not in ('finished', 'seeding', 'paused', 'error')]
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(tasks))
            self.table.clearSelection()
            for row, task in enumerate(tasks):
                progress, download, upload, eta = task_values(task)
                values = (str(task.get('title') or ''), self.tr(STATUS.get(task.get('status'), str(task.get('status') or ''))),
                          f'{progress}%', download, upload, eta)
                transfer = (task.get('additional') or {}).get('transfer') or {}
                speed = number(transfer.get('speed_download'))
                total, downloaded = number(task.get('size')), number(transfer.get('size_downloaded'))
                remaining = max(0, total - downloaded) / speed if task.get('status') == 'downloading' and speed > 0 and total > downloaded else float('inf')
                detail = (task.get('additional') or {}).get('detail') or {}
                state_rank = {'downloading':0,'finishing':1,'waiting':2,'hash_checking':3,'seeding':4,'finished':5,'paused':6,'error':7}.get(task.get('status'),8)
                keys = (values[0].casefold(), (state_rank,-number(detail.get('create_time')),values[1].casefold()), 100 if is_complete(task) else min(100, 100 * downloaded / total) if total else 0,
                        speed, number(transfer.get('speed_upload')), remaining)
                for column, value in enumerate(values):
                    item = TaskItem(value)
                    item.setData(SORT_ROLE, keys[column])
                    item.setData(Qt.ItemDataRole.UserRole, task.get('id') if column == 0 else progress if column == 2 else None)
                    self.table.setItem(row, column, item)
            self.table.setSortingEnabled(True)
            for row in range(self.table.rowCount()):
                if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) in selected:
                    for column in range(6):
                        self.table.item(row, column).setSelected(True)
        finally:
            self.table.setSortingEnabled(True)
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
        self.update_controls()

    def update_controls(self):
        selected = self.selected_ids() if hasattr(self, 'table') else []
        for button in (self.add_button, self.refresh_button):
            button.setEnabled(not self.busy and not self.closing)
        for button in (self.pause_button, self.resume_button, self.remove_button):
            button.setEnabled(bool(selected) and not self.busy and not self.closing)
        if not hasattr(self, 'detail'):
            return
        task = next((task for task in self.tasks if task.get('id') in selected), None)
        if task is None:
            self.detail.setText(self.tr('Nincs kijelölt feladat.'))
        else:
            extra = task.get('additional') or {}
            uploaded = number((extra.get('transfer') or {}).get('size_uploaded'))
            ratio = uploaded / number(task.get('size')) if number(task.get('size')) else 0
            destination = (extra.get('detail') or {}).get('destination') or '—'
            self.detail.setText(f"{self.tr('Célmappa')}: {destination}  ·  {self.tr('Feltöltve')}: {size_text(uploaded)}  ·  {self.tr('Arány')}: {ratio:.2f}")

    def continue_when_idle(self, callback):
        if self.closing:
            return
        if self.busy:
            self._after_operation = callback
        else:
            QTimer.singleShot(0, callback)

    def has_credentials(self):
        values = self.credentials()
        return bool(values.get('nas_username') and values.get('nas_password')
                    and (values.get('quickconnect_id') or values.get('nas_direct_url') or values.get('nas_local_url')))

    def add_download(self, files=None):
        if self.busy or self.closing or self.dialog_open:
            return
        if not self.has_credentials():
            self.status.setText(self.tr('A NAS belépési adatait a Beállítások / Távoli NAS alatt adhatod meg.'))
            self.services.configure_nas()
            if not self.has_credentials():
                return
        self.dialog_open = True
        dialog = CreateDownloadDialog(self, files if isinstance(files, list) else None)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.dialog_open = False
            return
        destination = normalize_destination(dialog.destination.text())
        files = dialog.files if dialog.tabs.currentIndex() == 1 else []
        uri = dialog.uri.text().strip() if not files else None

        def prepare(client):
            previews, errors = [], []
            for path in files or [None]:
                client._check_cancelled()
                try:
                    previews.extend(client.prepare(torrent_file=path, uri=uri if path is None else None, destination=destination))
                except InterruptedError:
                    raise
                except Exception as exc:
                    errors.append((Path(path).name + ': ' if path else '') + self.services.redact(exc))
            unique = {preview['list_id']: preview for preview in previews}
            return list(unique.values()), errors

        def failed(message):
            self.dialog_open = False
            QMessageBox.warning(self, self.tr('Letöltések'), self.tr(message))

        def prepared(result):
            previews, errors = result
            if errors:
                QMessageBox.warning(self, self.tr('Néhány letöltés hozzáadása nem sikerült.'), '\n'.join(errors))
            if not previews:
                self.dialog_open = False
                return
            picker = FileSelectionDialog(self, previews, size_text)
            if picker.exec() != QDialog.DialogCode.Accepted:
                self.continue_when_idle(lambda: self.discard_previews(previews))
                return
            selected = picker.selected_files()
            if not any(selected.values()):
                self.continue_when_idle(lambda: self.discard_previews(previews))
                return
            self.continue_when_idle(lambda: self.submit_selected(previews, selected))

        self.start_operation(prepare, prepared, failed)
        self.status.setText(self.tr('Fájllista előkészítése…'))

    def discard_previews(self, previews):
        def discard(client):
            errors = []
            for preview in previews:
                try:
                    client.discard_prepared(preview['list_id'])
                except InterruptedError:
                    raise
                except Exception as exc:
                    errors.append(self.services.redact(exc))
            return errors
        def discarded(errors):
            self.dialog_open = False
            self.notice.setText(self.tr('Az előkészített fájllista törlése nem sikerült. Letöltés nem indult.'
                                       if errors else 'A hozzáadás megszakítva. Letöltés nem indult.'))
        def failed(_message):
            self.dialog_open = False
            self.notice.setText(self.tr('Az előkészített fájllista törlése nem sikerült. Letöltés nem indult.'))
        self.start_operation(discard, discarded, failed)

    def submit_selected(self, previews, selected):
        def submit(client):
            success, errors = 0, []
            for preview in previews:
                client._check_cancelled()
                try:
                    indices = selected.get(preview['list_id'], [])
                    if indices:
                        client.start_prepared(preview['list_id'], indices)
                        success += 1
                    else:
                        client.discard_prepared(preview['list_id'])
                except InterruptedError:
                    raise
                except Exception as exc:
                    errors.append(preview['title'] + ': ' + self.services.redact(exc))
            return success, errors
        def submitted(result):
            count, errors = result
            self.dialog_open = False
            if count:
                config = self.services.config()
                previous = config.get('download_station_destination', '')
                config['download_station_destination'] = previews[0]['destination']
                saved, _error = self.services.save_config()
                if not saved:
                    config['download_station_destination'] = previous
                    self.notice.setText(self.tr('A célmappa mentése nem sikerült.'))
                else:
                    self.notice.setText(self.tr('{count} feladat elküldve a NAS-nak.').format(count=count))
            if errors:
                QMessageBox.warning(self, self.tr('Néhány letöltés hozzáadása nem sikerült.'), '\n'.join(errors))
            self.refresh_after = True
        def failed(message):
            self.dialog_open = False
            self.refresh_after = True
            QMessageBox.warning(self, self.tr('Letöltések'), self.tr(message))
        self.start_operation(submit, submitted, failed)
        self.status.setText(self.tr('Kijelölt fájlok indítása…'))

    def configure_nas(self):
        self.services.configure_nas()
        if getattr(self, '_profile', None) != tuple(self.credentials().values()):
            self.previous = None
            self.tasks = []
            self.render_tasks()
        self.refresh()

    def action(self, action):
        if getattr(self, '_profile', None) != tuple(self.credentials().values()):
            self.previous = None
            self.tasks = []
            self.render_tasks()
            self.refresh()
            return
        ids = self.selected_ids()
        if not ids or self.busy:
            return
        if action == 'delete' and QMessageBox.question(self, self.tr('Eltávolítás megerősítése'),
            self.tr('{count} feladatot eltávolítasz a Download Stationből? A befejezetlen adatok kezelését a NAS szabályai határozzák meg.').format(count=len(ids)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        def finished(_result):
            self.notice.setText(self.tr('A művelet kész.'))
            self.refresh_after = True
        def failed(message):
            self.refresh_after = True
            QMessageBox.warning(self, self.tr('Letöltések'), self.tr(message))
        self.start_operation(lambda client: client.task_action(action, ids), finished, failed)

    @staticmethod
    def dropped_files(mime):
        return [url.toLocalFile() for url in mime.urls() if url.isLocalFile()
                and Path(url.toLocalFile()).suffix.lower() == '.torrent' and Path(url.toLocalFile()).is_file()]

    def dragEnterEvent(self, event):
        if self.dropped_files(event.mimeData()) and not self.busy:
            event.acceptProposedAction()

    def dropEvent(self, event):
        files = self.dropped_files(event.mimeData())
        if files and not self.busy:
            event.acceptProposedAction()
            self.add_download(files)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.closing:
            QTimer.singleShot(0, self.refresh)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.timer.isActive():
            self.timer.setInterval(15000)

    def shutdown(self):
        self.closing = True
        self.timer.stop()
        if self.worker is not None:
            self.worker.requestInterruption()
        if self.client is not None:
            client, self.client = self.client, None
            def close(_stop):
                with client.lock:
                    client.close()
            self.services.run_worker(self.services.task_factory(close))



