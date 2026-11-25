package hu.synostream.android;
import java.util.*;import java.nio.charset.StandardCharsets;import java.security.*;import org.json.*;
final class PairingGenerationIndex {
 interface Read {byte[] bytes(NasClient.Entry entry)throws Exception;}
 static final class Value {final long modified,size,generation;final String key;Value(NasClient.Entry e,JSONObject event){modified=e.modified;size=e.size;generation=event==null?0:event.optLong("generation");key=event==null?"":identity(event.optString("relative_path"),event.optString("media_type"));}}
 private final Map<String,Map<String,Value>> scopes=new HashMap<>();
 static String identity(String relative,String type){try{byte[] bytes=MessageDigest.getInstance("SHA-256").digest((relative+"\0"+type).getBytes(StandardCharsets.UTF_8));return java.util.Base64.getEncoder().encodeToString(bytes);}catch(NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}}
 synchronized long generation(String owner,List<NasClient.Entry> entries,String relative,boolean movie,Read read)throws Exception{Map<String,Value> known=scopes.computeIfAbsent(owner,k->new HashMap<>());Set<String> present=new HashSet<>();long max=0;String target=identity(relative,movie?"movie":"tv");for(NasClient.Entry e:entries){if(e.directory||!e.name.matches("[0-9a-f]{32}\\.json")||e.size>16384)continue;present.add(e.path);Value value=known.get(e.path);if(e.modified<=0||value==null||value.modified!=e.modified||value.size!=e.size){JSONObject event=Pairings.validate(e.name,read.bytes(e));value=new Value(e,event);if(e.modified>0)known.put(e.path,value);else known.remove(e.path);}if(target.equals(value.key))max=Math.max(max,value.generation);}known.keySet().retainAll(present);return max;}
}
