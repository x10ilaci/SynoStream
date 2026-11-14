from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QContextMenuEvent
from PyQt6.QtWidgets import QComboBox, QLineEdit, QPlainTextEdit, QTextEdit, QMenu, QDialog

from synostream_downloads import DownloadStationError
from synostream_torrent_selection import default_file_selected, validate_files, TASK2, LIST_API, POLL_API
from synostream_file_selection_ui import FileSelectionDialog
from synostream_download_ui import size_text
from test_download_station import dsm_server, client, wait_until, MAGNET


@pytest.mark.parametrize(('name', 'selected'), [
    ('Movie.mkv', True), ('Subtitles/movie.srt', True), ('Movie.NFO', True),
    ('Movie.SaMpLe.1080p.mkv', False), ('Sample/video.mkv', False),
    ('path\\SAMPLES\\video.mp4', False), ('movie.nfo.txt', True), ('notes.txt', True),
])
def test_default_selection_includes_nfo_skips_sample_case_insensitively(name, selected):
    assert default_file_selected(name) is selected


def preview():
    return dict(list_id='prepared', title='Torrent', destination='video/Filmek', files=[
        dict(index=8, name='Movie.mkv', size=100),
        dict(index=22, name='Movie.NFO', size=20),
        dict(index=4, name='Samples/clip.mkv', size=10),
        dict(index=37, name='Subtitles/movie.srt', size=5)])


def test_file_picker_defaults_indices_and_manual_override(media, app):
    w = media.DSVideoWindow()
    dialog = FileSelectionDialog(w.downloads_page, [preview()], size_text)
    assert dialog.selected_files() == {'prepared': [8, 22, 37]}
    assert dialog.start_button.isEnabled()
    dialog.set_selection('none')
    assert dialog.selected_files() == {'prepared': []}
    assert not dialog.start_button.isEnabled()
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    dialog.set_selection('all')
    assert set(dialog.selected_files()['prepared']) == {8, 22, 4, 37}
    dialog.set_selection('recommended')
    assert dialog.selected_files()['prepared'] == [8, 22, 37]
    dialog.reject()
    w.close()


def test_nfo_selected_without_sample_and_still_requires_confirmation(media, app):
    w = media.DSVideoWindow()
    data = preview()
    data['files'] = [dict(index=0, name='file.nfo', size=1), dict(index=1, name='sample.mkv', size=1)]
    dialog = FileSelectionDialog(w.downloads_page, [data], size_text)
    assert dialog.start_button.isEnabled()
    assert dialog.selected_files() == {'prepared': [0]}
    assert dialog.result() != QDialog.DialogCode.Accepted
    dialog.reject()
    w.close()


def test_metadata_preparation_never_starts_download_and_cancel_only_deletes_list(client):
    state, c = client
    previews = c.prepare(uri=MAGNET, destination='video/Filmek')
    assert previews[0]['files'][0]['index'] == 0
    assert state['selected_starts'] == []
    assert not any(kind == 'write' for kind, _params in state['calls'])
    identifier = previews[0]['list_id']
    c.discard_prepared(identifier)
    assert identifier not in c.prepared_lists
    assert state['prepared'] == {}
    assert state['selected_starts'] == []


def test_selected_start_sends_exact_sparse_file_indices(client):
    state, c = client
    result = c.prepare(uri=MAGNET, destination='video/Filmek')[0]
    entry = c.prepared_lists[result['list_id']]
    entry['files'] = [dict(index=8, name='movie.mkv'), dict(index=22, name='movie.nfo')]
    c.start_prepared(result['list_id'], [8])
    assert state['selected_starts'][0]['selected'] == [8]
    assert state['selected_starts'][0]['create_subfolder'] is True
    assert result['list_id'] not in c.prepared_lists


@pytest.mark.parametrize('indices', [[], [99], [-1], [True], ['0']])
def test_empty_or_invalid_selection_never_calls_start(client, indices):
    state, c = client
    result = c.prepare(uri=MAGNET, destination='video/Filmek')[0]
    with pytest.raises(ValueError):
        c.start_prepared(result['list_id'], indices)
    assert state['selected_starts'] == []
    c.discard_prepared(result['list_id'])


def test_unsupported_selection_api_does_not_fall_back_to_legacy_create(client):
    state, c = client
    c.api_info.pop(TASK2)
    with pytest.raises(DownloadStationError, match='nem indult'):
        c.prepare(uri=MAGNET, destination='video/Filmek')
    assert state['calls'] == []


def test_failed_metadata_does_not_start_and_discards_known_list(client, monkeypatch):
    state, c = client
    original = c._selection_request
    def request(api, method, **kwargs):
        if api == LIST_API and method == 'get':
            return {'files': []}
        return original(api, method, **kwargs)
    monkeypatch.setattr(c, '_selection_request', request)
    with pytest.raises(ValueError):
        c.prepare(uri=MAGNET, destination='video/Filmek')
    assert not c.prepared_lists and not state['prepared']
    assert not state['selected_starts']


def test_uncertain_selected_start_cannot_be_replayed(client, monkeypatch):
    import requests
    _state, c = client
    result = c.prepare(uri=MAGNET, destination='video/Filmek')[0]
    post = Mock(side_effect=requests.Timeout())
    monkeypatch.setattr(c.session, 'post', post)
    with pytest.raises(DownloadStationError):
        c.start_prepared(result['list_id'], [0])
    with pytest.raises(DownloadStationError, match='elküldött'):
        c.start_prepared(result['list_id'], [0])
    assert post.call_count == 1


def test_cancelling_picker_does_not_submit_any_files(media, app, dsm_server, monkeypatch):
    import synostream_download_ui as ui
    state, factory = dsm_server
    media.config.update(quickconnect_id='test', nas_username='test', nas_password='test')
    w = media.DSVideoWindow()
    p = w.downloads_page
    p.client_factory = factory
    dialog = SimpleNamespace(exec=lambda: QDialog.DialogCode.Accepted, files=[],
        destination=SimpleNamespace(text=lambda: 'video/Filmek'),
        tabs=SimpleNamespace(currentIndex=lambda: 0), uri=SimpleNamespace(text=lambda: MAGNET))
    monkeypatch.setattr(ui, 'CreateDownloadDialog', lambda *_args: dialog)
    monkeypatch.setattr(ui, 'FileSelectionDialog', lambda *_args: SimpleNamespace(exec=lambda: QDialog.DialogCode.Rejected))
    p.add_download()
    wait_until(app, lambda: not p.busy and not p.dialog_open)
    assert not state['selected_starts']
    assert not state['prepared']
    assert not hasattr(p, 'configure_button')
    w.close()
    wait_until(app, lambda: not w.running_threads())


@pytest.mark.parametrize('kind', ['line', 'combo', 'plain', 'rich'])
@pytest.mark.parametrize('language', ['hu', 'en'])
def test_native_editors_use_application_context_menu_language(media, app, monkeypatch, kind, language):
    m = media
    monkeypatch.setattr(m, 'UI_LANGUAGE', language)
    captured = []
    class CapturingMenu(QMenu):
        def exec(self, _point):
            captured.append([action.text() for action in self.actions() if not action.isSeparator()])
    monkeypatch.setattr(m, 'QMenu', CapturingMenu)
    if kind == 'line':
        widget = QLineEdit('test')
        target = widget
    elif kind == 'combo':
        widget = QComboBox()
        widget.setEditable(True)
        widget.lineEdit().setText('test')
        target = widget.lineEdit()
    else:
        widget = QPlainTextEdit('test') if kind == 'plain' else QTextEdit('test')
        target = widget.viewport()
    widget.show()
    app.processEvents()
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(5, 5), target.mapToGlobal(QPoint(5, 5)))
    app.sendEvent(target, event)
    assert len(captured) == 1
    assert ('Beillesztés' if language == 'hu' else 'Paste') in captured[0]
    assert ('Másolás' if language == 'hu' else 'Copy') in captured[0]
    assert ('Összes kijelölése' if language == 'hu' else 'Select All') in captured[0]
    widget.close()


def test_download_navigation_has_spacing_above_and_below(media, app):
    w = media.DSVideoWindow()
    layout = w.sidebar.layout()
    index = layout.indexOf(w.btn_downloads)
    assert layout.itemAt(index - 1).spacerItem().sizeHint().height() >= 20
    assert layout.itemAt(index + 1).spacerItem().sizeHint().height() >= 20
    assert layout.itemAt(index - 2).spacerItem() is not None
    w.close()


