package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;
public class CacheLoadRulesTest {
 @Test public void discardedLatestLoadReleasesBusyAndClearsLoadingState(){CacheLoadRules.Finish finish=CacheLoadRules.finish(4,4,false,false);assertTrue(finish.latest);assertTrue(finish.busyRelease);assertFalse(finish.apply);assertTrue(finish.clear);}
 @Test public void discardedLoadCannotReleaseScanOwnedBusyOrClearItsState(){CacheLoadRules.Finish finish=CacheLoadRules.finish(4,4,false,true);assertTrue(finish.latest);assertFalse(finish.busyRelease);assertFalse(finish.apply);assertFalse(finish.clear);}
 @Test public void previousLoadCannotOverwriteNewerLoadOrReleaseItsBusy(){CacheLoadRules.Finish finish=CacheLoadRules.finish(4,5,true,false);assertFalse(finish.latest);assertFalse(finish.busyRelease);assertFalse(finish.apply);assertFalse(finish.clear);java.util.concurrent.atomic.AtomicInteger callbacks=new java.util.concurrent.atomic.AtomicInteger();finish.complete(callbacks::incrementAndGet);assertEquals(0,callbacks.get());}
 @Test public void acceptedAndDiscardedLatestLoadsBothCompleteExactlyOnce(){for(boolean apply:new boolean[]{true,false}){CacheLoadRules.Finish finish=CacheLoadRules.finish(5,5,apply,false);java.util.concurrent.atomic.AtomicInteger callbacks=new java.util.concurrent.atomic.AtomicInteger();finish.complete(callbacks::incrementAndGet);assertEquals(1,callbacks.get());assertEquals(apply,finish.apply);assertTrue(finish.busyRelease);assertEquals(!apply,finish.clear);}}
 @Test public void scanOwnedBusyRemainsOwnedEvenWhenCacheResultIsAccepted(){CacheLoadRules.Finish finish=CacheLoadRules.finish(5,5,true,true);assertTrue(finish.apply);assertFalse(finish.busyRelease);assertFalse(finish.clear);java.util.concurrent.atomic.AtomicBoolean completed=new java.util.concurrent.atomic.AtomicBoolean();finish.complete(()->completed.set(true));assertTrue(completed.get());}

 @Test public void currentResultMayReplaceCards(){assertTrue(CacheLoadRules.canApply(7,"movies",8,7,"movies",8));}
 @Test public void previousScanCannotReplaceNewerCards(){assertFalse(CacheLoadRules.canApply(7,"movies",8,7,"movies",9));}
 @Test public void previousAccountCannotReplaceCards(){assertFalse(CacheLoadRules.canApply(7,"movies",8,8,"movies",8));}
 @Test public void previousLibraryCannotReplaceCards(){assertFalse(CacheLoadRules.canApply(7,"movies",8,7,"shows",8));}
}
