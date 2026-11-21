package hu.synostream.android;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import android.content.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import static org.junit.Assert.*;
@RunWith(AndroidJUnit4.class)
public class LiveLibraryTest {
    private void write(File report,JSONObject data) throws Exception {try(FileOutputStream out=new FileOutputStream(report)){out.write(data.toString().getBytes(StandardCharsets.UTF_8));}}
    @Test public void optionalFullLibraryReadOnlyAudit() throws Exception {
        Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();File fixture=new File(context.getFilesDir(),"test_library.json");
        Assume.assumeTrue("No private NAS fixture injected",fixture.exists());
        JSONObject input;try{input=new JSONObject(new String(NasClient.readBounded(new FileInputStream(fixture),2*1024*1024),StandardCharsets.UTF_8));}finally{fixture.delete();}
        File report=new File(context.getFilesDir(),"audit020.json");JSONObject audit=new JSONObject().put("complete",false);JSONArray results=new JSONArray();audit.put("roots",results);write(report,audit);
        NasClient client=new NasClient(new NasClient.Credentials(input.getString("address"),"",input.getString("user"),input.getString("password"),""));
        int mismatches=0,errors=0;
        try{
            client.connect();audit.put("login",true);
            JSONArray roots=input.getJSONArray("roots");int rootIndex=0;
            for(int i=0;i<roots.length();i++){
                JSONObject root=roots.getJSONObject(i);String path=root.getString("path");boolean movie=root.getBoolean("movie");
                JSONObject result=new JSONObject().put("movie",movie).put("index",rootIndex++);results.put(result);write(report,audit);
                try{
                    TmdbApi api=new TmdbApi(input.getString("tmdb_key"),new MetadataCache(context));Library library=new Library((Library.Source)client,api);
                    final int index=i;
                    List<Library.Card> cards=library.scan(path,movie,count->{if(count%5==0)android.util.Log.i("SynoStreamAudit","root="+index+" cards="+count);});
                    JSONArray exported=new JSONArray();Map<String,Library.Card> byPath=new HashMap<>();
                    int episodes=0,unknown=0,posters=0,descriptions=0,manual=0,nfo=0;
                    for(Library.Card card:cards){exported.put(card.json());if(!card.poster.isBlank())posters++;if(!card.overview.isBlank())descriptions++;if(card.origin.equals("manual"))manual++;if(card.origin.equals("nfo"))nfo++;byPath.put(card.path,card);for(String episodeRoot:card.episodeRoots)byPath.put(episodeRoot,card);if(!movie){List<NasClient.Entry> list=library.episodes(card.episodeRoots.isEmpty()?List.of(card.path):card.episodeRoots);episodes+=list.size();for(NasClient.Entry e:list)assertTrue(e.season>=0&&e.episode>=0);}if(card.id<=0)unknown++;}
                    JSONArray differences=new JSONArray(),titleDifferences=new JSONArray();int compared=0;
                    JSONArray expected=input.getJSONArray("expected");
                    for(int j=0;j<expected.length();j++){JSONObject e=expected.getJSONObject(j);String file=e.getString("path");if(e.getBoolean("movie")!=movie||!(file.equals(path)||file.startsWith(path+"/")))continue;
                        compared++;Library.Card actual=byPath.get(file);if(actual!=null&&actual.id==e.getLong("id")&&!actual.title.equals(e.optString("title")))titleDifferences.put(new JSONObject().put("path",file).put("expected",e.optString("title")).put("actual",actual.title));if(actual==null||actual.id!=e.getLong("id")){differences.put(new JSONObject().put("expected",e).put("actual",actual==null?JSONObject.NULL:actual.json()));mismatches++;}
                    }
                    if(posters>0){Library.Card sample=null;for(Library.Card card:cards)if(!card.poster.isBlank()){sample=card;break;}java.net.HttpURLConnection connection=(java.net.HttpURLConnection)new java.net.URL(sample.poster).openConnection();connection.setConnectTimeout(10000);connection.setReadTimeout(15000);try{byte[] image=NasClient.readBounded(connection.getInputStream(),2*1024*1024);android.graphics.Bitmap bitmap=android.graphics.BitmapFactory.decodeByteArray(image,0,image.length);assertNotNull("Poster must decode on Android",bitmap);assertTrue(bitmap.getWidth()>0);bitmap.recycle();result.put("poster_download",true);}finally{connection.disconnect();}}
                    result.put("posters",posters).put("descriptions",descriptions).put("manual_cards",manual).put("nfo_cards",nfo).put("title_differences",titleDifferences).put("cards",exported).put("compared",compared).put("differences",differences).put("unmatched",unknown).put("episodes",episodes).put("videos",library.videosFound).put("folders",library.foldersRead).put("pairing_events",library.pairings.events).put("pairing_winners",library.pairings.winners.size()).put("invalid_pairings",library.pairings.invalid).put("nfos",library.nfosRead).put("ignored_nfos",library.nfosIgnored).put("metadata_errors",library.metadataErrors).put("requests",api.requests).put("cache_hits",api.cacheHits);
                    errors+=library.metadataErrors;
                }catch(Exception e){result.put("error",e.getClass().getSimpleName());errors++;}
                write(report,audit);android.util.Log.i("SynoStreamAudit","root="+i+" finished");
            }
            audit.put("complete",true).put("mismatches",mismatches).put("errors",errors);write(report,audit);
        }finally{client.logout();}
        assertEquals("Live scan metadata errors; inspect private audit report",0,errors);
        assertEquals("Live scan differs from Windows; inspect private audit report",0,mismatches);
    }
}
