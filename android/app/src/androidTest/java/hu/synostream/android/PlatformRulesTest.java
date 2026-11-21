package hu.synostream.android;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.*;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import java.nio.charset.StandardCharsets;
@RunWith(AndroidJUnit4.class)
public class PlatformRulesTest {
    @Test public void legacyHungarianTextNfoRunsOnAndroid(){
        Nfo.Hint hint=Nfo.parse("Cím: Árvíztűrő tükörfúrógép\nÉv: 1999\ntt0133093".getBytes(java.nio.charset.Charset.forName("windows-1250")),true);
        assertEquals("Árvíztűrő tükörfúrógép",hint.titles.get(0));assertEquals("1999",hint.year);assertEquals("tt0133093",hint.imdb);
    }
    @Test public void allWindowsParityCasesRunOnAndroid() throws Exception {
        byte[] bytes=NasClient.readBounded(androidx.test.platform.app.InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("windows186.json"),1024*1024);
        org.json.JSONObject fixture=new org.json.JSONObject(new String(bytes,StandardCharsets.UTF_8));
        org.json.JSONArray episodes=fixture.getJSONArray("episodes");for(int i=0;i<episodes.length();i++){org.json.JSONObject e=episodes.getJSONObject(i);EpisodeIndex.Position p=EpisodeIndex.parse(e.getString("path"));assertEquals(e.toString(),e.getInt("season"),p.season);assertEquals(e.toString(),e.getInt("episode"),p.episode);assertEquals(e.toString(),e.getBoolean("explicit"),p.explicit);}
        org.json.JSONArray names=fixture.getJSONArray("clean");for(int i=0;i<names.length();i++){org.json.JSONObject e=names.getJSONObject(i);MediaLogic.Name n=MediaLogic.clean(e.getString("name"),true);assertEquals(e.toString(),e.getString("title"),n.title);assertEquals(e.isNull("year")?null:e.getString("year"),n.year);}
        org.json.JSONArray matching=fixture.getJSONArray("matching");for(int i=0;i<matching.length();i++){org.json.JSONObject e=matching.getJSONObject(i);Recognition.Evaluation v=Recognition.evaluate(e.getJSONObject("candidate"),MediaLogic.normalize(e.getString("query")),e.isNull("year")?null:e.getString("year"),e.getBoolean("movie"));assertEquals(e.toString(),e.getBoolean("reliable"),v.reliable);assertEquals(e.getDouble("score"),v.score,.00001);}
    }

    @Test public void titleCleaningRunsOnAndroidRegex(){assertEquals("Kubo and the Two Strings",MediaLogic.clean("Kubo.and.the.Two.Strings.2016.720p.BluRay.mkv",true).title);}
    @Test public void episodeRulesRunOnAndroidRegex(){assertEquals(5,EpisodeIndex.parse("Sorozat/2. évad/05. rész.mkv").episode);assertEquals("A Show",EpisodeIndex.groupTitle("A.Show.S01",false));}
    @Test public void nfoXmlAndRelativePathsRunOnAndroid(){assertTrue(MediaLogic.safeRelative("Mappa/Film.mkv"));assertEquals(Long.valueOf(603),Nfo.parse("<movie><title>Mátrix</title><uniqueid type='tmdb'>603</uniqueid></movie>".getBytes(StandardCharsets.UTF_8),true).tmdb);}
}
