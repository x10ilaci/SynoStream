"""Maintainer command, run from a repository checkout. Draft by default."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
from verify_release import verify_apk
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from release_rules import validate_feed,validate_checksums,check_repository,asset_names,validate_repository_feed

def verify_feed(folder,repository_feed=None):
    folder=Path(folder).resolve()
    manifest_path=folder if folder.is_file() else folder/'android-update.json'
    folder=manifest_path.parent
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    validate_feed(manifest)
    if repository_feed is None:repository_feed=Path(__file__).resolve().parent/'update.json'
    validate_repository_feed(repository_feed,manifest,strict=True)
    apk=folder/manifest['filename']
    if not apk.is_file() or apk.stat().st_size!=manifest['size']:
        raise ValueError('Az APK hiányzik vagy mérete eltér a frissítési leírótól.')
    with apk.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=manifest['sha256']:raise ValueError('Az APK SHA256-értéke eltér a frissítési leírótól.')
    print('Frissítési leíró és APK ellenőrizve: '+manifest['version'],flush=True)
    return manifest


def publish(folder,public=False,build_commit=None):
    folder=Path(folder).resolve();manifest=json.loads((folder/'android-update.json').read_text(encoding='utf-8'))
    validate_feed(manifest)
    repo=Path(__file__).resolve().parents[1]
    if public:validate_repository_feed(repo/'android/update.json',manifest)
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
    if public:
        print('KÖTELEZŐ következő lépés a repóbeli feed frissítése után: python android/publish_android.py --verify-feed --folder <kiadási_mappa>',flush=True)

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('folder',nargs='?');parser.add_argument('--folder',dest='folder_option')
    parser.add_argument('--publish',action='store_true');parser.add_argument('--build-commit')
    parser.add_argument('--verify-feed',action='store_true')
    args=parser.parse_args(argv)
    if args.folder and args.folder_option:parser.error('A kiadási mappát csak egyszer add meg.')
    folder=args.folder_option or args.folder
    if not folder:parser.error('Add meg a kiadási mappát (--folder).')
    if args.verify_feed:
        if args.publish or args.build_commit:parser.error('Az ellenőrzés nem kombinálható publikálással.')
        return verify_feed(folder)
    return publish(folder,args.publish,args.build_commit)


if __name__=='__main__':main()
