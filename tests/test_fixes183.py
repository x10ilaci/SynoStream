from types import SimpleNamespace
from unittest.mock import Mock

def test_overlapping_episode_roots_do_not_duplicate_same_video(media,tmp_path):
    parent=tmp_path/'Show';child=parent/'Season1';child.mkdir(parents=True)
    file=child/'S01E01.mkv';file.touch()
    worker=media.EpisodeScanWorker([str(parent),str(child)]);results=[]
    worker.episodes_found.connect(lambda episodes,error:results.extend(episodes));worker.run()
    assert len(results)==1

def test_recovered_queue_processing_is_linear_in_card_count(media):
    visits=[0]
    class Counted(dict):
        def get(self,*args):visits[0]+=1;return super().get(*args)
    scanner=media.LibraryScannerThread([],[]);scanner.current_scan_library_id='movies'
    count=80
    scanner.emitted_card_items={'movies':[]}
    for i in range(count):
        path=f'C:/audit/file{i}.mkv';key=(media.normalize_media_path(path),True)
        scanner._deferred_metadata[key]=(SimpleNamespace(path=path),True,'movies',None)
        scanner.emitted_card_items['movies'].append(Counted(file_path=path,title='Old'))
    def process(entry,movie,conn):
        scanner._deferred_metadata.pop((media.normalize_media_path(entry.path),movie))
        return dict(file_path=entry.path,title='Recovered',id=222)
    scanner.process_media_item=Mock(side_effect=process)
    scanner.retry_deferred_metadata(None)
    assert len(scanner.emitted_card_items['movies'])==count
    assert visits[0]<count*12

def test_overlapping_nas_episode_roots_are_deduplicated(media,monkeypatch):
    client=Mock()
    client.list_folder.side_effect=lambda path: ([dict(name='Season1',path='/Show/Season1',isdir=True)] if path=='/Show' else [dict(name='S01E01.mkv',path='/Show/Season1/S01E01.mkv',isdir=False)])
    monkeypatch.setattr(media,'RemoteNASClient',Mock(return_value=client))
    worker=media.EpisodeScanWorker(['syno:///Show','syno:///Show/Season1']);items=[]
    worker.episodes_found.connect(lambda episodes,error:items.extend(episodes));worker.run()
    assert len(items)==1 and items[0][1]=='syno:///Show/Season1/S01E01.mkv'
    client.close.assert_called_once()

def test_failed_retry_keeps_existing_snapshot_rows(media):
    scanner=media.LibraryScannerThread([],[]);scanner.current_scan_library_id='movies'
    path='C:/audit/keep.mkv';key=(media.normalize_media_path(path),True)
    scanner._deferred_metadata[key]=(SimpleNamespace(path=path),True,'movies',None)
    scanner.emitted_card_items={'movies':[dict(file_path=path,title='Keep',episode_roots=['a','b'])]}
    scanner.process_media_item=Mock(return_value=dict(file_path=path,title='Unavailable',id=-1))
    scanner.retry_deferred_metadata(None)
    assert scanner.emitted_card_items['movies'][0]['title']=='Keep'
    assert scanner.emitted_card_items['movies'][0]['episode_roots']==['a','b']
