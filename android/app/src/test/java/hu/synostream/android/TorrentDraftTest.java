package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;
public class TorrentDraftTest {
 @Test public void newDraftCannotSubmitPreviouslyPickedFile(){TorrentDraft d=new TorrentDraft();d.reset();d.bytes=new byte[]{1};d.filename="old.torrent";d.destination="video";d.close();d.reset();assertNull(d.bytes);assertEquals("",d.filename);assertEquals("",d.destination);assertFalse(d.fileTab);assertTrue(d.open);}
 @Test public void activityRecreationCanReuseOpenDraft(){TorrentDraft d=new TorrentDraft();d.reset();d.link="magnet:test";d.fileTab=true;TorrentDraft restored=d;assertTrue(restored.open);assertTrue(restored.fileTab);assertEquals("magnet:test",restored.link);}
}
