package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;
public class StreamIdleTest {
 @Test public void waitsThirtyMinutesAndNeverStopsActiveSocket(){assertFalse(StreamIdle.expired(100+StreamIdle.TIMEOUT-1,100,0));assertTrue(StreamIdle.expired(100+StreamIdle.TIMEOUT,100,0));assertFalse(StreamIdle.expired(100+StreamIdle.TIMEOUT*2,100,1));assertFalse(StreamIdle.expired(100,200,0));}
}
