import copy
import json
from pathlib import PurePosixPath
from dataclasses import replace
from unittest.mock import Mock
import pytest
from synostream_deletion import Inventory,path
ROOT='/Media/Movies'
class Files:
 def __init__(self,files):
  self.rows={};self.deleted=[]
  for file in files:
   self.rows[file]={'path':file,'name':PurePosixPath(file).name,'isdir':False,'size':10,'additional':{'time':{'mtime':1}}}
   parent=str(PurePosixPath(file).parent)
   while parent!='/':
    self.rows.setdefault(parent,{'path':parent,'name':PurePosixPath(parent).name,'isdir':True,'additional':{'time':{'mtime':1}}});parent=str(PurePosixPath(parent).parent)
 def list(self,root):
  if root not in self.rows or not self.rows[root]['isdir']:raise OSError('missing fixture folder')
  return [copy.deepcopy(e) for p,e in self.rows.items() if str(PurePosixPath(p).parent)==root]
 def delete(self,paths):
  self.deleted.append(list(paths))
  for p in paths:
   assert p not in ('/Media',ROOT)
   if self.rows[p]['isdir']:assert self.list(p)==[],'recursive deletion is forbidden'
   del self.rows[p]
def movie(files,seed=ROOT+'/Movie/Movie.mkv',protected=()):
 fs=Files(files);return fs,Inventory([seed],[ROOT],True,fs.list,protected)
def series():
 root=ROOT+'/Show';fs=Files([root+'/Season 1/S01E01.mkv',root+'/Season 1/release.nfo',root+'/Season 2/S02E01.mkv',root+'/Season 2/release.nfo',root+'/tvshow.nfo',root+'/poster.jpg']);return fs,Inventory([root],[ROOT],False,fs.list),root

def test_movie_removes_own_nfo_subtitles_samples_and_empty_parent():
 file=ROOT+'/Movie/Disc1/Movie.mkv';fs,inv=movie([file,ROOT+'/Movie/release.nfo',ROOT+'/Movie/Subs/Movie.hu.srt',ROOT+'/Movie/Sample/sample.mkv'],file)
 fs.rows[ROOT+'/Movie/Empty']={'path':ROOT+'/Movie/Empty','isdir':True};inv=Inventory([file],[ROOT],True,fs.list)
 plan=inv.plan();assert len(plan.files)==4;result=inv.execute(plan,fs.delete)
 assert ROOT+'/Movie' in result['folders'] and ROOT in fs.rows
 assert not any(p.startswith(ROOT+'/Movie/') for p in fs.rows)
def test_shared_folder_keeps_other_movie_and_its_metadata():
 a=ROOT+'/A.mkv';b=ROOT+'/B.mkv';fs,inv=movie([a,ROOT+'/A.nfo',ROOT+'/A.hu.srt',b,ROOT+'/B.nfo',ROOT+'/library.nfo'],a,protected=[b])
 assert set(inv.plan().files)=={a,ROOT+'/A.nfo',ROOT+'/A.hu.srt'};inv.execute(inv.plan(),fs.delete)
 assert b in fs.rows and ROOT+'/B.nfo' in fs.rows and ROOT+'/library.nfo' in fs.rows
def test_partial_season_preserves_other_season_and_shared_nfo():
 fs,inv,root=series();assert inv.seasons==(1,2);plan=inv.plan([1]);assert not plan.all_seasons;inv.execute(plan,fs.delete)
 assert root+'/Season 1' not in fs.rows
 assert root+'/Season 2/S02E01.mkv' in fs.rows and root+'/tvshow.nfo' in fs.rows and root in fs.rows
def test_all_seasons_remove_show_metadata_and_show_folder():
 fs,inv,root=series();plan=inv.plan([1,2]);assert plan.all_seasons;inv.execute(plan,fs.delete);assert root not in fs.rows
def test_mixed_seasons_in_one_folder_keep_remaining_episode_sidecar():
 root=ROOT+'/Show';one=root+'/S01E01.mkv';two=root+'/S02E01.mkv';fs=Files([one,two,root+'/S01E01.nfo',root+'/S02E01.nfo',root+'/S01.nfo',root+'/S02.nfo',root+'/tvshow.nfo'])
 inv=Inventory([root],[ROOT],False,fs.list);plan=inv.plan([1]);assert root+'/S01.nfo' in plan.files and root+'/S02.nfo' not in plan.files;inv.execute(plan,fs.delete)
 assert two in fs.rows and root+'/S02E01.nfo' in fs.rows and root+'/tvshow.nfo' in fs.rows
def test_merged_season_roots_clean_common_show_folder_only_when_all_selected():
 fs,_,root=series();inv=Inventory([root+'/Season 1',root+'/Season 2'],[ROOT],False,fs.list);inv.execute(inv.plan([1,2]),fs.delete);assert root not in fs.rows
def test_empty_season_selection_never_deletes():
 fs,inv,_=series()
 with pytest.raises(ValueError):inv.plan([])
 assert fs.deleted==[]
def test_changed_snapshot_aborts_before_first_write():
 fs,inv=movie([ROOT+'/Movie/Movie.mkv',ROOT+'/Movie/a.nfo']);plan=inv.plan();fs.rows[ROOT+'/Movie/a.nfo']['additional']['time']['mtime']=2
 with pytest.raises(ValueError,match='megváltozott'):inv.execute(plan,fs.delete)
 assert fs.deleted==[]
def test_file_added_after_deletion_never_triggers_recursive_cleanup():
 fs,inv=movie([ROOT+'/Movie/Movie.mkv']);plan=inv.plan()
 def delete(paths):
  fs.delete(paths)
  if paths==list(plan.files):fs.rows[ROOT+'/Movie/new.nfo']={'path':ROOT+'/Movie/new.nfo','isdir':False,'size':1}
 inv.execute(plan,delete);assert ROOT+'/Movie/new.nfo' in fs.rows and ROOT+'/Movie' in fs.rows
def test_write_failure_is_not_retried():
 fs,inv=movie([ROOT+'/Movie/Movie.mkv']);delete=Mock(side_effect=TimeoutError('uncertain'))
 with pytest.raises(TimeoutError):inv.execute(inv.plan(),delete)
 assert delete.call_count==1
def test_forged_plan_and_protected_media_are_rejected():
 fs,inv=movie([ROOT+'/Movie/Movie.mkv'])
 with pytest.raises(ValueError):inv.execute(replace(inv.plan(),files=(ROOT+'/Other.mkv',)),fs.delete)
 assert fs.deleted==[]
@pytest.mark.parametrize('value',['/Media/../Other/file.mkv','/Media//Movie/a.mkv','/Media/./a.mkv','https://nas/file','/Media/a\x00.mkv','/Media/Movies\\a.mkv'])
def test_unsafe_paths_rejected(value):
 with pytest.raises(ValueError):path(value)
def test_symbolic_directory_and_real_path_escape_are_rejected():
 fs=Files([ROOT+'/Movie/Movie.mkv']);fs.rows[ROOT+'/Movie']['additional']['real_path']='/volume1/Media/Movies/Movie';fs.rows[ROOT+'/Movie/Movie.mkv']['additional']['real_path']='/volume1/Private/Movie.mkv'
 with pytest.raises(ValueError,match='hivatkozást'):Inventory([ROOT+'/Movie/Movie.mkv'],[ROOT],True,fs.list)
 assert fs.deleted==[]
def test_cancel_review_does_not_call_nas_delete(media,app):
 from synostream_delete_ui import DeleteMediaDialog
 factory=Mock();dialog=DeleteMediaDialog(None,'Movie',True,[ROOT+'/Movie/Movie.mkv'],[ROOT],[],factory,Mock(),Mock(),lambda:True,Mock())
 dialog.reject();app.processEvents();factory.assert_not_called()

@pytest.mark.parametrize('cancel',[False,True,'cache-failure'])
def test_real_review_dialog_writes_only_after_confirmation(media,app,cancel):
 import time
 from types import SimpleNamespace
 from synostream_delete_ui import DeleteMediaDialog
 fs,inv=movie([ROOT+'/Movie/Movie.mkv',ROOT+'/Movie/release.nfo'])
 result=[]
 def factory(stop):return SimpleNamespace(list_folder=fs.list,delete_paths=fs.delete,close=lambda:None)
 dialog=DeleteMediaDialog(None,'Movie',True,[ROOT+'/Movie/Movie.mkv'],[ROOT],[],factory,media.NasTask,media.run_worker,lambda:True,(Mock(side_effect=OSError('fixture save failure')) if cancel=='cache-failure' else result.append))
 dialog.show()
 deadline=time.monotonic()+5
 while dialog.inventory is None and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
 assert dialog.inventory is not None and fs.deleted==[]
 if cancel is True:
  dialog.reject();app.processEvents();assert fs.deleted==[] and result==[]
 else:
  dialog.delete.click()
  while not result and 'helyi lista' not in dialog.status.text() and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
  assert ROOT+'/Movie' not in fs.rows
  if cancel=='cache-failure':assert 'helyi lista' in dialog.status.text() and dialog.isVisible()
  else:assert result
 dialog.close();app.processEvents()

@pytest.mark.parametrize('outcome',['success','timeout','denied'])
def test_nas_delete_uses_exact_paths_nonrecursive_post_and_no_uncertain_retry(outcome):
 import threading,requests
 from synostream_nas import RemoteNASClient
 c=RemoteNASClient.__new__(RemoteNASClient);c.lock=threading.RLock();c.should_stop=lambda:False;c.transport='direct';c.sid='fixture';c.base_url='https://nas.example';c.credentials={}
 c.api_info={'SYNO.FileStation.Delete':{'path':'entry.cgi','maxVersion':2}}
 response=Mock(status_code=200);response.json.return_value={'success':outcome=='success','error':{'code':408}}
 c.session=Mock();c.session.post.return_value=response
 if outcome=='timeout':c.session.post.side_effect=requests.Timeout()
 if outcome=='success':c.delete_paths([ROOT+'/Movie/Movie.mkv'])
 else:
  with pytest.raises(RuntimeError):c.delete_paths([ROOT+'/Movie/Movie.mkv'])
 assert c.session.post.call_count==1
 data=c.session.post.call_args.kwargs['data']
 assert data['recursive']=='false' and json.loads(data['path'])==[ROOT+'/Movie/Movie.mkv']
