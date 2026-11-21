package hu.synostream.android;
import org.junit.*;
import org.json.*;
import static org.junit.Assert.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
public class PairingsTest {
    static JSONObject event(String id,String path,long tmdb,long generation) throws Exception {return new JSONObject().put("format_version",1).put("event_id",id).put("relative_path",path).put("media_type","movie").put("tmdb_id",tmdb).put("title","Magyar cím").put("deleted",false).put("generation",generation).put("created_ns",1_700_000_000_000_000_000L);}
    static byte[] bytes(JSONObject j){return j.toString().getBytes(StandardCharsets.UTF_8);}
    private final String a="00000000000000000000000000000001",b="00000000000000000000000000000002";
    @Test public void generationThenEventIdDeterminesWinner() throws Exception {Pairings p=new Pairings();p.add(b+".json",bytes(event(b,"Film.mkv",2,1)));p.add(a+".json",bytes(event(a,"Film.mkv",1,2)));assertEquals(1,p.get("/video","/video/Film.mkv",true).getLong("tmdb_id"));p=new Pairings();p.add(a+".json",bytes(event(a,"Film.mkv",1,1)));p.add(b+".json",bytes(event(b,"Film.mkv",2,1)));assertEquals(2,p.get("/video","/video/Film.mkv",true).getLong("tmdb_id"));}
    @Test public void deletionDoesNotResurrectOlderPairing() throws Exception {Pairings p=new Pairings();p.add(a+".json",bytes(event(a,"Film.mkv",1,1)));p.add(b+".json",bytes(event(b,"Film.mkv",2,2).put("deleted",true).put("tmdb_id",JSONObject.NULL)));assertTrue(p.get("/video","/video/Film.mkv",true).getBoolean("deleted"));}
    @Test public void malformedOrForeignSchemaCannotOverrideValidEvent() throws Exception {for(String key:List.of("format_version","event_id","relative_path","media_type","tmdb_id","title","deleted","generation","created_ns")){JSONObject j=event(a,"Film.mkv",1,1);j.remove(key);assertNull(key,Pairings.validate(a+".json",bytes(j)));}assertNull(Pairings.validate(b+".json",bytes(event(a,"Film.mkv",1,1))));assertNull(Pairings.validate(a+".json",bytes(event(a,"Film.mkv",1,1).put("foreign","field"))));}
    @Test public void unsafeRelativePathsRejected() throws Exception {for(String path:List.of("../file","a/../file","a//file","a/./file","C:/file","/file","a\\file",".SyNoStReAm/file","a\nfile","."))assertNull(path,Pairings.validate(a+".json",bytes(event(a,path,1,1))));}
    @Test public void typesAndLimitsMatchWindows() throws Exception {for(JSONObject bad:List.of(event(a,"f",1,1).put("tmdb_id",true),event(a,"f",1,1).put("generation",1.5),event(a,"f",1,1).put("format_version","1"),event(a,"f",1,1).put("title","bad\nname"),event(a,"f",1,1).put("deleted",true),event(a,"f",1,1).put("created_ns",-1),event(a,"f",1,1).put("tmdb_id",10_000_000_000L)))assertNull(Pairings.validate(a+".json",bytes(bad)));}
    @Test public void rootPairingOnlyAllowedForTv() throws Exception {assertNotNull(Pairings.validate(a+".json",bytes(event(a,".",1,1).put("media_type","tv"))));}
    @Test public void invalidRecordCannotReplaceExistingWinner() throws Exception {Pairings p=new Pairings();p.add(a+".json",bytes(event(a,"f",1,1)));p.add(b+".json",bytes(event(b,"f",99,100).put("title","bad\nname")));assertEquals(1,p.get("/video","/video/f",true).getLong("tmdb_id"));assertEquals(1,p.invalid);}
}
