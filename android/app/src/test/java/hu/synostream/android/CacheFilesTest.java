package hu.synostream.android;
import org.junit.*;import org.junit.rules.TemporaryFolder;import static org.junit.Assert.*;import java.io.*;import java.util.*;
public class CacheFilesTest {
 @Rule public TemporaryFolder tmp=new TemporaryFolder();
 @Test public void removesOldPathsAndDeletedLibraryFiles()throws Exception{File dir=tmp.newFolder();File old=new File(dir,"old.json"),keep=new File(dir,"current.json"),backup=new File(dir,"old.json.bak");assertTrue(old.createNewFile());assertTrue(keep.createNewFile());assertTrue(backup.createNewFile());CacheFiles.prune(dir,Set.of("current.json"));assertFalse(old.exists());assertFalse(backup.exists());assertTrue(keep.exists());CacheFiles.remove(keep);assertEquals(0,dir.list().length);}
}
