package hu.synostream.android;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.*;
import org.junit.runner.RunWith;
import org.json.*;
import static org.junit.Assert.*;
@RunWith(AndroidJUnit4.class)
public class MetadataCacheTest {
    @Test public void cacheExpiresAndNeverChangesHungarianText() throws Exception {
        MetadataCache cache=new MetadataCache(InstrumentationRegistry.getInstrumentation().getTargetContext());String key="test-only-"+System.nanoTime();
        assertNull(cache.get(key,10000));cache.put(key,new JSONObject().put("title","Árvíztűrő tükörfúrógép").put("id",1));
        assertEquals("Árvíztűrő tükörfúrógép",cache.get(key,10000).getString("title"));assertNull(cache.get(key,0));
    }
    @Test public void serializedSeriesRetainsAllEpisodeRootsAndType() throws Exception {
        Library.Card card=new Library.Card("/shows/A.S01","Műsor",false);card.id=17;card.episodeRoots.add("/shows/A.S01");card.episodeRoots.add("/shows/A.S02");
        Library.Card restored=Library.Card.from(new JSONObject(card.json().toString()));assertFalse(restored.movie);assertEquals(card.episodeRoots,restored.episodeRoots);assertEquals(17,restored.id);
    }
}
