"""Exercise the real NAS client and loopback proxy against a local DSM stand-in."""
import contextlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
import wave

import pytest
import requests
from synostream_nas import RemoteNASClient


@pytest.fixture
def nas_stream(media, monkeypatch):
    audio = io.BytesIO()
    with wave.open(audio, 'wb') as out:
        out.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
        out.writeframes(struct.pack('<h', 0) * 8000)
    payload = audio.getvalue()
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def send_payload(self, data, content_type='application/json', code=200, extra=None):
            body = json.dumps(data).encode() if content_type == 'application/json' else data
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', 0)))
            if self.path == '/Serv.php':
                self.send_payload([{'errno': 0, 'env': {'relay_region': 'test'}}])
            else:
                self.send_payload({'success': True, 'data': {'sid': 'test-session'}})
        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            calls.append((parsed.path, query, self.headers.get('Range')))
            if parsed.path == '/':
                self.send_payload({})
            elif parsed.path == '/webapi/query.cgi':
                self.send_payload({'success': True, 'data': {
                    'SYNO.API.Auth': {'path': 'auth.cgi', 'maxVersion': 6},
                    'SYNO.FileStation.List': {'path': 'list.cgi', 'maxVersion': 2},
                    'SYNO.FileStation.Download': {'path': 'download.cgi', 'maxVersion': 2}}})
            elif parsed.path == '/webapi/download.cgi':
                assert query['_sid'] == ['test-session']
                assert query['path'] == ['/video/test.wav']
                if self.headers.get('Range'):
                    start = int(self.headers['Range'].split('=')[1].split('-')[0])
                    self.send_payload(payload[start:], 'audio/wav', 206,
                        {'Content-Range': f'bytes {start}-{len(payload)-1}/{len(payload)}', 'Accept-Ranges': 'bytes'})
                else:
                    self.send_payload(payload, 'audio/wav', extra={'Accept-Ranges': 'bytes'})
            else:
                self.send_payload({'success': True, 'data': {'files': []}})
        def log_message(self, *_args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    class LocalNASClient(RemoteNASClient):
        def _connect_request(self, method, url, **kwargs):
            return super()._connect_request(method, base + urlsplit(url).path, **kwargs)
    client = LocalNASClient({'quickconnect_id': 'test', 'nas_username': 'test', 'nas_password': 'test'})
    # Keep real connection initialization above, then redirect the discovered endpoint to the test server.
    assert client.download_url == 'https://test.test.quickconnect.to/webapi/download.cgi'
    client.download_url = base + '/webapi/download.cgi'
    monkeypatch.setattr(media, 'RemoteNASClient', lambda credentials=None: client)
    monkeypatch.setattr(media, '_remote_playback_client', None)
    monkeypatch.setattr(media, '_remote_playback_server', None)
    monkeypatch.setattr(media, '_remote_playback_allowed_paths', set())
    url = media._remote_stream_url('syno:///video/test.wav')
    try:
        yield url, payload, calls
    finally:
        proxy = media._remote_playback_server
        if proxy:
            proxy.shutdown()
            proxy.server_close()
        client.session.close()
        server.shutdown()
        server.server_close()


def test_connection_discovers_download_endpoint_and_proxy_streams_bytes(nas_stream):
    url, payload, calls = nas_stream
    with requests.get(url, timeout=10) as response:
        assert response.status_code == 200
        assert response.content == payload
    with requests.get(url, headers={'Range': 'bytes=44-'}, timeout=10) as response:
        assert response.status_code == 206
        assert response.content == payload[44:]
        assert response.headers['Content-Range'].startswith('bytes 44-')
    assert any(path == '/webapi/download.cgi' for path, _, _ in calls)


def test_real_mpv_decodes_nas_proxy_stream(nas_stream, tmp_path):
    executable = os.environ.get('SYNOSTREAM_TEST_MPV')
    if not executable or not Path(executable).is_file():
        pytest.skip('Set SYNOSTREAM_TEST_MPV to an installed mpv.exe for the decoder integration check')
    url, _, calls = nas_stream
    log = tmp_path / 'mpv.log'
    result = subprocess.run([executable, '--no-config', '--ao=null', '--vo=null', '--length=0.3',
                             '--term-playing-msg=SYNOSTREAM_PLAYBACK_STARTED', f'--log-file={log}', url],
                            capture_output=True, timeout=30)
    assert result.returncode == 0, log.read_text(encoding='utf-8', errors='replace')[-3000:]
    assert b'SYNOSTREAM_PLAYBACK_STARTED' in result.stdout
    assert any(path == '/webapi/download.cgi' for path, _, _ in calls)
