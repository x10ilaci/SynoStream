import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock
import pytest


@pytest.mark.parametrize('movie',[True,False])
def test_scanner_persists_type_before_gui_receives_card(media,movie):
    scanner=media.LibraryScannerThread([],[]);scanner.current_scan_library_id='movies' if movie else 'shows'
    item=dict(file_path='syno:///Media/Entry',title='Entry',id=12)
    scanner.emit_item(item,movie)
    stored=scanner.emitted_card_items[scanner.current_scan_library_id][0]
    assert stored['is_movie'] is movie


@pytest.mark.parametrize('movie',[True,False])
def test_old_snapshot_restores_type_from_media_row_even_in_mixed_library(media,movie):
    path='syno:///Movies/Entry';media.config['movies_paths']=['syno:///Movies']
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO media_cache(file_path,is_movie,title) VALUES (?,?,?)',(path,int(movie),'Entry'))
        db.execute('INSERT INTO library_card_cache VALUES (?,?,?)',('movies',path,json.dumps(dict(file_path=path,title='Entry',id=12))))
    owner=SimpleNamespace(_library_cache_paths=lambda library:['syno:///Movies'],_legacy_cached_page_items=lambda *a:[])
    restored=media.DSVideoWindow._cached_page_items(owner,'movies')
    assert len(restored)==1 and restored[0]['is_movie'] is movie


def test_old_custom_show_snapshot_without_media_row_uses_library_type(media):
    root='syno:///Media/Shows';path=root+'/Entry'
    media.config['custom_libraries']=[dict(id='custom-series',name='My collection',media_type='shows',paths=[root])]
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO library_card_cache VALUES (?,?,?)',('custom-series',path,json.dumps(dict(title='Entry',id=12))))
    owner=SimpleNamespace(_library_cache_paths=lambda library:[root],_legacy_cached_page_items=lambda *a:[])
    restored=media.DSVideoWindow._cached_page_items(owner,'custom-series')
    assert restored[0]['is_movie'] is False


def test_type_resolver_preserves_explicit_mixed_card_and_episode_roots(media,monkeypatch):
    monkeypatch.setattr(media.os.path,'isdir',Mock(side_effect=AssertionError('No local stat for NAS URLs')))
    assert media.media_item_is_movie(dict(file_path='syno:///Media/Entry',is_movie=False,library_id='movies')) is False
    assert media.media_item_is_movie(dict(file_path='syno:///Media/Entry',episode_roots=['syno:///Media/Entry'])) is False
    assert media.media_item_is_movie(dict(file_path='syno:///Media/Entry',is_movie=True,episode_roots=['syno:///Media/Entry'])) is True
    assert media.media_item_is_movie(dict(file_path='syno:///Media/Entry',library_id='shows')) is False


def test_legacy_card_without_library_id_uses_longest_configured_nas_root(media,monkeypatch):
    media.config['movies_paths']=['syno:///Media']
    media.config['shows_paths']=['syno:///Media/Shows']
    monkeypatch.setattr(media.os.path,'isdir',Mock(side_effect=AssertionError('No local NAS stat')))
    assert media.media_item_is_movie(dict(file_path='syno:///Media/Shows/Entry')) is False
    assert media.media_item_is_movie(dict(file_path='syno:///Media/Feature.mkv')) is True


def test_restored_nas_show_detail_requests_tv_metadata_and_episode_picker(media,app,monkeypatch):
    media.config['shows_paths']=['syno:///Shows']
    path='syno:///Shows/Entry'
    with sqlite3.connect(media.DB_FILE) as db:
        db.execute('INSERT INTO library_card_cache VALUES (?,?,?)',('shows',path,json.dumps(dict(file_path=path,title='Entry',id=12,overview=''))))
    monkeypatch.setattr(media,'run_worker',Mock())
    monkeypatch.setattr(media,'read_tmdb_metadata_cache',lambda key:(None,False))
    window=media.DSVideoWindow();item=window._cached_page_items('shows')[0]
    seen=[]
    def inspect(dialog):
        workers=[call.args[0] for call in media.run_worker.call_args_list]
        requests=[worker for worker in workers if isinstance(worker,media.TmdbMediaMetadataWorker)]
        assert len(requests)==1 and requests[0].is_movie is False
        assert any(label.text().startswith('Epizódok') for label in dialog.findChildren(media.QLabel))
        seen.append(True);dialog.reject();return media.QDialog.DialogCode.Rejected
    monkeypatch.setattr(media.QDialog,'exec',inspect)
    try:
        window.open_media_detail(item)
        assert seen==[True]
    finally:window.close();app.processEvents()


def test_manual_lookup_for_untyped_nas_series_keeps_tv_type(media,app,monkeypatch):
    media.config['shows_paths']=['syno:///Shows']
    monkeypatch.setattr(media,'run_worker',Mock())
    monkeypatch.setattr(media.QDialog,'exec',lambda dialog:media.QDialog.DialogCode.Accepted)
    window=media.DSVideoWindow()
    try:
        window.start_video_info_lookup(dict(file_path='syno:///Shows/Entry',title='Entry',library_id='shows'))
        assert window.pending_override['is_movie'] is False
    finally:window.close();app.processEvents()
