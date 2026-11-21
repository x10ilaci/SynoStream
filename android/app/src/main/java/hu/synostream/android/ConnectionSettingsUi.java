package hu.synostream.android;
import android.app.*;import android.content.*;import android.view.*;import android.widget.*;import java.util.*;import java.util.concurrent.*;import java.util.concurrent.atomic.*;
final class ConnectionSettingsUi {
 private final MainActivity a;private final SynoApp s;private EditText address,local,ddns,quick,user,password,otp;private CheckBox remember;private LinearLayout advanced;private Dialog dialog;private long session;
 ConnectionSettingsUi(MainActivity activity){a=activity;s=a.s;}
 void show(){
  ConnectionDraft draft=s.connectionDraft;
  try{if(!draft.open){draft.profile=NasProfile.load(s.store);draft.credentials=s.client==null?s.store.credentials():s.client.settingsCredentials().withoutOtp();draft.remember=!s.store.secret("password").isEmpty();draft.expanded=draft.credentials.address.isBlank()&&(!draft.credentials.local.isBlank()||!draft.credentials.ddns.isBlank()||!draft.credentials.quick.isBlank());draft.begin();}}catch(Exception invalid){a.toast(SynoApp.safeError(invalid));return;}
  session=draft.generation;NasClient.Credentials c=draft.credentials;dialog=a.screenDialog();LinearLayout root=a.column();root.addView(a.dialogBar(a.getString(R.string.connection_profile_title),dialog::dismiss),a.lp(-1,52));ScrollView scroll=new ScrollView(a);LinearLayout form=a.column();form.setPadding(a.dp(16),0,a.dp(16),a.dp(16));scroll.addView(form);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
  address=a.input(form,a.getString(R.string.msg_nas_address_or_quickconnect_id_2e823a),R.id.profile_address,false);address.setText(c.address);
  user=a.input(form,a.getString(R.string.msg_username_fc62d7),R.id.profile_user,false);user.setText(c.user);user.setEnabled(s.client==null);
  password=a.input(form,a.getString(R.string.msg_password_5737d7),R.id.profile_password,true);password.setText(c.password);
  remember=new CheckBox(a);remember.setId(R.id.profile_remember);remember.setText(a.getString(R.string.msg_remember_me_28282a));remember.setTextColor(MainActivity.TEXT);remember.setChecked(draft.remember);form.addView(remember,a.lp(-1,48));
  advanced=a.column();advanced.setVisibility(draft.expanded?View.VISIBLE:View.GONE);
  Button more=a.button(a.getString(R.string.connection_more),()->{advanced.setVisibility(advanced.getVisibility()==View.GONE?View.VISIBLE:View.GONE);draft.expanded=advanced.getVisibility()==View.VISIBLE;});more.setId(R.id.profile_more);form.addView(more,a.lp(-1,48));form.addView(advanced);
  local=a.input(advanced,a.getString(R.string.msg_local_nas_address_optional_66fa40),R.id.profile_local,false);local.setText(c.local);local.setHint(a.getString(R.string.connection_local_example));
  ddns=a.input(advanced,a.getString(R.string.connection_ddns_optional),R.id.profile_ddns,false);ddns.setText(c.ddns);ddns.setHint(a.getString(R.string.connection_ddns_example));
  quick=a.input(advanced,a.getString(R.string.connection_quick_optional),R.id.profile_quick,false);quick.setText(c.quick);
  otp=a.input(advanced,a.getString(R.string.msg_two_step_code_if_requested_by_the_nas_35aa54),R.id.profile_otp,false);otp.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);
  TextView priority=a.text(a.getString(R.string.connection_priority),13,MainActivity.MUTED);priority.setPadding(0,a.dp(8),0,a.dp(8));form.addView(priority,a.lp(-1,-2));
  Button test=a.button(a.getString(R.string.connection_test),()->check(a,values()));test.setId(R.id.profile_test);form.addView(test,a.lp(-1,52));
  Button save=a.button(a.getString(R.string.connection_save),()->{capture();a.connectProfile(draft.profile.routes(values()),values(),remember.isChecked(),()->dialog.dismiss());});save.setId(R.id.profile_save);form.addView(save,a.lp(-1,52));
  dialog.setOnDismissListener(d->{if(!a.isChangingConfigurations()&&draft.current(session))draft.close();});a.showScreen(dialog,root);
 }
 private NasClient.Credentials values(){return new NasClient.Credentials(address.getText().toString(),local.getText().toString(),ddns.getText().toString(),quick.getText().toString(),user.getText().toString(),password.getText().toString(),otp.getText().toString());}
 void saved(){if(dialog!=null&&dialog.isShowing())dialog.dismiss();}
 void capture(){if(address!=null&&s.connectionDraft.current(session)){s.connectionDraft.credentials=values().withoutOtp();s.connectionDraft.remember=remember.isChecked();s.connectionDraft.expanded=advanced.getVisibility()==View.VISIBLE;}}
 static String kind(MainActivity a,NasRoutes.Kind kind){switch(kind){case LOCAL:return a.getString(R.string.connection_mode_local);case DDNS:return a.getString(R.string.connection_mode_ddns);case QUICKCONNECT:return "QuickConnect";default:return a.getString(R.string.msg_direct_connection_51a846);}}
 static void check(MainActivity a,NasClient.Credentials c){
  try{NasRoutes.plan(c,true);if(c.user.isBlank()||c.password.isEmpty()){a.toast(a.getString(R.string.connection_required_fields));return;}}catch(Exception invalid){a.toast(SynoApp.safeError(invalid));return;}
  ProgressDialog progress=new ProgressDialog(a);a.ownDialog(progress);progress.setMessage(a.getString(R.string.connection_checking));progress.setCancelable(true);AtomicBoolean cancelled=new AtomicBoolean();AtomicReference<Future<?>> job=new AtomicReference<>();
  progress.setOnDismissListener(d->{cancelled.set(true);Future<?> f=job.get();if(f!=null)f.cancel(true);});progress.show();boolean allowLocal=a.s.allowLocalNetwork();
  Future<?> future=a.s.profileIo.submit(()->{List<NasClient.ConnectionCheck> results=null;try{results=new NasClient(c.withoutOtp()).checkConnections(allowLocal);}catch(Exception unavailable){/* Canceled/invalid checks never affect the active connection. */}List<NasClient.ConnectionCheck> rows=results;a.s.main.post(()->{
   if(a.isDestroyed()||a.isFinishing()||cancelled.get())return;progress.dismiss();if(rows==null){a.toast(a.getString(R.string.connection_check_failed));return;}
   StringBuilder text=new StringBuilder();for(NasClient.ConnectionCheck row:rows){int label;switch(row.status){case SUCCESS:label=R.string.connection_check_success;break;case CODE_REQUIRED:label=R.string.connection_check_code_required;break;case AUTH_FAILED:label=R.string.connection_check_auth;break;case SKIPPED:label=R.string.connection_check_skipped;break;default:label=R.string.connection_check_unavailable;}
    if(text.length()>0)text.append("\n\n");text.append(kind(a,row.kind)).append(": ").append(a.getString(label));}
   AlertDialog result=new AlertDialog.Builder(a).setTitle(a.getString(R.string.connection_test)).setMessage(text.toString()).setPositiveButton(android.R.string.ok,null).create();a.ownDialog(result);result.show();
  });});job.set(future);if(cancelled.get())future.cancel(true);
 }
}
