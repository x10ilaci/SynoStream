from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from contextlib import closing
import sqlite3
import pytest
from synostream_logic import movie_search_context

FOLDER='Wish.Dragon.2021.720p.NF.WEB-DL.DDP5.1.Atmos.H.264.HUN-FULCRUM'
FILE='fulcrum-wsh.drgn.2021.720p.web.mkv'

def test_exact_wish_dragon_context():
    assert movie_search_context(FILE,FOLDER,True)==dict(title='Wish Dragon',year='2021',from_folder=True)
    assert not movie_search_context(FILE,FOLDER,False)['from_folder']
    assert not movie_search_context(FILE,FOLDER.replace('2021','2022'),True)['from_folder']

@pytest.mark.parametrize('remote',[False,True])
def test_wish_dragon_retries_previous_failure_without_nfo(media,tmp_path,monkeypatch,remote):
    scanner=media.LibraryScannerThread([],[]);scanner.get_poster=Mock(return_value=None)
    if remote:
        path='syno:///Movies/'+FOLDER+'/'+FILE
        entry=SimpleNamespace(path=path,name=FILE,stat=lambda:SimpleNamespace(st_mtime=1))
        scanner.remote_client=Mock();scanner.remote_client.list_folder.return_value=[dict(name=FILE,isdir=False)]
    else:
        folder=tmp_path/FOLDER;folder.mkdir();film=folder/FILE;film.touch()
        path=str(film);entry=SimpleNamespace(path=path,name=FILE,stat=film.stat)
    lookup=Mock(return_value=dict(status='success',id=550205,title='A kívánságsárkány',overview='Leírás',poster_url='',date='2021-01-15'))
    monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        scanner.save_cache(db,media.normalize_media_path(path),1,-1,FILE,'','','',entry.stat().st_mtime,'no_result','no_result:language_fallback_v5:hu-HU')
        result=scanner.process_media_item(entry,True,db)
        lookup.assert_called_once_with('Wish Dragon','2021',True)
        assert result['id']==550205
