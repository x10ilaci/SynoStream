package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;import java.util.concurrent.*;
public class PlaybackTaskTest {
 @Test public void cancelInterruptsWorkerAndClosesRead()throws Exception{ExecutorService pool=Executors.newSingleThreadExecutor();CountDownLatch started=new CountDownLatch(1),closed=new CountDownLatch(1);PlaybackTask task=new PlaybackTask();try{task.resource(closed::countDown);Future<?> future=pool.submit(()->{started.countDown();try{Thread.sleep(60000);}catch(InterruptedException expected){Thread.currentThread().interrupt();}});task.bind(future);assertTrue(started.await(2,TimeUnit.SECONDS));task.cancel();assertTrue(future.isCancelled());assertTrue(closed.await(2,TimeUnit.SECONDS));}finally{pool.shutdownNow();}}
 @Test public void lateNetworkResourceAlsoClosesAfterCancel()throws Exception{PlaybackTask task=new PlaybackTask();CountDownLatch closed=new CountDownLatch(1);task.cancel();task.resource(closed::countDown);assertTrue(closed.await(2,TimeUnit.SECONDS));}
}
