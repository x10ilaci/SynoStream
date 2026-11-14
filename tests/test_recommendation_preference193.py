import contextlib
import json
import random
import sqlite3
import time
from unittest.mock import Mock
import pytest
import synostream_recommendations as rec
from test_recommendations192 import cached,result,seed

@pytest.fixture
def store(media):return rec.RecommendationStore(media.DB_FILE)

def translation(overview='Magyar leírás',title='',country='HU',language='hu'):
    return dict(iso_639_1=language,iso_3166_1=country,data=dict(title=title,name=title,overview=overview))

def api_response(path,params):
    if path.endswith('/recommendations'):return {'results':[result(i) for i in range(100,120)]}
    return {'translations':[translation()]}


def test_preference_checks_translations_with_budget_and_accepts_empty_title(store):
    request=Mock(side_effect=api_response)
    loaded=store.load('A',[seed()],set(),'hu-HU',request,prefer_hungarian=True)
    assert loaded['requests']==1 and loaded['localization_requests']==rec.MAX_LOCALIZATION_REQUESTS
    assert sum(i.get('has_hu_metadata') is True for i in loaded['pool'].values())==8
    assert all(i['overview']=='Magyar leírás' for i in loaded['pool'].values() if i.get('has_hu_metadata'))
    assert {i['id'] for i in loaded['pool'].values()}==set(range(100,120))


def test_disabled_preference_never_requests_extra_translation_data(store):
    request=Mock(return_value={'results':[result()]})
    loaded=store.load('A',[seed()],set(),'hu-HU',request,prefer_hungarian=False)
    assert loaded['localization_requests']==0
    request.assert_called_once_with('movie/1/recommendations',{'language':'hu-HU','page':1})


@pytest.mark.parametrize('language',['hu-HU','en-US'])
def test_localization_cache_is_shared_between_libraries_but_display_language_is_preserved(store,language):
    item=rec.normalize_result(result(),'movie');cached(store,'A',[seed()],[item],language);cached(store,'B',[seed()],[item],language)
    request=Mock(return_value={'translations':[translation(title='Magyar cím')]})
    first=store.load('A',[seed()],set(),language,request,prefer_hungarian=True)
    second=store.load('B',[seed()],set(),language,request,prefer_hungarian=True)
    assert first['localization_requests']==1 and second['localization_requests']==0
    assert request.call_count==1
    assert second['items'][0]['title']==('Magyar cím' if language=='hu-HU' else item['title'])


def test_failure_does_not_cache_unknown_as_missing_hungarian(store):
    item=rec.normalize_result(result(),'movie');cached(store,'A',[seed()],[item])
    request=Mock(side_effect=RuntimeError('offline'))
    loaded=store.load('A',[seed()],set(),'hu-HU',request,prefer_hungarian=True)
    assert loaded['errors']==1 and loaded['items'][0]['has_hu_metadata'] is None
    assert store.localization()=={}


@pytest.mark.parametrize('translations',[[translation(language='en')],[translation(overview='   ')],[]])
def test_untranslated_candidates_are_retained(store,translations):
    item=rec.normalize_result(result(),'movie');cached(store,'A',[seed()],[item])
    loaded=store.load('A',[seed()],set(),'hu-HU',lambda *a:{'translations':translations},prefer_hungarian=True)
    assert len(loaded['items'])==1 and loaded['items'][0]['has_hu_metadata'] is False


def test_soft_preference_boosts_but_does_not_exclude_other_candidates(store):
    hu=dict(rec.normalize_result(result(100),'movie'),has_hu_metadata=True,score=1)
    other=dict(rec.normalize_result(result(101),'movie'),has_hu_metadata=False,score=1)
    pool={rec.identity(hu):hu,rec.identity(other):other}
    chosen=[store.draw('A',pool,set(),limit=1,rng=random.Random(i),prefer_hungarian=True)[0]['id'] for i in range(80)]
    assert 50<chosen.count(100)<80
    both=store.draw('A',pool,set(),rng=random.Random(3),prefer_hungarian=True)
    assert [i['id'] for i in both]==[100,101]
    assert len(store.draw('A',pool,set(),prefer_hungarian=False))==2


def test_owned_and_dismissed_titles_are_not_checked_or_reintroduced(store):
    rows=[rec.normalize_result(result(i),'movie') for i in (100,101,102)]
    cached(store,'A',[seed()],rows);store.set_feedback('A',rows[1],'dismissed')
    request=Mock(return_value={'translations':[translation()]})
    loaded=store.load('A',[seed()],{('movie',100)},'hu-HU',request,prefer_hungarian=True)
    request.assert_called_once_with('movie/102/translations',{})
    assert [i['id'] for i in loaded['items']]==[102]


def test_cancelled_translation_is_not_committed(store):
    item=rec.normalize_result(result(),'movie');cached(store,'A',[seed()],[item])
    stop=[False]
    def request(*args):stop[0]=True;return {'translations':[translation()]}
    with pytest.raises(InterruptedError):store.load('A',[seed()],set(),'hu-HU',request,lambda:stop[0],prefer_hungarian=True)
    assert store.localization()=={}


def test_save_option_survives_restart_and_false_is_not_overwritten(media,app,monkeypatch):
    window=media.DSVideoWindow()
    monkeypatch.setattr(media.QMessageBox,'information',Mock())
    try:
        assert window.recommendation_hungarian_check.isChecked()
        window.recommendation_hungarian_check.setChecked(False);window.save_playback_preferences()
        loaded,_=media.load_config();assert loaded['recommendation_prefer_hungarian'] is False
        assert media.config['recommendation_prefer_hungarian'] is False
    finally:window.close();app.processEvents()


def test_failed_save_restores_preference(media,app,monkeypatch):
    window=media.DSVideoWindow()
    monkeypatch.setattr(media.QMessageBox,'critical',Mock());monkeypatch.setattr(media,'save_config',lambda:(False,'test'))
    try:
        window.recommendation_hungarian_check.setChecked(False);window.save_playback_preferences()
        assert media.config['recommendation_prefer_hungarian'] is True
    finally:window.close();app.processEvents()
