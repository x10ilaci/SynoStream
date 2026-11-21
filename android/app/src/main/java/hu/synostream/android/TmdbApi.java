package hu.synostream.android;

import org.json.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Public TMDB response cache; cache keys never include API credentials. */
public final class TmdbApi implements Recognition.Api {
    public interface Cache {JSONObject get(String key,long ttl);void put(String key,JSONObject value);}
    private final String baseUrl;private final String apiKey;private final Cache disk;
    private final Map<String,JSONObject> memory=new HashMap<>();
    public int requests=0,cacheHits=0;
    public TmdbApi(String key,Cache cache){this(key,cache,"https://api.themoviedb.org/3/");}
    TmdbApi(String key,Cache cache,String base){apiKey=key;disk=cache;baseUrl=base;}
    @Override public JSONObject get(String endpoint,Map<String,String> parameters) throws Exception {
        if(Thread.currentThread().isInterrupted())throw new InterruptedException();
        String cacheKey="recognition-v2:"+endpoint+"?"+NasClient.form(new TreeMap<>(parameters));
        JSONObject value=memory.get(cacheKey);
        if(value==null&&disk!=null)value=disk.get(cacheKey,endpoint.startsWith("search/")?3600000L:7*86400000L);
        if(value!=null){cacheHits++;memory.put(cacheKey,value);return new JSONObject(value.toString());}
        Map<String,String> params=new TreeMap<>(parameters);params.put("api_key",apiKey);
        HttpURLConnection c=(HttpURLConnection)new URL(baseUrl+endpoint+"?"+NasClient.form(params)).openConnection();
        c.setConnectTimeout(10000);c.setReadTimeout(15000);c.setRequestProperty("User-Agent","SynoStreamAndroid/"+BuildConfig.VERSION_NAME);
        try{
            requests++;int status=c.getResponseCode();
            if(status==404)return new JSONObject(); // Do not permanently cache missing/deleted IDs.
            if(status==401||status==403)throw new java.io.IOException("A TMDB elutasította a lekérést. Ellenőrizd az API-kulcsot.");
            if(status==429)throw new java.io.IOException("A TMDB túl sok kérést kapott, próbáld később.");
            if(status!=200)throw new java.io.IOException("A TMDB-lekérés átmenetileg nem sikerült ("+status+"). Újrapróbálható.");
            value=new JSONObject(new String(NasClient.readBounded(c.getInputStream(),2*1024*1024),StandardCharsets.UTF_8));
            if(value.has("success")&&!value.optBoolean("success"))throw new java.io.IOException("A TMDB elutasította a lekérést. Ellenőrizd az API-kulcsot.");
            memory.put(cacheKey,new JSONObject(value.toString()));if(disk!=null)disk.put(cacheKey,value);
            return value;
        }finally{c.disconnect();}
    }
}
