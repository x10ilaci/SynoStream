import json
from pathlib import Path
import sqlite3
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from synostream_nfo import parse_nfo, select_nfo_names, MAX_NFO_BYTES


@pytest.mark.parametrize('encoding',['utf-8-sig','utf-16','cp1250','cp437'])
def test_text_imdb_and_title(encoding):
    text='Title: Test Film\nYear: 1999\nhttps://www.imdb.com/title/tt0133093/'
    assert parse_nfo(text.encode(encoding))=={'imdb_id':'tt0133093','titles':['Test Film'],'year':'1999'}


def test_kodi_xml_and_explicit_ids_beat_plot_links():
    data=b'<movie><title>The Matrix</title><originaltitle>Matrix</originaltitle><year>1999</year><uniqueid type="imdb">tt0133093</uniqueid><uniqueid type="tmdb">603</uniqueid><plot>Like tt0234215</plot></movie>'
    assert parse_nfo(data)==dict(imdb_id='tt0133093',tmdb_id=603,titles=['The Matrix','Matrix'],year='1999')


@pytest.mark.parametrize('payload',[b'',b'x'*(MAX_NFO_BYTES+1),b'<!DOCTYPE movie [<!ENTITY secret SYSTEM "file:///secret">]><movie><title>&secret;</title></movie>',b'<episodedetails><id>tt0133093</id></episodedetails>',b'tt0133093 tt0234215',b'<tvshow><title>Wrong type</title><id>tt0133093</id></tvshow>'], ids=['empty','oversize','entity','episode','ambiguous','wrong-type'])
def test_unsafe_oversized_or_ambiguous_input_ignored(payload):
    assert parse_nfo(payload)=={}


def test_movie_tv_type_and_tmdb_url():
    assert parse_nfo(b'https://www.themoviedb.org/tv/1399',False)=={'tmdb_id':1399}
    assert parse_nfo(b'https://www.themoviedb.org/tv/1399',True)=={}
    assert parse_nfo(b'<tvshow><title>Show</title><id>tt0944947</id></tvshow>',False)['imdb_id']=='tt0944947'


@pytest.mark.parametrize('names,name,movie,count,expected',[
    (['opaque.nfo','movie.nfo'],'opaque.mkv',True,2,['opaque.nfo']),
    (['release.nfo'],'opaque.mkv',True,1,['release.nfo']),
    (['movie.nfo'],'opaque.mkv',True,2,[]),
    (['release.nfo'],'opaque.mkv',True,2,[]),
    (['a.nfo','b.nfo'],'opaque.mkv',True,1,[]),
    (['tvshow.nfo'],'Folder',False,0,['tvshow.nfo']),
    (['A.NFO','a.nfo'],'a.mkv',True,1,[]),
])
def test_nfo_association(names,name,movie,count,expected):
    assert select_nfo_names(names,name,movie,count)==expected


def scan_item(media,folder,is_movie=True):
    path=folder/'001.mkv' if is_movie else folder
    if is_movie:path.touch(exist_ok=True)
    entry=SimpleNamespace(path=str(path),name=path.name,stat=path.stat)
    scanner=media.LibraryScannerThread([],[])
    scanner.get_poster=Mock(return_value=None)
    return scanner,entry


def success(identifier=603,title='The Matrix'):
    return dict(status='success',id=identifier,title=title,overview='Description',poster_url='',date='1999-03-31',complete=True)


def test_unknown_local_file_is_found_by_imdb_and_cached(media,tmp_path,monkeypatch):
    scanner,entry=scan_item(media,tmp_path)
    (tmp_path/'release.nfo').write_text('https://www.imdb.com/title/tt0133093/')
    api=Mock(return_value={'movie_results':[{'id':603}]});monkeypatch.setattr(media,'tmdb_request',api)
    lookup=Mock(return_value=success());monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        item=scanner.process_media_item(entry,True,db)
        assert item['title']=='The Matrix'
        api.assert_called_once_with('find/tt0133093',{'external_source':'imdb_id','language':media.current_tmdb_language()})
        lookup.assert_called_once_with(None,is_movie=True,tmdb_id=603)
        assert scanner.process_media_item(entry,True,db)['id']==603
        assert lookup.call_count==1


def test_existing_no_result_does_not_block_new_nfo(media,tmp_path,monkeypatch):
    scanner,entry=scan_item(media,tmp_path)
    lookup=Mock(return_value={'status':'no_result'});monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        scanner.process_media_item(entry,True,db)
        (tmp_path/'001.nfo').write_text('<movie><title>The Matrix</title><year>1999</year></movie>')
        fresh,_=scan_item(media,tmp_path)
        lookup.reset_mock();lookup.return_value=success()
        item=fresh.process_media_item(entry,True,db)
        assert item['id']==603
        lookup.assert_called_once_with('The Matrix','1999',True)


def test_nfo_edit_invalidates_previous_match(media,tmp_path,monkeypatch):
    scanner,entry=scan_item(media,tmp_path)
    nfo=tmp_path/'001.nfo';nfo.write_text('<movie><uniqueid type="tmdb">603</uniqueid></movie>')
    lookup=Mock(return_value=success());monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        assert scanner.process_media_item(entry,True,db)['id']==603
        nfo.write_text('<movie><uniqueid type="tmdb">604</uniqueid></movie>')
        fresh,_=scan_item(media,tmp_path);lookup.return_value=success(604,'Changed')
        assert fresh.process_media_item(entry,True,db)['id']==604
        assert lookup.call_args.kwargs['tmdb_id']==604


def test_manual_override_keeps_priority(media,tmp_path,monkeypatch):
    scanner,entry=scan_item(media,tmp_path)
    (tmp_path/'001.nfo').write_text('tt0133093')
    scanner.read_nfo_hint=Mock(side_effect=AssertionError('manual pairing must skip NFO'))
    lookup=Mock(return_value=success(99,'Manual'));monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO manual_overrides(file_path,tmdb_id,custom_title,is_movie) VALUES (?,?,?,1)',(media.normalize_media_path(entry.path),99,'Manual'));db.commit()
        assert scanner.process_media_item(entry,True,db)['id']==99


def test_nas_sidecar_is_bounded_closed_and_resolves_tv(media,monkeypatch):
    scanner=media.LibraryScannerThread([],[])
    response=Mock();response.iter_content.return_value=[b'<tvshow><title>Show</title><uniqueid type="tmdb">1399</uniqueid></tvshow>']
    scanner.remote_client=Mock();scanner.remote_client.list_folder.return_value=[dict(name='tvshow.nfo',isdir=False)]
    scanner.remote_client.open_stream.return_value=response
    entry=SimpleNamespace(path='syno:///tv/opaque',name='opaque',stat=lambda:SimpleNamespace(st_mtime=0))
    scanner.get_poster=Mock(return_value=None)
    lookup=Mock(return_value=success(1399,'Show'));monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        assert scanner.process_media_item(entry,False,db)['id']==1399
    scanner.remote_client.open_stream.assert_called_once_with('/tv/opaque/tvshow.nfo')
    response.close.assert_called_once();lookup.assert_called_once_with(None,is_movie=False,tmdb_id=1399)


def test_nas_oversize_and_download_error_fall_back(media):
    scanner=media.LibraryScannerThread([],[])
    scanner.remote_client=Mock();scanner.remote_client.list_folder.return_value=[dict(name='movie.nfo',isdir=False),dict(name='001.mkv',isdir=False)]
    response=Mock();response.iter_content.return_value=[b'x'*(MAX_NFO_BYTES+1)]
    scanner.remote_client.open_stream.return_value=response
    assert scanner.read_nfo_hint('syno:///movies/001.mkv','001.mkv',True)=={}
    response.close.assert_called_once()


def test_imdb_tv_lookup_does_not_use_episode_or_movie_result(media,monkeypatch):
    monkeypatch.setattr(media,'tmdb_request',Mock(return_value={'movie_results':[{'id':603}],'tv_episode_results':[{'id':1}]}))
    lookup=Mock();monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    assert media.fetch_tmdb_by_imdb('tt0133093',False)=={'status':'no_result'}
    lookup.assert_not_called()


def test_remote_nfo_cached_by_file_stamp_and_refreshed_on_edit(media,monkeypatch):
    response=Mock();response.iter_content.side_effect=lambda *_:[b'tt0133093']
    client=Mock();client.open_stream.return_value=response
    entry=dict(name='001.nfo',isdir=False,additional={'time':{'mtime':12345},'size':9})
    client.list_folder.return_value=[entry,dict(name='001.mkv',isdir=False)]
    for _ in range(2):
        scanner=media.LibraryScannerThread([],[]);scanner.remote_client=client
        assert scanner.read_nfo_hint('syno:///movies/001.mkv','001.mkv',True)['imdb_id']=='tt0133093'
    assert client.open_stream.call_count==1
    entry['additional']['time']['mtime']=12346
    response.iter_content.side_effect=lambda *_:[b'tt0234215']
    scanner=media.LibraryScannerThread([],[]);scanner.remote_client=client
    assert scanner.read_nfo_hint('syno:///movies/001.mkv','001.mkv',True)['imdb_id']=='tt0234215'
    assert client.open_stream.call_count==2


def test_imdb_api_error_is_retryable_not_cached_as_no_result(media,tmp_path,monkeypatch):
    scanner,entry=scan_item(media,tmp_path)
    (tmp_path/'001.nfo').write_text('tt0133093')
    monkeypatch.setattr(media,'tmdb_request',Mock(side_effect=media.TmdbError('offline')))
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        item=scanner.process_media_item(entry,True,db)
        assert item['id']<=0
        assert db.execute('SELECT COUNT(*) FROM media_cache').fetchone()[0]==0


def test_filename_matching_survives_unreadable_nfo(media,tmp_path,monkeypatch):
    scanner,entry=scan_item(media,tmp_path)
    (tmp_path/'001.nfo').write_bytes(b'<broken xml')
    lookup=Mock(return_value=success());monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        assert scanner.process_media_item(entry,True,db)['id']==603
    lookup.assert_called_once_with('001',None,True)


def test_nas_read_error_preserves_previous_successful_nfo_match(media,monkeypatch):
    scanner=media.LibraryScannerThread([],[]);scanner.remote_client=Mock()
    scanner.remote_client.list_folder.side_effect=OSError('NAS temporarily unavailable')
    scanner.get_poster=Mock(return_value=None)
    path='syno:///movies/001.mkv'
    entry=SimpleNamespace(path=path,name='001.mkv',stat=lambda:SimpleNamespace(st_mtime=1))
    lookup=Mock(side_effect=AssertionError('do not overwrite a known match during IO failure'))
    monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        scanner.save_cache(db,media.normalize_media_path(path),1,603,'Known','Overview','','1999',1,'success','nfo:old:hu-HU')
        assert scanner.process_media_item(entry,True,db)['id']==603
        assert db.execute('SELECT status FROM media_cache').fetchone()[0]=='success'


def test_explicit_tmdb_id_beats_plot_url():
    assert parse_nfo(b'<movie><tmdbid>603</tmdbid><plot>See themoviedb.org/movie/604</plot></movie>')=={'tmdb_id':603}


def test_complete_local_library_scan_uses_nfo(media,tmp_path,monkeypatch):
    folder=tmp_path/'Library';folder.mkdir()
    (folder/'001.mkv').touch();(folder/'release.nfo').write_text('Title: The Matrix\nYear: 1999')
    lookup=Mock(return_value=success());monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    scanner=media.LibraryScannerThread([str(folder)],[],library_key='movies')
    scanner.get_poster=Mock(return_value=None)
    items=[];scanner.item_ready.connect(lambda item,movie:items.append(item))
    scanner.run()
    assert not scanner.failed_libraries
    assert len(items)==1 and items[0]['id']==603
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        payload=json.loads(db.execute("SELECT payload FROM library_card_cache WHERE library_id='movies'").fetchone()[0])
        assert payload['id']==603


def test_complete_remote_scan_reuses_listing_for_nfo(media,monkeypatch):
    client=Mock()
    client.list_folder.return_value=[dict(name='001.mkv',path='/Movies/001.mkv',isdir=False,additional={'time':{'mtime':1}}),dict(name='release.nfo',path='/Movies/release.nfo',isdir=False)]
    response=Mock();response.iter_content.return_value=[b'Title: The Matrix\nYear: 1999']
    client.open_stream.return_value=response
    monkeypatch.setattr(media,'RemoteNASClient',Mock(return_value=client))
    lookup=Mock(return_value=success());monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    scanner=media.LibraryScannerThread(['syno:///Movies'],[],library_key='movies',force_remote_refresh=True)
    scanner.get_poster=Mock(return_value=None)
    items=[];scanner.item_ready.connect(lambda item,movie:items.append(item))
    scanner.run()
    assert not scanner.failed_libraries,scanner.errors
    assert len(items)==1 and items[0]['id']==603
    client.list_folder.assert_called_once_with('/Movies')
    client.open_stream.assert_called_once_with('/Movies/release.nfo')
    response.close.assert_called_once()
