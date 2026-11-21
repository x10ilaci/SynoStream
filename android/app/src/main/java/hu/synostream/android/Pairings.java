package hu.synostream.android;

import org.json.*;
import java.util.*;
import java.nio.charset.StandardCharsets;

/** Read-only Windows pairing events. Invalid records never override valid events. */
public final class Pairings {
    public final Map<String,JSONObject> winners=new HashMap<>();
    public int events=0,invalid=0;
    public static JSONObject validate(String filename,byte[] bytes){
        if(bytes.length>16384)return null;
        try{
            JSONObject j=new JSONObject(StandardCharsets.UTF_8.newDecoder().decode(java.nio.ByteBuffer.wrap(bytes)).toString());
            Set<String> required=Set.of("format_version","event_id","relative_path","media_type","tmdb_id","title","deleted","generation","created_ns");
            Set<String> actual=new HashSet<>();j.keys().forEachRemaining(actual::add);
            if(!actual.equals(required)||!integer(j.opt("format_version"))||j.getLong("format_version")!=1)return null;
            if(!(j.opt("event_id") instanceof String)||!j.getString("event_id").matches("[0-9a-f]{32}")||!filename.equals(j.getString("event_id")+".json"))return null;
            if(!(j.opt("relative_path") instanceof String)||!MediaLogic.safeRelative(j.getString("relative_path")))return null;
            String relative=j.getString("relative_path"),type=j.optString("media_type");if(!StandardCharsets.UTF_8.newEncoder().canEncode(relative))return null;
            if(!Set.of("movie","tv").contains(type)||relative.equals(".")&&type.equals("movie"))return null;
            if(!(j.opt("deleted") instanceof Boolean)||!integer(j.opt("generation"))||j.getLong("generation")<1||j.getLong("generation")>1_000_000_000)return null;
            if(!integer(j.opt("created_ns"))||j.getLong("created_ns")<0)return null;
            if(!(j.opt("title") instanceof String)||j.getString("title").length()>1000||java.util.regex.Pattern.compile("[\\x00-\\x1f]").matcher(j.getString("title")).find())return null;
            if(!StandardCharsets.UTF_8.newEncoder().canEncode(j.getString("title")))return null;
            if(j.getBoolean("deleted")){if(!j.isNull("tmdb_id"))return null;}
            else if(!integer(j.opt("tmdb_id"))||j.getLong("tmdb_id")<=0||j.getLong("tmdb_id")>=10_000_000_000L)return null;
            return j;
        }catch(Exception invalid){return null;}
    }
    private static boolean integer(Object value){return value instanceof Integer||value instanceof Long;}
    public void add(String filename,byte[] bytes){JSONObject event=validate(filename,bytes);if(event==null){invalid++;return;}events++;
        String key=event.optString("media_type")+":"+event.optString("relative_path");JSONObject previous=winners.get(key);
        if(previous==null||event.optLong("generation")>previous.optLong("generation")||event.optLong("generation")==previous.optLong("generation")&&event.optString("event_id").compareTo(previous.optString("event_id"))>0)winners.put(key,event);
    }
    public JSONObject get(String root,String path,boolean movie){return winners.get((movie?"movie:":"tv:")+MediaLogic.relative(root,path));}
}
