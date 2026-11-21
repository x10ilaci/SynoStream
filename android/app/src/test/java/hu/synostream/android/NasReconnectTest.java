package hu.synostream.android;
import org.junit.*;import static org.junit.Assert.*;import java.io.IOException;import java.util.*;
/** Both endpoints are local HTTP fixtures. No QuickConnect or live NAS requests. */
public class NasReconnectTest {
 NasClientTest local,remote;
 @Before public void start()throws Exception{local=new NasClientTest();local.start();remote=new NasClientTest();remote.start();}
 @After public void stop()throws Exception{local.stop();remote.stop();}
 String address(NasClientTest f){return "http://127.0.0.1:"+f.server.getLocalPort();}
 NasClient root(String otp)throws Exception{NasClient root=new NasClient(new NasClient.Credentials(address(remote),address(local),"test","secret",otp));root.connect();return root;}
 @Test public void networkChangeSwitchesFutureStreamsAndListing()throws Exception{
  NasClient root=root("");assertEquals(1,local.logins);assertEquals(0,remote.logins);int token=root.suspendConnection();
  assertTrue(root.installConnection(token,root.reconnectCandidate(false)));assertEquals(1,remote.logins);
  assertEquals(3,root.list("/video").size());try(NasClient.Stream s=root.stream("/video/film.mkv","bytes=2-4",false)){assertArrayEquals(new byte[]{2,3,4},s.body.readAllBytes());}
  assertEquals("bytes=2-4",remote.receivedRange);assertEquals("",local.receivedRange);
 }
 @Test public void wifiReturnUsesLocalEndpointAgain()throws Exception{NasClient root=root("");int mobile=root.suspendConnection();root.installConnection(mobile,root.reconnectCandidate(false));int wifi=root.suspendConnection();root.installConnection(wifi,root.reconnectCandidate(true));assertEquals(2,local.logins);try(NasClient.Stream s=root.stream("/video/film.mkv","bytes=2-4",false)){s.body.readAllBytes();}assertEquals("bytes=2-4",local.receivedRange);}
 @Test public void pendingRecoveryRejectsNewReadsAndWrites()throws Exception{NasClient root=root("");root.suspendConnection();assertThrows(IOException.class,()->root.list("/video"));assertThrows(IOException.class,()->root.stream("/video/A.mkv",null,false));assertThrows(IOException.class,()->root.call("SYNO.FileStation.List","list",Map.of()));assertThrows(IOException.class,()->root.apiRequest("synthetic","create",1,false,Map.of(),null,null,"torrent"));assertEquals(0,remote.logins);}
 @Test public void oldRecoveryCannotOverwriteNewerOne()throws Exception{NasClient root=root("");int first=root.suspendConnection();NasClient stale=root.reconnectCandidate(false);int latest=root.suspendConnection();assertFalse(root.installConnection(first,stale));assertThrows(IOException.class,()->root.list("/video"));assertTrue(root.installConnection(latest,root.reconnectCandidate(true)));}
 @Test public void candidateNeverReplaysOneTimeCode()throws Exception{NasClient root=root("123456");NasClient next=root.reconnectCandidate(false);assertEquals("123456",local.lastOtp);assertEquals("",remote.lastOtp);assertNotEquals(local.lastSession,remote.lastSession);}

 @Test public void logoutMakesLateInstallationInvalid()throws Exception{NasClient root=root("");int token=root.suspendConnection();NasClient next=root.reconnectCandidate(false);root.logout();assertFalse(root.installConnection(token,next));}
 @Test public void sharedDownloadModelUsesReplacementWithoutRecreation()throws Exception{NasClient root=root("");DownloadStation model=new DownloadStation(root,new TorrentRulesTest.Memory(),"fixture");int token=root.suspendConnection();root.installConnection(token,root.reconnectCandidate(false));assertTrue(model.tasks().isEmpty());assertEquals(1,remote.downloadTaskRequests);assertEquals(0,local.downloadTaskRequests);}
 @Test public void unsentTorrentStartRemainsEditableDuringReconnection()throws Exception{
  NasClient root=root("");TorrentRulesTest.Memory storage=new TorrentRulesTest.Memory();DownloadStation model=new DownloadStation(root,storage,"fixture");
  org.json.JSONObject preview=new org.json.JSONObject().put("list_id","pending").put("destination","video").put("submitted",false).put("files",new org.json.JSONArray().put(new org.json.JSONObject().put("index",0).put("name","movie.mkv")));
  model.prepared.put("pending",preview);root.suspendConnection();
  assertThrows(NasClient.ApiRejectedException.class,()->model.start("pending",Set.of(0)));
  assertFalse(model.prepared.get("pending").getBoolean("submitted"));assertEquals(0,local.downloadTaskRequests);assertEquals(0,remote.downloadTaskRequests);assertEquals(0,remote.logins);
 }

}
