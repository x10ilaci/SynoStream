from unittest.mock import Mock
import json,sqlite3,threading
import pytest
import synostream_pairings as p
from synostream_downloads import DownloadStationClient,DownloadStationError
from synostream_nas import RemoteNASClient

def test_reproduce_confirmed_download_reported_failed_when_poll_cleanup_fails():
    client=DownloadStationClient.__new__(DownloadStationClient)
    client.lock=threading.RLock();client.should_stop=lambda:False
    client.prepared_lists={'preview':dict(files=[dict(index=0)],submitted=False,destination='video')}
    calls=[]
    def request(api,method,**kw):
        calls.append(method)
        if method=='download':return dict(task_id='ticket')
        if method=='download_status':return dict(finish=True,success=True,data=dict(id='created-task'))
        raise DownloadStationError('poll cleanup failed')
    client._selection_request=request
    assert client.start_prepared('preview',[0])==dict(id='created-task')
    assert 'preview' not in client.prepared_lists
    assert calls==['download','download_status','download_stop']

def test_reproduce_one_corrupt_unicode_pairing_aborts_whole_sync(tmp_path):
    root=tmp_path/'Library';directory=root/p.SUBDIR;directory.mkdir(parents=True)
    for i,title in ((1,'\ud800'),(2,'Good')):
        event=dict(format_version=1,event_id=f'{i:032x}',relative_path=f'{i}.mkv',media_type='movie',tmdb_id=i,title=title,deleted=False,generation=1,created_ns=1)
        (directory/(event['event_id']+'.json')).write_bytes(json.dumps(event,ensure_ascii=True).encode('ascii'))
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE manual_overrides(file_path TEXT PRIMARY KEY,tmdb_id INTEGER,custom_title TEXT,is_movie INTEGER)')
        db.execute('CREATE TABLE media_cache(file_path TEXT PRIMARY KEY,signature TEXT)')
        p.init_tables(db);db.commit()
        result=p.synchronize(db,str(root),p.LocalBackend(root))
        assert result['invalid']==1 and result['imported']==1
        assert db.execute('SELECT tmdb_id FROM manual_overrides').fetchone()==(2,)

def test_deeply_nested_broken_json_does_not_abort_sync(tmp_path):
    root=tmp_path/'Library';directory=root/p.SUBDIR;directory.mkdir(parents=True)
    identifier='a'*32
    (directory/(identifier+'.json')).write_bytes(b'['*7000+b'0'+b']'*7000)
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE manual_overrides(file_path TEXT PRIMARY KEY,tmdb_id INTEGER,custom_title TEXT,is_movie INTEGER)')
        db.execute('CREATE TABLE media_cache(file_path TEXT PRIMARY KEY,signature TEXT)')
        p.init_tables(db);db.commit()
        assert p.synchronize(db,str(root),p.LocalBackend(root))['invalid']==1

def test_nas_reader_returns_deep_json_to_record_validator_and_closes_response():
    payload=b'['*7000+b'0'+b']'*7000
    client=RemoteNASClient.__new__(RemoteNASClient)
    client.lock=threading.RLock();client.should_stop=lambda:False
    client.download_url='https://example.invalid/download';client.download_version=2;client.sid='test'
    response=Mock();response.iter_content.return_value=iter([payload])
    client.session=Mock();client.session.get.return_value=response
    assert client.read_pairing('/Movies/.synostream/parositasok/'+'a'*32+'.json')==payload
    response.close.assert_called_once()

def test_confirmed_failed_download_remains_failure_even_if_cleanup_fails():
    client=DownloadStationClient.__new__(DownloadStationClient);client.lock=threading.RLock();client.should_stop=lambda:False
    client.prepared_lists={'preview':dict(files=[dict(index=0)],submitted=False,destination='video')}
    client._selection_request=Mock(side_effect=[dict(task_id='ticket'),dict(finish=True,success=False),DownloadStationError('cleanup')])
    with pytest.raises(DownloadStationError,match='nem tudta elindítani'):client.start_prepared('preview',[0])
    assert client.prepared_lists['preview']['submitted'] is True

