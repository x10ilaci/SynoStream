"""User data location, legacy migration and consistent upgrade snapshots."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time
import uuid
from contextlib import closing, contextmanager
import threading

SCHEMA_VERSION = 1


def data_directory(application_dir):
    app = Path(application_dir)
    override = os.environ.get("SYNOSTREAM_DATA_DIR")
    if override:
        target = Path(override)
    elif (app / "portable.flag").exists():
        target = app
    else:
        target = Path(os.environ.get("LOCALAPPDATA", str(app))) / "SynoStream" / "data"
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix="migration-", dir=target.parent))
            try:
                for name in ("config.json", "credentials.dat", "media_library.db", "cache_posters", "tools"):
                    source = app / name
                    if not source.exists():
                        continue
                    if name == "media_library.db":
                        with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(stage / name)) as dst:
                            src.backup(dst)
                    elif source.is_dir():
                        shutil.copytree(source, stage / name)
                    else:
                        shutil.copy2(source, stage / name)
                try:
                    os.replace(stage, target)
                except OSError:
                    # Another first-start process may have atomically published it.
                    # Adopt only a real directory; genuine publication errors still fail.
                    if not target.is_dir():
                        raise
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
    target.mkdir(parents=True, exist_ok=True)
    return str(target)


def backup_before_upgrade(directory, version):
    root = Path(directory)
    marker = root / "data_version.json"
    try:
        previous = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if not isinstance(previous, dict):
            raise ValueError("Invalid version marker")
    except (ValueError, UnicodeError):
        # Preserve the damaged metadata for diagnosis. Database schema validation
        # still runs independently before any migration is committed.
        os.replace(marker, root / ("data_version.corrupt-" + uuid.uuid4().hex + ".json"))
        previous = {}
    if previous.get("app_version") == version:
        return
    files = [root / name for name in ("config.json", "credentials.dat", "media_library.db")]
    if any(path.exists() for path in files):
        backups = root / "upgrade_backups"
        backups.mkdir(exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".pending-", dir=backups))
        try:
            for source in files:
                if not source.exists():
                    continue
                if source.suffix == ".db":
                    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(stage / source.name)) as dst:
                        src.backup(dst)
                else:
                    shutil.copy2(source, stage / source.name)
            (stage / "manifest.json").write_text(json.dumps({"before_version": version,
                "previous": previous, "created_at": time.time()}), encoding="utf-8")
            os.replace(stage, backups / (time.strftime("%Y%m%d-%H%M%S") + "-" + version + "-" + uuid.uuid4().hex[:6]))
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    # This marker is committed after the database migration succeeds.


def commit_data_version(directory, version):
    target = Path(directory) / "data_version.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps({"app_version": version, "schema_version": SCHEMA_VERSION}), encoding="utf-8")
    os.replace(temporary, target)


def migrate_schema(connection):
    current = connection.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise sqlite3.DatabaseError("Az adatbázis újabb SynoStream-verzióhoz tartozik.")
    connection.execute("CREATE INDEX IF NOT EXISTS playback_recent ON playback_state(last_played DESC)")
    connection.execute("PRAGMA user_version = 1")


_SETTINGS_LOCK = threading.RLock()
_SETTINGS_FILES = ("config.json", "credentials.dat")


def _restore_settings(root, journal):
    manifest = json.loads((journal / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not set(manifest).issubset(set(_SETTINGS_FILES) | {"media_library.db"}):
        raise ValueError("Invalid settings recovery manifest")
    for name in manifest:
        target = root / name
        if manifest[name]:
            if name != "media_library.db" and target.exists() and target.read_bytes() == (journal / name).read_bytes():
                continue
            fd, temporary = tempfile.mkstemp(prefix=".restore-settings-", dir=root)
            try:
                with os.fdopen(fd, "wb") as output:
                    with (journal / name).open("rb") as source:
                        shutil.copyfileobj(source, output)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.remove(temporary)
        elif target.exists():
            target.unlink()
    # Keep the journal until every file is restored; interrupted recovery is repeatable.
    completed = root / (".settings-recovered-" + uuid.uuid4().hex)
    os.replace(journal, completed)
    shutil.rmtree(completed, ignore_errors=True)


def recover_settings_transaction(directory):
    """Roll back an interrupted settings save before loading or backing up data."""
    with _SETTINGS_LOCK:
        root = Path(directory)
        journal = root / ".settings-pending"
        if journal.exists():
            _restore_settings(root, journal)


@contextmanager
def settings_transaction(directory, *, include_database=False):
    """Durable rollback journal for the JSON + DPAPI credential pair."""
    with _SETTINGS_LOCK:
        root = Path(directory)
        recover_settings_transaction(root)
        stage = Path(tempfile.mkdtemp(prefix=".settings-stage-", dir=root))
        journal = root / ".settings-pending"
        try:
            present = {}
            names = _SETTINGS_FILES + (("media_library.db",) if include_database else ())
            for name in names:
                source = root / name
                present[name] = source.exists()
                if present[name]:
                    if name == "media_library.db":
                        with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(stage / name)) as dst:
                            src.backup(dst)
                        with (stage / name).open("r+b") as output:
                            os.fsync(output.fileno())
                    else:
                        with (stage / name).open("wb") as output:
                            output.write(source.read_bytes())
                            output.flush()
                            os.fsync(output.fileno())
            with (stage / "manifest.json").open("w", encoding="utf-8") as output:
                json.dump(present, output)
                output.flush()
                os.fsync(output.fileno())
            os.replace(stage, journal)
            try:
                yield
                # Atomic rename is the commit point, after both durable writes.
                committed = root / (".settings-committed-" + uuid.uuid4().hex)
                os.replace(journal, committed)
            except BaseException:
                _restore_settings(root, journal)
                raise
            shutil.rmtree(committed, ignore_errors=True)
        finally:
            if stage.exists():
                shutil.rmtree(stage, ignore_errors=True)


class DataDirectoryInUse(RuntimeError):
    pass


def acquire_application_lock(directory, timeout=0):
    """Hold an OS-owned lock for the entire lifetime of this data directory user."""
    import msvcrt
    root = Path(directory)
    stream = (root / ".application.lock").open("a+b")
    try:
        if stream.seek(0, 2) == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.1)
    except OSError as exc:
        stream.close()
        raise DataDirectoryInUse("A SynoStream már fut ezzel az adatmappával.") from exc
    # Closing the process handle, including on a crash, releases the OS lock.
    import atexit
    atexit.register(stream.close)
    return stream
