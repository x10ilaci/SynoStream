package hu.synostream.android;
import org.junit.*;
import org.junit.runner.RunWith;
import org.junit.runners.Parameterized;
import org.json.*;
import java.util.*;
import java.nio.charset.StandardCharsets;
import static org.junit.Assert.*;
@RunWith(Parameterized.class)
public class WindowsParityTest {
    @Parameterized.Parameters(name="{0}: {1}")
    public static Collection<Object[]> cases() throws Exception {
        JSONObject fixture=new JSONObject(new String(WindowsParityTest.class.getResourceAsStream("/windows186.json").readAllBytes(),StandardCharsets.UTF_8));
        List<Object[]> rows=new ArrayList<>();for(String kind:List.of("episodes","clean","matching")){JSONArray array=fixture.getJSONArray(kind);for(int i=0;i<array.length();i++){JSONObject j=array.getJSONObject(i);rows.add(new Object[]{kind,j.optString("path",j.optString("name",j.optString("query"))),j});}}return rows;
    }
    private final String kind,name;private final JSONObject expected;
    public WindowsParityTest(String k,String n,JSONObject e){kind=k;name=n;expected=e;}
    @Test public void matchesWindows186() throws Exception {
        if(kind.equals("episodes")){EpisodeIndex.Position result=EpisodeIndex.parse(name);assertEquals(name,expected.getInt("season"),result.season);assertEquals(name,expected.getInt("episode"),result.episode);assertEquals(name,expected.getBoolean("explicit"),result.explicit);}
        else if(kind.equals("clean")){MediaLogic.Name result=MediaLogic.clean(name,true);assertEquals(name,expected.getString("title"),result.title);assertEquals(name,expected.isNull("year")?null:expected.getString("year"),result.year);}
        else {Recognition.Evaluation result=Recognition.evaluate(expected.getJSONObject("candidate"),MediaLogic.normalize(name),expected.isNull("year")?null:expected.getString("year"),expected.getBoolean("movie"));assertEquals(name,expected.getBoolean("reliable"),result.reliable);assertEquals(name,expected.getDouble("score"),result.score,.00001);}
    }
}
