package hu.synostream.android;
import org.json.*;import java.security.MessageDigest;import java.nio.charset.StandardCharsets;
/** Stable cache identity; display names are deliberately not part of the key. */
final class CacheKeys {
 static String fileName(String owner,JSONObject library)throws Exception{String key=owner+":recognition-v3:"+library.getString("id")+":"+library.optBoolean("movie",true)+":"+new JSONArray(LibraryConfig.paths(library)).toString();byte[] hash=MessageDigest.getInstance("SHA-256").digest(key.getBytes(StandardCharsets.UTF_8));StringBuilder name=new StringBuilder();for(byte value:hash)name.append(String.format("%02x",value));return name+".json";}
 static boolean changed(String owner,JSONObject before,JSONObject after)throws Exception{return before==null||!fileName(owner,before).equals(fileName(owner,after));}
 private CacheKeys(){}
}
