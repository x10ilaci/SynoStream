"""Maintainer command, run from a repository checkout. Draft by default."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
from verify_release import verify_apk
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import publish_release as github
from release_guard import scan_zip,scan_bytes

def publish(folder,public=False):
    folder=Path(folder).resolve();manifest=json.loads((folder/'android-update.json').read_text(encoding='utf-8'))
    version=manifest['version'];tag='android-v'+version;apk=folder/manifest['filename']
    verified=verify_apk(apk,version,manifest['version_code'])
    for key in ('application_id','sha256','size','signing_certificate_sha256'):
        if manifest[key]!=verified[key]: raise RuntimeError('A kiadási metaadat eltér az ellenőrzött APK-tól: '+key)
    if manifest.get('build_type')!='release' or manifest.get('debuggable') is not False or manifest.get('test_only') is not False:
        raise RuntimeError('A frissítési leíró nem igazol release csomagot.')
    names=[apk.name,'SynoStream_Android_'+version+'_forraskod.zip','SHA256.json','android-update.json','LICENSE','NOTICE.md']
    for name,digest in json.loads((folder/'SHA256.json').read_text()).items():
        if Path(name).name!=name or hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Hibás ellenőrzőösszeg.')
    for name in names:
        path=folder/name
        if name.endswith(('.apk','.zip')):scan_zip(path)
        else:scan_bytes(path.read_bytes(),name)
    repo=Path(__file__).resolve().parents[1];sha=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip();client=github.session()
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
    parser=argparse.ArgumentParser();parser.add_argument('folder');parser.add_argument('--publish',action='store_true');args=parser.parse_args();publish(args.folder,args.publish)
