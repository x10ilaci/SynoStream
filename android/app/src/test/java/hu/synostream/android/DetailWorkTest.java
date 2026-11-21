package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;import java.util.*;import java.util.concurrent.*;
public class DetailWorkTest {
 @Test public void episodeSourceLoadsWhileScanIsBlocked()throws Exception{
 ExecutorService scanner=Executors.newSingleThreadExecutor(),detail=DetailWork.create();CountDownLatch blocked=new CountDownLatch(1),release=new CountDownLatch(1);
 Library.Source source=new Library.Source(){public List<NasClient.Entry> list(String p)throws Exception{if(p.equals("/scan")){blocked.countDown();release.await();}return List.of(new NasClient.Entry("S01E01.mkv",p+"/S01E01.mkv",false,1));}public byte[] readFile(String p,int n){return new byte[0];}};
 try{Future<?> scan=scanner.submit(()->{try{source.list("/scan");}catch(Exception e){throw new RuntimeException(e);}});assertTrue(blocked.await(2,TimeUnit.SECONDS));assertEquals(1,detail.submit(()->new Library(source,null).episodes("/show").size()).get(2,TimeUnit.SECONDS).intValue());assertFalse(scan.isDone());}finally{release.countDown();scanner.shutdownNow();detail.shutdownNow();}
 }
}
