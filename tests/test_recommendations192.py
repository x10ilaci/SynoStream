import contextlib
import json
import random
import sqlite3
import time
from unittest.mock import Mock
import pytest
import synostream_recommendations as rec
from synostream_recommendation_ui import RecommendationsDialog

@pytest.fixture
def store(media):return rec.RecommendationStore(media.DB_FILE)

def seed(id=1,kind='movie'):return dict(id=id,media_type=kind,title='Seed '+str(id))

def result(id=100,kind='movie',**changes):
    item=dict(id=id,title='Film '+str(id),name='TV '+str(id),poster_path='/poster.jpg',overview='Leírás',release_date='2020-01-01')
    item.update(changes);return item

def cached(store,library,seeds,rows,language='hu-HU',fetched=None):
    with store.connection() as db, db:
        for s in seeds:
            key=rec.identity(s)
            db.execute('INSERT OR REPLACE INTO recommendation_cache VALUES (?,?,?,?,?,?)',(library,*key,language,json.dumps(rows),time.time() if fetched is None else fetched))

def test_cached_requests_are_reused_and_new_seeds_extend_pool(store):
    request=Mock(return_value={'results':[result()]})
    first=store.load('A',[seed()],set(),'hu-HU',request)
    assert first['requests']==1 and first['items'][0]['title']=='Film 100'
    second=store.load('A',[seed()],set(),'hu-HU',request)
    assert second['requests']==0 and request.call_count==1
    third=store.load('A',[seed(),seed(2)],set(),'hu-HU',request)
    assert third['requests']==1 and request.call_count==2
    assert third['items'][0]['reasons']==['Seed 1','Seed 2']


def test_request_budget_rotates_unfetched_seed_titles(store):
    request=Mock(return_value={'results':[result()]})
    seeds=[seed(i) for i in range(1,11)]
    store.load('A',seeds,set(),'hu-HU',request)
    assert request.call_count==rec.MAX_REQUESTS
    store.load('A',seeds,set(),'hu-HU',request)
    assert request.call_count==8
    paths=[call.args[0] for call in request.call_args_list]
    assert len(set(paths))==8


def test_library_and_language_caches_are_independent(store):
    request=Mock(return_value={'results':[result()]})
    for library,language in [('A','hu-HU'),('B','hu-HU'),('A','en-US')]:
        store.load(library,[seed()],set(),language,request)
    assert request.call_count==3
    assert {c.args[1]['language'] for c in request.call_args_list}=={'hu-HU','en-US'}


def test_owned_titles_and_feedback_excluded_by_type_and_library(store):
    request=Mock(return_value={'results':[result(100),result(101),result(102)]})
    loaded=store.load('A',[seed()],{('movie',100)},'hu-HU',request)
    assert {i['id'] for i in loaded['items']}=={101,102}
    item=loaded['pool'][('movie',101)];store.set_feedback('A',item,'dismissed')
    assert {i['id'] for i in store.draw('A',loaded['pool'],{('movie',100)})}=={102}
    assert {i['id'] for i in store.draw('B',loaded['pool'],{('tv',100)})}=={100,101,102}


def test_interested_list_is_persistent_can_be_removed_and_hides_owned(store,media):
    item=rec.normalize_result(result(),'movie')
    store.set_feedback('A',item,'interested')
    other=rec.RecommendationStore(media.DB_FILE)
    assert other.saved('A',set())==[item]
    assert other.saved('B',set())==[]
    assert other.saved('A',{('movie',100)})==[]
    store.set_feedback('A',item,'neutral');assert store.saved('A',set())==[]


def test_new_batches_rotate_and_small_pools_do_not_disappear(store):
    rows=[rec.normalize_result(result(i),'movie') for i in range(100,140)]
    cached(store,'A',[seed()],rows)
    pool,_=store.pool('A',[seed()],'hu-HU')
    first=store.draw('A',pool,set(),rng=random.Random(1));store.mark_seen('A',first)
    second=store.draw('A',pool,set(),[rec.identity(i) for i in first],rng=random.Random(2))
    assert not {i['id'] for i in first}&{i['id'] for i in second}
    tiny={rec.identity(rows[0]):rows[0]}
    assert store.draw('A',tiny,set(),[rec.identity(rows[0])])==[rows[0]]


def test_empty_or_unidentified_library_never_calls_api(store):
    request=Mock()
    assert store.load('A',[dict(id=-1,is_movie=True)],set(),'hu-HU',request)['items']==[]
    request.assert_not_called()


def test_tv_endpoint_and_same_numeric_movie_id_stay_distinct(store):
    request=Mock(return_value={'results':[result(100)]})
    loaded=store.load('A',[seed(1,'tv')],{('movie',100)},'hu-HU',request)
    request.assert_called_once_with('tv/1/recommendations',{'language':'hu-HU','page':1})
    assert loaded['items'][0]['media_type']=='tv' and loaded['items'][0]['title']=='TV 100'


def test_network_error_preserves_stale_cached_recommendations(store):
    item=rec.normalize_result(result(),'movie')
    cached(store,'A',[seed()],[item],fetched=time.time()-rec.CACHE_TTL-10)
    request=Mock(side_effect=RuntimeError('offline'))
    loaded=store.load('A',[seed()],set(),'hu-HU',request)
    assert loaded['errors']==1 and loaded['items'][0]['id']==100


@pytest.mark.parametrize('stage',['before','after'])
def test_cancelled_request_does_not_commit_results(store,stage):
    stopped=[stage=='before']
    def request(*args):stopped[0]=True;return {'results':[result()]}
    with pytest.raises(InterruptedError):store.load('A',[seed()],set(),'hu-HU',request,lambda:stopped[0])
    assert store.pool('A',[seed()],'hu-HU')==({}, {})


@pytest.mark.parametrize('item',[None,{},dict(id=-1,title='bad'),dict(id=True,title='bad'),dict(id=100,title='',name='',original_title=''),dict(id=100,title='adult',adult=True)])
def test_invalid_results_do_not_become_cards(item):
    assert rec.normalize_result(item,'movie') is None


def test_external_poster_host_is_not_accepted():
    item=rec.normalize_result(result(poster_path='https://example.org/a.jpg'),'movie')
    assert item['poster_url']==''


def test_multiple_support_and_duplicate_source_results(store):
    item=rec.normalize_result(result(),'movie')
    cached(store,'A',[seed()],[item,item]);cached(store,'A',[seed(2)],[item])
    pool,_=store.pool('A',[seed(),seed(2)],'hu-HU')
    assert pool[('movie',100)]['score']==pytest.approx(0.5)
    assert len(pool[('movie',100)]['source_keys'])==2


def test_removed_seed_no_longer_influences_pool(store):
    item=rec.normalize_result(result(),'movie');cached(store,'A',[seed()],[item])
    assert store.pool('A',[seed(2)],'hu-HU')==({}, {})


def test_interested_feedback_contributes_only_to_its_library(store):
    store.set_feedback('A',rec.normalize_result(result(100),'movie'),'interested')
    request=Mock(return_value={'results':[]})
    store.load('A',[seed()],set(),'hu-HU',request)
    assert {c.args[0] for c in request.call_args_list}=={'movie/1/recommendations','movie/100/recommendations'}
    request.reset_mock();store.load('B',[seed()],set(),'hu-HU',request)
    request.assert_called_once_with('movie/1/recommendations',{'language':'hu-HU','page':1})


def test_recommendation_posters_survive_library_orphan_cleanup(media,store,tmp_path):
    item=rec.normalize_result(result(),'movie');cached(store,'A',[seed()],[item])
    path=tmp_path/'cache_posters/movie_100.jpg';path.write_bytes(b'image')
    with store.connection() as db:media.cleanup_orphaned_poster_files(db)
    assert path.exists()


def test_context_uses_only_target_seeds_but_excludes_every_library(media,app):
    media.config.update(movies_paths=['C:/Film'],shows_paths=['C:/TV'])
    window=media.DSVideoWindow()
    try:
        window.movies_page.add_item(dict(file_path='C:/Film/a.mkv',id=1,title='Movie',is_movie=True))
        window.shows_page.add_item(dict(file_path='C:/TV/b',id=100,title='TV',is_movie=False))
        context=window.recommendation_context('movies')
        assert {rec.identity(i) for i in context['seeds']}=={('movie',1)}
        assert context['owned']=={('movie',1),('tv',100)}
        assert window.recommendation_context('movies') is context
    finally:window.close();app.processEvents()


def test_manual_override_wins_over_old_identification_and_unconfigured_paths(media,app):
    media.config['movies_paths']=['C:/Film']
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        path=media.normalize_media_path('C:/Film/a.mkv')
        db.execute('INSERT INTO media_cache(file_path,tmdb_id,is_movie,status) VALUES (?,?,?,?)',(path,3,1,'success'))
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,?)',(path,4,'Chosen',1))
        db.execute('INSERT INTO media_cache(file_path,tmdb_id,is_movie,status) VALUES (?,?,?,?)',(media.normalize_media_path('C:/Removed/old.mkv'),5,1,'success'));db.commit()
    window=media.DSVideoWindow()
    try:
        context=window.recommendation_context('movies')
        assert ('movie',4) in context['owned']
        assert ('movie',3) not in context['owned'] and ('movie',5) not in context['owned']
    finally:window.close();app.processEvents()


def test_all_library_buttons_open_their_own_recommendations(media,app,monkeypatch):
    media.config['custom_libraries']=[dict(id='animation',name='Animációk',media_type='movies',paths=[])]
    window=media.DSVideoWindow();opened=Mock();monkeypatch.setattr(window,'show_recommendations',opened)
    try:
        for key in ('movies','shows','animation'):window.library_pages[key].recommendations_button.click()
        assert [c.args[0] for c in opened.call_args_list]==['movies','shows','animation']
    finally:window.close();app.processEvents()


def make_dialog(media,store,context):
    return RecommendationsDialog(None,'A','Test',store,lambda:context,Mock(), 'hu-HU',lambda w:None,media.NasTask,lambda *a:None,media.placeholder_pixmap,'',media.translate_text)


def test_ui_filters_titles_acquired_while_request_was_running(media,app,store):
    context=dict(seeds=[seed()],owned=set());dialog=make_dialog(media,store,context)
    item=rec.normalize_result(result(),'movie');pool={rec.identity(item):dict(item,score=1)}
    try:
        context['owned'].add(('movie',100))
        dialog.loaded(dict(pool=pool,seed_count=1,errors=0),set())
        assert dialog.visible_items()==[]
    finally:dialog.reject();dialog.deleteLater();app.processEvents()


def test_ui_feedback_saved_and_undoable_per_library(media,app,store):
    context=dict(seeds=[seed()],owned=set());dialog=make_dialog(media,store,context)
    item=rec.normalize_result(result(),'movie')
    try:
        dialog.batch=[item];dialog.feedback(item,'interested');assert dialog.visible_items()==[]
        dialog.tabs.setCurrentIndex(1);assert dialog.visible_items()==[item]
        context['owned'].add(('movie',100));dialog.filter_owned();assert dialog.visible_items()==[]
        context['owned'].clear();dialog.feedback(item,'neutral');assert store.feedback('A')=={}
    finally:dialog.reject();dialog.deleteLater();app.processEvents()


def test_ui_close_cancels_background_operations(media,app,store):
    dialog=make_dialog(media,store,dict(seeds=[],owned=set()))
    worker=Mock();poster=Mock();dialog._worker=worker;dialog._poster_worker=poster
    dialog.reject()
    worker.requestInterruption.assert_called_once();poster.requestInterruption.assert_called_once()
    dialog.deleteLater();app.processEvents()


def test_background_loading_finishes_and_dialog_closes_cleanly(media,app,store):
    import time
    request=lambda *args:{'results':[result(i) for i in range(100,120)]}
    dialog=RecommendationsDialog(None,'A','Test',store,lambda:dict(seeds=[seed()],owned=set()),request,
        'hu-HU',media.run_worker,media.NasTask,lambda *a:None,media.placeholder_pixmap,'',media.translate_text)
    try:
        dialog.show()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            app.processEvents()
            if dialog._worker is None and len(dialog.batch)==12:break
            time.sleep(.005)
        assert len(dialog.batch)==12 and dialog._worker is None
        assert dialog.next_button.isEnabled()
        assert len(dialog._visible_keys)==12
    finally:
        dialog.reject()
        deadline=time.monotonic()+2
        while media._background_workers and time.monotonic()<deadline:
            app.processEvents();time.sleep(.005)
        dialog.deleteLater();app.processEvents()
    assert not any(worker.isRunning() for worker in media._background_workers)
