package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;
public class PairingReadCacheTest {
 NasClient.Entry entry(String name){NasClient.Entry e=new NasClient.Entry(name,"/root/"+name,false,3);e.modified=1;return e;}
 @Test public void ownerTimestampAndSizeArePartOfTheReadCache(){PairingReadCache c=new PairingReadCache();NasClient.Entry e=entry("event.json");c.put("alice",e,new byte[]{1,2,3});assertArrayEquals(new byte[]{1,2,3},c.get("alice",e));assertNull(c.get("bob",e));e.modified=2;assertNull(c.get("alice",e));e.modified=0;assertNull(c.get("alice",e));}
 @Test public void cacheIsBoundedAndReturnedArraysAreDetached(){PairingReadCache c=new PairingReadCache();for(int i=0;i<2000;i++)c.put("user",entry("event"+i),new byte[2048]);assertNull(c.get("user",entry("event0")));NasClient.Entry last=entry("event1999");byte[] bytes=c.get("user",last);assertNotNull(bytes);bytes[0]=99;assertEquals(0,c.get("user",last)[0]);}
}
