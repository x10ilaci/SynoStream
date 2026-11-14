from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog, QMessageBox
import synostream_download_ui as ui


def tasks():
    return [dict(id=str(i), title=name, status=status, size=100000,
                 additional={'transfer': {'size_downloaded': downloaded,
                                         'speed_download': speed, 'speed_upload': upload}})
            for i, (name, status, downloaded, speed, upload) in enumerate([
                ('Z', 'downloading', 9000, 1024, 9),
                ('A', 'downloading', 80000, 900, 1024),
                ('M', 'paused', 1000, 0, 100)])]


@pytest.mark.parametrize('column', range(6))
def test_header_clicks_sort_and_refresh_preserves_selection(media, app, column):
    w = media.DSVideoWindow()
    page = w.downloads_page
    page.refresh = lambda: None
    w.show_downloads()
    w.show()
    page.apply_tasks(tasks())
    page.timer.stop()
    app.processEvents()
    header = page.table.horizontalHeader()
    from PyQt6.QtCore import QPoint
    point = QPoint(header.sectionViewportPosition(column) + header.sectionSize(column)//2, header.height()//2)
    QTest.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, pos=point)
    app.processEvents()
    first = [page.table.item(row, column).data(ui.SORT_ROLE) for row in range(3)]
    assert first == sorted(first, reverse=header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder)
    QTest.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, pos=point)
    second = [page.table.item(row, column).data(ui.SORT_ROLE) for row in range(3)]
    assert second == list(reversed(first))
    page.table.selectRow(1)
    selected = page.selected_ids()
    page.apply_tasks(list(reversed(tasks())))
    page.timer.stop()
    assert page.selected_ids() == selected
    assert [page.table.item(row, column).data(ui.SORT_ROLE) for row in range(3)] == second
    w.close()


def test_site_add_remove_save_reopen_and_open_url(media, app, monkeypatch):
    w = media.DSVideoWindow()
    page = w.downloads_page
    dialog = ui.TorrentSitesDialog(page)
    assert dialog.sites[0]['name'] == 'nCore'
    dialog.name.setText('Saját oldal')
    dialog.url.setText('https://example.test/torrents?sort=new')
    dialog.add_site()
    assert len(dialog.sites) == 2
    dialog.items.setCurrentRow(0)
    dialog.remove_site()
    assert dialog.sites == [{'name': 'Saját oldal', 'url': 'https://example.test/torrents?sort=new'}]
    monkeypatch.setattr(dialog, 'exec', lambda: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(ui, 'TorrentSitesDialog', lambda _page: dialog)
    page.manage_sites()
    assert media.config['torrent_sites'] == dialog.sites
    opened = Mock()
    monkeypatch.setattr(ui.QDesktopServices, 'openUrl', opened)
    page.site_buttons[0].click()
    assert page.site_buttons[0].text() == 'Saját oldal'
    assert opened.call_args.args[0].toString() == dialog.sites[0]['url']
    other = media.DSVideoWindow()
    assert other.downloads_page.site_buttons[0].text() == 'Saját oldal'
    other.close()
    w.close()


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'file:///C:/test', 'https://', 'bad link'])
def test_unsafe_site_links_rejected(url):
    assert ui.torrent_sites({'torrent_sites': [{'name': 'Oldal', 'url': url}]}) == []


def test_empty_sites_stays_empty_and_failed_save_rolls_back(media, app, monkeypatch):
    media.config['torrent_sites'] = []
    w = media.DSVideoWindow()
    page = w.downloads_page
    assert not page.site_buttons
    monkeypatch.setattr(ui, 'TorrentSitesDialog', lambda _: SimpleNamespace(
        exec=lambda: QDialog.DialogCode.Accepted, sites=[{'name': 'Új', 'url': 'https://example.test'}]))
    monkeypatch.setattr(page.services, 'save_config', lambda: (False, 'disk'))
    monkeypatch.setattr(QMessageBox, 'warning', Mock())
    page.manage_sites()
    assert media.config['torrent_sites'] == []
    assert not page.site_buttons
    w.close()
