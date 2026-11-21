package hu.synostream.android;
import org.junit.Test;
import static org.junit.Assert.*;
public class ConnectionRecoveryTest {
 ConnectionRecovery ready(){ConnectionRecovery r=new ConnectionRecovery();assertNull(r.observe("wifi",false,true,false));return r;}
 @Test public void initialCallbackDoesNotRelogin(){assertEquals(ConnectionRecovery.State.READY,ready().state());}
 @Test public void cellularSkipsLocal(){ConnectionRecovery r=ready();ConnectionRecovery.Request q=r.observe("mobile",true,true,false);assertTrue(q.available);assertFalse(q.allowLocal);assertEquals(ConnectionRecovery.State.CONNECTING,r.state());}
 @Test public void wifiReturnPrefersLocal(){ConnectionRecovery r=ready();r.observe("mobile",true,true,false);assertTrue(r.observe("wifi2",false,true,false).allowLocal);}
 @Test public void offlineDoesNotAttemptLogin(){ConnectionRecovery r=ready();assertFalse(r.observe(null,false,true,false).available);assertEquals(ConnectionRecovery.State.OFFLINE,r.state());assertTrue(r.observe("mobile",true,true,false).available);}
 @Test public void repeatedCapabilitiesDoNotDuplicateLogin(){ConnectionRecovery r=ready();r.observe("mobile",true,true,false);assertNull(r.observe("mobile",true,true,false));assertNull(r.observe("mobile",true,true,true));}
 @Test public void olderResultCannotRestoreOldRoute(){ConnectionRecovery r=ready();long old=r.observe("mobile",true,true,false).token;long latest=r.observe("wifi2",false,true,false).token;assertFalse(r.finish(old,true,false));assertEquals(ConnectionRecovery.State.CONNECTING,r.state());assertTrue(r.finish(latest,true,false));assertEquals(ConnectionRecovery.State.READY,r.state());}
 @Test public void retryAfterFailureIsAllowedWithoutNetworkChange(){ConnectionRecovery r=ready();long token=r.observe("mobile",true,true,false).token;r.finish(token,false,false);assertNotNull(r.observe("mobile",true,true,true));}
 @Test public void resumeAfterSuccessDoesNotRelogin(){ConnectionRecovery r=ready();long token=r.observe("mobile",true,true,false).token;r.finish(token,true,false);assertNull(r.observe("mobile",true,true,true));}
 @Test public void otpFailureRequiresSignInInsteadOfRepeatedLogins(){ConnectionRecovery r=ready();long token=r.observe("mobile",true,true,false).token;r.finish(token,false,true);assertEquals(ConnectionRecovery.State.AUTH_REQUIRED,r.state());assertNull(r.observe("mobile",true,true,true));}
 @Test public void logoutInvalidatesRunningAttempt(){ConnectionRecovery r=ready();long token=r.observe("mobile",true,true,false).token;r.reset();assertFalse(r.finish(token,true,false));}
 @Test public void loggedOutNetworkChangesDoNotConnect(){ConnectionRecovery r=ready();assertNull(r.observe("mobile",true,false,false));assertEquals(ConnectionRecovery.State.READY,r.state());}
 @Test public void networkChangeDuringInitialLoginCanBeRecovered(){ConnectionRecovery r=ready();r.requireReconnect();assertNotNull(r.observe("wifi",false,true,true));}
}
