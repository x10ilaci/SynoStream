package hu.synostream.android;
import org.json.*;import java.util.*;
/** One NAS profile; per-user data owners survive endpoint changes. Never contains passwords. */
final class NasProfile {
 interface Storage extends DownloadStation.Persistence {void replaceBrokenProfile(String recovered)throws Exception;}
 static NasProfile recover(Storage store)throws Exception{
  NasProfile recovered=new NasProfile(UUID.randomUUID().toString(),store.get("address",""),store.get("local",""),store.get("ddns",""),store.get("quick",""),new JSONObject());
  // Preserve the new identity between confirmation and a later successful login.
  // The broken key is removed, not silently interpreted as a legacy profile.
  store.replaceBrokenProfile(recovered.json("").toString());return recovered;
 }
 final String id,address,local,ddns,quick;private final JSONObject owners;
 NasProfile(String id,String a,String l,String d,String q,JSONObject o){this.id=id;address=a;local=l;ddns=d;quick=q;try{owners=new JSONObject(o.toString());}catch(JSONException invalid){throw new IllegalArgumentException(invalid);}}
 static NasProfile load(DownloadStation.Persistence store)throws JSONException{
  String saved=store.get("nas_profile","");if(!saved.isEmpty())return from(new JSONObject(saved));
  String recovered=store.get("nas_profile_recovery","");if(!recovered.isEmpty())return from(new JSONObject(recovered));
  String a=store.get("address",""),u=store.get("user","");JSONObject owners=new JSONObject();
  // Capture the old account anchor BEFORE the user edits a route. Old cache names stay valid.
  String expected=AccountIdentity.owner(a,u),legacy=store.get("libraries_owner",expected);int split=legacy.lastIndexOf('|');
  if(!a.isBlank()&&!u.isBlank()&&split>=0&&AccountIdentity.owner(legacy.substring(0,split),legacy.substring(split+1)).equals(expected))owners.put(userKey(u),expected);
  return new NasProfile(UUID.randomUUID().toString(),a,store.get("local",""),store.get("ddns",""),store.get("quick",""),owners);
 }
 static NasProfile from(JSONObject o)throws JSONException{String id=o.getString("id");try{UUID.fromString(id);}catch(IllegalArgumentException invalid){throw new JSONException("A NAS-profil nem olvasható.");}return new NasProfile(id,o.optString("address"),o.optString("local"),o.optString("ddns"),o.optString("quick"),o.getJSONObject("owners"));}
 NasProfile routes(NasClient.Credentials c){return new NasProfile(id,c.address,c.local,c.ddns,c.quick,owners);}
 String owner(String user){return owners.optString(userKey(user),"nas:"+id+"|"+userKey(user));}
 JSONObject json(String user)throws JSONException{JSONObject accounts=new JSONObject(owners.toString());if(!user.isBlank())accounts.put(userKey(user),owner(user));return new JSONObject().put("version",1).put("id",id).put("address",address).put("local",local).put("ddns",ddns).put("quick",quick).put("owners",accounts);}
 private static String userKey(String user){return user.trim().toLowerCase(Locale.ROOT);}
}
