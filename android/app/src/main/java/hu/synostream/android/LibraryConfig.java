package hu.synostream.android;
import org.json.*;
import java.util.*;

/** Concrete default libraries, not aliases of the first custom library. */
public final class LibraryConfig {
    public static List<String> paths(JSONObject library){
        LinkedHashSet<String> paths=new LinkedHashSet<>();JSONArray array=library.optJSONArray("paths");
        if(array!=null)for(int i=0;i<array.length();i++){String p=array.optString(i).replaceAll("/+$","");if(p.startsWith("/"))paths.add(p);}
        else {String p=library.optString("path").replaceAll("/+$","");if(p.startsWith("/"))paths.add(p);}
        return new ArrayList<>(paths);
    }
    public static void paths(JSONObject library,Collection<String> paths) throws JSONException {library.put("paths",new JSONArray(new LinkedHashSet<>(paths)));library.remove("path");}
    public static JSONArray migrate(JSONArray existing){
        try{
            List<JSONObject> objects=new ArrayList<>();Set<String> ids=new HashSet<>();
            for(int i=0;i<existing.length();i++){JSONObject original=existing.optJSONObject(i);if(original==null)continue;JSONObject copy=new JSONObject(original.toString());String id=copy.optString("id");if(id.isEmpty()||!ids.add(id)){id=UUID.randomUUID().toString();copy.put("id",id);ids.add(id);}paths(copy,paths(copy));objects.add(copy);}
            JSONArray result=new JSONArray();Set<String> used=new HashSet<>();
            for(boolean movie:List.of(true,false)){
                String title=movie?"Filmek":"TV műsorok";JSONObject chosen=null;
                for(JSONObject o:objects)if(o.optBoolean("movie",true)==movie&&o.optBoolean("builtin")&&!used.contains(o.optString("id"))){chosen=o;break;}
                if(chosen==null)for(JSONObject o:objects)if(o.optBoolean("movie",true)==movie&&MediaLogic.normalize(o.optString("name")).equals(MediaLogic.normalize(title))&&!used.contains(o.optString("id"))){chosen=o;break;}
                if(chosen==null)chosen=new JSONObject().put("id",movie?"builtin-movies":"builtin-shows").put("paths",new JSONArray());
                chosen.put("name",title).put("movie",movie).put("builtin",true);used.add(chosen.getString("id"));result.put(chosen);
                List<String> sources=new ArrayList<>(paths(chosen));
                for(JSONObject o:objects)if(!used.contains(o.optString("id"))&&o.optBoolean("movie",true)==movie&&MediaLogic.normalize(o.optString("name")).equals(MediaLogic.normalize(title))){
                    for(String path:paths(o))if(!sources.contains(path))sources.add(path);used.add(o.getString("id"));
                }
                paths(chosen,sources);
            }
            for(JSONObject o:objects)if(!used.contains(o.getString("id"))){o.put("builtin",false);result.put(o);}
            return result;
        }catch(JSONException impossible){throw new IllegalStateException(impossible);}
    }
    public static JSONObject find(JSONArray libraries,String id){for(int i=0;i<libraries.length();i++){JSONObject l=libraries.optJSONObject(i);if(l!=null&&l.optString("id").equals(id))return l;}return null;}
    public static JSONObject defaultLibrary(JSONArray libraries,boolean movie){for(int i=0;i<libraries.length();i++){JSONObject l=libraries.optJSONObject(i);if(l!=null&&l.optBoolean("builtin")&&l.optBoolean("movie",true)==movie)return l;}return null;}
    public static JSONArray replace(JSONArray libraries,JSONObject library){JSONArray out=new JSONArray();boolean found=false;for(int i=0;i<libraries.length();i++){JSONObject current=libraries.optJSONObject(i);if(current==null)continue;if(current.optString("id").equals(library.optString("id"))){out.put(library);found=true;}else out.put(current);}if(!found)out.put(library);return out;}
    public static JSONArray remove(JSONArray libraries,String id){JSONArray out=new JSONArray();for(int i=0;i<libraries.length();i++){JSONObject l=libraries.optJSONObject(i);if(l!=null&&!l.optString("id").equals(id))out.put(l);}return out;}
    public static String rootFor(JSONObject library,String path){String best=null;for(String root:paths(library))if((path.equals(root)||path.startsWith(root+"/"))&&(best==null||root.length()>best.length()))best=root;return best;}
}
