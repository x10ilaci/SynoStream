package hu.synostream.android;
import org.junit.*;
import org.json.*;
import java.util.*;
import static org.junit.Assert.*;
public class RecognitionTest {
    @Test public void punctuationFallbackAlwaysUsesSingleSpaces() throws Exception {
        Recognition engine=new Recognition((endpoint,p)->{
            if(endpoint.startsWith("search/"))return new JSONObject().put("results","Long Title Subtitle".equals(p.get("query"))?new JSONArray().put(film(1,"Long Title - Subtitle","2020",10)):new JSONArray());
            if(endpoint.endsWith("alternative_titles"))return new JSONObject();return film(1,"Magyar cím","2020",10);
        });assertEquals(1,engine.find("Long Title - Subtitle","2020",true).getLong("id"));
    }
    @Test public void explicitYearAndOriginalTitleCanCorroborateUniqueTopContender() throws Exception {
        JSONObject a=film(1,"Echo","2020",1400),b=film(2,"Echo","2020",157).put("original_title","Más eredeti cím");
        assertEquals(1,Recognition.pick(List.of(a,b),"echo","2020",true).getLong("id"));
        assertNull(Recognition.pick(List.of(a,b),"echo",null,true));
        assertNull(Recognition.pick(List.of(a,film(3,"Echo","2020",1400)),"echo","2020",true));
    }
    private JSONObject film(long id,String title,String year,int votes) throws Exception {return new JSONObject().put("id",id).put("title",title).put("original_title",title).put("release_date",year+"-01-01").put("vote_count",votes).put("overview","Leírás");}
    @Test public void aliasesAreVerifiedBeforeRomanizedTitleIsAccepted() throws Exception {
        JSONObject correct=film(1,"Your Name","2016",100),wrong=film(2,"Boku wa Kimi no Namida","1998",0);
        Recognition engine=new Recognition((endpoint,p)->{
            if(endpoint.startsWith("search/"))return new JSONObject().put("results",new JSONArray().put(wrong).put(correct));
            if(endpoint.endsWith("alternative_titles"))return new JSONObject().put("titles",endpoint.contains("/1/")?new JSONArray().put(new JSONObject().put("title","Kimi no Na wa")):new JSONArray());
            return endpoint.equals("movie/1")?correct:wrong;
        });
        assertEquals(1,engine.find("Kimi no wa",null,true).getLong("id"));
    }
    @Test public void grammarRecoveryMustStillMatchOriginalFullTitle() throws Exception {
        JSONObject correct=film(1,"Even Mice Belong in Heaven","2021",50);
        Recognition engine=new Recognition((endpoint,p)->endpoint.startsWith("search/")?new JSONObject().put("results",p.get("query").equals("Even Mice Belong Heaven")?new JSONArray().put(correct):new JSONArray()):endpoint.endsWith("alternative_titles")?new JSONObject():correct);
        assertEquals(1,engine.find("Even Mice Belong to Heaven","2021",true).getLong("id"));
    }
    @Test public void recoveryCannotAcceptOnlyOneOverlappingWord() throws Exception {
        JSONObject wrong=film(1,"Heaven","2021",100000);
        Recognition engine=new Recognition((endpoint,p)->endpoint.startsWith("search/")?new JSONObject().put("results",p.get("query").equals("Even Mice Belong to Heaven")?new JSONArray():new JSONArray().put(wrong)):new JSONObject());
        assertNull(engine.find("Even Mice Belong to Heaven","2021",true));
    }
    @Test public void yearFilteredResultsCannotHideAdjacentYearFilm() throws Exception {
        JSONObject obscure=film(1,"Sacrifice","2025",0),correct=film(2,"Sacrifice","2026",159),near=film(3,"A Sacrifice","2024",171);
        Recognition engine=new Recognition((endpoint,p)->{
            if(endpoint.startsWith("search/"))return new JSONObject().put("results",p.containsKey("primary_release_year")?new JSONArray().put(obscure):new JSONArray().put(near).put(correct).put(obscure));
            if(endpoint.endsWith("alternative_titles"))return new JSONObject();return correct;
        });
        assertEquals(2,engine.find("Sacrifice","2025",true).getLong("id"));
    }
    @Test public void ambiguityIsIndependentOfResultOrder() throws Exception {JSONObject a=film(1,"Same Title","2020",10),b=film(2,"Same Title","2020",10);assertNull(Recognition.pick(List.of(a,b),"same title","2020",true));assertNull(Recognition.pick(List.of(b,a),"same title","2020",true));}
    @Test public void wrongYearCannotWinByVotes() throws Exception {JSONObject a=film(1,"Same Title","2020",10),b=film(2,"Same Title","1980",100000);assertEquals(1,Recognition.pick(List.of(b,a),"same title","2020",true).getLong("id"));}
    @Test public void englishOverviewDoesNotReplaceHungarianTitle() throws Exception {
        Recognition engine=new Recognition((endpoint,p)->film(1,p.get("language").equals("hu-HU")?"Magyar cím":"Original title","2020",1).put("overview",p.get("language").equals("hu-HU")?"":"English description"));
        JSONObject info=engine.details(1,true);assertEquals("Magyar cím",info.getString("title"));assertEquals("English description",info.getString("overview"));
    }
    @Test public void hungarianConnectorCanFindFrenchSeries() throws Exception {
        JSONObject series=new JSONObject().put("id",1).put("name","Ernest et Célestine").put("original_name","Ernest et Célestine").put("first_air_date","2017-01-01").put("overview","Leírás");
        Recognition engine=new Recognition((endpoint,p)->endpoint.startsWith("search/")?new JSONObject().put("results",p.get("query").equals("Ernest et Célestine")?new JSONArray().put(series):new JSONArray()):endpoint.endsWith("alternative_titles")?new JSONObject():new JSONObject(series.toString()).put("name","Ernest és Célestine"));
        assertEquals("Ernest és Célestine",engine.find("Ernest és Célestine",null,false).getString("name"));
    }
    @Test public void imdbCannotUseMovieAsSeriesOrChooseBetweenAmbiguousIds() throws Exception {
        Recognition engine=new Recognition((endpoint,p)->new JSONObject().put("movie_results",new JSONArray().put(new JSONObject().put("id",1)).put(new JSONObject().put("id",2))));
        assertNull(engine.imdb("tt0133093",false));assertNull(engine.imdb("tt0133093",true));
    }
    @Test public void localizedSearchNamesAreRetainedAcrossLanguages() throws Exception {
        Recognition engine=new Recognition((endpoint,p)->{
            if(endpoint.startsWith("search/"))return new JSONObject().put("results",new JSONArray().put(film(1,p.get("language").equals("hu-HU")?"Távoli magyar cím":"Exact English Title","2020",1)));
            return film(1,"Magyar cím","2020",1);
        });
        assertEquals("Magyar cím",engine.find("Exact English Title","2020",true).getString("title"));
    }
 @org.junit.Test public void failedOptionalEnglishDescriptionKeepsHungarianInfo()throws Exception{Recognition r=new Recognition((endpoint,p)->{if("en-US".equals(p.get("language")))throw new java.io.IOException("offline");return new org.json.JSONObject().put("id",99).put("title","Magyar cím").put("overview","");});org.junit.Assert.assertEquals("Magyar cím",r.details(99,true).getString("title"));}
 @org.junit.Test(expected=InterruptedException.class) public void optionalDescriptionPreservesCancellation()throws Exception{Recognition r=new Recognition((endpoint,p)->{if("en-US".equals(p.get("language")))throw new InterruptedException();return new org.json.JSONObject().put("id",99).put("overview","");});r.details(99,true);}
}
