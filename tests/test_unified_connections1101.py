import contextlib
import ntpath
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urlsplit
import pytest
import requests
from PyQt6.QtWidgets import QDialog, QLineEdit, QMessageBox
from synostream_connections import normalize_local_url
from synostream_sources import SourceRouter, RoutedNASClient, automatic_pairs, nas_root_from_local
from synostream_source_folders import records_from_settings, SourceFoldersDialog, SourceFolderDialog
from synostream_download_ui import DownloadPage
from synostream_downloads import DownloadStationClient
from synostream_nas import RemoteNASClient, NASAuthenticationError
from test_ddns1100 import Session, response
from test_download_station import dsm_server
from test_nas_playback_integration import nas_stream

LOCAL=r'\\192.168.1.2\Media\Film'
REMOTE='syno:///Media/Film'
LIBRARIES=[('movies','Filmek'),('shows','TV')]


def settings(**extra):
    return dict(nas_local_url='http://192.168.1.2:5000',movies_paths=[REMOTE],shows_paths=[],**extra)


@pytest.mark.parametrize('value,expected', [('192.168.1.2','http://192.168.1.2:5000'),
    ('http://nas.local','http://nas.local:5000'),('https://[fd00::1]:5001/','https://[fd00::1]:5001')])
def test_local_address_defaults(value,expected):
    assert normalize_local_url(value)==expected


@pytest.mark.parametrize('value',['http://8.8.8.8:5000','http://public.example:5000','http://user:pass@nas.local','https://nas.local/path','http://nas.local:70000'])
def test_insecure_or_malformed_local_address_rejected(value):
    with pytest.raises(ValueError):normalize_local_url(value)


class Routes(Session):
    def __init__(self, failures=(), rejected=False):
        super().__init__(rejected=rejected);self.failures=set(failures)
    def get(self,url,**kwargs):
        if urlsplit(url).hostname in self.failures:
            self.calls.append(('get',url,kwargs));raise requests.Timeout()
        return super().get(url,**kwargs)
    def post(self,url,**kwargs):
        result=super().post(url,**kwargs)
        if url.endswith('auth.cgi') and not self.rejected:
            result.json.return_value['data']['sid']='sid-'+urlsplit(url).hostname
        return result


@pytest.mark.parametrize('factory',[RemoteNASClient,DownloadStationClient])
@pytest.mark.parametrize('failures,expected',[((),'local'),(('192.168.1.2',),'direct'),(('192.168.1.2','nas.example'),'quickconnect')])
def test_all_routes_obey_priority(monkeypatch,factory,failures,expected):
    session=Routes(failures);monkeypatch.setattr(requests,'Session',lambda:session)
    credentials=dict(nas_local_url='http://192.168.1.2:5000',nas_direct_url='https://nas.example',quickconnect_id='synthetic',nas_username='synthetic',nas_password='synthetic')
    client=factory(credentials)
    try:
        assert client.transport==expected
        assert urlsplit(session.calls[0][1]).hostname=='192.168.1.2'
        if expected=='local':assert all(url.startswith('http://192.168.1.2:5000') for _,url,_ in session.calls)
        if expected=='direct':assert not any('quickconnect.to' in url for _,url,_ in session.calls)
        for _,url,kw in session.calls:
            if 'quickconnect.to' not in url:assert kw['allow_redirects'] is False
    finally:client.close()


def test_local_api_auth_rejection_does_not_replay_login(monkeypatch):
    session=Routes(rejected=True);monkeypatch.setattr(requests,'Session',lambda:session)
    with pytest.raises(NASAuthenticationError):RemoteNASClient(dict(nas_local_url='http://192.168.1.2:5000',nas_direct_url='https://nas.example',quickconnect_id='synthetic',nas_username='synthetic',nas_password='synthetic'))
    assert len([1 for method,_,_ in session.calls if method=='post'])==1


def test_one_remote_source_automatically_gets_local_smb():
    router=SourceRouter(automatic_pairs(settings()))
    assert router.physical(REMOTE+'/Release/Movie.mkv')==LOCAL+r'\Release\Movie.mkv'
    assert router.canonical(LOCAL+r'\Release\Movie.mkv')==REMOTE+'/Release/Movie.mkv'
    assert nas_root_from_local(r'\\other-nas\Media\Film',settings()) is None


def test_profile_address_change_updates_automatic_smb_without_touching_identity():
    first=settings();second={**first,'nas_local_url':'http://192.168.1.3:5000'}
    a,b=(SourceRouter(automatic_pairs(value)) for value in (first,second))
    assert a.pairs[0].id==b.pairs[0].id
    assert b.physical(REMOTE+'/A.mkv')==r'\\192.168.1.3\Media\Film\A.mkv'
    assert a.canonical(LOCAL+r'\A.mkv')==b.canonical(REMOTE+'/A.mkv')


def test_legacy_duplicate_sources_collapse_only_for_configured_nas():
    config=settings();config['movies_paths']=[LOCAL,REMOTE]
    rows=records_from_settings(config,LIBRARIES)
    assert len(rows)==1 and rows[0]['local_root']==LOCAL and rows[0]['remote_root']==REMOTE
    config['nas_local_url']='http://different-nas:5000'
    assert len(records_from_settings(config,LIBRARIES))==2


def test_local_api_can_read_usb_without_smb(monkeypatch):
    session=Routes();monkeypatch.setattr(requests,'Session',lambda:session)
    client=RemoteNASClient(dict(nas_local_url='http://192.168.1.2:5000',nas_username='synthetic',nas_password='synthetic'))
    try:
        client.list_folder('/usbshare1/Films')
        assert client.transport=='local'
        assert session.calls[-1][2]['params']['folder_path']=='/usbshare1/Films'
    finally:client.close()


def test_unavailable_smb_uses_local_api(monkeypatch):
    router=SourceRouter(automatic_pairs(settings()))
    monkeypatch.setattr(router,'local_operation',Mock(side_effect=OSError('unavailable')))
    remote=SimpleNamespace(list_folder=Mock(return_value=[{'path':'/Media/Film/a.mkv'}]))
    client=RoutedNASClient(router,lambda:remote)
    assert client.list_folder('/Media/Film')==[{'path':'/Media/Film/a.mkv'}]
    remote.list_folder.assert_called_once_with('/Media/Film')


def test_source_editor_shows_one_path_and_auto_merges_without_question(app,monkeypatch):
    config=settings();config['movies_paths']=[LOCAL,REMOTE]
    rows=records_from_settings(config,LIBRARIES)
    save=Mock();question=Mock(side_effect=AssertionError('No alias question should be necessary'))
    monkeypatch.setattr(QMessageBox,'question',question)
    dialog=SourceFoldersDialog(None,rows,LIBRARIES,save,Mock(),Mock(),settings=lambda:config)
    try:
        assert dialog.listing.count()==1
        assert 'Helyi:' not in dialog.listing.item(0).text()
        dialog.accept();save.assert_called_once();question.assert_not_called()
    finally:dialog.close();dialog.deleteLater();app.processEvents()


def test_connection_settings_do_not_show_source_browser(media):
    dialog=media.RemoteQuickConnectDialog(connection_only=True)
    try:
        assert dialog.items.isHidden() and dialog.up_btn.isHidden()
        assert dialog.local_edit.placeholderText()
        assert dialog.connect_btn.text()=='Kapcsolat ellenőrzése és mentése'
    finally:dialog.close();dialog.deleteLater()


def test_automatic_upgrade_preserves_history_and_manual_info(media,app):
    media.config.update(settings());media.config['movies_paths']=[LOCAL,REMOTE]
    path=ntpath.normcase(ntpath.normpath(LOCAL+r'\Movie.mkv'))
    with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO playback_state(file_path,position) VALUES (?,?)',(path,42))
        db.execute('INSERT INTO manual_overrides VALUES (?,?,?,?)',(path,603,'Kézi cím',1))
        db.execute('INSERT INTO library_card_cache VALUES (?,?,?)',('movies',path,json.dumps({'file_path':LOCAL+r'\Movie.mkv'})))
        db.execute('INSERT INTO library_card_cache VALUES (?,?,?)',('movies',REMOTE+'/Movie.mkv',json.dumps({'file_path':REMOTE+'/Movie.mkv'})))
        db.commit()
    window=media.DSVideoWindow()
    try:
        assert media.configured_paths('movies')==[REMOTE]
        assert len(records_from_settings(media.config,LIBRARIES))==1
        assert media.get_playback_state(REMOTE+'/Movie.mkv')['position']==42
        with contextlib.closing(sqlite3.connect(media.DB_FILE)) as db:
            assert db.execute('SELECT tmdb_id,custom_title FROM manual_overrides WHERE file_path=?',(REMOTE+'/Movie.mkv',)).fetchone()==(603,'Kézi cím')
            assert db.execute('SELECT COUNT(*) FROM library_card_cache').fetchone()[0]==1
    finally:window.close();app.processEvents()


def test_one_nas_source_save_does_not_store_automatic_alias(media,app):
    media.config.update(settings());media.config['unified_sources_local_url']=media.config['nas_local_url']
    window=media.DSVideoWindow()
    try:
        window.save_library_sources([dict(id='source',library_id='movies',local_root='',remote_root=REMOTE)])
        assert media.config['paired_sources']==[]
        assert media.config['movies_paths']==[REMOTE]
        assert media.source_router().physical(REMOTE+'/A.mkv')==LOCAL+r'\A.mkv'
    finally:window.close();app.processEvents()


def test_real_local_download_station_http(dsm_server):
    state,factory=dsm_server
    bootstrap=factory(dict(quickconnect_id='synthetic',nas_username='synthetic',nas_password='synthetic'))
    base=bootstrap.base_url;bootstrap.close()
    client=DownloadStationClient(dict(nas_local_url=base,nas_username='synthetic',nas_password='synthetic'))
    try:
        assert client.transport=='local'
        assert len(client.list_tasks())==1
    finally:client.close()


def test_real_local_stream_uses_same_file_station_path(nas_stream,media):
    _,payload,_=nas_stream
    bootstrap=media.RemoteNASClient()
    parts=urlsplit(bootstrap.download_url)
    client=RemoteNASClient(dict(nas_local_url=f'{parts.scheme}://{parts.netloc}',nas_username='synthetic',nas_password='synthetic'))
    try:
        with contextlib.closing(client.open_stream('/video/test.wav',headers={'Range':'bytes=10-'})) as result:
            assert result.status_code==206
            assert b''.join(result.iter_content(4096))==payload[10:]
        assert client.transport=='local'
    finally:client.close()

@pytest.mark.parametrize('factory',[RemoteNASClient,DownloadStationClient])
def test_network_change_recovers_existing_client_without_readding_source(monkeypatch,factory):
    session=Routes();monkeypatch.setattr(requests,'Session',lambda:session)
    client=factory(dict(nas_local_url='http://192.168.1.2:5000',nas_direct_url='https://nas.example',quickconnect_id='synthetic',nas_username='synthetic',nas_password='synthetic'))
    try:
        assert client.transport=='local'
        session.failures.add('192.168.1.2')
        if factory is DownloadStationClient:client._task_request('list',readonly=True)
        else:client.list_folder('/Media/Film')
        assert client.transport=='direct'
        assert session.calls[-1][1].startswith('https://nas.example/')
        assert session.calls[-1][2]['params']['_sid']==client.sid
    finally:client.close()


def test_unc_and_nas_path_case_preserves_existing_nas_spelling():
    config=settings();config['movies_paths']=[LOCAL.lower(),REMOTE]
    row=records_from_settings(config,LIBRARIES)[0]
    assert row['remote_root']==REMOTE
