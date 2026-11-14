from unittest.mock import Mock
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import pytest


def film(identifier, title, year, votes=0, **extra):
    return dict(id=identifier, title=title, original_title=title,
                release_date=f'{year}-01-01', vote_count=votes, overview='Description', **extra)


@pytest.mark.parametrize('name,expected', [
    ('Some.Show.S03E.WEB-DL.1080p', 'Some Show'),
    ('Some.Show.COMPLETE.1080p.BluRay', 'Some Show'),
    ('Complete.2019.1080p.mkv', 'Complete'),
    ('The.Complete.Truth.2019.1080p.mkv', 'The Complete Truth'),
])
def test_release_markers_do_not_pollute_or_remove_real_title(media,name,expected):
    assert media.clean_name(name, is_file=name.endswith('.mkv'))[0] == expected


@pytest.mark.parametrize('query,candidate', [
    ('river', 'River of No Return'),
    ('kimi no wa', 'Boku wa Kimi no Namida'),
    ('rio', 'El Rio'),
])
def test_year_and_shared_words_do_not_make_unrelated_title_reliable(media,query,candidate):
    assert not media.evaluate_hit(film(1,candidate,2020),query,'2020',True)[0]


def test_long_joined_series_name_is_recognized_but_short_abbreviation_is_not(media):
    assert media.evaluate_hit(dict(id=1,name='Boribonmesék'), 'boribon',None,False)[0]
    assert not media.evaluate_hit(film(2,'Kubo and the Two Strings',2016),'kubo',None,True)[0]


def test_ambiguous_namesakes_do_not_depend_on_result_order(media):
    rows=[film(1,'Same Title',2020),film(2,'Same Title',2020)]
    assert media.pick_reliable_hit(rows,'same title','2020',True) is None
    assert media.pick_reliable_hit(rows[::-1],'same title','2020',True) is None


def install_api(media,monkeypatch,search,details,aliases=None):
    monkeypatch.setattr(media,'search_tmdb',Mock(side_effect=search))
    def request(endpoint,params):
        if endpoint.endswith('/alternative_titles'):
            return {'titles': [{'title': name} for name in (aliases or {}).get(int(endpoint.split('/')[1]),[])]}
        return details[int(endpoint.split('/')[1])]
    monkeypatch.setattr(media,'tmdb_request',request)


def test_filtered_search_does_not_hide_adjacent_year_exact_title(media,monkeypatch):
    wrong=film(1,'Sacrifice',2025)
    correct=film(2,'Sacrifice',2026,159)
    near=film(3,'A Sacrifice',2024,171)
    install_api(media,monkeypatch,lambda title,year,*a,**kw:[wrong] if year else [near,correct,wrong],{1:wrong,2:correct,3:near})
    assert media.fetch_tmdb_data('Sacrifice','2025',True)['id']==2
    assert {call.args[1] for call in media.search_tmdb.call_args_list}=={'2025',None}


def test_alternative_romanized_title_beats_loose_word_overlap(media,monkeypatch):
    correct=film(1,'Your Name',2016,100)
    wrong=film(2,'Boku wa Kimi no Namida',1998)
    install_api(media,monkeypatch,lambda *a,**kw:[wrong,correct],{1:correct,2:wrong},{1:['Kimi no Na wa']})
    assert media.fetch_tmdb_data('Kimi no wa')['id']==1


def test_grammatical_word_fallback_checks_full_title(media,monkeypatch):
    correct=film(1,'Even Mice Belong in Heaven',2021)
    install_api(media,monkeypatch,lambda title,*a,**kw:[correct] if title=='Even Mice Belong Heaven' else [],{1:correct})
    assert media.fetch_tmdb_data('Even Mice Belong to Heaven','2021')['id']==1


def test_compact_query_cannot_accept_unrelated_partial_title(media,monkeypatch):
    wrong=film(1,'Heaven',2021,10000)
    install_api(media,monkeypatch,lambda title,*a,**kw:[] if title=='Even Mice Belong to Heaven' else [wrong],{1:wrong})
    assert media.fetch_tmdb_data('Even Mice Belong to Heaven','2021')['status']=='no_result'


def test_namesake_with_more_votes_cannot_bypass_year_window(media,monkeypatch):
    correct=film(1,'Same Title',2020,10)
    wrong=film(2,'Same Title',1980,100000)
    install_api(media,monkeypatch,lambda *a,**kw:[wrong,correct],{1:correct,2:wrong})
    assert media.fetch_tmdb_data('Same Title','2020')['id']==1


def test_old_auto_match_is_invalidated_but_manual_signature_is_preserved(media):
    scanner=media.LibraryScannerThread([],[])
    path='syno:///Movies/Title.2020.mkv'
    row=dict(status='success',signature='language:hu-HU',release_date='2020-01-01',file_mtime=1)
    assert not scanner._cached_row_is_current(path,'Title.2020.mkv',True,row)
    scanner.manual_override_index[(media.normalize_media_path(path),1)]=(99,'Chosen')
    row['signature']='override:99:hu-HU'
    assert scanner._cached_row_is_current(path,'Title.2020.mkv',True,row)


@pytest.mark.parametrize('nfo',[False,True])
def test_movie_titles_in_parentheses_are_searched_independently(media,tmp_path,monkeypatch,nfo):
    path=tmp_path/'Original title(Magyar cím).mkv';path.touch()
    scanner=media.LibraryScannerThread([],[]);scanner.get_poster=lambda *a:None
    scanner.read_nfo_hint=Mock(return_value={'titles':['Unknown NFO title']} if nfo else {})
    def lookup(title,*args,**kwargs):
        if title=='Magyar cím':return dict(status='success',id=12,title='Magyar cím',overview='',poster_url='',date='2020',complete=True)
        return dict(status='no_result')
    monkeypatch.setattr(media,'fetch_tmdb_data',Mock(side_effect=lookup))
    with sqlite3.connect(media.DB_FILE) as db:
        item=scanner.process_media_item(SimpleNamespace(path=str(path),name=path.name,stat=path.stat),True,db)
    assert item['id']==12
    assert any(call.args[0]=='Original title' for call in media.fetch_tmdb_data.call_args_list)


@pytest.mark.parametrize('previous_id,expected',[(1,1),(3,-1)])
def test_ambiguous_match_only_preserves_previously_valid_candidate(media,tmp_path,monkeypatch,previous_id,expected):
    path=tmp_path/'Same.Title.2020.mkv';path.touch()
    scanner=media.LibraryScannerThread([],[]);scanner.get_poster=lambda *a:None
    def lookup(title,*args,**kwargs):
        if kwargs.get('tmdb_id'):
            return dict(status='success',id=kwargs['tmdb_id'],title='Same Title',overview='',poster_url='',date='2020',complete=True)
        return dict(status='no_result',message='Ambiguous',ambiguous_ids=[1,2])
    monkeypatch.setattr(media,'fetch_tmdb_data',Mock(side_effect=lookup))
    with sqlite3.connect(media.DB_FILE) as db:
        scanner.save_cache(db,media.normalize_media_path(str(path)),1,previous_id,'Same Title','','','2020-01-01',path.stat().st_mtime,'success','language:hu-HU')
        item=scanner.process_media_item(SimpleNamespace(path=str(path),name=path.name,stat=path.stat),True,db)
    assert item['id']==expected


def test_new_ambiguous_match_exposes_only_competing_reliable_ids(media,monkeypatch):
    a=film(1,'Same Title',2020,10);b=film(2,'Same Title',2020,10);wrong=film(3,'Other Title',2020,10000)
    install_api(media,monkeypatch,lambda *args,**kw:[a,b,wrong],{1:a,2:b,3:wrong})
    result=media.fetch_tmdb_data('Same Title','2020')
    assert result['status']=='no_result' and set(result['ambiguous_ids'])=={1,2}


def test_series_alias_cache_signature_matches_incremental_scan(media,tmp_path,monkeypatch):
    path=tmp_path/'Original (Magyar cím)';path.mkdir()
    scanner=media.LibraryScannerThread([],[]);scanner.get_poster=lambda *a:None
    monkeypatch.setattr(media,'fetch_tmdb_data',Mock(return_value=dict(status='success',id=12,title='Magyar cím',overview='',poster_url='',date='2020',complete=True)))
    with sqlite3.connect(media.DB_FILE) as db:
        scanner.process_media_item(SimpleNamespace(path=str(path),name=path.name,stat=path.stat),False,db)
        db.row_factory=sqlite3.Row
        row=dict(db.execute('SELECT * FROM media_cache').fetchone())
    assert scanner._cached_row_is_current(str(path),path.name,False,row)
