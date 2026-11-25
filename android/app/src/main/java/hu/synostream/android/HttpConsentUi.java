package hu.synostream.android;
import android.app.AlertDialog;import android.content.SharedPreferences;import java.util.*;
final class HttpConsentUi {
 static boolean require(MainActivity a,NasClient.Credentials c,Runnable retry){SharedPreferences p=a.getSharedPreferences("http_consent",0);List<String> pending=HttpConsent.pending(c,k->p.getBoolean(k,false));if(pending.isEmpty())return false;AlertDialog d=new AlertDialog.Builder(a).setTitle(a.getString(R.string.http_consent_title)).setMessage(a.getString(R.string.http_consent_message)).setNegativeButton(a.getString(R.string.msg_cancel_b3e118),null).setPositiveButton(a.getString(R.string.http_consent_accept),(dialog,which)->{SharedPreferences.Editor e=p.edit();for(String key:pending)e.putBoolean(key,true);e.apply();retry.run();}).create();a.ownDialog(d);d.show();return true;}
}
