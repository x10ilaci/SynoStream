package hu.synostream.android;
import org.json.*;import org.junit.Test;import static org.junit.Assert.*;import java.io.*;
public class PendingSyncTest {
 JSONArray libraries()throws Exception{return new JSONArray().put(new JSONObject().put("id","movies").put("movie",true).put("paths",new JSONArray().put("/video")));}
 @Test public void retriesAfterFailureAndOnlyClearsSuccessfulWrites()throws Exception{LocalEdits edits=new LocalEdits("{}");edits.manual(true,"/video/a.mkv",new JSONObject().put("id",1));assertEquals(0,PendingSync.retry(edits,libraries(),(r,p,m,i)->{throw new IOException("offline");}));assertEquals(1,edits.overrides().size());LocalEdits restart=new LocalEdits(edits.toString());assertEquals(1,PendingSync.retry(restart,libraries(),(r,p,m,i)->assertEquals("/video",r)));assertTrue(new LocalEdits(restart.toString()).overrides().isEmpty());}
 @Test public void newerCorrectionDuringWriteSurvives()throws Exception{LocalEdits edits=new LocalEdits("{}");edits.manual(true,"/video/a.mkv",new JSONObject().put("id",1));PendingSync.retry(edits,libraries(),(r,p,m,i)->edits.manual(m,p,new JSONObject().put("id",2)));assertEquals(2,edits.overrides().get("movie:/video/a.mkv").getInt("id"));}
}
