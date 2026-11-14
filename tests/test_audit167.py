import copy
import json
import logging
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from synostream_storage import recover_settings_transaction, settings_transaction, backup_before_upgrade, migrate_schema
from synostream_playback import MpvPlaybackMonitor


@pytest.mark.parametrize('mode', ['password_change', 'remove_password', 'first_save'])
def test_failed_settings_save_restores_pair(media, monkeypatch, mode):
    if mode != 'first_save':
        media.config.update(nas_username='old-user', nas_password='old-password', quickconnect_id='old-nas')
        assert media.save_config()[0]
    paths = [Path(media.CONFIG_FILE), Path(media.SECRET_STORE_FILE)]
    before = [p.read_bytes() if p.exists() else None for p in paths]
    media.config.update(nas_username='new-user', nas_password='' if mode == 'remove_password' else 'new-password', quickconnect_id='new-nas')
    def fail(_config):
        raise OSError('simulated config failure')
    monkeypatch.setattr(media, 'write_config_atomic', fail)
    assert not media.save_config()[0]
    assert before == [p.read_bytes() if p.exists() else None for p in paths]
    assert not (paths[0].parent / '.settings-pending').exists()
    loaded, _ = media.load_config()
    assert loaded['nas_username'] == (media.DEFAULT_CONFIG['nas_username'] if mode == 'first_save' else 'old-user')
    assert loaded['nas_password'] == (media.DEFAULT_CONFIG['nas_password'] if mode == 'first_save' else 'old-password')


@pytest.mark.parametrize('previous', [True, False])
def test_interrupted_settings_save_is_recovered_on_next_process(tmp_path, previous):
    if previous:
        (tmp_path / 'config.json').write_bytes(b'old-config')
        (tmp_path / 'credentials.dat').write_bytes(b'old-encrypted')
    code = '''import os,sys
from pathlib import Path
from synostream_storage import settings_transaction
p=Path(sys.argv[1])
with settings_transaction(p):
    (p/'credentials.dat').write_bytes(b'new-encrypted')
    (p/'config.json').write_bytes(b'new-config')
    os._exit(37)
'''
    process = subprocess.run([sys.executable, '-c', code, str(tmp_path)], timeout=10)
    assert process.returncode == 37
    recover_settings_transaction(tmp_path)
    for name, value in [('config.json', b'old-config'), ('credentials.dat', b'old-encrypted')]:
        p = tmp_path / name
        assert p.read_bytes() == value if previous else not p.exists()
    recover_settings_transaction(tmp_path)  # idempotent


def test_successful_settings_save_survives_recovery(tmp_path):
    with settings_transaction(tmp_path):
        (tmp_path / 'config.json').write_bytes(b'new-config')
        (tmp_path / 'credentials.dat').write_bytes(b'new-encrypted')
    recover_settings_transaction(tmp_path)
    assert (tmp_path / 'config.json').read_bytes() == b'new-config'
    assert (tmp_path / 'credentials.dat').read_bytes() == b'new-encrypted'


def test_empty_local_library_removes_deleted_cache(media, tmp_path):
    folder = tmp_path / 'movies'
    folder.mkdir()
    path = media.normalize_media_path(str(folder / 'Deleted.mkv'))
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO media_cache(file_path,is_movie,title) VALUES (?,1,?)', (path, 'Deleted'))
        db.execute('INSERT INTO library_card_cache(library_id,file_path,payload) VALUES (?,?,?)', ('movies', path, json.dumps(dict(file_path=path, title='Deleted', is_movie=True))))
    scan = media.LibraryScannerThread([str(folder)], [], library_key='movies', force_remote_refresh=True)
    scan.run()
    assert not scan.failed_libraries
    with sqlite3.connect(media.DB_FILE) as db:
        assert db.execute('SELECT COUNT(*) FROM media_cache WHERE file_path=?', (path,)).fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM library_card_cache WHERE file_path=?', (path,)).fetchone()[0] == 0


def test_suspicious_remote_empty_scan_still_preserves_cache(media):
    root = media.REMOTE_PREFIX + '/Movies'
    path = media.normalize_media_path(root + '/Existing.mkv')
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO media_cache(file_path,is_movie,title) VALUES (?,1,?)', (path, 'Existing'))
    scan = media.LibraryScannerThread([root], [], library_key='movies')
    with sqlite3.connect(media.DB_FILE) as db:
        scan.cleanup_stale_media_cache(db, [('movies', root, True)], True)
        assert 'movies' in scan.failed_libraries
        assert db.execute('SELECT COUNT(*) FROM media_cache WHERE file_path=?', (path,)).fetchone()[0] == 1


@pytest.mark.parametrize('content', [b'{', b'[]', b'null', b'\xff'])
def test_corrupt_marker_preserved_and_schema_guard_kept(tmp_path, content):
    marker = tmp_path / 'data_version.json'
    marker.write_bytes(content)
    with sqlite3.connect(tmp_path / 'media_library.db') as db:
        db.execute('PRAGMA user_version=99')
    backup_before_upgrade(tmp_path, '1.96')
    preserved = list(tmp_path.glob('data_version.corrupt-*.json'))
    assert len(preserved) == 1 and preserved[0].read_bytes() == content
    with sqlite3.connect(tmp_path / 'media_library.db') as db:
        with pytest.raises(sqlite3.DatabaseError):
            migrate_schema(db)
        assert db.execute('PRAGMA user_version').fetchone()[0] == 99


def test_partial_progress_notifies_only_after_persistence(app):
    events = []
    entry = {'path': 'movie.mkv'}
    monitor = MpvPlaybackMonitor(None, '', [entry], save_progress=lambda *args: events.append('saved'), set_watched=lambda *args: None, normalize_path=lambda p:p, logger=logging.getLogger(__name__))
    monitor.progress_saved.connect(lambda p: events.append(p))
    monitor._bind_source(entry["path"])
    monitor.position, monitor.duration = 12, 100
    monitor._save_current()
    assert events == ['saved', 'movie.mkv']
