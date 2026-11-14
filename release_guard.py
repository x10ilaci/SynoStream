"""Fail-closed checks for public sources and release artifacts.

Diagnostics identify a file and a category, never the matched secret value.
Known private values may be supplied by a local, in-memory audit; CI does not
need access to any end-user credentials.
"""
import io
from pathlib import Path, PurePosixPath
import re
import zipfile


class UnsafeRelease(ValueError):
    pass


_TOKENS = (
    re.compile(rb'gh[pousr]_[A-Za-z0-9]{25,}'),
    re.compile(rb'github_pat_[A-Za-z0-9_]{30,}'),
    re.compile(rb'AKIA[0-9A-Z]{16}'),
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{64,}'),
)


def check_name(name):
    value = str(name).replace('\\', '/')
    parts = PurePosixPath(value).parts
    if not parts or value.startswith('/') or ':' in value or '..' in parts:
        raise UnsafeRelease('Unsafe artifact path: ' + value)
    forbidden = {'.git', '.env', '.settings-pending', '.application.lock', 'cache_posters',
                 'upgrade_backups', '__pycache__', '.pytest_cache', 'logs'}
    for part in parts:
        low = part.casefold()
        if (low in forbidden or low.startswith(('.env.', '.settings-', 'credentials.', 'config.json', 'data_version.'))
                or low.startswith('media_library.db')
                or low.endswith(('.db', '.db-wal', '.db-shm', '.sqlite', '.sqlite3', '.log', '.pfx', '.p12', '.key'))
                or re.fullmatch(r'config[._-].*\.(?:json|bak|backup)', low)):
            raise UnsafeRelease('Private/runtime artifact: ' + value)


def scan_bytes(data, label, known_secrets=()):
    for pattern in _TOKENS:
        if pattern.search(data): raise UnsafeRelease('Credential-like content: ' + str(label))
    for secret in known_secrets:
        if not secret: continue
        needle = secret.encode('utf-8') if isinstance(secret, str) else bytes(secret)
        if needle in data: raise UnsafeRelease('Known private value: ' + str(label))


def scan_zip(path, known_secrets=()):
    with zipfile.ZipFile(path) as archive:
        seen = set(); total = 0
        for item in archive.infolist():
            check_name(item.filename)
            name = item.filename.replace('\\', '/').rstrip('/').casefold()
            if name in seen: raise UnsafeRelease('Duplicate artifact path: ' + item.filename)
            seen.add(name); total += item.file_size
            if total > 512 * 1024 * 1024: raise UnsafeRelease('Oversized release archive')
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise UnsafeRelease('Linked artifact path: ' + item.filename)
            if not item.is_dir(): scan_bytes(archive.read(item), item.filename, known_secrets)
        if archive.testzip() is not None: raise UnsafeRelease('Corrupt release archive')


def scan_executable(path, known_secrets=()):
    """Inspect decompressed PyInstaller members and Python constant pools."""
    import marshal
    import types
    from PyInstaller.archive.readers import CArchiveReader
    def constants(code, label):
        if isinstance(code, types.CodeType):
            for child in code.co_consts: constants(child, label)
        elif isinstance(code, str): scan_bytes(code.encode('utf-8', errors='replace'), label, known_secrets)
        elif isinstance(code, bytes): scan_bytes(code, label, known_secrets)
        elif isinstance(code, (tuple, list, frozenset)):
            for child in code: constants(child, label)
    archive = CArchiveReader(str(path))
    for name, entry in archive.toc.items():
        payload = archive.extract(name)
        scan_bytes(payload, name, known_secrets)
        if entry[-1] == 's': constants(marshal.loads(payload), name)
        elif name.endswith('.pyz'):
            pyz = archive.open_embedded_archive(name)
            for module in pyz.toc:
                value = pyz.extract(module)
                constants(value, module)
        elif name.endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(payload)) as nested:
                for member in nested.namelist(): scan_bytes(nested.read(member), name + '/' + member, known_secrets)


def scan_source_files(root, names, known_secrets=()):
    root = Path(root).resolve()
    for name in names:
        check_name(name); path = root / name
        if path.is_symlink() or path.is_junction(): raise UnsafeRelease('Linked source artifact: ' + str(name))
        if not path.resolve().is_relative_to(root): raise UnsafeRelease('Source outside repository: ' + str(name))
        if path.is_file(): scan_bytes(path.read_bytes(), name, known_secrets)


def scan_git(root, history=False):
    import subprocess
    root = Path(root)
    def git(*args): return subprocess.check_output(['git', '-C', str(root), *args])
    entries = git('ls-files', '--stage', '-z').decode('utf-8').strip('\0').split('\0')
    checked = set()
    for entry in entries:
        if not entry: continue
        metadata, name = entry.split('\t', 1); mode, identifier, stage = metadata.split()
        check_name(name)
        if mode not in ('100644', '100755') or stage != '0': raise UnsafeRelease('Non-regular staged source: ' + name)
        scan_bytes(git('cat-file', 'blob', identifier), name); checked.add(identifier)
    if history:
        for entry in git('rev-list', '--objects', '--all').decode('utf-8').splitlines():
            fields = entry.split(' ', 1); identifier = fields[0]
            if identifier in checked or git('cat-file', '-t', identifier).strip() != b'blob': continue
            if len(fields) > 1: check_name(fields[1])
            scan_bytes(git('cat-file', 'blob', identifier), 'Git blob ' + identifier[:12]); checked.add(identifier)
    return len(checked)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument('--git-index', action='store_true'); parser.add_argument('--git-history', action='store_true')
    args = parser.parse_args()
    if not (args.git_index or args.git_history): parser.error('Choose a Git audit mode')
    print('Public-source guard passed:', scan_git(Path.cwd(), args.git_history), 'blobs')
