import hashlib,json,subprocess
from pathlib import Path
import pytest
from release_rules import validate_feed,validate_checksums,check_repository,asset_names

def feed():
 return dict(format=1,platform='android',application_id='hu.synostream.android',version='0.5.25',version_code=30,min_sdk=26,filename='SynoStream_Android_0.5.25.apk',url='https://github.com/x10ilaci/SynoStream/releases/download/android-v0.5.25/SynoStream_Android_0.5.25.apk',size=100,sha256='a'*64,signing_certificate_sha256='b'*64,notes='fixture',build_type='release',debuggable=False,test_only=False,build_commit='c'*40)

@pytest.mark.parametrize('key,value',[('format',2),('platform','windows'),('application_id','other'),('version','0.25'),('version_code',0),('size',150*1024*1024+1),('size',True),('min_sdk',25),('url','http://evil.invalid/app.apk'),('filename','../app.apk'),('sha256','bad'),('signing_certificate_sha256','F'*64),('notes','x'*32001),('debuggable',True),('build_commit','bad')])
def test_invalid_feed_fails_before_publication(key,value):
 m=feed();m[key]=value
 with pytest.raises(ValueError):validate_feed(m)

def test_valid_feed_and_java_utf16_note_limit():
 validate_feed(feed());m=feed();m['notes']='😀'*16001
 with pytest.raises(ValueError):validate_feed(m)

def test_checksums_cover_every_published_asset(tmp_path):
 names=asset_names(feed());sums={}
 for name in names:
  if name=='SHA256.json':continue
  (tmp_path/name).write_bytes(b'fixture');sums[name]=hashlib.sha256(b'fixture').hexdigest()
 (tmp_path/'SHA256.json').write_text(json.dumps(sums));validate_checksums(tmp_path,names)
 del sums['NOTICE.md'];(tmp_path/'SHA256.json').write_text(json.dumps(sums))
 with pytest.raises(ValueError):validate_checksums(tmp_path,names)

def test_dirty_tree_and_wrong_build_commit_rejected(tmp_path):
 def git(*args):return subprocess.check_output(['git','-C',str(tmp_path),*args],text=True).strip()
 git('init');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid');(tmp_path/'source').write_text('fixture');git('add','source');git('commit','-m','fixture');head=check_repository(tmp_path)
 assert check_repository(tmp_path,head)==head
 with pytest.raises(ValueError):check_repository(tmp_path,'0'*40)
 (tmp_path/'source').write_text('dirty')
 with pytest.raises(ValueError):check_repository(tmp_path,head)


def test_publisher_rejects_invalid_feed_before_network(tmp_path,monkeypatch):
 import publish_android
 import sys
 class NoNetwork:
  @staticmethod
  def session():raise AssertionError('network must not be reached')
 monkeypatch.setitem(sys.modules,'publish_release',NoNetwork)
 m=feed();m['debuggable']=True
 (tmp_path/'android-update.json').write_text(json.dumps(m))
 with pytest.raises(ValueError):publish_android.publish(tmp_path,True)
