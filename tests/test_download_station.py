import contextlib
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests
from PyQt6.QtCore import Qt, QMimeData, QUrl
from PyQt6.QtWidgets import QDialog

from synostream_downloads import DownloadStationClient, DownloadStationError, normalize_destination, validate_uri
from synostream_download_ui import CreateDownloadDialog, FolderDialog, task_values


MAGNET = 'magnet:?xt=urn:btih:' + 'a' * 40


def task(identifier='dbid_1', status='downloading', destination='video/Filmek'):
    return dict(id=identifier, title='Tesztfilm', status=status, size=1000,
                additional={'detail': {'destination': destination},
                            'transfer': {'size_downloaded': 500, 'size_uploaded': 250,
                                         'speed_download': 100, 'speed_upload': 20}})


@pytest.fixture
def dsm_server():
    state = {'calls': [], 'tasks': [task()], 'session_expired': False, 'missing_package': False,
             'task_error': None, 'session_names': [], 'prepared': {}, 'selected_starts': [], 'prepare_seq': 0}
    class Handler(BaseHTTPRequestHandler):
        def prepared(self):
            state['prepare_seq'] += 1
            key = 'prepared_' + str(state['prepare_seq'])
            state['prepared'][key] = {'title':'Synthetic test','type':'bt','files':[
                {'index':0,'name':'film.mkv','size':100},
                {'index':1,'name':'film.nfo','size':10},
                {'index':2,'name':'film-sample.mkv','size':20}]}
            return key
        def selection(self, params):
            api, method = params['api'][0], params['method'][0]
            decoded = {key: json.loads(value[0]) for key,value in params.items() if key not in ('api','method','version','_sid')}
            state['calls'].append(('selection', {'api':api,'method':method, **decoded}))
            if api.endswith('Settings.Location'):
                self.reply({'success':True,'data':{'default_destination':'video/Filmek'}})
            elif api == 'SYNO.DownloadStation2.Task':
                assert decoded['create_list'] is True
                self.reply({'success':True,'data':{'list_id':[self.prepared()]}})
            elif api.endswith('Task.List'):
                key=decoded['list_id']
                if method=='get': self.reply({'success':True,'data':state['prepared'][key]})
                else:
                    state['prepared'].pop(key,None)
                    self.reply({'success':True,'data':{}})
            elif api.endswith('Task.List.Polling'):
                if method=='download':
                    state['selected_starts'].append(decoded)
                    self.reply({'success':True,'data':{'task_id':'synthetic-ticket'}})
                elif method=='download_status': self.reply({'success':True,'data':{'finish':True,'success':True,'data':{}}})
                else: self.reply({'success':True,'data':{}})
        def reply(self, data):
            content = json.dumps(data).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        def do_POST(self):
            content = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            if self.path == '/Serv.php':
                self.reply([{'errno': 0, 'env': {'relay_region': 'test'}}])
                return
            if self.path == '/webapi/auth.cgi':
                params = parse_qs(content.decode())
                state['session_names'].append(params.get('session', [''])[0])
                self.reply({'success': True, 'data': {'sid': 'download-session'}})
                return
            if 'multipart' in self.headers.get('Content-Type', ''):
                state['calls'].append(('upload', content))
                if b'SYNO.DownloadStation2.Task' in content:
                    assert b'name="create_list"' in content and b'\r\ntrue\r\n' in content
                    self.reply({'success':True,'data':{'list_id':[self.prepared()]}})
                else:
                    self.reply({'success': True, 'data': {}})
                return
            params = parse_qs(content.decode())
            if params.get('api', [''])[0].startswith('SYNO.DownloadStation2.'):
                self.selection(params)
                return
            state['calls'].append(('write', params))
            self.reply({'success': True, 'data': {}})
        def do_GET(self):
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query)
            if parsed.path == '/':
                self.reply({})
            elif parsed.path == '/webapi/query.cgi':
                data = {
                    'SYNO.API.Auth': {'path': 'auth.cgi', 'maxVersion': 6},
                    'SYNO.FileStation.List': {'path': 'files.cgi', 'maxVersion': 2},
                    'SYNO.FileStation.Download': {'path': 'download.cgi', 'maxVersion': 2},
                }
                if not state['missing_package']:
                    data['SYNO.DownloadStation.Task'] = {'path': 'DownloadStation/task.cgi', 'maxVersion': 3}
                    for api in ('SYNO.DownloadStation2.Task','SYNO.DownloadStation2.Task.List','SYNO.DownloadStation2.Task.List.Polling','SYNO.DownloadStation2.Settings.Location'):
                        data[api] = {'path':'entry.cgi','maxVersion':2,'requestFormat':'JSON'}
                state['query'] = params['query'][0]
                self.reply({'success': True, 'data': data})
            elif parsed.path == '/webapi/entry.cgi':
                self.selection(params)
            elif parsed.path == '/webapi/DownloadStation/task.cgi':
                state['calls'].append(('read', params))
                if state['session_expired']:
                    state['session_expired'] = False
                    self.reply({'success': False, 'error': {'code': 106}})
                elif state['task_error']:
                    self.reply({'success': False, 'error': {'code': state['task_error']}})
                else:
                    offset, limit = int(params.get('offset', [0])[0]), int(params.get('limit', [100])[0])
                    self.reply({'success': True, 'data': {'tasks': state['tasks'][offset:offset+limit], 'total': len(state['tasks'])}})
            elif parsed.path == '/webapi/files.cgi':
                key = 'shares' if params.get('method') == ['list_share'] else 'files'
                self.reply({'success': True, 'data': {key: [{'name': 'video', 'path': '/video', 'isdir': True}], 'total': 1}})
            else:
                self.reply({'success': True, 'data': {}})
        def log_message(self, *_args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    class LocalClient(DownloadStationClient):
        def _connect_request(self, method, url, **kwargs):
            return super()._connect_request(method, base + urlsplit(url).path, **kwargs)
        def connect(self):
            super().connect()
            self.task_url = base + urlsplit(self.task_url).path
            self.list_url = base + urlsplit(self.list_url).path
            self.auth_url = base + '/webapi/auth.cgi'
            self.base_url = base
    try:
        yield state, LocalClient
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def client(dsm_server):
    state, factory = dsm_server
    client = factory(dict(quickconnect_id='test', nas_username='test', nas_password='test'))
    try:
        yield state, client
    finally:
        client.close()


def test_download_station_login_discovery_and_pagination(client):
    state, c = client
    state['tasks'] = [task(f'dbid_{i}') for i in range(205)]
    assert len(c.list_tasks()) == 205
    assert state['session_names'] == ['DownloadStation']
    assert 'SYNO.DownloadStation.Task' in state['query']
    assert [call[1]['offset'][0] for call in state['calls'] if call[0] == 'read'] == ['0', '100', '200']


def test_download_station_renews_its_own_session(client):
    state, c = client
    state['session_expired'] = True
    assert c.list_tasks()[0]['id'] == 'dbid_1'
    assert state['session_names'] == ['DownloadStation', 'DownloadStation']


def test_magnet_task_posts_explicit_destination(client):
    state, c = client
    c.create(uri=MAGNET, destination='syno:///video/Filmek')
    params = state['calls'][-1][1]
    assert params['method'] == ['create']
    assert params['uri'] == [MAGNET]
    assert params['destination'] == ['video/Filmek']
    assert params['_sid'] == ['download-session']


def test_torrent_upload_is_multipart_and_file_is_last(client, tmp_path):
    state, c = client
    path = tmp_path / 'sample.torrent'
    path.write_bytes(b'd4:infod4:name4:demoee')
    c.create(torrent_file=path, destination='/video/Filmek')
    kind, content = state['calls'][-1]
    assert kind == 'upload'
    assert b'filename="sample.torrent"' in content
    assert content.index(b'name="destination"') < content.index(b'name="file"')
    assert b'video/Filmek' in content


@pytest.mark.parametrize('action', ['pause', 'resume', 'delete'])
def test_task_actions_are_scoped_to_selected_ids(client, action):
    state, c = client
    c.task_action(action, ['dbid_1', 'dbid_2'])
    params = state['calls'][-1][1]
    assert params['method'] == [action]
    assert params['id'] == ['dbid_1,dbid_2']
    if action == 'delete':
        assert params['force_complete'] == ['false']


def test_mutating_timeouts_do_not_resubmit(client, monkeypatch):
    _state, c = client
    post = Mock(side_effect=requests.Timeout())
    monkeypatch.setattr(c.session, 'post', post)
    with pytest.raises(DownloadStationError, match='visszaigazolás'):
        c.create(uri=MAGNET)
    assert post.call_count == 1


def test_unsupported_package_and_permission_errors(dsm_server):
    state, factory = dsm_server
    state['missing_package'] = True
    with pytest.raises(DownloadStationError, match='Telepítsd'):
        factory(dict(quickconnect_id='test', nas_username='test', nas_password='test'))
    state['missing_package'] = False
    c = factory(dict(quickconnect_id='test', nas_username='test', nas_password='test'))
    state['task_error'] = 105
    with pytest.raises(DownloadStationError, match='jogosultsága'):
        c.list_tasks()
    c.close()


def test_old_api_reports_missing_creation_capabilities(client):
    _state, c = client
    c.task_version = 1
    with pytest.raises(DownloadStationError, match='célmappát'):
        c.create(torrent_file='irrelevant.torrent', destination='video')
    with pytest.raises(DownloadStationError, match='újabb'):
        c.create(uri=MAGNET)


@pytest.mark.parametrize('uri', ['', 'file:///C:/private', 'javascript:alert(1)', 'magnet:?dn=missing', 'https://a.test/one\nhttps://b.test/two'])
def test_invalid_download_links_are_rejected(uri):
    with pytest.raises(ValueError):
        validate_uri(uri)


def test_destination_normalization_and_validation():
    assert normalize_destination('syno:///video/TV műsorok') == 'video/TV műsorok'
    with pytest.raises(ValueError):
        normalize_destination('/video/../private')


def wait_until(app, predicate):
    deadline = time.monotonic() + 4
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    assert predicate()


def test_download_page_location_navigation_and_last_library(media, app):
    w = media.DSVideoWindow()
    w.downloads_page.refresh = lambda: None
    layout = w.sidebar.layout()
    assert layout.indexOf(w.library_nav_widget) < layout.indexOf(w.btn_downloads)
    assert layout.indexOf(w.btn_downloads) < layout.count() - 1
    old = media.config['last_library']
    w.show_downloads()
    assert w.stack.currentWidget() is w.downloads_page
    assert media.config['last_library'] == old
    w.switch_library('shows')
    assert not w.btn_downloads.isChecked()
    w.close()


def test_selection_stays_on_task_id_after_reorder_and_language_switch(media, app):
    w = media.DSVideoWindow()
    p = w.downloads_page
    p.apply_tasks([task('one'), task('two')])
    p.timer.stop()
    p.table.selectRow(0)
    assert p.selected_ids() == ['one']
    p.apply_tasks([task('two'), task('one')])
    p.timer.stop()
    assert p.selected_ids() == ['one']
    media.config['language'] = 'en'
    p.retranslate_texts()
    assert p.table.horizontalHeaderItem(0).text() == 'Name'
    assert p.status.text() == '2 tasks · 2 active'
    w.close()


def test_completion_notifies_once_and_only_refreshes_matching_library(media, app, monkeypatch):
    w = media.DSVideoWindow()
    media.config['remote_movies_path'] = '/video/Filmek'
    media.config['remote_shows_path'] = '/video/TV'
    start = Mock()
    monkeypatch.setattr(w, 'start_library_scan', start)
    w.downloads_page.apply_tasks([task()])
    start.assert_not_called()
    w.downloads_page.apply_tasks([task(status='seeding')])
    assert start.call_args.args == ('movies',)
    assert start.call_args.kwargs == {'force_remote_refresh': True}
    start.reset_mock()
    w.downloads_page.apply_tasks([task(status='seeding')])
    start.assert_not_called()
    w.close()


def test_download_page_fetches_async_and_folder_browser_uses_same_client(media, app, dsm_server):
    state, factory = dsm_server
    media.config.update(quickconnect_id='test', nas_username='test', nas_password='test')
    w = media.DSVideoWindow()
    p = w.downloads_page
    p.client_factory = factory
    p.refresh()
    wait_until(app, lambda: not p.busy)
    assert p.table.rowCount() == 1
    dialog = FolderDialog(p)
    dialog.show()
    wait_until(app, lambda: not p.busy and dialog.items.count() == 1)
    dialog.load('/video')
    wait_until(app, lambda: not p.busy)
    assert dialog.path == '/video'
    dialog.reject()
    w.close()
    wait_until(app, lambda: not w.running_threads())


def test_drop_filter_and_creation_dialog_defaults(media, app, tmp_path):
    media.config['remote_movies_path'] = '/video/Filmek'
    media.config['download_station_destination'] = 'video/Filmek'
    w = media.DSVideoWindow()
    path = tmp_path / 'one.torrent'
    path.write_bytes(b'de')
    other = tmp_path / 'ignore.exe'
    other.write_bytes(b'')
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)), QUrl.fromLocalFile(str(other)), QUrl('https://example.test/a.torrent')])
    assert [Path(value) for value in w.downloads_page.dropped_files(mime)] == [path]
    dialog = CreateDownloadDialog(w.downloads_page, [str(path)])
    assert dialog.tabs.currentIndex() == 1
    assert dialog.destination.text() == 'video/Filmek'
    assert not hasattr(dialog, 'kind')
    assert not hasattr(dialog, 'libraries')
    assert dialog.file_list.count() == 1
    dialog.reject()
    w.close()


def test_task_display_handles_unknown_size_and_eta():
    t = task()
    assert task_values(t)[0] == 50
    assert task_values(t)[3] == '0:05'
    t['size'] = None
    assert task_values(t)[0] == 0
    t['status'] = 'seeding'
    assert task_values(t)[0] == 100


def test_multiple_torrents_submit_from_dialog_and_defaults_persist(media, app, dsm_server, monkeypatch, tmp_path):
    import synostream_download_ui as ui
    state, factory = dsm_server
    media.config.update(quickconnect_id='test', nas_username='test', nas_password='test')
    w = media.DSVideoWindow()
    p = w.downloads_page
    p.client_factory = factory
    files = []
    for index in range(2):
        path = tmp_path / f'{index}.torrent'
        path.write_bytes(b'd4:infod4:name4:demoee')
        files.append(str(path))
    dialog = SimpleNamespace(exec=lambda: QDialog.DialogCode.Accepted, files=files,
        destination=SimpleNamespace(text=lambda: 'video/Filmek'), kind=SimpleNamespace(currentData=lambda: 'movies'),
        tabs=SimpleNamespace(currentIndex=lambda: 1), uri=SimpleNamespace(text=lambda: ''))
    monkeypatch.setattr(ui, 'CreateDownloadDialog', lambda *_args: dialog)
    picker = SimpleNamespace(exec=lambda: QDialog.DialogCode.Accepted,
                             selected_files=lambda: {'prepared_1':[0], 'prepared_2':[0]})
    monkeypatch.setattr(ui, 'FileSelectionDialog', lambda *_args: picker)
    p.add_download(files)
    wait_until(app, lambda: not p.busy)
    assert len([call for call in state['calls'] if call[0] == 'upload']) == 2
    assert media.config['download_station_destination'] == 'video/Filmek'
    assert [entry['selected'] for entry in state['selected_starts']] == [[0], [0]]
    assert p.table.rowCount() == 1
    w.close()
    wait_until(app, lambda: not w.running_threads())


def test_cancelled_removal_never_calls_nas(media, app, monkeypatch):
    import synostream_download_ui as ui
    w = media.DSVideoWindow()
    p = w.downloads_page
    p.apply_tasks([task()])
    p.timer.stop()
    p.table.selectRow(0)
    start = Mock()
    monkeypatch.setattr(p, 'start_operation', start)
    monkeypatch.setattr(ui.QMessageBox, 'question', lambda *_args: ui.QMessageBox.StandardButton.No)
    p.action('delete')
    start.assert_not_called()
    w.close()


def test_completion_refreshes_multiple_libraries_in_sequence(media, app, monkeypatch):
    w = media.DSVideoWindow()
    media.config['remote_movies_path'] = '/video/Filmek'
    media.config['remote_shows_path'] = '/video/TV'
    calls = []
    def start(key, **kwargs):
        calls.append(key)
        w.scanner_thread = SimpleNamespace(wait=lambda: None, isRunning=lambda: False)
    monkeypatch.setattr(w, 'start_library_scan', start)
    w.on_downloads_completed([task(destination='video')])
    assert calls == ['movies']
    assert list(w.download_refresh_targets) == ['shows']
    w.on_scanner_finished()
    assert calls == ['movies', 'shows']
    w.on_scanner_finished()
    assert not w.download_refresh_targets
    w.close()


def test_shutdown_during_connection_closes_late_client(media, app):
    gate = threading.Event()
    closed = []
    w = media.DSVideoWindow()
    p = w.downloads_page
    class Client:
        def __init__(self, credentials, stop):
            self.credentials, self.should_stop = credentials, stop
            self.lock = threading.RLock()
            gate.wait(2)
        def _check_cancelled(self):
            if self.should_stop():
                raise InterruptedError()
        def close(self):
            closed.append(True)
    p.client_factory = Client
    p.start_operation(lambda _client: [])
    p.shutdown()
    gate.set()
    wait_until(app, lambda: not p.busy)
    assert closed and p.client is None
    w.close()


def test_changed_nas_cannot_receive_action_for_old_selected_task(media, app, monkeypatch):
    w = media.DSVideoWindow()
    p = w.downloads_page
    p.apply_tasks([task()])
    p.timer.stop()
    p.table.selectRow(0)
    media.config['nas_username'] = 'different-account'
    refresh = Mock()
    start = Mock()
    monkeypatch.setattr(p, 'refresh', refresh)
    monkeypatch.setattr(p, 'start_operation', start)
    p.action('pause')
    start.assert_not_called()
    refresh.assert_called_once()
    assert p.table.rowCount() == 0
    w.close()


def test_stale_reply_after_nas_change_is_ignored(media, app):
    w = media.DSVideoWindow()
    p = w.downloads_page
    p._operation_credentials = p.credentials()
    p._success = Mock()
    media.config['quickconnect_id'] = 'changed-nas'
    p.operation_succeeded([task()])
    p._success.assert_not_called()
    assert p.refresh_after
    p.refresh_after = False
    w.close()


def test_new_task_already_finished_on_first_seen_poll_is_reported(media, app):
    w = media.DSVideoWindow()
    p = w.downloads_page
    received = []
    p.completed.connect(received.append)
    p.apply_tasks([task('existing', 'seeding')])
    assert received == []
    p.apply_tasks([task('existing', 'seeding'), task('new', 'finished')])
    assert len(received) == 1
    assert received[0][0]['id'] == 'new'
    p.timer.stop()
    w.close()

