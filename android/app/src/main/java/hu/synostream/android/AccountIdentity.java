package hu.synostream.android;
import java.util.Locale;
final class AccountIdentity {
 static String owner(String address,String user){return address.trim().toLowerCase(Locale.ROOT).replaceFirst("^https?://", "").replaceAll("/+$", "")+"|"+user.trim().toLowerCase(Locale.ROOT);}
 static void migrateKeys(DownloadStation.Persistence store,String address,String user){String target=owner(address,user),legacy=store.get("libraries_owner",address+"|"+user);int split=legacy.lastIndexOf('|');if(split<0||!owner(legacy.substring(0,split),legacy.substring(split+1)).equals(target)||legacy.equals(target))return;
  for(String prefix:new String[]{"edits:","torrent_sites:","prepared:"}){String current=store.get(prefix+target,"");if(empty(current)){String value=store.get(prefix+legacy,"");if(!value.isEmpty())store.put(prefix+target,value);}}
  try{org.json.JSONArray pending=new org.json.JSONArray(store.get("prepared:"+target,"[]"));for(int i=0;i<pending.length();i++){org.json.JSONObject item=pending.optJSONObject(i);if(item==null)continue;String suffix=":"+item.optString("list_id");if(store.get("torrent_choice:"+target+suffix,"").isEmpty()){String value=store.get("torrent_choice:"+legacy+suffix,"");if(!value.isEmpty())store.put("torrent_choice:"+target+suffix,value);}}}catch(org.json.JSONException invalid){/* Corrupt preview state is handled by DownloadStation. */}
 }
 static boolean empty(String value){if(value.trim().isEmpty())return true;try{org.json.JSONTokener parser=new org.json.JSONTokener(value);Object parsed=parser.nextValue();if(parser.nextClean()!=0)return false;return emptyValue(parsed);}catch(org.json.JSONException invalid){return false;}}
 private static boolean emptyValue(Object value){if(value instanceof org.json.JSONObject){org.json.JSONObject object=(org.json.JSONObject)value;java.util.Iterator<String> keys=object.keys();while(keys.hasNext())if(!emptyValue(object.opt(keys.next())))return false;return true;}if(value instanceof org.json.JSONArray){org.json.JSONArray array=(org.json.JSONArray)value;for(int i=0;i<array.length();i++)if(!emptyValue(array.opt(i)))return false;return true;}return value instanceof String&&((String)value).isEmpty();}
 private AccountIdentity(){}
}
