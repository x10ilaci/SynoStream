import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import pytest
from synostream_storage import acquire_application_lock

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'SynoStream_1.108.py'
BOOT = '''import os,sys,importlib.util
from pathlib import Path
sys.path.insert(0,sys.argv[1])
spec=importlib.util.spec_from_file_location('probe',Path(sys.argv[1])/'SynoStream_1.108.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sys.excepthook=sys.__excepthook__
root=Path(m.BASE_DIR)
'''


def environment(tmp_path):
    env = os.environ.copy()
    env['SYNOSTREAM_DATA_DIR'] = str(tmp_path)
    env['LOCALAPPDATA'] = str(tmp_path / 'localappdata')
    env['QT_QPA_PLATFORM'] = 'offscreen'
    return env


@pytest.mark.parametrize('release', ['normal', 'crash'])
def test_second_application_cannot_touch_active_save(tmp_path, release):
    code = BOOT + '''m.config.update(nas_username='owner',nas_password='owner-password')
assert m.save_config()[0]
original=m.write_config_atomic
def paused(values):
 (root/'ready').touch()
 while not (root/'go').exists():
  import time;time.sleep(.02)
 if sys.argv[2]=='crash':os._exit(37)
 original(values)
m.write_config_atomic=paused
m.config.update(nas_username='next',nas_password='next-password')
assert m.save_config()[0]
'''
    env = environment(tmp_path)
    owner = subprocess.Popen([sys.executable, '-c', code, str(ROOT), release], env=env)
    try:
        deadline = time.monotonic() + 15
        while not (tmp_path / 'ready').exists():
            assert owner.poll() is None
            assert time.monotonic() < deadline
            time.sleep(.02)
        before = {name: (tmp_path / name).read_bytes() for name in ('config.json', 'credentials.dat')}
        attempt = subprocess.run([sys.executable, str(APP), '--smoke-test'], env=env, timeout=10)
        assert attempt.returncode == 2
        assert (tmp_path / '.settings-pending').exists()
        assert before == {name: (tmp_path / name).read_bytes() for name in before}
        (tmp_path / 'go').touch()
        assert owner.wait(timeout=15) == (37 if release == 'crash' else 0)
        expected = 'owner' if release == 'crash' else 'next'
        check = BOOT + f"assert m.config['nas_username']=={expected!r};assert m.config['nas_password']=={(expected+'-password')!r}"
        run = subprocess.run([sys.executable, '-c', check, str(ROOT)], env=env, capture_output=True, text=True, timeout=15)
        assert run.returncode == 0, run.stderr
    finally:
        if owner.poll() is None:
            owner.kill();owner.wait()


def test_restart_waits_for_previous_owner(tmp_path):
    lock = acquire_application_lock(tmp_path)
    env = environment(tmp_path)
    process = subprocess.Popen([sys.executable, str(APP), '--smoke-test', '--wait-for-instance'], env=env)
    try:
        time.sleep(1)
        assert process.poll() is None
        lock.close()
        assert process.wait(timeout=20) == 0
    finally:
        lock.close()
        if process.poll() is None:process.kill();process.wait()


@pytest.mark.parametrize('point', ['credentials', 'database', 'config'])
def test_interrupted_restore_recovers_all_three_files(tmp_path, point):
    env = environment(tmp_path)
    code = BOOT + '''import sqlite3
from contextlib import closing
m.init_db()
m.config.update(nas_username='backup-user',nas_password='backup-password')
with closing(sqlite3.connect(m.DB_FILE)) as db:
 db.execute("INSERT INTO media_cache(file_path,is_movie,title) VALUES ('audit',1,'backup-state')");db.commit()
m.create_backup_archive(str(root/'backup.zip'))
m.config.update(nas_username='current-user',nas_password='current-password')
assert m.save_config()[0]
with closing(sqlite3.connect(m.DB_FILE)) as db:
 db.execute("UPDATE media_cache SET title='current-state' WHERE file_path='audit'");db.commit()
point=sys.argv[2]
if point=='credentials':
 original=m.os.remove
 def crash(path):
  original(path)
  if str(path)==m.SECRET_STORE_FILE:os._exit(37)
 m.os.remove=crash
else:
 original=m.os.replace
 def crash(source,destination):
  original(source,destination)
  target=m.DB_FILE if point=='database' else m.CONFIG_FILE
  if str(destination)==target and 'synostream_restore_' in str(source):os._exit(37)
 m.os.replace=crash
m.restore_backup_archive(str(root/'backup.zip'))
raise AssertionError('crash hook did not run')
'''
    result = subprocess.run([sys.executable, '-c', code, str(ROOT), point], env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 37, result.stderr
    assert (tmp_path / '.settings-pending').exists()
    check = BOOT + '''m.init_db()
assert m.config['nas_username']=='current-user'
assert m.config['nas_password']=='current-password'
import sqlite3
from contextlib import closing
with closing(sqlite3.connect(m.DB_FILE)) as db:
 assert db.execute("SELECT title FROM media_cache WHERE file_path='audit'").fetchone()[0]=='current-state'
assert not (root/'.settings-pending').exists()
'''
    result = subprocess.run([sys.executable, '-c', check, str(ROOT)], env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('stale', [False, True])
def test_chrome_rebinds_wrapper_and_replaces_deleted_entry(media, app, stale):
    from PyQt6 import sip
    from PyQt6.QtWidgets import QDialog
    chrome = app._synostream_chrome
    window = QDialog()
    if stale:
        previous = QDialog()
        chrome.apply(previous)
        bar = previous._syno_title_bar
        sip.delete(previous)
        assert sip.isdeleted(bar)
        chrome.bars[sip.unwrapinstance(window)] = bar
    else:
        chrome.apply(window)
        del window._syno_title_bar
    chrome.apply(window)
    window.show()
    app.processEvents()
    assert window._syno_title_bar.isVisible()
    assert not sip.isdeleted(window._syno_title_bar)
    sip.delete(window)
