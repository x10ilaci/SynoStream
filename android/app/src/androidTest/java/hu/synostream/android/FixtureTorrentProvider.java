package hu.synostream.android;
import android.content.*;import android.database.*;import android.net.Uri;import android.os.*;import android.provider.OpenableColumns;import java.io.*;import java.nio.charset.StandardCharsets;
/** Test APK only. Serves synthetic bytes, never reads the filesystem. */
public class FixtureTorrentProvider extends ContentProvider {
 public static final String AUTHORITY="hu.synostream.android.test.torrentfixture";
 public static final byte[] BYTES="d4:infod6:lengthi1e4:name7:Fixtureee".getBytes(StandardCharsets.US_ASCII);
 public boolean onCreate(){return true;}
 static String kind(Uri uri){return uri.getLastPathSegment().split("-",2)[0];}
 public String getType(Uri uri){return kind(uri).equals("octet")||kind(uri).equals("wrong")?"application/octet-stream":"application/x-bittorrent";}
 public Cursor query(Uri uri,String[] projection,String selection,String[] args,String sort){String name=kind(uri).equals("wrong")?"other.bin":kind(uri).equals("second")?"Second.torrent":kind(uri).equals("nameless")?null:"Example.torrent";MatrixCursor cursor=new MatrixCursor(new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE});cursor.addRow(new Object[]{name,BYTES.length});return cursor;}
 public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{if(kind(uri).equals("missing"))throw new FileNotFoundException("Synthetic unavailable fixture");try{ParcelFileDescriptor[] pipe=ParcelFileDescriptor.createPipe();new Thread(()->{try(OutputStream out=new ParcelFileDescriptor.AutoCloseOutputStream(pipe[1])){out.write(kind(uri).equals("invalid")?"{\"info\":\"not a torrent\"}".getBytes(StandardCharsets.US_ASCII):BYTES);}catch(IOException ignored){}},"torrent-fixture").start();return pipe[0];}catch(IOException e){throw new FileNotFoundException("Fixture pipe unavailable");}}
 public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}public int delete(Uri uri,String s,String[] a){throw new UnsupportedOperationException();}public int update(Uri uri,ContentValues values,String s,String[] a){throw new UnsupportedOperationException();}
}
