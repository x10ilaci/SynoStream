package hu.synostream.android;
import android.app.AlertDialog;import android.content.SharedPreferences;import java.util.*;
final class HttpConsentUi {
 static boolean require(MainActivity a,NasClient.Credentials c,Runnable retry){SharedPreferences p=a.getSharedPreferences("http_consent",0);List<String> pending=HttpConsent.pending(c,k->p.getBoolean(k,false));if(pending.isEmpty())return false;AlertDialog d=new AlertDialog.Builder(a).setTitle("Nem titkosított NAS-kapcsolat").setMessage("A jelszó és a munkamenet titkosítatlanul megy.").setNegativeButton("Mégse",null).setPositiveButton("Elfogadom",(dialog,which)->{SharedPreferences.Editor e=p.edit();for(String key:pending)e.putBoolean(key,true);e.apply();retry.run();}).create();a.ownDialog(d);d.show();return true;}
}
