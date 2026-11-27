import threading,time,contextlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import Mock
import pytest,requests
from test_upgrade import bare_client,response

@pytest.mark.parametrize('dialog_proxy',[False,True])
def test_proxy_forwards_first_small_block_before_upstream_megabyte(media,app,monkeypatch,dialog_proxy):
 release=threading.Event();received=threading.Event();result=[];payload=b'x'*(1024*1024+65536)
 class Nas(BaseHTTPRequestHandler):
  def do_GET(self):
   self.send_response(200);self.send_header('Content-Type','video/mp4');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload[:65536]);self.wfile.flush();release.wait(4)
   try:self.wfile.write(payload[65536:])
   except (BrokenPipeError,ConnectionResetError):pass
  def log_message(self,*a):pass
 nas=ThreadingHTTPServer(('127.0.0.1',0),Nas);t=threading.Thread(target=nas.serve_forever,daemon=True);t.start()
 client=SimpleNamespace(sid='fixture',download_version=2,close=Mock(),open_stream=lambda p,h:requests.get('http://127.0.0.1:'+str(nas.server_port),headers=h,stream=True,timeout=5))
 dialog=None
 if dialog_proxy:
  dialog=media.RemoteQuickConnectDialog(None);dialog._nas_client=client;dialog._proxy_allowed_paths.add('/video/a.mkv');dialog.start_proxy();server=dialog._proxy_server;url=f'http://127.0.0.1:{server.server_port}/stream?token={dialog._proxy_token}&path=%2Fvideo%2Fa.mkv'
 else:
  monkeypatch.setattr(media,'RemoteNASClient',lambda credentials:client);monkeypatch.setattr(media,'_remote_playback_server',None);monkeypatch.setattr(media,'_remote_playback_profiles',{});monkeypatch.setattr(media,'_remote_playback_allowed_paths',set());url=media._remote_stream_url('syno:///video/a.mkv');server=media._remote_playback_server
 def read():
  with requests.get(url,stream=True,timeout=5) as reply:
   for part in reply.iter_content(1024):result.append(part);received.set();break
 reader=threading.Thread(target=read,daemon=True);reader.start()
 try:assert received.wait(1.5),'Proxy withheld an available 64 KiB block waiting for 1 MiB'
 finally:
  release.set();reader.join(5);server.shutdown();server.server_close();nas.shutdown();nas.server_close()
  if dialog:dialog._proxy_server=None;dialog._nas_client=None;dialog.session.close()
 assert result==[b'x'*1024]

def test_raw_media_requests_disable_compression_and_preserve_range():
 c=bare_client();c._request=Mock(return_value=response());c.open_stream('/video/a.mkv',{'Range':'bytes=123-'})
 assert c._request.call_args.kwargs['headers']=={'Range':'bytes=123-','Accept-Encoding':'identity'}

def test_automatic_inventory_waits_for_active_playback(media,app,monkeypatch):
 window=media.DSVideoWindow();scan=Mock();monkeypatch.setattr(window,'start_library_scan',scan)
 worker=media.MpvPlaybackMonitor(SimpleNamespace(poll=lambda:None),'fixture',[],0)
 monkeypatch.setattr(media,'_background_workers',[worker])
 try:
  window._last_inventory_check=time.monotonic()-301;window.check_library_changes();scan.assert_not_called()
  worker.process=SimpleNamespace(poll=lambda:0);window.check_library_changes();scan.assert_called_once_with()
 finally:window.close();app.processEvents()


def test_hidden_download_poll_waits_for_playback_but_manual_refresh_remains_available(media,app,monkeypatch):
 window=media.DSVideoWindow();page=window.downloads_page;refresh=Mock();monkeypatch.setattr(page,'refresh',refresh);monkeypatch.setattr(page,'playback_active',lambda:True);monkeypatch.setattr(window,'isActiveWindow',lambda:False)
 try:
  page.poll();refresh.assert_not_called();monkeypatch.setattr(window,'isActiveWindow',lambda:True);page.poll();refresh.assert_called_once()
 finally:window.close();app.processEvents()
