"""Maintainer command / CI: upload verified release files, draft by default.

Uses GITHUB_TOKEN in Actions or Git Credential Manager locally. Credentials
stay in memory and are never copied to release packages or printed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile
import requests

REPO = 'x10ilaci/SynoStream'
API = 'https://api.github.com/repos/' + REPO


def session():
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        result = subprocess.run(['git', '-c', 'credential.interactive=never', 'credential', 'fill'],
            input='protocol=https\nhost=github.com\n\n', text=True, capture_output=True, timeout=20,
            env={**os.environ, 'GIT_TERMINAL_PROMPT':'0', 'GCM_INTERACTIVE':'never'}, check=True)
        fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        token = fields.get('password')
    if not token: raise RuntimeError('GitHub authentication is unavailable')
    client = requests.Session(); client.headers.update({'Authorization':'Bearer ' + token,
        'Accept':'application/vnd.github+json', 'X-GitHub-Api-Version':'2022-11-28'})
    return client


def verify(directory):
    from synostream_updates import validate_manifest, sha256
    from release_guard import scan_zip, scan_executable, scan_bytes, UnsafeRelease
    root = Path(directory); m = validate_manifest(json.loads((root/'update.json').read_text(encoding='utf-8-sig')))
    version = m['version']; base = f'SynoStream_{version}'
    names = [base+'.exe', base+'_Windows_x64.zip', base+'_Source.zip', base+'_SHA256.txt', 'update.json']
    for name in names:
        if not (root/name).is_file(): raise UnsafeRelease('Missing release artifact: '+name)
    if (root/m['filename']).stat().st_size != m['size'] or (root/(base+'.exe')).stat().st_size != m['exe_size']:
        raise UnsafeRelease('Release artifact size mismatch')
    if sha256(root/m['filename']) != m['sha256'] or sha256(root/(base+'.exe')) != m['exe_sha256']:
        raise UnsafeRelease('Release artifact checksum mismatch')
    checked = set()
    for line in (root/(base+'_SHA256.txt')).read_text().splitlines():
        parts = line.split()
        if len(parts) != 2: raise UnsafeRelease('Invalid checksum entry')
        digest, name = parts
        if name not in names[:3] or name in checked or sha256(root/name) != digest:
            raise UnsafeRelease('Invalid artifact checksum: '+name)
        checked.add(name)
    if checked != set(names[:3]): raise UnsafeRelease('Incomplete artifact checksums')
    for name in names:
        if name.endswith('.zip'): scan_zip(root/name)
        elif name.endswith('.exe'): scan_executable(root/name)
        else: scan_bytes((root/name).read_bytes(), name)
    return m, names


def publish(directory, make_public=False):
    root = Path(directory); m, names = verify(root); client = session(); tag = 'v'+m['version']
    response = client.get(API+'/releases/tags/'+tag, timeout=30)
    if response.status_code == 404:
        drafts = client.get(API+'/releases', params={'per_page':100}, timeout=30)
        drafts.raise_for_status()
        draft = next((item for item in drafts.json() if item['tag_name']==tag), None)
        if draft:
            response = client.get(API+'/releases/'+str(draft['id']), timeout=30)
        else:
            response = client.post(API+'/releases', json={'tag_name':tag, 'target_commitish':'main',
                'name':'SynoStream '+m['version'], 'body':m['notes'], 'draft':True, 'prerelease':False}, timeout=30)
    response.raise_for_status(); release = response.json()
    if not release['draft']:
        print('Release is already public; keeping its immutable files:', release['html_url']); return release
    existing = {asset['name']:asset for asset in release['assets']}
    for name in names:
        path = root/name
        if name in existing:
            digest = existing[name].get('digest')
            actual = 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != actual: raise RuntimeError('Existing release asset differs: '+name)
            continue
        with path.open('rb') as data:
            uploaded = client.post(release['upload_url'].split('{')[0], params={'name':name}, data=data,
                headers={'Content-Type':'application/octet-stream'}, timeout=(20, 240))
            uploaded.raise_for_status()
        print('Uploaded', name, flush=True)
    if make_public:
        response = client.patch(API+'/releases/'+str(release['id']), json={'draft':False,'make_latest':'true'}, timeout=30)
        response.raise_for_status(); release = response.json()
    print('Public release:' if not release['draft'] else 'Draft prepared:', release['html_url'], flush=True)
    return release


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',required=True);parser.add_argument('--publish',action='store_true')
    args=parser.parse_args();publish(args.directory,args.publish)
