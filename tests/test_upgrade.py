import json
from pathlib import Path
import sqlite3
import time
from types import SimpleNamespace
from unittest.mock import Mock
import zipfile

import pytest
import requests

from synostream_nas import RemoteNASClient
from synostream_storage import data_directory, backup_before_upgrade, commit_data_version, migrate_schema


def bare_client():
    c = RemoteNASClient.__new__(RemoteNASClient)
    import threading
    c.lock = threading.RLock()
    c.sid = 'old-session'
    c.list_url = 'https://example.invalid/webapi/entry.cgi'
    c.download_url = c.list_url
    c.download_version = c.list_version = 2
    c.should_stop = lambda: False
    c.session = Mock()
    c.connect = Mock(side_effect=lambda: setattr(c, 'sid', 'new-session'))
    c._pause = Mock()
    return c


def response(payload=None, status=200):
    r = Mock()
    r.status_code = status
    r.headers = {}
    r.json.return_value = payload
    if status >= 400:
        r.raise_for_status.side_effect = requests.HTTPError(response=r)
    return r


def test_nas_session_renews_once():
    c = bare_client()
    c.session.get.side_effect = [response({'success': False, 'error': {'code': 106}}),
                               response({'success': True, 'data': {'files': [1]}})]
    assert c.api_get('api', 2, 'list') == {'files': [1]}
    c.connect.assert_called_once()
    assert c.session.get.call_args.kwargs['params']['_sid'] == 'new-session'


def test_nas_session_does_not_loop_on_repeated_expiry():
    c = bare_client()
    c.session.get.return_value = response({'success': False, 'error': {'code': 119}})
    with pytest.raises(RuntimeError):
        c.api_get('api', 2, 'list')
    assert c.connect.call_count == 1
    assert c.session.get.call_count == 2


def test_nas_timeout_retry_is_bounded():
    c = bare_client()
    c.session.get.side_effect = requests.Timeout()
    with pytest.raises(RuntimeError, match='nem érhető el'):
        c.api_get('api', 2, 'list')
    assert c.session.get.call_count == 3


def test_nas_http_retry_then_success():
    c = bare_client()
    c.session.get.side_effect = [response(status=503), response({'success': True, 'data': {'ok': 1}})]
    assert c.api_get('api', 2, 'list') == {'ok': 1}
    assert c._pause.call_count == 1


def test_permission_error_is_not_retried():
    c = bare_client()
    c.session.get.return_value = response({'success': False, 'error': {'code': 105}})
    with pytest.raises(RuntimeError, match='105'):
        c.api_get('api', 2, 'list')
    assert c.session.get.call_count == 1


def test_nas_cancel_does_not_issue_request():
    c = bare_client()
    c.should_stop = lambda: True
    with pytest.raises(InterruptedError):
        c.list_folder('/video')
    c.session.get.assert_not_called()


def test_nas_paginates_large_folders():
    c = bare_client()
    entries = [{'name': f'{index}.mkv', 'path': f'/video/{index}.mkv'} for index in range(502)]
    c.api_get = Mock(side_effect=[{'total': 502, 'files': entries[:500]},
                                 {'total': 502, 'files': entries[500:]}])
    assert c.list_folder('/video') == entries
    assert c.api_get.call_args.kwargs['offset'] == 500


def test_stream_renews_session_and_preserves_range():
    c = bare_client()
    expired = response({'success': False, 'error': {'code': 106}})
    expired.headers = {'Content-Type': 'application/json'}
    video = response(status=206)
    c.session.get.side_effect = [expired, video]
    assert c.open_stream('/video/movie.mkv', {'Range': 'bytes=100-'}) is video
    assert c.session.get.call_args.kwargs['headers']['Range'] == 'bytes=100-'
    assert c.session.get.call_args.kwargs['params']['_sid'] == 'new-session'
    expired.close.assert_called_once()


def test_legacy_data_migrates_without_changing_original(tmp_path, monkeypatch):
    monkeypatch.delenv('SYNOSTREAM_DATA_DIR')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    old = tmp_path / 'old'
    old.mkdir()
    (old / 'config.json').write_text('{"language":"hu"}')
    with sqlite3.connect(old / 'media_library.db') as conn:
        conn.execute('CREATE TABLE sample(value)')
        conn.execute('INSERT INTO sample VALUES (42)')
    target = Path(data_directory(old))
    assert target != old
    assert (old / 'config.json').exists()
    with sqlite3.connect(target / 'media_library.db') as conn:
        assert conn.execute('SELECT value FROM sample').fetchone()[0] == 42
    (old / 'config.json').write_text('{}')
    assert data_directory(old) == str(target)
    assert json.loads((target / 'config.json').read_text())['language'] == 'hu'


def test_portable_mode(tmp_path, monkeypatch):
    monkeypatch.delenv('SYNOSTREAM_DATA_DIR')
    (tmp_path / 'portable.flag').touch()
    assert Path(data_directory(tmp_path)) == tmp_path


def test_upgrade_backup_precedes_new_version_marker(tmp_path):
    (tmp_path / 'config.json').write_text('{"old":true}')
    backup_before_upgrade(tmp_path, '1.96')
    copies = list((tmp_path / 'upgrade_backups').glob('*/config.json'))
    assert len(copies) == 1
    assert copies[0].read_text() == '{"old":true}'
    assert not (tmp_path / 'data_version.json').exists()
    commit_data_version(tmp_path, '1.96')
    backup_before_upgrade(tmp_path, '1.96')
    assert len(list((tmp_path / 'upgrade_backups').glob('*/config.json'))) == 1


def test_schema_rejects_future_version():
    with sqlite3.connect(':memory:') as conn:
        conn.execute('PRAGMA user_version=99')
        with pytest.raises(sqlite3.DatabaseError):
            migrate_schema(conn)


def test_playback_progress_and_completed_episode_state(media):
    m = media
    episodes = [{'path': 'C:/shows/test/e1.mkv', 'episode_title': 'S01E01'},
                {'path': 'C:/shows/test/e2.mkv', 'episode_title': 'S01E02'}]
    entry = dict(episodes[0], media_title='Test show', is_movie=False)
    m.save_playback_progress(entry, 30, 100, episodes)
    state = m.get_playback_state(episodes[0]['path'])
    assert state['position'] == 30 and not state['watched']
    m.save_playback_progress(entry, 95, 100, episodes)
    state = m.get_playback_state(episodes[0]['path'])
    assert state['watched'] and state['playlist_paths'] == episodes


def test_backup_restore_roundtrip_and_no_exported_secrets(media, tmp_path):
    m = media
    m.config['tmdb_api_key'] = 'test-private-key'
    m.save_playback_progress({'path': 'C:/movie.mkv', 'media_title': 'Film'}, 45, 200, [])
    archive = str(tmp_path / 'backup.zip')
    m.create_backup_archive(archive)
    with zipfile.ZipFile(archive) as z:
        assert 'test-private-key' not in z.read('config.json').decode()
        assert 'credentials.dat' not in z.namelist()
    m.save_playback_progress({'path': 'C:/movie.mkv'}, 80, 200, [])
    m.restore_backup_archive(archive)
    assert m.get_playback_state('C:/movie.mkv')['position'] == 45


def test_virtual_grid_10000_items_scroll_search_update_and_resize(media, app):
    page = media.MediaPage('Test')
    page.resize(1000, 720)
    page.show()
    app.processEvents()
    page.replace_items([dict(file_path=f'C:/demo/{i}.mkv', title=f'Movie {i}', is_movie=True)
                        for i in range(10000)])
    page.reflow()
    app.processEvents()
    assert page.count() == 10000
    assert 0 < sum(r.widget is not None for _, r in page.cards) < 50
    first = page._ordered_records[0]
    page.scroll.verticalScrollBar().setValue(page.scroll.verticalScrollBar().maximum())
    app.processEvents()
    assert first.widget is None
    assert page._ordered_records[-1].widget is not None
    page.search_box.setText('Movie 9999')
    page.reflow()
    app.processEvents()
    assert len(page._ordered_records) == 1
    page.update_item(dict(file_path='C:/demo/9999.mkv', title='Updated', is_movie=True))
    page.search_box.clear()
    page.set_card_size('large')
    page.reflow()
    app.processEvents()
    assert page.count() == 10000
    assert sum(r.widget is not None for _, r in page.cards) < 50
    page.close()


def test_partial_scan_preserves_failed_library(media):
    m = media
    scanner = m.LibraryScannerThread(['C:/good', 'C:/bad'], [])
    scanner.failed_libraries.add('bad')
    scanner.seen_media_keys = {(m.normalize_media_path('C:/good/keep.mkv'), 1)}
    with sqlite3.connect(m.DB_FILE) as conn:
        for path in ('C:/good/keep.mkv', 'C:/good/remove.mkv', 'C:/bad/keep.mkv'):
            conn.execute('INSERT INTO media_cache(file_path,is_movie) VALUES (?,1)', (path,))
        conn.commit()
        scanner.cleanup_stale_media_cache(conn, [('good', 'C:/good', True), ('bad', 'C:/bad', True)], False)
        remaining = {row[0] for row in conn.execute('SELECT file_path FROM media_cache')}
    assert remaining == {'C:/good/keep.mkv', 'C:/bad/keep.mkv'}


def wait_for(app, predicate):
    deadline = time.monotonic() + 3
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    assert predicate()


def test_nas_dialog_remains_responsive_and_cancel_discards_result(media, app, monkeypatch):
    import threading
    gate = threading.Event()
    closed = []
    class Client:
        sid = 'test'
        def __init__(self, credentials, stop):
            gate.wait(2)
        def close(self):
            closed.append(True)
    monkeypatch.setattr(media, 'RemoteNASClient', Client)
    dialog = media.RemoteQuickConnectDialog()
    dialog.id_edit.setText('test')
    dialog.user_edit.setText('test')
    dialog.pass_edit.setText('test')
    dialog.show()
    dialog.connect_nas()
    tick = []
    media.QTimer.singleShot(0, lambda: tick.append(True))
    wait_for(app, lambda: bool(tick))
    assert dialog._nas_task is not None
    dialog.reject()
    gate.set()
    wait_for(app, lambda: dialog._nas_task is None)
    wait_for(app, lambda: bool(closed))
    assert dialog.sid == ''


def test_last_library_starts_without_home_or_nas_network(media, app):
    media.config['last_library'] = 'shows'
    window = media.DSVideoWindow()
    assert window.stack.currentWidget() is window.shows_page
    assert not hasattr(window, 'home_page')
    assert not hasattr(window, 'btn_home')
    window.show()
    app.processEvents()
    window.close()


def test_monitor_saves_previous_episode_before_switch_and_marks_eof(media, app):
    m = media
    entries = [dict(path='C:/episode1.mkv', media_title='Show', is_movie=False),
               dict(path='C:/episode2.mkv', media_title='Show', is_movie=False)]
    monitor = m.MpvPlaybackMonitor(Mock(), 'unused', entries)
    monitor._bind_source(entries[0]['path'])
    monitor._on_message({'event': 'property-change', 'name': 'duration', 'data': 100})
    monitor._on_message({'event': 'property-change', 'name': 'time-pos', 'data': 40})
    monitor._on_message({'event': 'start-file'})
    monitor._bind_source(entries[1]['path'])
    assert m.get_playback_state(entries[0]['path'])['position'] == 40
    assert monitor.position == monitor.duration == 0
    monitor._on_message({'event': 'property-change', 'name': 'duration', 'data': 200})
    monitor._on_message({'event': 'end-file', 'reason': 'eof'})
    assert m.get_playback_state(entries[1]['path'])['watched']


def test_connection_retries_before_login_only_on_transient_failures():
    client = bare_client()
    client.session.get.side_effect = [requests.Timeout(), response({'ok': True})]
    assert client._connect_request('get', 'https://example.invalid', timeout=(1, 1)).json() == {'ok': True}
    assert client.session.get.call_count == 2


def test_future_backup_rejected_before_replacing_current_data(media, tmp_path):
    m = media
    m.save_playback_progress({'path': 'C:/film.mkv'}, 45, 100, [])
    original = str(tmp_path / 'original.zip')
    m.create_backup_archive(original)
    future_db = tmp_path / 'future.db'
    m.snapshot_database(m.DB_FILE, str(future_db))
    from contextlib import closing
    with closing(sqlite3.connect(future_db)) as conn:
        conn.execute('PRAGMA user_version=99')
        conn.commit()
    archive = tmp_path / 'future.zip'
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(archive, 'w') as dst:
        for name in src.namelist():
            dst.writestr(name, future_db.read_bytes() if name == 'media_library.db' else src.read(name))
    with pytest.raises(ValueError, match='újabb'):
        m.restore_backup_archive(str(archive))
    assert m.get_playback_state('C:/film.mkv')['position'] == 45


def test_nas_dialog_connect_then_loads_folders(media, app, monkeypatch):
    clients = []
    class Client:
        def __init__(self, credentials, stop):
            for key in ('base_url', 'sid', 'auth_url', 'list_url', 'download_url'):
                setattr(self, key, 'test')
            self.auth_version = self.list_version = self.download_version = 2
            self.session = Mock()
            self.should_stop = stop
            self.closed = False
            clients.append(self)
        def list_folder(self, path):
            return [{'name': 'Movies', 'path': '/Movies', 'isdir': True}]
        def close(self):
            self.closed = True
    monkeypatch.setattr(media, 'RemoteNASClient', Client)
    dialog = media.RemoteQuickConnectDialog()
    dialog.id_edit.setText('test')
    dialog.user_edit.setText('test')
    dialog.pass_edit.setText('test')
    dialog.show()
    dialog.connect_nas()
    wait_for(app, lambda: dialog._nas_task is None and dialog.items.count() == 1)
    assert dialog.sid == 'test'
    assert dialog.select_folder_btn.isEnabled()
    dialog.reject()
    wait_for(app, lambda: clients[0].closed)
