from unittest.mock import Mock
import pytest
import requests
from synostream_nas import RemoteNASClient, normalize_direct_url, NASAuthenticationError
from synostream_downloads import DownloadStationClient

INFO = {k: {'path':'auth.cgi' if k == 'SYNO.API.Auth' else 'entry.cgi','maxVersion':3}
        for k in ('SYNO.API.Auth','SYNO.FileStation.List','SYNO.FileStation.Download','SYNO.DownloadStation.Task')}

def response(data, status=200):
    result=Mock(status_code=status)
    result.json.return_value=data
    result.raise_for_status.side_effect=requests.HTTPError() if status >= 400 else None
    return result

class Session:
    def __init__(self, direct_error=None, login_error=None, rejected=False):
        self.headers={};self.calls=[];self.direct_error=direct_error;self.login_error=login_error;self.rejected=rejected
    def close(self):pass
    def get(self,url,**kwargs):
        self.calls.append(('get',url,kwargs))
        if url.startswith('https://nas.example') and self.direct_error:
            raise self.direct_error
        if url.endswith('query.cgi'):return response({'success':True,'data':INFO})
        return response({'success':True,'data':{}})
    def post(self,url,**kwargs):
        self.calls.append(('post',url,kwargs))
        if url.endswith('Serv.php'):return response([{'errno':0,'env':{'relay_region':'test'}}])
        if url.startswith('https://nas.example') and self.login_error:raise self.login_error
        return response({'success':not self.rejected,'error':{'code':400},'data':{'sid':'synthetic-session'}})

@pytest.mark.parametrize('value', ['ftp://nas.example','https://user:pass@nas.example','https://nas.example/path','https://nas.example?x=1','https://nas.example#x','https://nas.example:invalid','https://nas.example:70000','https://nas.example\\evil','https://nas .example'])
def test_reject_unsafe_url(value):
    with pytest.raises(ValueError):normalize_direct_url(value)

def test_normalize():
    assert normalize_direct_url(' nas.example:5001/ ')=='https://nas.example:5001'
    assert normalize_direct_url('')==''

@pytest.mark.parametrize('factory',[RemoteNASClient,DownloadStationClient])
@pytest.mark.parametrize('qc',['','synthetic'])
def test_direct_connection_without_quickconnect(monkeypatch,factory,qc):
    session=Session();monkeypatch.setattr(requests,'Session',lambda:session)
    client=factory(dict(nas_direct_url='nas.example:5001',quickconnect_id=qc,nas_username='synthetic',nas_password='synthetic'))
    assert client.transport=='direct'
    assert client.base_url=='https://nas.example:5001'
    assert all(url.startswith(client.base_url) and kw['allow_redirects'] is False for _,url,kw in session.calls)
    if factory is DownloadStationClient:client._task_request('list',readonly=True)
    else:client.api_get('SYNO.FileStation.List',2,'list_share')
    assert session.calls[-1][2]['allow_redirects'] is False
    client.close()

@pytest.mark.parametrize('stage',['discovery','login'])
@pytest.mark.parametrize('error',[requests.Timeout(),requests.exceptions.SSLError()])
def test_fallback_to_quickconnect(monkeypatch,stage,error):
    session=Session(**{('direct_error' if stage=='discovery' else 'login_error'):error})
    monkeypatch.setattr(requests,'Session',lambda:session)
    client=RemoteNASClient(dict(nas_direct_url='https://nas.example',quickconnect_id='synthetic',nas_username='synthetic',nas_password='synthetic'))
    assert client.transport=='quickconnect'
    assert client.base_url=='https://synthetic.test.quickconnect.to'
    assert client.credentials['nas_direct_url']=='https://nas.example'
    client.close()

def test_auth_rejection_not_retried(monkeypatch):
    session=Session(rejected=True);monkeypatch.setattr(requests,'Session',lambda:session)
    with pytest.raises(NASAuthenticationError):RemoteNASClient(dict(nas_direct_url='nas.example',quickconnect_id='synthetic',nas_username='synthetic',nas_password='synthetic'))
    assert not any(url.endswith('Serv.php') for _,url,_ in session.calls)

def test_redirect_cannot_leak_password(monkeypatch):
    session=Session();session.get=lambda *a,**kw:response({},302)
    monkeypatch.setattr(requests,'Session',lambda:session)
    with pytest.raises(RuntimeError):RemoteNASClient(dict(nas_direct_url='nas.example',nas_username='synthetic',nas_password='synthetic'))
    assert not session.calls

def test_connection_rechecks_direct_after_recovery(monkeypatch):
    session=Session(direct_error=requests.Timeout());monkeypatch.setattr(requests,'Session',lambda:session)
    client=RemoteNASClient(dict(nas_direct_url='nas.example',quickconnect_id='synthetic',nas_username='synthetic',nas_password='synthetic'))
    assert client.transport=='quickconnect'
    session.direct_error=None;client.connect()
    assert client.transport=='direct'
    assert 'Referer' not in session.headers
    client.close()

@pytest.mark.parametrize('direct,qc,expected',[('https://nas.example','',True),('','synthetic',True),('','',False)])
def test_download_ui_accepts_either_connection(direct,qc,expected):
    from types import SimpleNamespace
    from synostream_download_ui import DownloadPage
    page=SimpleNamespace(credentials=lambda:dict(nas_direct_url=direct,quickconnect_id=qc,nas_username='synthetic',nas_password='synthetic'))
    assert DownloadPage.has_credentials(page) is expected

def test_dialog_passes_direct_only_credentials(media,monkeypatch):
    dialog=media.RemoteQuickConnectDialog()
    try:
        dialog.direct_edit.setText('nas.example:5001')
        dialog.user_edit.setText('synthetic');dialog.pass_edit.setText('synthetic')
        captured=[]
        monkeypatch.setattr(dialog,'_start_task',lambda operation,*args:captured.append(operation))
        monkeypatch.setattr(media,'RemoteNASClient',lambda credentials,stop:credentials)
        dialog.connect_nas()
        assert len(captured)==1
        credentials=captured[0](lambda:False)
        assert credentials['nas_direct_url']=='https://nas.example:5001'
        assert credentials['quickconnect_id']==''
    finally:
        dialog.close()
