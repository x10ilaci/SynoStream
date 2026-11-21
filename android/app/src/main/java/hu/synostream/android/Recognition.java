package hu.synostream.android;

import org.json.*;
import java.util.*;

/** Windows matching pipeline, injectable for deterministic offline regression tests. */
public final class Recognition {
    public interface Api {JSONObject get(String endpoint,Map<String,String> params) throws Exception;}
    private final Api api;
    public final Set<Long> ambiguousIds=new LinkedHashSet<>();
    public Recognition(Api a){api=a;}
    public JSONObject details(long id,boolean movie) throws Exception {
        String endpoint=(movie?"movie/":"tv/")+id;
        JSONObject info=api.get(endpoint,Map.of("language","hu-HU"));
        if(info.optLong("id")!=id)return null;
        // Only descriptions may fall back to English; never replace the Hungarian title.
        if(info.optString("overview").isBlank()){
            try{JSONObject english=api.get(endpoint,Map.of("language","en-US"));
                if(english.optLong("id")==id)info.put("overview",english.optString("overview"));
            }catch(InterruptedException cancelled){throw cancelled;}catch(Exception optionalDescriptionUnavailable){/* Keep valid Hungarian metadata. */}
        }
        return info;
    }
    public JSONObject imdb(String identifier,boolean movie) throws Exception {
        JSONArray hits=api.get("find/"+identifier,Map.of("external_source","imdb_id","language","hu-HU")).optJSONArray(movie?"movie_results":"tv_results");
        Set<Long> ids=new LinkedHashSet<>();if(hits!=null)for(int i=0;i<hits.length();i++){JSONObject h=hits.optJSONObject(i);if(h!=null&&h.optLong("id")>0)ids.add(h.getLong("id"));}
        return ids.size()==1?details(ids.iterator().next(),movie):null;
    }
    public JSONObject find(String title,String year,boolean movie) throws Exception {
        ambiguousIds.clear();String query=MediaLogic.normalize(title);if(query.isEmpty())return null;
        LinkedHashSet<String> searchTitles=new LinkedHashSet<>();
        for(String source:List.of(title,title.replaceAll("[-–]+"," ").trim()))searchTitles.addAll(MediaLogic.titleVariants(source));
        Map<Long,JSONObject> candidates=new LinkedHashMap<>();JSONObject best=null;
        for(String language:List.of("hu-HU","en-US")){
            for(String search:searchTitles){
                if(year!=null)collect(candidates,search,year,year,movie,language);
                collect(candidates,search,null,year,movie,language);
            }
            best=pick(candidates.values(),query,year,movie);
            if(best!=null&&names(best,movie).contains(query))break;
        }
        if(candidates.isEmpty()){
            Set<String> grammar=Set.of("the","a","an","of","and","to","in","on","at","for","with","from","by");
            List<String> content=new ArrayList<>();for(String word:title.split("\\s+"))if(!grammar.contains(MediaLogic.normalize(word)))content.add(word);
            String compact=String.join(" ",content);
            if(content.size()>=2&&!compact.equals(title))collect(candidates,compact,null,year,movie,"en-US");
            if(candidates.isEmpty()&&content.size()>=3)collect(candidates,content.get(0)+" "+content.get(content.size()-1),null,year,movie,"en-US");
        }
        if(best==null||displaySimilarity(query,best,movie)<.95){
            List<JSONObject> ranked=new ArrayList<>(candidates.values());ranked.sort(Comparator.comparingDouble((JSONObject c)->c.optDouble("vote_count",0)).reversed());
            for(JSONObject candidate:ranked.subList(0,Math.min(5,ranked.size()))){
                JSONObject alternatives=api.get((movie?"movie/":"tv/")+candidate.getLong("id")+"/alternative_titles",Map.of());
                JSONArray rows=alternatives.optJSONArray(movie?"titles":"results");if(rows==null)rows=alternatives.optJSONArray(movie?"results":"titles");
                if(rows!=null)for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null)addAlias(candidate,row.optString("title"));}
            }
        }
        best=pick(candidates.values(),query,year,movie);
        if(best==null){double top=Double.NEGATIVE_INFINITY;Map<Long,Double> reliable=new HashMap<>();for(JSONObject c:candidates.values()){Evaluation e=evaluate(c,query,year,movie);if(e.reliable){reliable.put(c.optLong("id"),e.score);top=Math.max(top,e.score);}}for(Map.Entry<Long,Double> e:reliable.entrySet())if(top-e.getValue()<1)ambiguousIds.add(e.getKey());if(ambiguousIds.size()<2)ambiguousIds.clear();}
        return best==null?null:details(best.getLong("id"),movie);
    }
    private void collect(Map<Long,JSONObject> candidates,String title,String filterYear,String expectedYear,boolean movie,String language) throws Exception {
        Map<String,String> params=new HashMap<>(Map.of("query",title,"language",language));if(filterYear!=null)params.put(movie?"primary_release_year":"first_air_date_year",filterYear);
        JSONArray rows=api.get("search/"+(movie?"movie":"tv"),params).optJSONArray("results");if(rows==null)return;
        for(int i=0;i<rows.length();i++){
            JSONObject row=rows.optJSONObject(i);if(row==null||row.optLong("id")<=0||movie&&!MediaLogic.nearYear(row.optString("release_date"),expectedYear))continue;
            long id=row.getLong("id");JSONObject existing=candidates.get(id);
            if(existing==null)candidates.put(id,new JSONObject(row.toString()));
            else for(String key:List.of("title","original_title","name","original_name"))addAlias(existing,row.optString(key));
        }
    }
    private static void addAlias(JSONObject candidate,String value) throws JSONException {if(value.isEmpty())return;JSONArray aliases=candidate.optJSONArray("_matching_aliases");if(aliases==null){aliases=new JSONArray();candidate.put("_matching_aliases",aliases);}aliases.put(value);}
    private static Set<String> names(JSONObject candidate,boolean movie){Set<String> names=new HashSet<>();names.add(MediaLogic.normalize(candidate.optString(movie?"title":"name")));names.add(MediaLogic.normalize(candidate.optString(movie?"original_title":"original_name")));JSONArray aliases=candidate.optJSONArray("_matching_aliases");if(aliases!=null)for(int i=0;i<aliases.length();i++)names.add(MediaLogic.normalize(aliases.optString(i)));return names;}
    private static double displaySimilarity(String query,JSONObject candidate,boolean movie){return Math.max(MediaLogic.similarity(query,candidate.optString(movie?"title":"name")),MediaLogic.similarity(query,candidate.optString(movie?"original_title":"original_name")));}
    public static final class Evaluation {public final boolean reliable;public final double score;Evaluation(boolean r,double s){reliable=r;score=s;}}
    public static Evaluation evaluate(JSONObject candidate,String query,String year,boolean movie){
        Set<String> variants=new HashSet<>();for(String value:MediaLogic.titleVariants(query))variants.add(MediaLogic.normalize(value));
        Set<String> names=names(candidate,movie);double similarity=0;for(String value:variants)for(String name:names)similarity=Math.max(similarity,MediaLogic.similarity(value,name));
        boolean exact=false;for(String value:variants)if(names.contains(value))exact=true;
        String date=candidate.optString(movie?"release_date":"first_air_date");boolean exactYear=year!=null&&date.startsWith(year);
        double score=similarity*30+(exact?3:0)+(exactYear?2:0)+Math.min(5,Math.log10(1+Math.max(0,candidate.optDouble("vote_count",0)))*2);
        boolean reliable=similarity>=.76||exactYear&&similarity>=.72;
        if(movie){
            if(!MediaLogic.nearYear(date,year))reliable=false;
            if(!query.contains(" ")&&query.length()<=4&&!query.equals(MediaLogic.normalize(candidate.optString("title")))&&!query.equals(MediaLogic.normalize(candidate.optString("original_title"))))reliable=false;
        }
        return new Evaluation(reliable,score);
    }
    public static JSONObject pick(Collection<JSONObject> candidates,String query,String year,boolean movie){
        JSONObject best=null;double first=Double.NEGATIVE_INFINITY,second=Double.NEGATIVE_INFINITY;
        for(JSONObject candidate:candidates){Evaluation e=evaluate(candidate,query,year,movie);if(!e.reliable)continue;if(e.score>first){second=first;first=e.score;best=candidate;}else second=Math.max(second,e.score);}
        if(best==null)return null;
        if(first-second>=1)return best;
        // With an explicit year, matching BOTH original and localized titles is
        // additional evidence. Resolve only a unique corroborated top contender.
        // Two genuinely identical namesakes remain ambiguous.
        if(year!=null){
            JSONObject corroborated=null;int count=0;
            for(JSONObject c:candidates){Evaluation e=evaluate(c,query,year,movie);if(!e.reliable||first-e.score>=1)continue;
                if(c.optString(movie?"release_date":"first_air_date").startsWith(year)
                    &&MediaLogic.normalize(c.optString(movie?"title":"name")).equals(query)
                    &&MediaLogic.normalize(c.optString(movie?"original_title":"original_name")).equals(query)){corroborated=c;count++;}
            }
            if(count==1)return corroborated;
        }
        return null;
    }
}
