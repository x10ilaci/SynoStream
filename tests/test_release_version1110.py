import subprocess,sys
from pathlib import Path
import pytest
from release_tools import source_version

ROOT=Path(__file__).resolve().parents[1]
def source(tmp_path,version='1.110'):
 (tmp_path/'release_version.txt').write_text(version+'\n');(tmp_path/('SynoStream_'+version+'.py')).write_text('APP_VERSION = '+repr(version)+'\n');(tmp_path/('CHANGELOG_'+version+'.md')).write_text('Fixture');return tmp_path

def test_actual_release_version_matches_entrypoint_and_tag():
 version=source_version(ROOT)
 assert source_version(ROOT,'v'+version)==version
 run=subprocess.run([sys.executable,str(ROOT/'release_tools.py'),'--check-source',str(ROOT),'--tag','v'+version],capture_output=True,text=True)
 assert run.returncode==0 and run.stdout.strip()==version

@pytest.mark.parametrize('mutation',['tag','entry','app','changelog','format'])
def test_source_drift_is_rejected_before_build(tmp_path,mutation):
 root=source(tmp_path);tag='v1.110'
 if mutation=='tag':tag='v1.109'
 if mutation=='entry':(root/'SynoStream_1.110.py').unlink()
 if mutation=='app':(root/'SynoStream_1.110.py').write_text("APP_VERSION='1.109'")
 if mutation=='changelog':(root/'CHANGELOG_1.110.md').unlink()
 if mutation=='format':(root/'release_version.txt').write_text('../other')
 with pytest.raises(ValueError):source_version(root,tag)
