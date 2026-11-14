from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from contextlib import closing
import sqlite3
import pytest
from synostream_logic import movie_search_context

FILE='HDGirL-tales.from.earthsea.720p.mkv'
FOLDER='Tales.from.Earthsea.720p.BluRay.DTS.x264.Hun-HDGirL'

def test_yearless_release_folder_removes_matching_group_prefix():
    assert movie_search_context(FILE,FOLDER,True)==dict(title='Tales from Earthsea',year=None,from_folder=True)

@pytest.mark.parametrize('folder,single',[(FOLDER,False),('Tales from Earthsea',True),('Earthsea.720p',True),('Different.Movie.720p',True)])
def test_ambiguous_or_nonrelease_folder_not_used(folder,single):
    assert not movie_search_context(FILE,folder,single)['from_folder']

@pytest.mark.parametrize('remote',[False,True])
def test_exact_hdgirl_release_lookup_without_nfo(media,tmp_path,monkeypatch,remote):
    scanner=media.LibraryScannerThread([],[]);scanner.get_poster=Mock(return_value=None)
    if remote:
        path='syno:///Movies/'+FOLDER+'/'+FILE
        entry=SimpleNamespace(path=path,name=FILE,stat=lambda:SimpleNamespace(st_mtime=1))
        scanner.remote_client=Mock();scanner.remote_client.list_folder.return_value=[dict(name=FILE,isdir=False)]
    else:
        folder=tmp_path/FOLDER;folder.mkdir();film=folder/FILE;film.touch()
        path=str(film);entry=SimpleNamespace(path=path,name=FILE,stat=film.stat)
    lookup=Mock(return_value=dict(status='success',id=37933,title='Tales from Earthsea',overview='',date='2006',poster_url=''))
    monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        scanner.save_cache(db,media.normalize_media_path(path),1,-1,FILE,'','','',entry.stat().st_mtime,'no_result','no_result:language_fallback_v5:hu-HU')
        assert scanner.process_media_item(entry,True,db)['id']==37933
        lookup.assert_called_once_with('Tales from Earthsea',None,True)
