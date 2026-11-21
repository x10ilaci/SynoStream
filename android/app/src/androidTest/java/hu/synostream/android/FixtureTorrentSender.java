package hu.synostream.android;
import android.app.*;import android.content.*;import android.net.Uri;import android.os.Bundle;
/** Separate test-app UID supplies the temporary URI grant, just like a file manager. */
public class FixtureTorrentSender extends Activity {
 @Override public void onCreate(Bundle state){super.onCreate(state);String kind=getIntent().getStringExtra("kind");if(kind==null)kind="ok";Uri uri=Uri.parse("content://"+FixtureTorrentProvider.AUTHORITY+"/document/"+kind+"-"+System.nanoTime());boolean share=getIntent().getBooleanExtra("share",false);Intent out=new Intent(share?Intent.ACTION_SEND:Intent.ACTION_VIEW);String mime=getContentResolver().getType(uri);if(share)out.setType(mime).putExtra(Intent.EXTRA_STREAM,uri);else out.setDataAndType(uri,mime);out.setClipData(ClipData.newRawUri("Torrent fixture",uri));out.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);out.setPackage("hu.synostream.android");startActivity(out);finish();}
}
