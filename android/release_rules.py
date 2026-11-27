"""Pure release metadata and repository preflight. No network or signing-key access."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,warnings
PACKAGE='hu.synostream.android'

def validate_feed(m, *, require_build_commit=True):
    def integer(key,minimum,maximum=None):
        v=m.get(key)
        if type(v) is not int or v<minimum or maximum is not None and v>maximum:raise ValueError('Hibás frissítési metaadat: '+key)
    if m.get('format')!=1 or type(m.get('format')) is not int or m.get('platform')!='android' or m.get('application_id')!=PACKAGE:raise ValueError('Hibás frissítési formátum vagy alkalmazás.')
    version=m.get('version');notes=m.get('notes','')
    if not isinstance(version,str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){2}',version):raise ValueError('Hibás verziószám.')
    integer('version_code',1);integer('size',1,150*1024*1024);integer('min_sdk',26)
    for key in ('sha256','signing_certificate_sha256'):
        if not isinstance(m.get(key),str) or not re.fullmatch(r'[a-f0-9]{64}',m[key]):raise ValueError('Hibás hash vagy tanúsítvány.')
    filename='SynoStream_Android_'+version+'.apk'
    if m.get('filename')!=filename or m.get('url')!='https://github.com/x10ilaci/SynoStream/releases/download/android-v'+version+'/'+filename:raise ValueError('Hibás frissítési URL vagy fájlnév.')
    if not isinstance(notes,str) or len(notes.encode('utf-16-le'))//2>32000:raise ValueError('Túl hosszú vagy hibás kiadási jegyzet.')
    if m.get('build_type')!='release' or m.get('debuggable') is not False or m.get('test_only') is not False:raise ValueError('A kiadás nem release csomag.')
    if (require_build_commit or 'build_commit' in m) and (not isinstance(m.get('build_commit'),str) or not re.fullmatch(r'[a-f0-9]{40}',m['build_commit'])):raise ValueError('Hiányzó fordítási commit.')
    return m

def validate_repository_feed(path, manifest):
    """Compare a staged feed; an older live feed is normal before publication."""
    path=Path(path)
    if not path.exists():
        warnings.warn('A tároló frissítési leírója még hiányzik; publikálás után kötelező ellenőrizni.', RuntimeWarning)
        return False
    current=json.loads(path.read_text(encoding='utf-8-sig'))
    validate_feed(current,require_build_commit=False)
    if (current['version_code'] < manifest['version_code']
            and tuple(map(int,current['version'].split('.'))) < tuple(map(int,manifest['version'].split('.')))):
        warnings.warn('A tároló még a korábbi kiadást hirdeti; az új feed nincs előkészítve. Publikálás után kötelező frissíteni és ellenőrizni.', RuntimeWarning)
        return False
    keys=('format','platform','application_id','version','version_code','min_sdk','filename','url','sha256','size','signing_certificate_sha256','notes','build_type','debuggable','test_only')
    if any(current.get(key)!=manifest.get(key) for key in keys):
        raise ValueError('A tároló frissítési leírója eltér a kiadási melléklettől.')
    return True


def check_repository(repo,expected=None):
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True,encoding='utf-8').strip()
    if git('status','--porcelain'):raise ValueError('A munkafa nem tiszta; a kiadás nem publikálható.')
    head=git('rev-parse','HEAD')
    if expected is not None and head!=expected:raise ValueError('A HEAD nem a megadott fordítási commit.')
    return head

def asset_names(m):return [m['filename'],'SynoStream_Android_'+m['version']+'_forraskod.zip','android-update.json','LICENSE','NOTICE.md','build-provenance.json','SHA256.json']

def validate_checksums(folder,names):
    folder=Path(folder);sums=json.loads((folder/'SHA256.json').read_text(encoding='utf-8-sig'));expected=set(names)-{'SHA256.json'}
    if not isinstance(sums,dict) or set(sums)!=expected:raise ValueError('Hiányos vagy nem várt SHA256-bejegyzések.')
    for name,digest in sums.items():
        if Path(name).name!=name or not re.fullmatch(r'[a-f0-9]{64}',str(digest)) or hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest:raise ValueError('Hibás kiadási ellenőrzőösszeg.')
    return sums

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--commit');a=p.parse_args();print(check_repository(a.repo,a.commit))
