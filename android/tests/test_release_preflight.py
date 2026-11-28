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


@pytest.mark.parametrize('key,value',[('version','0.5.26'),('version_code',31),('version_code',29),('min_sdk',27),('filename','other.apk'),('url','https://other.invalid/app.apk'),('sha256','d'*64),('size',101),('signing_certificate_sha256','e'*64),('notes','changed')])
def test_repository_feed_must_match_release(tmp_path,key,value):
 from release_rules import validate_repository_feed
 m=feed();current=dict(m);current[key]=value;p=tmp_path/'update.json';p.write_text(json.dumps(current))
 with pytest.raises(ValueError):validate_repository_feed(p,m)

def test_feed_without_build_commit_matches_and_older_or_missing_is_warned(tmp_path):
 from release_rules import validate_repository_feed
 m=feed();current=dict(m);del current['build_commit'];p=tmp_path/'update.json';p.write_text(json.dumps(current));assert validate_repository_feed(p,m)
 current['version_code']=29;current['version']='0.5.24';current['filename']='SynoStream_Android_0.5.24.apk';current['url']='https://github.com/x10ilaci/SynoStream/releases/download/android-v0.5.24/SynoStream_Android_0.5.24.apk';p.write_text(json.dumps(current))
 with pytest.warns(RuntimeWarning,match='korábbi'):assert not validate_repository_feed(p,m)
 with pytest.warns(RuntimeWarning,match='hiányzik'):assert not validate_repository_feed(tmp_path/'missing.json',m)

def test_publication_checks_repository_feed_before_network(tmp_path,monkeypatch):
 import publish_android
 m=feed();(tmp_path/'android-update.json').write_text(json.dumps(m));seen=[]
 def mismatch(path,manifest):seen.append(path);raise ValueError('fixture mismatch')
 monkeypatch.setattr(publish_android,'validate_repository_feed',mismatch)
 with pytest.raises(ValueError,match='fixture mismatch'):publish_android.publish(tmp_path,True)
 assert seen and seen[0].name=='update.json'


@pytest.mark.parametrize('fault',['none','missing','older','mismatch','size','hash'])
def test_strict_postpublication_verification(tmp_path,fault):
 from publish_android import verify_feed
 folder=tmp_path/'release';folder.mkdir();m=feed();payload=b'fixture-apk'
 m.update(size=len(payload),sha256=hashlib.sha256(payload).hexdigest())
 (folder/m['filename']).write_bytes(payload)
 (folder/'android-update.json').write_text(json.dumps(m))
 current=dict(m);repo=tmp_path/'update.json'
 if fault=='older':
  current.update(version='0.5.24',version_code=29,filename='SynoStream_Android_0.5.24.apk',url='https://github.com/x10ilaci/SynoStream/releases/download/android-v0.5.24/SynoStream_Android_0.5.24.apk')
 if fault=='mismatch':current['notes']='different'
 if fault!='missing':repo.write_text(json.dumps(current))
 if fault=='size':(folder/m['filename']).write_bytes(payload+b'x')
 if fault=='hash':(folder/m['filename']).write_bytes(b'X'*len(payload))
 if fault=='none':assert verify_feed(folder,repo)==m
 else:
  with pytest.raises(ValueError):verify_feed(folder,repo)

def test_verify_cli_does_not_publish(tmp_path,monkeypatch):
 import publish_android
 from unittest.mock import Mock
 verify=Mock();publish=Mock();monkeypatch.setattr(publish_android,'verify_feed',verify);monkeypatch.setattr(publish_android,'publish',publish)
 publish_android.main(['--verify-feed','--folder',str(tmp_path)])
 verify.assert_called_once();publish.assert_not_called()
