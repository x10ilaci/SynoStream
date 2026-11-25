from pathlib import Path
import argparse,json
from verify_release import verify_apk
from release_rules import check_repository
p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--commit',required=True);p.add_argument('--apk',required=True);p.add_argument('--version',required=True);p.add_argument('--code',required=True,type=int);p.add_argument('--out',required=True);a=p.parse_args()
check_repository(a.repo,a.commit);metadata=verify_apk(a.apk,a.version,a.code);metadata.update(format=1,build_commit=a.commit);Path(a.out).write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8');print('Fordítási commit és APK rögzítve.')
