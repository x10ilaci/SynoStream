"""Generate the public update manifest from the actual packaged release."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def make_manifest(directory, version, notes):
    if not re.fullmatch(r'[1-9]\d{0,3}\.\d{1,4}(?:\.\d{1,4})?', version): raise ValueError('Invalid release version')
    root = Path(directory); filename = f'SynoStream_{version}_Windows_x64.zip'
    exe = root / f'SynoStream_{version}.exe'; package = root / filename
    def digest(path):
        with path.open('rb') as file: return hashlib.file_digest(file, 'sha256').hexdigest()
    manifest = dict(format=1, version=version, filename=filename,
        url=f'https://github.com/x10ilaci/SynoStream/releases/download/v{version}/{filename}',
        sha256=digest(package), size=package.stat().st_size,
        exe_sha256=digest(exe), exe_size=exe.stat().st_size, notes=str(notes)[:12000])
    (root / 'update.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('directory'); parser.add_argument('version'); parser.add_argument('notes')
    args = parser.parse_args(); make_manifest(args.directory, args.version, Path(args.notes).read_text(encoding='utf-8-sig'))
