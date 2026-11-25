import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock
from urllib.parse import urlsplit, parse_qs, urlencode, urlunsplit
import pytest
import requests
from synostream_downloads import DownloadStationClient, DownloadStationError
from synostream_torrent_selection import LIST_API
from test_download_station import wait_until
from test_nas_playback_integration import nas_stream


@pytest.mark.parametrize('sites', [[{'name': 'Saját oldal', 'url': 'https://example.test/torrent'}], []])
def test_torrent_sites_survive_real_process_restart(media, tmp_path, sites):
    media.config['torrent_sites'] = sites
    assert media.save_config()[0]
    source = Path(__file__).resolve().parents[1] / 'SynoStream_1.107.py'
    script = "import sys,importlib.util,json; from pathlib import Path; p=Path(sys.argv[1]); sys.path.insert(0,str(p.parent)); s=importlib.util.spec_from_file_location('restart_app',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(json.dumps(m.config['torrent_sites']))"
    env = os.environ.copy()
    env['SYNOSTREAM_DATA_DIR'] = str(tmp_path)
    env['LOCALAPPDATA'] = str(tmp_path / 'localappdata')
    result = subprocess.run([sys.executable, '-c', script, str(source)], env=env,
                            text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == sites
    assert json.loads(Path(media.CONFIG_FILE).read_text(encoding='utf-8'))['torrent_sites'] == sites


def test_legacy_settings_receive_default_site_but_unchanged_file_is_not_rewritten(media, monkeypatch):
    path = Path(media.CONFIG_FILE)
    path.write_text('{"language":"hu"}', encoding='utf-8')
    config, _warning = media.load_config()
    assert config['torrent_sites'][0]['name'] == 'nCore'
    before = path.read_bytes()
    writer = Mock(side_effect=AssertionError('Unchanged settings should not be rewritten'))
    monkeypatch.setattr(media, 'write_config_atomic', writer)
    assert media.load_config()[0]['torrent_sites'] == config['torrent_sites']
    writer.assert_not_called()
    assert path.read_bytes() == before


@pytest.mark.parametrize('operation', ['startup', 'save'])
@pytest.mark.parametrize('failure', ['partial_write', 'replace'])
def test_configuration_failure_preserves_previous_file(media, monkeypatch, operation, failure):
    path = Path(media.CONFIG_FILE)
    previous = b'{"movies_paths":["C:/AuditOnly/Movies"],"language":"hu"}'
    path.write_bytes(previous)
    media.config['movies_paths'] = ['C:/AuditOnly/Changed']
    if failure == 'partial_write':
        def dump(_value, output, **_kwargs):
            output.write('{"partial":')
            raise OSError(28, 'Simulated disk full')
        monkeypatch.setattr(media.json, 'dump', dump)
    else:
        original = media.os.replace
        def replace(source, destination):
            if str(destination) == media.CONFIG_FILE:
                raise OSError('Simulated replacement failure')
            return original(source, destination)
        monkeypatch.setattr(media.os, 'replace', replace)
    if operation == 'startup':
        assert media.load_config()[0]['movies_paths'] == ['C:/AuditOnly/Movies']
    else:
        assert not media.save_config()[0]
    assert path.read_bytes() == previous
    assert not list(path.parent.glob('.config-*.tmp'))


@pytest.fixture
def profile_proxy(media, monkeypatch):
    created = []
    class Upstream:
        status_code = 200
        def __init__(self, account):
            self.body = account.encode()
            self.headers = {'Content-Type':'video/mp4', 'Content-Length':str(len(self.body))}
        def iter_content(self, _size):
            yield self.body
        def close(self):
            pass
    class Client:
        def __init__(self, credentials):
            self.credentials = dict(credentials)
            self.sid = 'audit-session'
            self.closed = False
            self.download_version = 2
            created.append(self)
        def open_stream(self, _path, _headers):
            assert not self.closed
            return Upstream(self.credentials['nas_username'])
        def close(self):
            self.closed = True
    monkeypatch.setattr(media, 'RemoteNASClient', Client)
    monkeypatch.setattr(media, '_remote_playback_server', None)
    monkeypatch.setattr(media, '_remote_playback_client', None)
    monkeypatch.setattr(media, '_remote_playback_profiles', {})
    monkeypatch.setattr(media, '_remote_playback_allowed_paths', set())
    media.config.update(quickconnect_id='audit', nas_username='account-A', nas_password='password-A')
    try:
        yield media, created
    finally:
        if media._remote_playback_server:
            media._remote_playback_server.shutdown()
            media._remote_playback_server.server_close()
        for client in created:
            if not client.closed:
                client.close()


def test_new_nas_profile_does_not_change_running_stream_or_authorize_old_paths(profile_proxy):
    m, clients = profile_proxy
    old = m._remote_stream_url('syno:///video/same.mkv')
    private = m._remote_stream_url('syno:///video/old-only.mkv')
    assert requests.get(old, timeout=3).text == 'account-A'
    m.config.update(nas_username='account-B', nas_password='password-B', quickconnect_id='other-nas')
    new = m._remote_stream_url('syno:///video/same.mkv')
    assert requests.get(new, timeout=3).text == 'account-B'
    assert requests.get(old, timeout=3).text == 'account-A'
    assert [client.credentials['nas_username'] for client in clients] == ['account-A', 'account-B']
    assert 'account-' not in new and 'password-' not in new
    parts = urlsplit(new)
    query = parse_qs(parts.query)
    query['path'] = ['/video/old-only.mkv']
    forged = urlunsplit(parts._replace(query=urlencode(query, doseq=True)))
    assert requests.get(forged, timeout=3).status_code == 403
    assert requests.get(private, timeout=3).text == 'account-A'


def test_stream_leases_keep_parallel_players_and_close_only_unused_profile(profile_proxy, app):
    m, clients = profile_proxy
    first = m._remote_stream_url('syno:///video/same.mkv')
    duplicate = m._remote_stream_url('syno:///video/same.mkv')
    assert requests.get(first, timeout=3).text == 'account-A'
    m.release_remote_sources([first])
    assert not clients[0].closed
    assert requests.get(duplicate, timeout=3).text == 'account-A'
    m.config['nas_username'] = 'account-B'
    other = m._remote_stream_url('syno:///video/same.mkv')
    assert requests.get(other, timeout=3).text == 'account-B'
    m.release_remote_sources([duplicate])
    wait_until(app, lambda: clients[0].closed)
    assert not clients[1].closed
    assert requests.get(other, timeout=3).text == 'account-B'
    assert requests.get(first, timeout=3).status_code == 403
    m.release_remote_sources([other])
    wait_until(app, lambda: clients[1].closed)
    assert not m._remote_playback_profiles
    assert not m._remote_playback_allowed_paths


@pytest.mark.parametrize('readonly', [True, False])
def test_session_renewal_rediscovers_url_and_endpoint(readonly):
    client = DownloadStationClient.__new__(DownloadStationClient)
    client.api_info = {LIST_API: {'path':'old.cgi', 'maxVersion':2}}
    client.base_url, client.sid = 'https://old.example.test', 'old'
    client._check_cancelled = lambda: None
    expired, success = Mock(), Mock()
    expired.json.return_value = {'success':False, 'error':{'code':106}}
    success.json.return_value = {'success':True, 'data':{'ok':True}}
    client.session = Mock()
    transport = client.session.get if readonly else client.session.post
    transport.side_effect = [expired, success]
    def reconnect():
        client.base_url, client.sid = 'https://new.example.test', 'new'
        client.api_info[LIST_API] = {'path':'new.cgi', 'maxVersion':2}
    client.connect = reconnect
    assert client._selection_request(LIST_API,'get',readonly=readonly) == {'ok':True}
    assert transport.call_args_list[1].args[0] == 'https://new.example.test/webapi/new.cgi'
    params = transport.call_args_list[1].kwargs['params' if readonly else 'data']
    assert params['_sid'] == 'new'


def test_real_playback_releases_profile_when_mpv_exits(media, app, nas_stream, monkeypatch):
    executable = os.environ.get('SYNOSTREAM_TEST_MPV')
    if not executable or not Path(executable).is_file():
        pytest.skip('Set SYNOSTREAM_TEST_MPV for real IPC lifecycle validation')
    url, _payload, calls = nas_stream
    media.release_remote_sources([url])
    client = media.RemoteNASClient({})
    client.auth_url = client.download_url.rsplit('/',1)[0] + '/auth.cgi'
    media.config['mpv_path'] = executable
    monkeypatch.setattr(media, 'mpv_localized_context_menu_args', lambda _path: [])
    failed = Mock()
    monkeypatch.setattr(media.QMessageBox, 'critical', failed)
    original = media.subprocess.Popen
    spawned = []
    def popen(command, **kwargs):
        process = original([*command, '--ao=null', '--vo=null', '--force-window=no', '--terminal=no', '--speed=10'], **kwargs)
        spawned.append(process)
        return process
    monkeypatch.setattr(media.subprocess, 'Popen', popen)
    parent = media.QWidget()
    media.play_with_mpv(parent, 'syno:///video/test.wav', title='IPC test', resume_position=0)
    wait_until(app, lambda: spawned and spawned[0].poll() is not None and not media._remote_playback_profiles)
    wait_until(app, lambda: not any(worker.isRunning() for worker in media._background_workers))
    assert spawned[0].returncode == 0
    failed.assert_not_called()
    assert any(path == '/webapi/download.cgi' for path, _, _ in calls)
    parent.close()


def test_ipc_monitor_ending_does_not_close_a_still_running_player(profile_proxy, app):
    import threading
    m, clients = profile_proxy
    url = m._remote_stream_url('syno:///video/still-playing.mkv')
    assert requests.get(url, timeout=3).text == 'account-A'
    stopped = threading.Event()
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = lambda: stopped.wait(5)
    try:
        m.release_remote_sources_after_exit(process, (url,))
        wait_until(app, lambda: process.wait.called)
        assert not clients[0].closed
        assert requests.get(url, timeout=3).text == 'account-A'
        process.poll.return_value = 0
        stopped.set()
        wait_until(app, lambda: clients[0].closed)
        assert not m._remote_playback_profiles
    finally:
        stopped.set()
