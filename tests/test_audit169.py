import json
import logging
import os
from pathlib import Path
import subprocess
import time
import wave
from unittest.mock import Mock
import pytest
from synostream_playback import MpvPlaybackMonitor


def monitor(entries, sources=None):
    saved, watched = [], []
    m = MpvPlaybackMonitor(None, '', entries, save_progress=lambda *a:saved.append(a), set_watched=lambda *a:watched.append(a), normalize_path=lambda p:str(p).replace('\\','/').lower(), logger=logging.getLogger(__name__), source_paths=sources)
    return m, saved, watched


def bind_via_ipc(m, path):
    commands = []
    m._query_current_source(lambda command, request:commands.append((command,request)))
    for command, request in commands:
        value = {'path':path,'duration':100,'time-pos':10}[command[1]]
        m._on_message({'request_id':request,'error':'success','data':value})


def test_unknown_replacement_does_not_mark_or_save_original():
    m, saved, watched = monitor([{'path':'A.mkv'}])
    bind_via_ipc(m,'A.mkv')
    m._on_message({'event':'end-file','reason':'stop'})
    m._on_message({'event':'start-file'})
    bind_via_ipc(m,'foreign.mkv')
    count=len(saved)
    m._on_message({'event':'end-file','reason':'eof'})
    m._save_current()
    assert len(saved)==count and not watched


def test_playlist_position_does_not_override_verified_identity():
    m, saved, watched = monitor([{'path':'A.mkv'},{'path':'B.mkv'}])
    bind_via_ipc(m,'B.mkv')
    m._on_message({'event':'property-change','name':'playlist-pos','data':0})
    m._on_message({'event':'end-file','reason':'eof'})
    assert watched[0][0]=='B.mkv'
    assert all(call[0]['path']=='B.mkv' for call in saved)


def test_late_identity_reply_from_previous_file_is_ignored():
    m, saved, watched = monitor([{'path':'A.mkv'}])
    requests=[]
    m._query_current_source(lambda command, request:requests.append((command,request)))
    m._on_message({'event':'start-file'})
    for command, request in requests:
        m._on_message({'request_id':request,'error':'success','data':'A.mkv' if command[1]=='path' else 100})
    m._on_message({'event':'end-file','reason':'eof'})
    assert not saved and not watched


def test_remote_proxy_source_matches_exactly_without_persisting_token():
    url='http://127.0.0.1:123/video?session=OpaqueToken&path=%2FShow'
    m, saved, watched = monitor([{'path':'syno:///Show'}],[url])
    bind_via_ipc(m,url.lower())
    m._save_current();assert not saved
    bind_via_ipc(m,url)
    m._save_current()
    assert saved[0][0]['path']=='syno:///Show'
    assert 'OpaqueToken' not in json.dumps(saved)


def audio(path, seconds):
    with wave.open(str(path),'wb') as f:
        f.setparams((1,2,8000,0,'NONE','not compressed'))
        f.writeframes(b'\0\0'*(8000*seconds))


@pytest.mark.parametrize('change',['replace','reorder','resume'])
def test_real_mpv_file_identity(media, app, tmp_path, monkeypatch, change):
    mpv=os.environ.get('SYNOSTREAM_TEST_MPV')
    if not mpv or not Path(mpv).is_file():pytest.skip('Set SYNOSTREAM_TEST_MPV for real IPC test')
    a,b=tmp_path/'A.mkv',tmp_path/'B.mkv';audio(a,20);audio(b,4)
    script=tmp_path/'change.lua'
    command=("mp.commandv('loadfile', "+json.dumps(str(b).replace('\\','/'))+", 'replace')") if change=='replace' else "mp.commandv('playlist-move',0,2);mp.commandv('playlist-play-index',0)"
    if change=='resume':command="mp.commandv('quit')"
    script.write_text("local switched=false\nmp.register_event('file-loaded',function() if not switched then switched=true;mp.add_timeout(.6,function() "+command+" end) end end)\nmp.register_event('end-file',function(e) if switched and e.reason=='eof' then mp.commandv('quit') end end)\nmp.add_timeout(10,function() mp.commandv('quit') end)",encoding='utf-8')
    media.config.update(mpv_path=mpv,startup_scan_mode='none')
    original=subprocess.Popen;children=[]
    def launch(command,**kwargs):
        child=original([*command,'--no-config','--ao=null','--vo=null','--force-window=no','--terminal=no','--speed=2',f'--script={script}'],**kwargs)
        children.append(child);return child
    monkeypatch.setattr(media.subprocess,'Popen',launch)
    monkeypatch.setattr(media,'mpv_localized_context_menu_args',lambda _:[])
    failed=Mock();monkeypatch.setattr(media.QMessageBox,'critical',failed)
    window=media.DSVideoWindow()
    try:
        entries=[dict(path=str(a)),dict(path=str(b))] if change=='reorder' else None
        media.play_with_mpv(window,str(a),playlist_entries=entries,resume_position=8 if change=='resume' else 0)
        deadline=time.monotonic()+16
        while time.monotonic()<deadline:
            app.processEvents()
            if children and children[0].poll() is not None and not any(t.isRunning() for t in media._background_workers):break
            time.sleep(.01)
        failed.assert_not_called();assert children and children[0].returncode==0
        state=media.get_playback_state(str(a))
        assert not state['watched'] and state['duration']==20
        other=media.get_playback_state(str(b))
        if change in ('replace','resume'):assert other is None
        if change=='resume':assert state['position']>=8
        if change=='reorder':assert other['watched'] and other['duration']==4
    finally:
        for child in children:
            if child.poll() is None:child.kill();child.wait()
        deadline=time.monotonic()+4
        while any(t.isRunning() for t in media._background_workers) and time.monotonic()<deadline:
            app.processEvents();time.sleep(.01)
        window.close();app.processEvents()


def test_open_episode_detail_refreshes_without_recursive_save(media, app, tmp_path, monkeypatch):
    from PyQt6.QtCore import QTimer, Qt
    from PyQt6.QtWidgets import QDialog, QTreeWidget, QPushButton
    folder=tmp_path/'Series';folder.mkdir()
    episode=folder/'Series.S01E01.mkv';episode.touch()
    window=media.DSVideoWindow();window.show();app.processEvents()
    original=media.set_playback_watched
    write=Mock(wraps=original);monkeypatch.setattr(media,'set_playback_watched',write)
    errors=[];finished=[]
    before=window.receivers(window.playback_state_changed)
    timer=QTimer();timer.setInterval(20)
    def inspect():
        dialog=next((d for d in app.topLevelWidgets() if isinstance(d,QDialog) and d.isVisible() and d.parentWidget() is window),None)
        if dialog is None:return
        tree=next((t for t in dialog.findChildren(QTreeWidget) if t.topLevelItemCount() and t.topLevelItem(0).childCount()),None)
        if tree is None:return
        timer.stop()
        try:
            node=tree.topLevelItem(0).child(0)
            assert node.checkState(0)==Qt.CheckState.Unchecked
            original(str(episode),'Series','S01E01','',False,True)
            window.on_playback_watched(str(episode))
            assert node.checkState(0)==Qt.CheckState.Checked
            buttons=[b for b in dialog.findChildren(QPushButton) if b.isCheckable()]
            assert any(b.isChecked() and 'Megnézve' in b.text() for b in buttons)
            write.assert_not_called()
            node.setCheckState(0,Qt.CheckState.Unchecked)
            assert write.call_count==1
            assert not media.get_playback_state(str(episode))['watched']
            assert all(not b.isChecked() for b in buttons)
            finished.append(True)
        except Exception as exc:errors.append(repr(exc))
        dialog.reject()
    timer.timeout.connect(inspect)
    watchdog=QTimer();watchdog.setSingleShot(True)
    def abort():
        errors.append('detail timeout')
        for d in app.topLevelWidgets():
            if isinstance(d,QDialog) and d.isVisible():d.reject()
    watchdog.timeout.connect(abort);watchdog.start(5000);timer.start()
    try:
        window.open_media_detail(dict(file_path=str(folder),title='Series',is_movie=False,id=0))
        assert not errors,errors
        assert finished
        assert window.receivers(window.playback_state_changed)==before
        window.on_playback_watched(str(episode))
    finally:
        timer.stop();watchdog.stop();window.close();app.processEvents()


def test_real_mpv_attach_after_file_loaded(media, app, tmp_path):
    import uuid
    mpv=os.environ.get('SYNOSTREAM_TEST_MPV')
    if not mpv or not Path(mpv).is_file():pytest.skip('Set SYNOSTREAM_TEST_MPV for real IPC test')
    clip=tmp_path/'Already loaded.mkv';audio(clip,20)
    ready=tmp_path/'ready'
    script=tmp_path/'ready.lua'
    script.write_text("mp.register_event('file-loaded',function() local f=io.open("+json.dumps(str(ready).replace('\\','/'))+",'w'); f:write('loaded');f:close() end)\nmp.add_timeout(3,function() mp.commandv('quit') end)",encoding='utf-8')
    pipe=r"\\.\pipe\SynoStream-late-"+uuid.uuid4().hex
    child=subprocess.Popen([mpv,'--no-config','--ao=null','--vo=null','--force-window=no','--terminal=no','--pause=yes',f'--input-ipc-server={pipe}',f'--script={script}',str(clip)])
    watcher=None
    try:
        deadline=time.monotonic()+5
        while not ready.exists():
            assert child.poll() is None
            assert time.monotonic()<deadline
            time.sleep(.02)
        watcher=media.MpvPlaybackMonitor(child,pipe,[dict(path=str(clip))],resume_position=8)
        failed=Mock();watcher.startup_failed.connect(failed)
        media.run_worker(watcher)
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            app.processEvents()
            if child.poll() is not None and not watcher.isRunning():break
            time.sleep(.01)
        assert child.returncode==0
        failed.assert_not_called()
        state=media.get_playback_state(str(clip))
        assert state and 8<state['position']<20 and state['duration']==20
    finally:
        if child.poll() is None:child.kill();child.wait()
        if watcher is not None:watcher.wait(4000)
        app.processEvents()
