package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;import org.json.*;import java.util.*;
public class CorrectionJournalTest {
 @Test public void scanCannotOverwriteCorrectionCompletedDuringScan()throws Exception{CorrectionJournal journal=new CorrectionJournal();long started=journal.revision();Library.Card scanned=new Library.Card("/video/a.mkv","Régi",true);journal.record(true,scanned.path,new JSONObject().put("id",99).put("title","Kézi javítás"));assertTrue(journal.applyAfter(List.of(scanned),started));assertEquals("Kézi javítás",scanned.title);assertEquals(99,scanned.id);}
 @Test public void oldLocalChangesDoNotOverrideNewSharedScan()throws Exception{CorrectionJournal journal=new CorrectionJournal();journal.record(true,"/video/a.mkv",new JSONObject().put("id",1));long started=journal.revision();Library.Card shared=new Library.Card("/video/a.mkv","Másik gép javítása",true);shared.id=2;assertFalse(journal.applyAfter(List.of(shared),started));assertEquals(2,shared.id);}
}
