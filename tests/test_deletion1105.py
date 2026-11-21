from test_deletion1104 import Files,movie,ROOT
from synostream_deletion import Inventory
import pytest

def test_longest_stem_companion_and_shared_subs():
 a=ROOT+'/Alien.mkv';b=ROOT+'/Alien.Resurrection.mkv';sub=ROOT+'/Subs/Alien.Resurrection.srt';fs=Files([a,b,sub,ROOT+'/Alien.en.srt'])
 assert sub not in Inventory([a],[ROOT],True,fs.list).plan().files
 assert sub in Inventory([b],[ROOT],True,fs.list).plan().files
 assert ROOT+'/Alien.en.srt' in Inventory([a],[ROOT],True,fs.list).plan().files

def test_unknown_default_and_explicit_opt_in():
 file=ROOT+'/Movie/Movie.mkv';pdf=ROOT+'/Movie/notes.pdf';fs,inv=movie([file,pdf]);plan=inv.plan();assert plan.unknown==(pdf,) and pdf not in plan.files;inv.execute(plan,fs.delete);assert pdf in fs.rows and ROOT+'/Movie' in fs.rows
 fs,inv=movie([file,pdf]);inv.execute(inv.plan(include_unknown=True),fs.delete);assert ROOT+'/Movie' not in fs.rows

@pytest.mark.parametrize('mode',['missing','root_alias','file_alias'])
def test_physical_metadata_fails_closed(mode):
 file=ROOT+'/Movie/Movie.mkv';fs=Files([file])
 if mode=='missing':fs.rows[file]['additional'].pop('real_path')
 elif mode=='root_alias':
  fs.rows[ROOT+'/Movie']['additional']['real_path']='/volume1/Private';fs.rows[file]['additional']['real_path']='/volume1/Private/Movie.mkv'
 else:fs.rows[file]['additional']['real_path']='/volume1'+ROOT+'/Movie/Other.mkv'
 with pytest.raises(ValueError):Inventory([file],[ROOT],True,fs.list)
 assert fs.deleted==[]
