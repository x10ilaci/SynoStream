import json
from unittest.mock import Mock
import pytest
from synostream_logic import is_sample_video
from test_upgrade import bare_client,response
from test_deletion1104 import Files,ROOT
from synostream_deletion import Inventory

@pytest.mark.parametrize('size,largest,wanted',[(120000000,125000000,False),(50000000,4000000000,True),(3000000000,4000000000,False),(None,4000000000,False),(100,None,False),(400,4000,False),(399,4000,True)])
def test_ratio_required(size,largest,wanted):
 assert is_sample_video('Sample Show - 01.mkv',size,largest)==wanted

def test_sample_title_series_deletion():
 folder=ROOT+'/Sample Show';a=folder+'/Sample Show - 01.mkv';b=folder+'/Sample Show - 02.mkv'
 fs=Files([a,b]);fs.rows[a]['size']=120000000;fs.rows[b]['size']=125000000
 inv=Inventory([folder],[ROOT],False,fs.list)
 assert set(inv.plan([1]).files)=={a,b}

@pytest.mark.parametrize('version',[5,6])
def test_no_otp_no_trust_warning(version):
 c=bare_client();c.base_url='https://fixture.invalid';c.session_name='fixture';c.credentials={'remember_device':True}
 c._connect_request=Mock(return_value=response({'success':True,'data':{'sid':'fixture'}}))
 c._login_from_info({'SYNO.API.Auth':{'maxVersion':version}},'fixture','fixture')
 assert not c.device_trust_warning

@pytest.mark.parametrize('replacement',[False,True])
def test_rejected_token_only_for_attempted_profile(media,app,monkeypatch,replacement):
 d=media.RemoteQuickConnectDialog(None,connection_only=True)
 credentials={'quickconnect_id':'fixture','nas_username':'fixture','use_device_token':True}
 # Use the exact same profile key and token lookup as production.
 key=media.nas_device_key(credentials)
 credentials['nas_device_tokens']=json.dumps({key:'rejected-token'})
 d._login_attempt_credentials=credentials
 token=media.trusted_device_id(credentials)
 assert token
 stored='replacement-token' if replacement else token
 media.config['nas_device_tokens']=json.dumps({key:stored,'other-profile':'other-token'})
 monkeypatch.setattr(media,'save_config',lambda:(True,''))
 d.id_edit.setText('edited-profile')
 d._nas_failure('K\u00e9tl\u00e9pcs\u0151s k\u00f3d sz\u00fcks\u00e9ges: fixture')
 result=json.loads(media.config['nas_device_tokens'])
 assert result.get(key)==('replacement-token' if replacement else None)
 assert result['other-profile']=='other-token'
 d.session.close();d.close()


def test_login_captures_attempted_profile_before_fields_change(media,app,monkeypatch):
 d=media.RemoteQuickConnectDialog(None,connection_only=True)
 d.id_edit.setText('fixture');d.user_edit.setText('fixture');d.pass_edit.setText('fixture');d.remember_device.setChecked(True)
 credentials={'quickconnect_id':'fixture','nas_username':'fixture'};key=media.nas_device_key(credentials)
 media.config['nas_device_tokens']=json.dumps({key:'rejected-token'})
 work=Mock();monkeypatch.setattr(d,'_start_task',work);monkeypatch.setattr(media,'save_config',lambda:(True,''))
 d.connect_nas();work.assert_called_once()
 assert media.trusted_device_id(d._login_attempt_credentials)=='rejected-token'
 d.id_edit.setText('another-profile');d._nas_failure('K\u00e9tl\u00e9pcs\u0151s k\u00f3d sz\u00fcks\u00e9ges: fixture')
 assert key not in json.loads(media.config['nas_device_tokens'])
 d._otp_once='fixture-otp';d.connect_nas()
 assert not media.trusted_device_id(d._login_attempt_credentials)
 assert d._login_attempt_credentials['otp_code']=='fixture-otp'
 d.session.close();d.close()
