package hu.synostream.android;
import java.util.*;import org.json.*;
final class PendingSync {
 interface Writer {void save(String root,String path,boolean movie,JSONObject info)throws Exception;}
 static int retry(LocalEdits edits,JSONArray libraries,Writer writer)throws Exception{int synced=0;for(Map.Entry<String,JSONObject> e:edits.overrides().entrySet()){if(Thread.currentThread().isInterrupted())throw new InterruptedException();boolean movie=e.getKey().startsWith("movie:");String path=e.getKey().substring(e.getKey().indexOf(':')+1),root=null;for(int i=0;i<libraries.length();i++){JSONObject library=libraries.getJSONObject(i);if(library.optBoolean("movie",true)==movie){root=LibraryConfig.rootFor(library,path);if(root!=null)break;}}if(root==null)continue;try{writer.save(root,path,movie,e.getValue());edits.syncedIfSame(movie,path,e.getValue());synced++;}catch(InterruptedException cancelled){throw cancelled;}catch(Exception unavailable){/* Retain the outbox entry for the next scan. */}}return synced;}
 private PendingSync(){}
}
