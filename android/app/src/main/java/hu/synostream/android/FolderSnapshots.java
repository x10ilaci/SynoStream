package hu.synostream.android;
import java.util.*;import org.json.*;
final class FolderSnapshots {
 private final JSONObject data;
 FolderSnapshots(String json){JSONObject loaded;try{loaded=new JSONObject(json);}catch(Exception invalid){loaded=new JSONObject();}data=loaded;}
 synchronized List<NasClient.Entry> get(String path,long modified,Map<String,Library.Card> previous){
  if(modified<=0)return null;JSONObject s=data.optJSONObject(path);if(s==null||s.optLong("modified")!=modified||!s.optBoolean("leaf"))return null;
  JSONArray rows=s.optJSONArray("entries"),cards=s.optJSONArray("cards");if(rows==null||cards==null||(s.optBoolean("movie",true)?cards.length()!=s.optInt("videos",-1):cards.length()!=1||s.optInt("videos",0)<1))return null;
  Set<String> expected=new HashSet<>();for(int i=0;i<cards.length();i++)expected.add(cards.optString(i));Set<String> actual=new HashSet<>();for(Library.Card c:previous.values())if(c.movie&&parent(c.path).equals(path)||!c.movie&&c.episodeRoots.contains(path))actual.add((c.movie?"movie:":"tv:")+c.path);if(!expected.equals(actual))return null;
  List<NasClient.Entry> result=new ArrayList<>();try{for(int i=0;i<rows.length();i++){JSONObject j=rows.getJSONObject(i);if(!parent(j.getString("path")).equals(path)||j.optBoolean("directory"))return null;NasClient.Entry e=new NasClient.Entry(j.getString("name"),j.getString("path"),false,j.optLong("size"));e.modified=j.optLong("modified");e.sizeKnown=j.optBoolean("known");result.add(e);}}catch(Exception invalid){return null;}return result;
 }
 synchronized void put(String path,long modified,List<NasClient.Entry> entries,List<Library.Card> cards)throws JSONException{
  if(modified<=0||entries.stream().anyMatch(e->e.directory)){data.remove(path);return;}long largest=MediaLogic.largestVideoSize(entries);int videos=0;JSONArray rows=new JSONArray(),paths=new JSONArray();for(NasClient.Entry e:entries){if(MediaLogic.video(e.name)&&!MediaLogic.ignored(e.name)&&!MediaLogic.sampleEntry(e,largest))videos++;rows.put(new JSONObject().put("name",e.name).put("path",e.path).put("directory",false).put("size",e.size).put("known",e.sizeKnown).put("modified",e.modified));}boolean movie=true;for(Library.Card c:cards)if(c.movie&&parent(c.path).equals(path)||!c.movie&&c.episodeRoots.contains(path)){paths.put((c.movie?"movie:":"tv:")+c.path);movie=c.movie;}if(movie?videos!=paths.length():paths.length()!=1||videos<1){data.remove(path);return;}
  data.put(path,new JSONObject().put("modified",modified).put("leaf",true).put("movie",movie).put("videos",videos).put("entries",rows).put("cards",paths));
 }
 static String parent(String path){int n=path.lastIndexOf('/');return n<=0?"/":path.substring(0,n);}
 public synchronized String toString(){return data.toString();}
}
