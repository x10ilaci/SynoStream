import contextlib,socket,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urlsplit,quote
import pytest
from test_deletion1104 import Files,ROOT
from synostream_deletion import Inventory,video
from synostream_connections import normalize_local_url

@pytest.mark.parametrize('extension',['.wmv','.mts','.m2ts','.mpg','.mpeg','.webm'])
def test_scanner_and_deletion_agree_on_supported_video_formats(media,tmp_path,monkeypatch,extension):
 root=tmp_path/'movies';root.mkdir();f=root/('Movie'+extension);f.write_bytes(b'x');scanner=media.LibraryScannerThread([str(root)],[],library_key='movies');seen=[]
 def resolve(entry,movie,conn,token):seen.append(entry.path);return scanner.make_item(entry.path,'Fixture','',media_id=42)
 monkeypatch.setattr(scanner,'_process_media_item',resolve);scanner.run();assert not scanner.errors;assert str(f) in seen
 assert video('/Media/Movies/Movie'+extension)

def test_episode_walk_excludes_nested_extras_but_preserves_samples_card(media,tmp_path):
 root=tmp_path/'Samples';(root/'Samples').mkdir(parents=True);(root/'Extras').mkdir();(root/'Samples'/'clip.mkv').write_bytes(b'x');(root/'Extras'/'clip.mkv').write_bytes(b'x');(root/'S01E01.mkv').write_bytes(b'x')
 episodes,error=media.find_episodes(str(root));assert not error;assert [Path(p).name for _,p in episodes]==['S01E01.mkv']

def test_movie_scan_excludes_only_samples_below_card_root(media,tmp_path,monkeypatch):
 root=tmp_path/'Samples';(root/'Samples'/'Samples').mkdir(parents=True);(root/'Samples'/'Samples'/'clip.mkv').write_bytes(b'x');main=root/'Samples'/'Movie.mkv';main.write_bytes(b'x');scanner=media.LibraryScannerThread([str(root)],[],library_key='movies');seen=[]
 def resolve(entry,movie,conn,token):seen.append(entry.path);return scanner.make_item(entry.path,'Fixture','',media_id=42)
 monkeypatch.setattr(scanner,'_process_media_item',resolve);scanner.run();assert not scanner.errors;assert seen==[str(main)]

def test_invalid_local_address_has_readable_hungarian_message():
 with pytest.raises(ValueError,match='Helyi NAS-címet adj meg, például'):normalize_local_url('http://nas.example.org')

@pytest.mark.parametrize('dialog_proxy',[False,True])
def test_truncated_nas_stream_is_closed_without_second_http_response(media,app,monkeypatch,dialog_proxy):
 class BrokenStream:
  status_code=200;headers={'Content-Type':'video/mp4','Content-Length':'100'}
  def __init__(self):self.close=Mock()
  def iter_content(self,size):yield b'abcd';raise OSError('fixture interrupted stream')
 upstream=BrokenStream();client=SimpleNamespace(sid='fixture',open_stream=lambda *args:upstream,close=Mock(),download_version=2)
 dialog=None;server=None
 if dialog_proxy:
  dialog=media.RemoteQuickConnectDialog(None);dialog._nas_client=client;dialog._proxy_allowed_paths.add('/video/a.mkv');dialog.start_proxy();server=dialog._proxy_server;url=f'http://127.0.0.1:{server.server_address[1]}/stream?token={dialog._proxy_token}&path='+quote('/video/a.mkv',safe='')
 else:
  monkeypatch.setattr(media,'RemoteNASClient',lambda credentials:client);monkeypatch.setattr(media,'_remote_playback_server',None);monkeypatch.setattr(media,'_remote_playback_profiles',{});monkeypatch.setattr(media,'_remote_playback_allowed_paths',set());url=media._remote_stream_url('syno:///video/a.mkv');server=media._remote_playback_server
 try:
  parsed=urlsplit(url)
  with socket.create_connection(('127.0.0.1',parsed.port),timeout=3) as s:
   s.sendall(('GET '+parsed.path+'?'+parsed.query+' HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n').encode());chunks=[]
   while True:
    data=s.recv(65536)
    if not data:break
    chunks.append(data)
  raw=b''.join(chunks);assert raw.startswith(b'HTTP/1.0 200');assert b'502' not in raw.split(b'\r\n\r\n',1)[1];assert upstream.close.call_count>=1
 finally:
  server.shutdown();server.server_close()
  if dialog:dialog._proxy_server=None;dialog._nas_client=None;dialog.session.close()


def test_nas_movie_scan_preserves_top_level_samples_title_and_skips_nested_extras(media,monkeypatch):
 import sqlite3
 scanner=media.LibraryScannerThread([],[]);scanner.remote_client=object();seen=[]
 def row(path,directory):return {'name':path.rsplit('/',1)[-1],'path':path,'isdir':directory,'additional':{'time':{'mtime':1},'size':100}}
 tree={'/video/Samples':[row('/video/Samples/Samples',True)],'/video/Samples/Samples':[row('/video/Samples/Samples/Movie.mkv',False),row('/video/Samples/Samples/Extras',True)]}
 def listing(path):assert path in tree,'Nested sample/extra folders must never be listed';return tree[path]
 monkeypatch.setattr(scanner,'portable_remote_listing',listing)
 def resolve(entry,movie,conn,token):seen.append(entry.path);return scanner.make_item(entry.path,'Fixture','',media_id=42)
 monkeypatch.setattr(scanner,'_process_media_item',resolve)
 with contextlib.closing(sqlite3.connect(media.DB_FILE)) as conn:scanner.scan_remote_folder(conn,'syno:///video/Samples',True,'Film')
 assert not scanner.errors and seen==['syno:///video/Samples/Samples/Movie.mkv']

def test_local_nas_validation_has_english_translation(media,monkeypatch):
 monkeypatch.setattr(media,'UI_LANGUAGE','en')
 with pytest.raises(ValueError) as failure:normalize_local_url('http://public.example.org')
 assert media.translate_text(str(failure.value)).startswith('Enter a local NAS address')
