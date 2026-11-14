from unittest.mock import Mock
from types import SimpleNamespace
import os

from synostream_performance import PosterPixmapCache


def test_scaled_posters_are_cached_and_file_changes_invalidate(media, app, tmp_path):
    m = media
    path = tmp_path / 'poster.png'
    image = m.QImage(300, 450, m.QImage.Format.Format_RGB32)
    image.fill(m.QColor('red'))
    image.save(str(path))
    cache = PosterPixmapCache()
    first = cache.load(str(path), 100, 150)
    assert cache.load(str(path), 100, 150) is first
    assert cache.decodes == 1
    image.fill(m.QColor('green'))
    image.save(str(path))
    info = path.stat()
    os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 10000000))
    second = cache.load(str(path), 100, 150)
    assert cache.decodes == 2
    assert second.toImage().pixelColor(0, 0).green() > 0
    assert second is not first


def test_poster_memory_cache_evicts_least_recent_items(media, app, tmp_path):
    cache = PosterPixmapCache(max_bytes=8192)
    for i in range(3):
        image = media.QImage(32, 32, media.QImage.Format.Format_RGB32)
        image.fill(media.QColor(i * 20, 0, 0))
        path = tmp_path / f'{i}.png'
        image.save(str(path))
        cache.load(str(path), 32, 32)
    assert cache.bytes_used <= 8192
    assert len(cache.entries) == 2
    assert all(key[0] != str(tmp_path / '0.png') for key in cache.entries)


def test_corrupted_poster_is_removed_for_later_download(media, app, tmp_path):
    path = tmp_path / 'movie_999.jpg'
    path.write_bytes(b'not a valid picture')
    assert PosterPixmapCache(managed_directory=path.parent).load(str(path), 100, 150) is None
    assert not path.exists()


def test_rebound_card_clears_previous_poster_and_progress(media, app, tmp_path):
    m = media
    image = m.QImage(32, 48, m.QImage.Format.Format_RGB32)
    image.fill(m.QColor('red'))
    path = tmp_path / 'red.png'
    image.save(str(path))
    m.save_playback_progress({'path': 'C:/first.mkv'}, 40, 100, [])
    card = m.MediaCard(dict(file_path='C:/first.mkv', title='First', date='2020', poster=str(path)))
    assert card.progress.value() == 40
    card.bind_item(dict(file_path='C:/second.mkv', title='Second', date='2022'))
    assert card.item['file_path'] == 'C:/second.mkv'
    assert card.title_label.text() == 'Second'
    assert card.metadata_label.text() == '2022'
    from synostream_performance import placeholder_pixmap
    assert card.poster_label.pixmap().toImage() == placeholder_pixmap('C:/second.mkv',
        card.poster_label.width(), card.poster_label.height()).toImage()
    assert card.progress.isHidden()
    card.close()


def test_card_state_snapshot_loads_once_and_follows_playback_writes(media, app):
    m = media
    m.DISPLAY_STATE_CACHE.clear()
    initial = m.DISPLAY_STATE_CACHE.loads
    for _ in range(100):
        assert m.get_display_playback_state('C:/movie.mkv') == {}
    assert m.DISPLAY_STATE_CACHE.loads == initial + 1
    m.save_playback_progress({'path': 'C:/movie.mkv'}, 30, 100, [])
    assert m.get_display_playback_state('C:/movie.mkv')['position'] == 30
    m.set_playback_watched('C:/movie.mkv', 'Movie', '', '', True, True)
    assert m.get_display_playback_state('C:/movie.mkv')['watched']
    m.set_playback_watched('C:/movie.mkv', 'Movie', '', '', True, False)
    assert m.get_display_playback_state('C:/movie.mkv')['position'] == 0
    assert m.DISPLAY_STATE_CACHE.loads == initial + 1


def test_pooled_cards_emit_their_current_item(media, app):
    page = media.MediaPage('Test')
    page.resize(1000, 760)
    page.show()
    app.processEvents()
    items = [dict(file_path=f'C:/demo/{i}.mkv', title=f'Movie {i:04}', date='2020', is_movie=True)
             for i in range(1000)]
    page.replace_items(items)
    page.reflow()
    app.processEvents()
    original = {id(record.widget) for record in page._visible_records}
    page.scroll.verticalScrollBar().setValue(page.scroll.verticalScrollBar().maximum())
    app.processEvents()
    assert original.intersection(id(record.widget) for record in page._visible_records)
    chosen = page._ordered_records[-1]
    received = []
    page.card_clicked.connect(received.append)
    chosen.widget.clicked.emit()
    assert received == [chosen.item]
    assert received[0]['file_path'] == items[-1]['file_path']
    assert page.widget_creations < 40
    page.close()


def test_resize_and_search_reuse_sort_but_updates_invalidate(media, app):
    page = media.MediaPage('Test')
    page.replace_items([dict(file_path='C:/a.mkv', title='A', date='2020'),
                        dict(file_path='C:/b.mkv', title='B', date='2021')])
    page.sort_criterion.setCurrentIndex(page.sort_criterion.findData('year'))
    page.reflow()
    passes = page.sort_passes
    page.resize(900, 700)
    page.reflow()
    page.search_box.setText('B')
    page.reflow()
    assert page.sort_passes == passes
    assert [r.item['title'] for r in page._ordered_records] == ['B']
    page.search_box.clear()
    page.add_item(dict(file_path='C:/b.mkv', title='B', date='2019'))
    page.reflow()
    assert page.sort_passes == passes + 1
    assert [r.item['title'] for r in page._ordered_records] == ['B', 'A']
    page.close()


def test_scan_completion_waits_until_bounded_queue_is_applied(media, app):
    m = media
    window = m.DSVideoWindow()
    scanner = SimpleNamespace(wait=Mock(), metadata_failed_libraries=set(), failed_libraries=set(),
                              unattributed_scan_error=False)
    window.scanner_thread = scanner
    window.scanner_scope = 'movies'
    window.scan_page_keys = ['movies']
    window.scan_seen_paths = {'movies': set()}
    window.movies_page.begin_bulk_update()
    for i in range(80):
        window.on_item_ready(dict(file_path=f'C:/movie/{i}.mkv', title=f'Movie {i}', library_id='movies'), True)
    window.on_scan_completed([])
    window.on_scanner_finished()
    assert window.movies_page.count() == 0
    assert window.scanner_thread is scanner
    window.drain_scan_items()
    assert 0 < window.movies_page.count() <= 32
    assert window.scanner_thread is scanner
    while window.scan_item_queue:
        window.drain_scan_items()
    assert window.scanner_thread is None
    assert window.movies_page.count() == 80
    assert window.movies_page.bulk_update_depth == 0
    scanner.wait.assert_called_once()
    window.close()


def test_placeholder_assignment_stays_stable_and_cache_is_shared(media, app):
    from synostream_performance import placeholder_variant, placeholder_pixmap, _paint_placeholder
    keys = [f'C:/movie/{i}.mkv' for i in range(1000)]
    choices = [placeholder_variant(key) for key in keys]
    assert set(choices) == {0, 1, 2}
    assert all(250 < choices.count(i) < 420 for i in range(3))
    _paint_placeholder.cache_clear()
    for key in keys:
        image = placeholder_pixmap(key, 160, 240)
        assert image.width() == 160 and image.height() == 240
    assert _paint_placeholder.cache_info().currsize == 3
    _paint_placeholder.cache_clear()
    assert [placeholder_variant(key) for key in keys] == choices


def test_real_poster_replaces_placeholder_and_resize_retains_color(media, app, tmp_path):
    from synostream_performance import placeholder_pixmap
    item = dict(file_path='C:/movie.mkv', title='Movie')
    card = media.MediaCard(item)
    card.set_card_size('large')
    assert card.poster_label.pixmap().toImage() == placeholder_pixmap(item['file_path'],
        card.poster_label.width(), card.poster_label.height()).toImage()
    path = tmp_path / 'real.png'
    image = media.QImage(200, 300, media.QImage.Format.Format_RGB32)
    image.fill(media.QColor('red'))
    image.save(str(path))
    card.bind_item(dict(item, poster=str(path)))
    assert card.poster_label.pixmap().toImage().pixelColor(10, 10) == media.QColor('red')
    card.close()

