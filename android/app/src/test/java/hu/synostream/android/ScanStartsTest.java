package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;
public class ScanStartsTest {
 @Test public void completionUsesDuplicateStartIdInsteadOfOriginalScanId(){ScanStarts starts=new ScanStarts();starts.started(1);int original=starts.completionId();starts.started(2);assertEquals(1,original);assertEquals(2,starts.completionId());assertNotEquals(original,starts.completionId());}
 @Test public void staleStartCannotLowerCompletionId(){ScanStarts starts=new ScanStarts();starts.started(3);starts.started(2);assertEquals(3,starts.completionId());}
}
