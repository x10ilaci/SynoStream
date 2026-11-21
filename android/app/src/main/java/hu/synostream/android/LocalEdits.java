package hu.synostream.android;
import org.json.*;
import java.util.*;

/** Local hide/merge settings and pending metadata; never deletes NAS media. */
public final class LocalEdits {
    private final JSONObject data;
    public LocalEdits(String json){JSONObject value;try{value=new JSONObject(json);}catch(Exception invalid){value=new JSONObject();}data=value;}
    @Override public synchronized String toString(){return data.toString();}
    private JSONObject object(String name){JSONObject o=data.optJSONObject(name);if(o==null){o=new JSONObject();try{data.put(name,o);}catch(JSONException e){throw new IllegalStateException(e);}}return o;}
    private static String key(boolean movie,String path){return (movie?"movie:":"tv:")+path;}
    public synchronized void hide(Library.Card card) throws JSONException {object("hidden").put(key(card.movie,card.path),card.title);for(String path:card.episodeRoots)object("hidden").put(key(false,path),card.title);}
    public synchronized void restore(String key){object("hidden").remove(key);}
    public synchronized JSONObject hidden(){return object("hidden");}
    public synchronized void manual(boolean movie,String path,JSONObject info) throws JSONException {object("manual").put(key(movie,path),info);}
    public synchronized void syncedIfSame(boolean movie,String path,JSONObject expected){JSONObject current=object("manual").optJSONObject(key(movie,path));if(current!=null&&current.toString().equals(expected.toString()))synced(movie,path);}
    public synchronized void synced(boolean movie,String path){object("manual").remove(key(movie,path));}
    public synchronized Map<String,JSONObject> overrides(){Map<String,JSONObject> out=new HashMap<>();JSONObject records=object("manual");Iterator<String> keys=records.keys();while(keys.hasNext()){String key=keys.next();JSONObject value=records.optJSONObject(key);if(value!=null)out.put(key,value);}return out;}
    private static List<String> members(Library.Card card){return card.memberPaths.isEmpty()?List.of(card.path):card.memberPaths;}
    public synchronized void merge(String libraryId,Library.Card source,Library.Card target) throws JSONException {
        if(source.movie||target.movie||source.path.equals(target.path))throw new IllegalArgumentException("Csak külön sorozatkártyák vonhatók össze.");
        List<String> all=new ArrayList<>(members(target));for(String path:members(source))if(!all.contains(path))all.add(path);
        JSONObject groups=object("groups");List<String> discard=new ArrayList<>();Iterator<String> keys=groups.keys();while(keys.hasNext()){String id=keys.next();JSONObject group=groups.optJSONObject(id);if(group!=null&&group.optString("library").equals(libraryId)){JSONArray paths=group.optJSONArray("members");if(paths!=null)for(int i=0;i<paths.length();i++)if(all.contains(paths.optString(i))){discard.add(id);break;}}}for(String id:discard)groups.remove(id);
        groups.put(UUID.randomUUID().toString(),new JSONObject().put("library",libraryId).put("target",target.path).put("members",new JSONArray(all)));
    }
    public synchronized void deletedMedia(java.util.function.Predicate<String> removed)throws JSONException {
        for(String name:List.of("manual","hidden")){JSONObject values=object(name);List<String> discard=new ArrayList<>();Iterator<String> keys=values.keys();while(keys.hasNext()){String key=keys.next();int colon=key.indexOf(':');if(colon>=0&&removed.test(key.substring(colon+1)))discard.add(key);}for(String key:discard)values.remove(key);}
        JSONObject groups=object("groups");List<String> discard=new ArrayList<>();Iterator<String> ids=groups.keys();while(ids.hasNext()){String id=ids.next();JSONObject group=groups.optJSONObject(id);if(group==null)continue;JSONArray members=group.optJSONArray("members");if(members==null)continue;List<String> kept=new ArrayList<>();for(int i=0;i<members.length();i++)if(!removed.test(members.optString(i)))kept.add(members.optString(i));if(kept.size()<2){discard.add(id);continue;}group.put("members",new JSONArray(kept));if(!kept.contains(group.optString("target")))group.put("target",kept.get(0));}for(String id:discard)groups.remove(id);
    }
    public synchronized void unmerge(String group){object("groups").remove(group);}
    public synchronized List<Library.Card> apply(List<Library.Card> input,String libraryId){
        List<Library.Card> out=new ArrayList<>();JSONObject hidden=object("hidden");
        for(Library.Card original:input){boolean excluded=hidden.has(key(original.movie,original.path));for(String root:original.episodeRoots)excluded|=hidden.has(key(false,root));if(excluded)continue;
            try{Library.Card c=Library.Card.from(original.json());c.memberPaths.clear();c.memberPaths.add(c.path);c.manualGroupId="";JSONObject override=object("manual").optJSONObject(key(c.movie,c.path));if(override!=null)Library.apply(c,override);out.add(c);}catch(JSONException invalid){throw new IllegalStateException(invalid);}
        }
        JSONObject groups=object("groups");Iterator<String> ids=groups.keys();while(ids.hasNext()){
            String id=ids.next();JSONObject group=groups.optJSONObject(id);if(group==null||!group.optString("library").equals(libraryId))continue;
            JSONArray paths=group.optJSONArray("members");if(paths==null)continue;Set<String> wanted=new HashSet<>();for(int i=0;i<paths.length();i++)wanted.add(paths.optString(i));
            Library.Card target=null;List<Library.Card> selected=new ArrayList<>();for(Library.Card c:out)if(!c.movie&&wanted.contains(c.path)){selected.add(c);if(c.path.equals(group.optString("target")))target=c;}
            if(target==null||selected.size()<2)continue;
            target.manualGroupId=id;target.memberPaths.clear();target.episodeRoots.clear();
            for(Library.Card c:selected){target.memberPaths.add(c.path);Library.Card raw=null;for(Library.Card r:input)if(r.path.equals(c.path)&&!r.movie){raw=r;break;}if(raw!=null){List<String> roots=raw.episodeRoots.isEmpty()?List.of(raw.path):raw.episodeRoots;for(String root:roots)if(!target.episodeRoots.contains(root))target.episodeRoots.add(root);}}
            for(Library.Card c:selected)if(c!=target)out.remove(c);
        }
        out.sort(Comparator.comparing(c->MediaLogic.normalize(c.title)));return out;
    }
}
