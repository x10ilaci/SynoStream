import json
import sqlite3
import threading
import time
from unittest.mock import Mock

import pytest
import synostream_recommendations as rec
from synostream_recommendation_ui import PosterBatch
from test_recommendations192 import seed, result, cached, make_dialog


@pytest.fixture
def store(media): return rec.RecommendationStore(media.DB_FILE)


def run_thread(operation):
    outcome = {}
    def run():
        try: outcome['value'] = operation()
        except BaseException as error: outcome['error'] = error
    thread = threading.Thread(target=run); thread.start()
    return thread, outcome


def test_seed_requests_run_concurrently_with_the_existing_budget(store):
    gate = threading.Event(); all_started = threading.Event(); lock = threading.Lock(); started = []
    def request(path, params):
        with lock:
            started.append(path)
            if len(started) == 4: all_started.set()
        assert gate.wait(5)
        return {'results':[result(100+int(path.split('/')[1]))]}
    thread, outcome = run_thread(lambda:store.load('A',[seed(i) for i in range(1,11)],set(),'hu-HU',request))
    try: assert all_started.wait(3), 'Four requests must start before any one is released'
    finally: gate.set(); thread.join(5)
    assert not thread.is_alive() and 'error' not in outcome
    assert outcome['value']['requests'] == 4 and len(started) == 4


def test_translation_requests_use_bounded_parallelism_and_keep_all_candidates(store):
    rows=[rec.normalize_result(result(i),'movie') for i in range(100,140)]
    cached(store,'A',[seed()],rows)
    gate=threading.Event(); first_wave=threading.Event(); lock=threading.Lock(); counts={'active':0,'peak':0,'calls':0}
    def request(path,params):
        with lock:
            counts['active']+=1; counts['calls']+=1; counts['peak']=max(counts['peak'],counts['active'])
            if counts['active']==4:first_wave.set()
        try:
            assert gate.wait(5)
            return {'translations':[{'iso_639_1':'hu','iso_3166_1':'HU','data':{'overview':'Magyar leírás'}}]}
        finally:
            with lock:counts['active']-=1
    thread,outcome=run_thread(lambda:store.load('A',[seed()],set(),'hu-HU',request,prefer_hungarian=True))
    try:assert first_wave.wait(3)
    finally:gate.set();thread.join(5)
    assert 'error' not in outcome and not thread.is_alive()
    assert counts['peak']==4 and counts['calls']==8
    assert len(outcome['value']['pool'])==40


def test_preview_arrives_before_slow_seed_or_translation_checks_complete(store):
    slow=threading.Event(); preview=threading.Event(); snapshots=[]
    def request(path,params):
        if path=='movie/2/recommendations':assert slow.wait(5)
        if path.endswith('/translations'):return {'translations':[]}
        return {'results':[result(i) for i in range(100,125)]}
    def progress(value):snapshots.append(value);preview.set()
    thread,outcome=run_thread(lambda:store.load('A',[seed(1),seed(2)],set(),'hu-HU',request,
        prefer_hungarian=True,on_progress=progress))
    try:
        assert preview.wait(3) and thread.is_alive()
        assert snapshots[0]['pool'] and snapshots[0]['seed_count']==1
    finally:slow.set();thread.join(5)
    assert 'error' not in outcome and len(snapshots)==1


def test_cancelled_parallel_work_does_not_write_cache(store):
    gate=threading.Event(); started=threading.Event(); cancelled=threading.Event()
    def request(*args):started.set();assert gate.wait(5);return {'results':[result()]}
    thread,outcome=run_thread(lambda:store.load('A',[seed(i) for i in range(1,5)],set(),'hu-HU',request,cancelled.is_set))
    try:assert started.wait(3);cancelled.set()
    finally:gate.set();thread.join(5)
    assert isinstance(outcome.get('error'),InterruptedError)
    assert store.pool('A',[seed(i) for i in range(1,5)],'hu-HU')==({}, {})


def test_localization_lookup_reads_only_requested_identities_in_chunks(store):
    with store.connection() as conn, conn:
        conn.executemany('INSERT INTO recommendation_localization VALUES (?,?,?,?,?,?)',
            [('movie',i,'hu',1,json.dumps({'overview':'Magyar'}),time.time()) for i in range(1,1002)])
    assert store.localization([])=={}
    assert set(store.localization([('movie',1),('tv',1)]))=={('movie',1)}
    keys=[('movie',i) for i in range(1,802)]
    assert set(store.localization(keys))==set(keys)


def test_one_slow_poster_does_not_block_other_eleven(app,tmp_path):
    slow=threading.Event(); received=[]
    def fetch(url,media_id,movie,stop):
        if media_id==100:
            while not slow.wait(.01):
                if stop():return None
        return str(tmp_path/(str(media_id)+'.jpg'))
    worker=PosterBatch(1,[dict(rec.normalize_result(result(i),'movie')) for i in range(100,112)],fetch)
    worker.ready.connect(lambda generation,key,path:received.append(key[1]));worker.start()
    try:
        deadline=time.monotonic()+3
        while len(received)<11 and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
        assert set(received)==set(range(101,112)) and worker.isRunning()
    finally:slow.set();worker.requestInterruption();assert worker.wait(3000);app.processEvents()


def test_final_result_keeps_preview_and_does_not_double_count_seen(media,app,store):
    context=dict(seeds=[seed()],owned=set());dialog=make_dialog(media,store,context)
    rows=[dict(rec.normalize_result(result(i),'movie'),score=1) for i in range(100,140)]
    pool={rec.identity(row):row for row in rows}
    try:
        dialog.preview_loaded(dict(pool=pool,seed_count=1,errors=0));first=list(dialog.batch)
        context['owned'].add(rec.identity(first[0]));store.set_feedback('A',first[1],'dismissed')
        dialog.loaded(dict(pool=pool,seed_count=1,errors=0),set())
        keys={rec.identity(i) for i in dialog.batch}
        assert len(keys)==12 and not keys & {rec.identity(first[0]),rec.identity(first[1])}
        assert {rec.identity(i) for i in first[2:]} <= keys
        with store.connection() as conn:
            assert all(count==1 for count, in conn.execute('SELECT shown_count FROM recommendation_seen'))
    finally:dialog.reject();dialog.deleteLater();app.processEvents()


def test_cached_next_batch_changes_before_background_worker_finishes(media,app,store):
    context=dict(seeds=[seed()],owned=set());dialog=make_dialog(media,store,context)
    rows=[dict(rec.normalize_result(result(i),'movie'),score=1) for i in range(100,140)]
    try:
        dialog.pool={rec.identity(i):i for i in rows};dialog.batch=rows[:12];first={rec.identity(i) for i in dialog.batch}
        dialog.next_batch()
        assert not first & {rec.identity(i) for i in dialog.batch}
        assert dialog._worker is not None
    finally:dialog.reject();dialog.deleteLater();app.processEvents()


def test_same_cards_reflow_or_localize_without_interrupting_poster_work(media,app,store):
    dialog=make_dialog(media,store,dict(seeds=[seed()],owned=set()))
    try:
        dialog.batch=[rec.normalize_result(result(i),'movie') for i in (100,101)];dialog.render()
        worker=Mock();dialog._poster_worker=worker;generation=dialog._generation
        dialog.batch.reverse();dialog.batch[0]['has_hu_metadata']=True;dialog.render()
        assert dialog._generation==generation
        worker.requestInterruption.assert_not_called()
    finally:dialog.reject();dialog.deleteLater();app.processEvents()


def test_cards_are_visible_while_language_requests_are_still_pending(media,app,store):
    from synostream_recommendation_ui import RecommendationsDialog
    gate=threading.Event()
    def request(path,params):
        if path.endswith('/translations'):
            assert gate.wait(5)
            return {'translations':[]}
        return {'results':[result(i) for i in range(100,125)]}
    dialog=RecommendationsDialog(None,'A','Test',store,lambda:dict(seeds=[seed()],owned=set()),request,
        'hu-HU',media.run_worker,media.NasTask,lambda *a:None,media.placeholder_pixmap,'',media.translate_text,
        prefer_hungarian=True)
    try:
        dialog.show();deadline=time.monotonic()+3
        while not dialog.batch and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
        assert len(dialog._visible_keys)==12 and dialog._worker is not None and dialog._worker.isRunning()
    finally:
        gate.set();dialog.reject();deadline=time.monotonic()+5
        while media._background_workers and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
        dialog.deleteLater();app.processEvents()
    assert not any(worker.isRunning() for worker in media._background_workers)
