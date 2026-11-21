package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;
public class ConnectionDraftTest {
 @Test public void closingDraftClearsCredentialsAndTransientUiState(){ConnectionDraft d=new ConnectionDraft();d.open=true;d.expanded=true;d.remember=true;d.credentials=new NasClient.Credentials("fixture-qc","","user","secret","");d.close();assertFalse(d.open);assertFalse(d.expanded);assertFalse(d.remember);assertNull(d.credentials);assertNull(d.profile);}
 @Test public void oldCompletionCannotOwnReopenedEditor(){ConnectionDraft d=new ConnectionDraft();d.begin();long first=d.generation;assertTrue(d.current(first));d.close();d.begin();long second=d.generation;assertNotEquals(first,second);assertFalse(d.current(first));assertTrue(d.current(second));}

}
