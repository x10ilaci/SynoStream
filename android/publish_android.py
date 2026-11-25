"""Maintainer command, run from a repository checkout. Draft by default."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
from verify_release import verify_apk
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from release_rules import validate_feed,validate_checksums,check_repository,asset_names

def publish(folder,public=False,build_commit=None):
    folder=Path(folder).resolve();manifest=json.loads((folder/'android-update.json').read_text(encoding='utf-8'))
    validate_feed(manifest)
    repo=Path(__file__).resolve().parents[1]
    expected=build_commit or manifest['build_commit']
    if expected!=manifest['build_commit']:raise RuntimeError('Eltérő fordítási commit a metaadatban.')
    sha=check_repository(repo,expected)
    names=asset_names(manifest);checksums=validate_checksums(folder,names)
    provenance=json.loads((folder/'build-provenance.json').read_text(encoding='utf-8'))
    if provenance.get('build_commit')!=sha or any(provenance.get(k)!=manifest.get(k) for k in ('sha256','size','version','version_code','application_id')):raise RuntimeError('A fordítási bizonyíték eltér a kiadástól.')
    version=manifest['version'];tag='android-v'+version;apk=folder/manifest['filename']
    verified=verify_apk(apk,version,manifest['version_code'])
    for key in ('application_id','sha256','size','signing_certificate_sha256','min_sdk'):
        if manifest[key]!=verified[key]: raise RuntimeError('A kiadási metaadat eltér az ellenőrzött APK-tól: '+key)
    if manifest.get('build_type')!='release' or manifest.get('debuggable') is not False or manifest.get('test_only') is not False:
        raise RuntimeError('A frissítési leíró nem igazol release csomagot.')
    from release_guard import scan_zip,scan_bytes
    for name in names:
        path=folder/name
        if name.endswith(('.apk','.zip')):scan_zip(path)
        else:scan_bytes(path.read_bytes(),name)
    import publish_release as github
    client=github.session()
    response=client.get(github.API+'/git/ref/heads/main',timeout=30);response.raise_for_status()
    if response.json()['object']['sha']!=sha:raise RuntimeError('A GitHub main nem az ellenőrzött commiton áll.')
    response=client.get(github.API+'/releases/tags/'+tag,timeout=30)
    if response.status_code==404:
        listing=client.get(github.API+'/releases',params={'per_page':100},timeout=30);listing.raise_for_status();draft=next((v for v in listing.json() if v['tag_name']==tag),None)
        if draft:response=client.get(github.API+'/releases/'+str(draft['id']),timeout=30)
        else:response=client.post(github.API+'/releases',json={'tag_name':tag,'target_commitish':sha,'name':'SynoStream Android '+version,'body':manifest['notes']+'\n\nEllenőrzött, nem hibakereshető release APK, azonos aláírással a korábbi verzió fölé telepíthető. APK, forrás és SHA256 mellékelve.','draft':True,'prerelease':False,'make_latest':'false'},timeout=30)
    response.raise_for_status();release=response.json();existing={v['name']:v for v in release['assets']}
    for name in names:
        path=folder/name;digest='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
        if name in existing:
            if existing[name].get('digest')!=digest:raise RuntimeError('A meglévő kiadási fájl eltér; nem írható felül.')
            continue
        if not release['draft']:raise RuntimeError('Nyilvános kiadás fájljai nem módosíthatók.')
        with path.open('rb') as data:response=client.post(release['upload_url'].split('{')[0],params={'name':name},data=data,headers={'Content-Type':'application/octet-stream'},timeout=(20,240))
        response.raise_for_status()
        if response.json().get('digest')!=digest:raise RuntimeError('Eltérő feltöltött fájl.')
        print('Uploaded:',name,flush=True)
    if public and release['draft']:
        response=client.patch(github.API+'/releases/'+str(release['id']),json={'draft':False,'make_latest':'false'},timeout=30);response.raise_for_status();release=response.json()
    print(('Public: ' if not release['draft'] else 'Draft: ')+release['html_url'],flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder');parser.add_argument('--publish',action='store_true');parser.add_argument('--build-commit');args=parser.parse_args();publish(args.folder,args.publish,args.build_commit)
