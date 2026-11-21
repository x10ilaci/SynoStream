package hu.synostream.android;
import org.junit.*;import org.junit.rules.TemporaryFolder;import static org.junit.Assert.*;import java.io.*;
public class PosterDiskTest {
 @Rule public TemporaryFolder tmp=new TemporaryFolder();
 @Test public void evictsOldestAndUsesOpaqueKeys()throws Exception{File dir=tmp.newFolder();PosterDisk cache=new PosterDisk(dir,8);cache.put("https://example.invalid/a",new byte[]{1,2,3,4});File old=new File(dir,PosterDisk.key("https://example.invalid/a"));assertTrue(old.setLastModified(1000));cache.put("https://example.invalid/b",new byte[]{5,6,7,8});cache.put("https://example.invalid/c",new byte[]{9,10,11,12});assertNull(cache.get("https://example.invalid/a"));assertArrayEquals(new byte[]{9,10,11,12},cache.get("https://example.invalid/c"));long total=0;for(File f:dir.listFiles()){total+=f.length();assertTrue(f.getName().matches("[a-f0-9]{64}"));}assertTrue(total<=8);}
 @Test public void oversizedEntryCannotExceedLimit()throws Exception{File dir=tmp.newFolder();PosterDisk cache=new PosterDisk(dir,2);cache.put("a",new byte[3]);assertNull(cache.get("a"));}
}
