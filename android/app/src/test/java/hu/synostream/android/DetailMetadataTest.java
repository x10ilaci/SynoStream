package hu.synostream.android;
import org.json.*;import org.junit.Test;import static org.junit.Assert.*;
public class DetailMetadataTest {
    @Test public void legacyCachedCardsRemainSerializableWithoutNewDetailFields() throws Exception {
        Library.Card c=Library.Card.from(new JSONObject().put("path","/Movies/old.mkv").put("title","Régi kártya").put("movie",true));
        assertEquals(0,c.rating,0);assertEquals(0,c.runtime);assertEquals("",c.backdrop);assertEquals("Régi kártya",c.json().getString("title"));
    }
    @Test public void realDetailFieldsSurviveCacheAndLocalEditRoundTrip() throws Exception {
        Library.Card c=new Library.Card("/Movies/film.mkv","Cím",true);Library.apply(c,new JSONObject().put("id",1).put("title","Magyar cím").put("backdrop_path","/backdrop.jpg").put("runtime",123).put("vote_average",7.6).put("genres",new JSONArray().put(new JSONObject().put("name","Animáció"))));
        Library.Card restored=Library.Card.from(c.json());assertEquals(123,restored.runtime);assertEquals(7.6,restored.rating,0);assertEquals("Animáció",restored.genres);assertEquals("https://image.tmdb.org/t/p/w780/backdrop.jpg",restored.backdrop);
    }
}
