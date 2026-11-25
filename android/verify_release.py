"""Fail-closed APK distribution gate. Never prints or reads signing-key material."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,zipfile

PACKAGE = 'hu.synostream.android'
CERTIFICATE = '993702ff90412c5aefcb43797d67adccb7bcdf62969f215fb92e9a5c52bca857'

def verify_apk(apk, version, version_code, sdk=None):
    apk = Path(apk).resolve()
    sdk = Path(sdk or os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or Path(os.environ['LOCALAPPDATA'])/'Android/Sdk')
    tools = sdk/'build-tools/36.1.0'
    java = str(Path(os.environ['JAVA_HOME'])/'bin/java.exe') if os.environ.get('JAVA_HOME') else shutil.which('java')
    if not java: raise RuntimeError('A release ellenőrzéshez JDK szükséges.')
    def run(args): return subprocess.check_output(args,text=True,encoding='utf-8',errors='replace',stderr=subprocess.STDOUT,timeout=60)
    badging = run([str(tools/'aapt.exe'),'dump','badging',str(apk)])
    package = re.search(r"package: name='([^']+)' versionCode='([0-9]+)' versionName='([^']+)'",badging)
    if not package or package.groups() != (PACKAGE,str(version_code),version):
        raise RuntimeError('Az APK azonosítója vagy verziója nem a várt kiadás.')
    sdk_match = re.search(r"sdkVersion:'([0-9]+)'",badging)
    if not sdk_match or int(sdk_match.group(1)) < 26: raise RuntimeError('Érvénytelen minimum Android SDK.')
    if 'application-debuggable' in badging:
        raise RuntimeError('Hibakereshető APK nem terjeszthető.')
    xml = run([str(tools/'aapt.exe'),'dump','xmltree',str(apk),'AndroidManifest.xml'])
    for flag in ('debuggable','testOnly'):
        rows = [line for line in xml.splitlines() if 'android:'+flag+'(' in line]
        for line in rows:
            match = re.search(r'=\(type 0x12\)0x([0-9a-fA-F]+)',line)
            if not match or int(match.group(1),16) != 0:
                raise RuntimeError('Terjesztésnél tiltott vagy ismeretlen manifest-jelző: '+flag)
    signature = run([java,'-jar',str(tools/'lib/apksigner.jar'),'verify','--print-certs',str(apk)])
    fingerprints = re.findall(r'Signer #[0-9]+ certificate SHA-256 digest: ([0-9a-fA-F]{64})',signature)
    if fingerprints != [CERTIFICATE]:
        raise RuntimeError('Az APK aláírása eltér a meglévő telepítésekétől.')
    with zipfile.ZipFile(apk) as archive:
        if archive.testzip() is not None: raise RuntimeError('Sérült APK.')
    return {'application_id':PACKAGE,'version':version,'version_code':version_code,
            'debuggable':False,'test_only':False,'min_sdk':int(sdk_match.group(1)),'signing_certificate_sha256':CERTIFICATE,
            'sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'size':apk.stat().st_size}

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('apk');parser.add_argument('--version',required=True);parser.add_argument('--version-code',required=True,type=int);parser.add_argument('--sdk')
    args=parser.parse_args();print(json.dumps(verify_apk(args.apk,args.version,args.version_code,args.sdk),indent=2))
