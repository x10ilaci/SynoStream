from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import sqlite3

def test_numbered_series_merge_in_movie_library(media,tmp_path,monkeypatch):
    root=tmp_path/'Movies';root.mkdir()
    a=root/'Show A';b=root/'Show B'
    for folder in (a,b):
        folder.mkdir();(folder/'01.mkv').touch();(folder/'02.mkv').touch()
    groups=[dict(id='joined',title='Target',paths=[str(b),str(a)],library_id='movies')]
    scanner=media.LibraryScannerThread([str(root)],[],library_key='movies',manual_show_groups=groups)
    scanner.sync_portable_roots=Mock();scanner.get_poster=Mock(return_value=None)
    monkeypatch.setattr(media,'fetch_tmdb_data',Mock(return_value=dict(status='success',id=222,title='Target',overview='',date='',poster_url='')))
    found=[];scanner.item_ready.connect(lambda item,movie:found.append(item))
    scanner.run()
    assert len(found)==1 and found[0]['manual_group_id']=='joined'
    assert found[0]['file_path']==str(b) and found[0]['episode_roots']==[str(b),str(a)]

def test_manual_search_cleans_release_and_searches_english(media,monkeypatch):
    search=Mock(side_effect=lambda title,year,movie,language=None:[dict(id=222,title='Target',release_date='2016')] if title=='Target' and language=='en-US' else [])
    monkeypatch.setattr(media,'search_tmdb',search)
    result=media.search_tmdb_multiple('Target.2016.720p.BluRay',True)
    assert result['status']=='success' and result['results'][0]['id']==222

@pytest.mark.parametrize('manual',[False,True])
def test_ernest_celestine_foreign_connector(media,monkeypatch,manual):
    hit=dict(id=74623,name='Ernest and Célestine, The Collection',original_name='Ernest et Célestine, la collection',first_air_date='2017-04-01',overview='Description')
    monkeypatch.setattr(media,'search_tmdb',Mock(side_effect=lambda title,*a,**kw:[hit] if title=='Ernest and Célestine' else []))
    monkeypatch.setattr(media,'tmdb_request',Mock(return_value=hit))
    title,year=media.clean_name('Ernest és Célestine S01 1080i',False)
    assert title=='Ernest és Célestine'
    result=media.search_tmdb_multiple(title,False) if manual else media.fetch_tmdb_data(title,year,False)
    assert result['status']=='success'
    assert (result['results'][0]['id'] if manual else result['id'])==74623

def test_merge_uses_selected_target_without_name_question(media,app,tmp_path,monkeypatch):
    a=tmp_path/'A';b=tmp_path/'B';a.mkdir();b.mkdir()
    media.config.update(shows_paths=[str(tmp_path)],shows_path=str(tmp_path))
    window=media.DSVideoWindow();window.start_library_scan=Mock()
    items=[dict(file_path=str(p),title=t,id=i,overview='',is_movie=False,library_id='shows') for p,t,i in ((a,'Source',111),(b,'Target',222))]
    for item in items:window.shows_page.add_item(item)
    monkeypatch.setattr(media.QInputDialog,'getItem',Mock(return_value=(0,True)))
    monkeypatch.setattr(media.QInputDialog,'getText',Mock(side_effect=AssertionError('No name question')))
    try:
        window.merge_show_cards(items[0])
        group=media.config['manual_show_groups'][-1]
        assert group['title']=='Target' and group['paths']==[str(b),str(a)]
        window.start_library_scan.assert_called_once_with('shows')
    finally:window.close();app.processEvents()
