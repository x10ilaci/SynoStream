package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;import org.json.*;
public class WebsiteListTest {
 @Test public void malformedItemsAreSkippedButValidSitesRemain()throws Exception{JSONArray input=new JSONArray().put(JSONObject.NULL).put(3).put("bad").put(new JSONObject()).put(new JSONObject().put("name","Bad").put("url","not a link")).put(new JSONObject().put("name","Good").put("url","https://example.org"));JSONArray sites=DownloadsUi.websiteList(input.toString());assertEquals(1,sites.length());assertEquals("Good",sites.getJSONObject(0).getString("name"));}
 @Test public void malformedJsonNeverCrashesEditing(){for(String raw:new String[]{"[", "{}", "null", "[]"})assertEquals(0,DownloadsUi.websiteList(raw).length());}
}
