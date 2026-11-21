package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;import java.util.*;
public class MediaDeleteProtocolTest {
 @Test public void versionResolutionUsesAdvertisedRange()throws Exception{for(int max:new int[]{1,2})try(NasClientConcurrencyTest.Fixture f=new NasClientConcurrencyTest.Fixture()){f.deleteMaxVersion=max;f.client().deleteMediaPaths(List.of("/video/fixture.mkv"));assertEquals(max,f.lastDeleteVersion);assertEquals(1,f.mediaDeletes.get());}assertEquals(3,NasClient.deleteVersion(3,4));assertThrows(java.io.IOException.class,()->NasClient.deleteVersion(2,1));}
 @Test public void slowSynchronousDeleteHasItsOwnLongerReadDeadline()throws Exception{assertEquals(15000,NasClient.DEFAULT_API_READ_TIMEOUT);assertEquals(120000,NasClient.DELETE_READ_TIMEOUT);try(NasClientConcurrencyTest.Fixture f=new NasClientConcurrencyTest.Fixture()){f.deleteDelay=15500;f.client().deleteMediaPaths(List.of("/video/fixture.mkv"));assertEquals(1,f.mediaDeletes.get());}}

 @Test public void deletionShareAndFolderFieldsMatchTheirDocumentedSchemas()throws Exception{try(NasClientConcurrencyTest.Fixture f=new NasClientConcurrencyTest.Fixture()){f.strictDeletionLists=true;NasClient c=f.client();assertTrue(c.listForDeletion("").isEmpty());assertTrue(c.listForDeletion("/video").isEmpty());}}
}
