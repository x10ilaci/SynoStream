package hu.synostream.android;
import android.content.*;import androidx.test.ext.junit.runners.AndroidJUnit4;import androidx.test.platform.app.InstrumentationRegistry;import androidx.test.uiautomator.*;import org.junit.*;import org.junit.runner.RunWith;import static org.junit.Assert.*;import java.util.*;import java.util.concurrent.*;import java.util.concurrent.atomic.*;
@RunWith(AndroidJUnit4.class) public class Android0513Test {
 final Android050FlowTest f=new Android050FlowTest();
 @Before public void init(){f.instrumentation=InstrumentationRegistry.getInstrumentation();f.context=f.instrumentation.getTargetContext();f.app=(SynoApp)f.context.getApplicationContext();f.device=UiDevice.getInstance(f.instrumentation);UiLocale.save(f.context,"hu");}
 @After public void cleanup()throws Exception{f.instrumentation.runOnMainSync(()->{f.app.forgetConnection();f.app.client=null;f.app.recovery.reset();f.app.checkNetwork();f.app.cancelScan();f.app.epoch++;});f.cleanup();UiLocale.save(f.context,"hu");}
 void waitFor(java.util.function.BooleanSupplier condition)throws Exception{long end=android.os.SystemClock.elapsedRealtime()+10000;while(!condition.getAsBoolean()&&android.os.SystemClock.elapsedRealtime()<end)Thread.sleep(50);assertTrue("Recovery did not finish",condition.getAsBoolean());}
 void ready()throws Exception{AtomicBoolean ready=new AtomicBoolean();waitFor(()->{f.instrumentation.runOnMainSync(()->ready.set(f.app.connectionReady()));return ready.get();});}
 void setup(FakeNas n)throws Exception{f.instrumentation.runOnMainSync(()->{f.app.client=null;f.app.recovery.reset();f.app.checkNetwork();});f.setup(n,List.of(new Library.Card("/Movies/Demo.Movie.2020.mkv","Fixture",true)));}
 @Test public void recoveryDoesNotWaitForNasWorkerAndKeepsLibraryAndDownloadModel()throws Exception{
  try(FakeNas n=new FakeNas()){
   setup(n);NasClient root=f.app.client;CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);Future<?> blocked=f.app.worker.submit(()->{entered.countDown();try{release.await(15,TimeUnit.SECONDS);}catch(InterruptedException e){Thread.currentThread().interrupt();}});assertTrue(entered.await(3,TimeUnit.SECONDS));
   try{
    f.instrumentation.runOnMainSync(()->{f.app.downloads=new DownloadStation(root,f.app.store,f.app.identity);f.app.networkChanged("fixture-mobile",true,false);});
    waitFor(()->n.authLogins>=2);ready();assertFalse(blocked.isDone());assertSame(root,f.app.client);assertEquals(1,f.app.cards.size());
    assertEquals(1,f.app.downloads.tasks().size());try(NasClient.Stream s=root.stream("/Movies/Demo.Movie.2020.mkv",null,false)){assertArrayEquals(new byte[]{0,1,2,3},s.body.readAllBytes());}
    assertEquals(0,n.starts);assertEquals(0,n.prepares);
   }finally{release.countDown();blocked.get(5,TimeUnit.SECONDS);}
  }
 }
 @Test public void offlineThenAvailableRecoversWithoutRestartOrExtraScan()throws Exception{
  try(FakeNas n=new FakeNas()){
   setup(n);int before=n.authLogins;f.instrumentation.runOnMainSync(()->f.app.networkChanged(null,false,false));
   assertTrue(f.device.wait(Until.hasObject(By.res(f.pkg+":id/connection_toolbar").text(f.activity().getString(R.string.network_offline))),5000));assertEquals(before,n.authLogins);
   f.instrumentation.runOnMainSync(()->f.app.networkChanged("fixture-mobile",true,false));waitFor(()->n.authLogins>before);ready();assertEquals(1,f.app.cards.size());assertFalse(f.app.scanRunning);assertEquals(1,n.listRequestRead.getCount());
   f.instrumentation.runOnMainSync(()->f.app.networkChanged("fixture-wifi",false,false));waitFor(()->n.authLogins>=before+2);ready();assertEquals(1,f.app.cards.size());
  }
 }
 @Test public void failedAuthenticationShowsActionableLocalisedStatusWithoutLooping()throws Exception{
  try(FakeNas n=new FakeNas()){
   setup(n);n.rejectNewLogins=true;f.instrumentation.runOnMainSync(()->{f.app.recovery.requireReconnect();f.app.checkNetwork();});
   AtomicBoolean failed=new AtomicBoolean();waitFor(()->{f.instrumentation.runOnMainSync(()->failed.set(f.app.recovery.state()==ConnectionRecovery.State.AUTH_REQUIRED));return failed.get();});int logins=n.authLogins;
   assertTrue(f.device.wait(Until.hasObject(By.res(f.pkg+":id/connection_toolbar").text(f.activity().getString(R.string.network_auth_required))),5000));
   f.instrumentation.runOnMainSync(f.app::checkNetwork);Thread.sleep(300);assertEquals(logins,n.authLogins);assertEquals(1,f.app.cards.size());
  }
 }
 @Test public void realDefaultNetworkCallbackRecoversAcrossWifiAndCellular()throws Exception{
  String wifi=f.device.executeShellCommand("settings get global wifi_on").trim();
  try(FakeNas n=new FakeNas()){
   f.device.executeShellCommand("svc data enable");f.device.executeShellCommand("svc wifi enable");
   android.net.ConnectivityManager cm=f.context.getSystemService(android.net.ConnectivityManager.class);
   waitFor(()->{android.net.Network net=cm.getActiveNetwork();android.net.NetworkCapabilities c=net==null?null:cm.getNetworkCapabilities(net);return c!=null&&c.hasTransport(android.net.NetworkCapabilities.TRANSPORT_WIFI);});
   setup(n);android.net.Network initial=cm.getActiveNetwork();int logins=n.authLogins;
   f.device.executeShellCommand("svc wifi disable");
   waitFor(()->{android.net.Network net=cm.getActiveNetwork();android.net.NetworkCapabilities c=net==null?null:cm.getNetworkCapabilities(net);return net!=null&&!net.equals(initial)&&c!=null&&c.hasTransport(android.net.NetworkCapabilities.TRANSPORT_CELLULAR);});
   waitFor(()->n.authLogins>logins);ready();try(NasClient.Stream stream=f.app.client.stream("/Movies/Demo.Movie.2020.mkv",null,false)){assertArrayEquals(new byte[]{0,1,2,3},stream.body.readAllBytes());}
   int mobileLogins=n.authLogins;f.device.executeShellCommand("svc wifi enable");
   waitFor(()->{android.net.Network net=cm.getActiveNetwork();android.net.NetworkCapabilities c=net==null?null:cm.getNetworkCapabilities(net);return c!=null&&c.hasTransport(android.net.NetworkCapabilities.TRANSPORT_WIFI);});
   waitFor(()->n.authLogins>mobileLogins);ready();assertEquals(1,f.app.cards.size());assertFalse(f.app.scanRunning);
   assertEquals(0,n.starts);assertEquals(0,n.prepares);
  }finally{f.device.executeShellCommand("svc wifi "+("1".equals(wifi)?"enable":"disable"));}
 }

 @Test public void networkChangeClosesAudioChoiceAndAllowsAnotherPlayback()throws Exception{
  try(FakeNas n=new FakeNas()){
   String path="/Movies/Multilingual.mkv";n.files.put(path,Android050FlowTest.join(new byte[]{0x18,0x53,(byte)0x80,0x67,(byte)0xff},Android050FlowTest.elem(0x1654ae6b,Android050FlowTest.join(Android050FlowTest.track(1,"hun"),Android050FlowTest.track(2,"eng")))));
   setup(n);f.device.executeShellCommand("pm grant "+f.pkg+" android.permission.POST_NOTIFICATIONS");MainActivity a=f.activity();AtomicInteger intents=new AtomicInteger();
   android.app.Instrumentation.ActivityMonitor monitor=new android.app.Instrumentation.ActivityMonitor(){@Override public android.app.Instrumentation.ActivityResult onStartActivity(Intent intent){if(Intent.ACTION_VIEW.equals(intent.getAction())){intents.incrementAndGet();return new android.app.Instrumentation.ActivityResult(android.app.Activity.RESULT_CANCELED,null);}return null;}};
   f.instrumentation.addMonitor(monitor);
   try{
    f.instrumentation.runOnMainSync(()->a.play(path,false));assertTrue(f.device.wait(Until.hasObject(By.text("Szám 1: hun (ac3)")),10000));
    f.instrumentation.runOnMainSync(()->f.app.networkChanged(null,false,false));assertTrue(f.device.wait(Until.gone(By.text("Szám 1: hun (ac3)")),5000));f.instrumentation.runOnMainSync(()->assertFalse(a.playbackBusy));assertEquals(0,intents.get());
    int before=n.authLogins;f.instrumentation.runOnMainSync(()->f.app.networkChanged("fixture-mobile",true,false));waitFor(()->n.authLogins>before);ready();
    f.instrumentation.runOnMainSync(()->a.play(path,false));assertTrue(f.device.wait(Until.hasObject(By.text("Szám 1: hun (ac3)")),10000));f.text("Szám 1: hun (ac3)");waitFor(()->intents.get()==1);assertEquals(0,n.starts);
   }finally{f.instrumentation.removeMonitor(monitor);}
  }
 }

}
