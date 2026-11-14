from unittest.mock import Mock
from types import SimpleNamespace
from contextlib import closing
import sqlite3
import pytest
from synostream_torrent_selection import default_file_selected

TITLE='Sen to Chihiro no kamikakushi'
FOLDER='Sen.to.Chihiro.no.kamikakushi.2001.720p.BluRay.DTS-ES.x264.HuN-TRiNiTY'
FILE='stcnk.720p-trinity.mkv'

def test_exact_alternative_title_not_rejected_as_different_script(media,monkeypatch):
    hit=dict(id=129,title='Chihiro szellemországban',original_title='千と千尋の神隠し',release_date='2001-07-20',overview='Leírás')
    monkeypatch.setattr(media,'search_tmdb',Mock(return_value=[hit]))
    monkeypatch.setattr(media,'tmdb_request',Mock(side_effect=lambda path,params:dict(titles=[dict(title=TITLE)]) if path.endswith('alternative_titles') else hit))
    assert media.fetch_tmdb_data(TITLE,'2001',True)['id']==129

@pytest.mark.parametrize('nfo',[{},dict(titles=['Unknown release title'])])
def test_filename_and_failed_nfo_do_not_prevent_folder_lookup(media,tmp_path,monkeypatch,nfo):
    folder=tmp_path/FOLDER;folder.mkdir();film=folder/FILE;film.touch()
    scanner=media.LibraryScannerThread([],[]);scanner.get_poster=Mock(return_value=None);scanner.read_nfo_hint=Mock(return_value=nfo)
    hit=dict(status='success',id=129,title='Chihiro szellemországban',overview='',poster_url='',date='2001')
    lookup=Mock(side_effect=lambda title,*a,**kw:hit if title==TITLE else dict(status='no_result'))
    monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        assert scanner.process_media_item(SimpleNamespace(path=str(film),name=FILE,stat=film.stat),True,db)['id']==129
    assert any(call.args== (TITLE,'2001',True) for call in lookup.call_args_list)

def test_nfo_selected_and_sample_nfo_excluded():
    assert default_file_selected('release.NFO')
    assert not default_file_selected('Sample/release.nfo')
