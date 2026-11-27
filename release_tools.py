"""Generate the public update manifest from the actual packaged release."""
import ast
import argparse
import hashlib
import json
from pathlib import Path
import re


def source_version(directory, tag=None):
    """Fail before building if the canonical version, entry point or tag drift."""
    root=Path(directory)
    version=(root/'release_version.txt').read_text(encoding='utf-8-sig').strip()
    if not re.fullmatch(r'[1-9]\d{0,3}\.\d{1,4}(?:\.\d{1,4})?',version):
        raise ValueError('Invalid canonical release version')
    if tag is not None and tag!='v'+version:
        raise ValueError('Tag and source version differ')
    entry=root/f'SynoStream_{version}.py'
    if not entry.is_file():raise ValueError('Missing release entry point')
    module=ast.parse(entry.read_text(encoding='utf-8-sig'))
    values=[node.value.value for node in module.body if isinstance(node,ast.Assign)
            and any(isinstance(target,ast.Name) and target.id=='APP_VERSION' for target in node.targets)
            and isinstance(node.value,ast.Constant)]
    if values!=[version]:raise ValueError('APP_VERSION and canonical release version differ')
    if not (root/f'CHANGELOG_{version}.md').is_file():raise ValueError('Missing release changelog')
    return version


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
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-source', metavar='DIRECTORY')
    parser.add_argument('--tag')
    parser.add_argument('directory', nargs='?');parser.add_argument('version', nargs='?');parser.add_argument('notes', nargs='?')
    args=parser.parse_args()
    if args.check_source:
        print(source_version(args.check_source,args.tag))
    else:
        if not all((args.directory,args.version,args.notes)):parser.error('directory, version and notes are required')
        make_manifest(args.directory,args.version,Path(args.notes).read_text(encoding='utf-8-sig'))
