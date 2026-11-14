from contextlib import closing
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from synostream_logic import movie_search_context

CASES=[
 ('Kubo.and.the.Two.Strings.2016.720p.BluRay.DTS.x264.HuN-HyperX','kubo-720p-hyperx.mkv','Kubo and the Two Strings','2016',100),
 ('Lady.and.the.Tramp.1955.720p.BluRay.DTS.x264.HuN-TRiNiTY','latt.720p-trinity.mkv','Lady and the Tramp','1955',200),
]


@pytest.mark.parametrize('folder,file,title,year,identifier',CASES,ids=['kubo','lady-and-tramp'])
def test_exact_user_release_names(folder,file,title,year,identifier):
    assert movie_search_context(file,folder,True)=={'title':title,'year':year,'from_folder':True}


@pytest.mark.parametrize('folder,file,single',[
 ('Movies.2016','kubo.mkv',True),('Animation.2016','kubo.mkv',True),
 ('Pixar.Collection.2016','kubo.mkv',True),
 ('Lady.and.the.Tramp.1955','Lady.and.the.Tramp.2019.mkv',True),
 ('Kubo.and.the.Two.Strings.2016','kubo.mkv',False),
 ('Films','known.mkv',True),
])
def test_collection_or_explicit_filename_year_not_overridden(folder,file,single):
    assert not movie_search_context(file,folder,single)['from_folder']


def test_movie_word_inside_real_title_is_not_a_collection():
    assert movie_search_context('tlm.mkv','The.Lego.Movie.2014.1080p',True)['title']=='The Lego Movie'


@pytest.mark.parametrize('date',['1965-01-01','1967-01-01','2019-01-01',''])
def test_large_or_unknown_year_mismatch_rejected(media,date):
    assert not media.evaluate_hit({'title':'Lady and the Tramp','original_title':'Lady and the Tramp','release_date':date},'lady and the tramp','1955',True)[0]


def test_short_abbreviation_does_not_match_unrelated_long_title(media):
    assert not media.evaluate_hit({'title':'Latt Saheb','release_date':'1967-01-01'},'latt',None,True)[0]
    assert media.evaluate_hit({'title':'Up','release_date':'2009-01-01'},'up',None,True)[0]


def test_adjacent_release_year_allowed(media):
    assert media.evaluate_hit({'title':'Film','release_date':'2015-12-31'},'film','2016',True)[0]


def test_unfiltered_search_cannot_bypass_year_check(media,monkeypatch):
    search=Mock(return_value=[{'id':1,'title':'Kubo and the Two Strings','release_date':'1965-01-01'}])
    monkeypatch.setattr(media,'search_tmdb',search)
    assert media.fetch_tmdb_data('Kubo and the Two Strings','2016',True)['status']=='no_result'
    assert any(call.args[1] is None for call in search.call_args_list)


def info(identifier,title,year):
    return dict(status='success',id=identifier,title=title,overview='Metadata',poster_url='',date=year+'-01-01',complete=True)


@pytest.mark.parametrize('folder,file,title,year,identifier',CASES,ids=['kubo','lady-and-tramp'])
@pytest.mark.parametrize('remote',[False,True],ids=['local','nas'])
def test_existing_wrong_auto_match_is_rechecked(media,tmp_path,monkeypatch,folder,file,title,year,identifier,remote):
    if remote:
        path='syno:///Movies/'+folder+'/'+file
        entry=SimpleNamespace(path=path,name=file,stat=lambda:SimpleNamespace(st_mtime=1))
        scanner=media.LibraryScannerThread([],[])
        scanner.remote_client=Mock()
        scanner.remote_client.list_folder.return_value=[dict(name=file,isdir=False)]
    else:
        parent=tmp_path/folder;parent.mkdir();path=str(parent/file);Path(path).touch()
        entry=SimpleNamespace(path=path,name=file,stat=Path(path).stat)
        scanner=media.LibraryScannerThread([],[])
    scanner.get_poster=Mock(return_value=None)
    lookup=Mock(return_value=info(identifier,title,year));monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        scanner.save_cache(db,media.normalize_media_path(path),1,999,'Wrong 1965','','','1965-01-01',entry.stat().st_mtime,'success','language:'+media.current_tmdb_language())
        result=scanner.process_media_item(entry,True,db)
        assert result['id']==identifier and result['title']==title
        lookup.assert_called_once_with(title,year,True)
        assert db.execute('SELECT signature FROM media_cache WHERE file_path=?',(media.normalize_media_path(path),)).fetchone()[0].startswith('language:movie_folder_v3:')
        assert scanner.process_media_item(entry,True,db)['id']==identifier
        assert lookup.call_count==1


def test_remote_incremental_snapshot_does_not_hide_old_wrong_match(media):
    folder,file,title,year,identifier=CASES[0]
    directory='syno:///Movies/'+folder
    path=directory+'/'+file
    scanner=media.LibraryScannerThread([],[])
    scanner.directory_scan_token='audit'
    scanner._record_directory_snapshot(directory,1,False,1)
    row=dict(status='success',signature='language:'+media.current_tmdb_language(),file_mtime=1,release_date='2016-01-01')
    assert not scanner._cached_row_is_current(path,file,True,row)
    context=movie_search_context(file,folder,True)
    row['signature']=media.movie_lookup_signatures(context)[0]
    assert scanner._cached_row_is_current(path,file,True,row)


def test_single_movie_plus_sample_uses_folder(media,tmp_path,monkeypatch):
    folder,file,title,year,identifier=CASES[0]
    parent=tmp_path/folder;parent.mkdir()
    path=parent/file;path.touch();(parent/'sample.mkv').touch()
    scanner=media.LibraryScannerThread([],[])
    assert scanner.movie_name_context(str(path),file)['from_folder']


def test_multiple_movies_do_not_use_shared_folder_title(media,tmp_path):
    folder,file,title,year,identifier=CASES[0]
    parent=tmp_path/folder;parent.mkdir()
    path=parent/file;path.touch();(parent/'other.mkv').touch()
    scanner=media.LibraryScannerThread([],[])
    assert not scanner.movie_name_context(str(path),file)['from_folder']


def test_nfo_remains_stronger_than_folder(media,tmp_path,monkeypatch):
    folder,file,title,year,identifier=CASES[0]
    parent=tmp_path/folder;parent.mkdir()
    path=parent/file;path.touch();path.with_suffix('.nfo').write_text('<movie><uniqueid type="tmdb">77</uniqueid></movie>')
    scanner=media.LibraryScannerThread([],[]);scanner.get_poster=Mock(return_value=None)
    lookup=Mock(return_value=info(77,'From NFO','2016'));monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        assert scanner.process_media_item(SimpleNamespace(path=str(path),name=file,stat=path.stat),True,db)['id']==77
    lookup.assert_called_once_with(None,is_movie=True,tmdb_id=77)


@pytest.mark.parametrize('folder,file,title,year,identifier',CASES,ids=['kubo','lady-and-tramp'])
def test_full_nas_scan_replaces_wrong_incremental_card(media,monkeypatch,folder,file,title,year,identifier):
    import json
    root='/Movies';directory=root+'/'+folder;path='syno://'+directory+'/'+file
    wrong={'id':999,'title':'Kubo' if identifier==100 else 'Latt Saheb','original_title':'Kubo' if identifier==100 else 'Latt Saheb','release_date':'1965-01-01' if identifier==100 else '1967-01-01','overview':'Wrong'}
    correct={'id':identifier,'title':'Kubo és a varázshúrok' if identifier==100 else 'Susi és Tekergő','original_title':title,'release_date':year+'-01-01','overview':'Correct description'}
    search=Mock(return_value=[wrong,correct]);monkeypatch.setattr(media,'search_tmdb',search)
    monkeypatch.setattr(media,'tmdb_request',Mock(return_value=correct))
    client=Mock()
    def listing(directory_path):
        if directory_path==root:return [dict(name=folder,path=directory,isdir=True,additional={'time':{'mtime':1}})]
        if directory_path==directory:return [dict(name=file,path=directory+'/'+file,isdir=False,additional={'time':{'mtime':1}})]
        raise AssertionError(directory_path)
    client.list_folder.side_effect=listing
    monkeypatch.setattr(media,'RemoteNASClient',Mock(return_value=client))
    scanner=media.LibraryScannerThread(['syno://'+root],[],library_key='movies');scanner.get_poster=Mock(return_value=None)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        scanner.save_cache(db,media.normalize_media_path(path),1,999,wrong['title'],'Wrong','',wrong['release_date'],1,'success','language:'+media.current_tmdb_language())
        db.execute('INSERT INTO scan_directory_cache(library_id,is_movie,file_path,mtime,has_subdirs,video_count,scan_token) VALUES (?,?,?,?,?,?,?)',('movies',1,'syno://'+directory,1,0,1,'old'))
        db.execute('INSERT INTO library_card_cache(library_id,file_path,payload) VALUES (?,?,?)',('movies',media.normalize_media_path(path),json.dumps(dict(file_path=path,title=wrong['title'],id=999,is_movie=True))))
        db.commit()
    emitted=[];scanner.item_ready.connect(lambda item,is_movie:emitted.append(item))
    scanner.run()
    assert not scanner.failed_libraries,scanner.errors
    assert len(emitted)==1 and emitted[0]['id']==identifier
    assert emitted[0]['title']==correct['title']
    search.assert_any_call(title,year,True,language=media.current_tmdb_language())
    search.assert_any_call(title,None,True,language=media.current_tmdb_language())
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        payload=json.loads(db.execute("SELECT payload FROM library_card_cache WHERE library_id='movies'").fetchone()[0])
        assert payload['id']==identifier


def test_wrong_cached_year_is_rechecked_even_with_full_filename(media,tmp_path,monkeypatch):
    path=tmp_path/'Good.Movie.2016.mkv';path.touch()
    scanner=media.LibraryScannerThread([],[]);scanner.get_poster=Mock(return_value=None)
    lookup=Mock(return_value=info(5,'Good Movie','2016'));monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        scanner.save_cache(db,media.normalize_media_path(str(path)),1,999,'Good Movie','Wrong','','1965-01-01',path.stat().st_mtime,'success','language:'+media.current_tmdb_language())
        result=scanner.process_media_item(SimpleNamespace(path=str(path),name=path.name,stat=path.stat),True,db)
        assert result['id']==5
    lookup.assert_called_once_with('Good Movie','2016',True)



