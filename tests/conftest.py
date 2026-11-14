import importlib.util
import os
from pathlib import Path
import sys
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
_data = tempfile.TemporaryDirectory(prefix='synostream-tests-')
os.environ['SYNOSTREAM_DATA_DIR'] = _data.name
spec = importlib.util.spec_from_file_location('synostream_app', ROOT / 'SynoStream_1.96.py')
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)


@pytest.fixture(scope="session")
def app():
    instance = app_module.QApplication.instance() or app_module.QApplication([])
    yield instance
    instance.processEvents()


@pytest.fixture
def media(tmp_path, monkeypatch):
    m = app_module
    for name, value in {'BASE_DIR': str(tmp_path), 'DB_FILE': str(tmp_path / 'media_library.db'),
                        'CONFIG_FILE': str(tmp_path / 'config.json'),
                        'SECRET_STORE_FILE': str(tmp_path / 'credentials.dat'),
                        'CACHE_DIR': str(tmp_path / 'cache_posters')}.items():
        monkeypatch.setattr(m, name, value)
    (tmp_path / 'cache_posters').mkdir()
    monkeypatch.setattr(m, 'config', m.copy.deepcopy(m.DEFAULT_CONFIG))
    m.config['startup_scan_mode'] = 'none'
    m.config['movies_paths'] = []
    m.config['shows_paths'] = []
    m.init_db()
    return m



@pytest.fixture(autouse=True)
def collect_qt_objects_on_test_thread(app):
    # Qt widgets must be destroyed on the GUI thread. Collect test-created
    # signal/parent cycles here, never during a later worker-thread allocation.
    import gc
    enabled = gc.isenabled()
    gc.disable()
    yield
    app.processEvents()
    gc.collect()
    app.processEvents()
    if enabled:
        gc.enable()
