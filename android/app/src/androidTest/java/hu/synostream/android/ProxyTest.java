package hu.synostream.android;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import android.content.*;
import org.junit.*;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
@RunWith(AndroidJUnit4.class)
public class ProxyTest {
 @Test public void opaqueUrlHeadRangeAndAccessControl() throws Exception {
  Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();SynoApp app=(SynoApp)context.getApplicationContext();
  try(ServerSocket server=new ServerSocket(0,8,InetAddress.getByName("127.0.0.1"))){
   Thread worker=new Thread(()->{while(!server.isClosed())try(Socket socket=server.accept()){BufferedReader reader=new BufferedReader(new InputStreamReader(socket.getInputStream(),StandardCharsets.US_ASCII));String line=reader.readLine();boolean head=line.startsWith("HEAD ");boolean range=false;String h;while((h=reader.readLine())!=null&&!h.isEmpty())if(h.toLowerCase().startsWith("range:"))range=true;String json;
   if(line.contains("SYNO.API.Info"))json="{\"success\":true,\"data\":{\"SYNO.API.Auth\":{\"path\":\"auth.cgi\"},\"SYNO.FileStation.List\":{\"path\":\"entry.cgi\"},\"SYNO.FileStation.Download\":{\"path\":\"entry.cgi\"}}}";
   else if(line.startsWith("POST"))json="{\"success\":true,\"data\":{\"sid\":\"fixture-private-sid\"}}";
   else {byte[] bytes=range?new byte[]{2,3,4}:new byte[]{0,1,2,3,4,5,6,7,8,9};String header="HTTP/1.1 "+(range?"206 Partial Content":"200 OK")+"\r\nContent-Type: video/x-matroska\r\nContent-Length: "+bytes.length+"\r\n"+(range?"Content-Range: bytes 2-4/10\r\n":"")+"Connection: close\r\n\r\n";socket.getOutputStream().write(header.getBytes(StandardCharsets.US_ASCII));if(!head)socket.getOutputStream().write(bytes);continue;}
   byte[] b=json.getBytes(StandardCharsets.UTF_8);socket.getOutputStream().write(("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "+b.length+"\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));socket.getOutputStream().write(b);
   }catch(Exception ignored){}});worker.start();
   NasClient old=app.client;NasClient client=new NasClient(new NasClient.Credentials("http://127.0.0.1:"+server.getLocalPort(),"","fixture-user","fixture-password",""));client.connect();app.client=client;
   try{StreamService.readyUri=null;context.startForegroundService(new Intent(context,StreamService.class).putExtra("path","/video/film.mkv"));long until=System.currentTimeMillis()+10000;while(StreamService.readyUri==null&&System.currentTimeMillis()<until)Thread.sleep(50);assertNotNull(StreamService.readyUri);String url=StreamService.readyUri.toString();assertFalse(url.contains("fixture"));assertFalse(url.contains("_sid"));
    HttpURLConnection get=(HttpURLConnection)new URL(url).openConnection();get.setRequestProperty("Range","bytes=2-4");assertEquals(206,get.getResponseCode());assertEquals(StreamService.mime("/video/film.mkv"),get.getContentType());assertArrayEquals(new byte[]{2,3,4},NasClient.readBounded(get.getInputStream(),10));get.disconnect();
    HttpURLConnection head=(HttpURLConnection)new URL(url).openConnection();head.setRequestMethod("HEAD");assertEquals(200,head.getResponseCode());assertEquals(10,head.getContentLength());head.disconnect();
    HttpURLConnection denied=(HttpURLConnection)new URL(url.replace("/media/","/wrong/")).openConnection();assertEquals(403,denied.getResponseCode());denied.disconnect();
   }finally{context.stopService(new Intent(context,StreamService.class));app.client=old;}
  }
 }
}
