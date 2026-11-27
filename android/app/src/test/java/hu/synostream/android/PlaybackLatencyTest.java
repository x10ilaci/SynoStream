package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;import java.net.*;import java.io.*;import java.nio.charset.StandardCharsets;
public class PlaybackLatencyTest {
 @Test public void loopbackDisablesNagleAndBuffersRequestHeadersWithoutLosingBytes()throws Exception{
  try(ServerSocket server=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"));Socket player=new Socket("127.0.0.1",server.getLocalPort());Socket bridge=server.accept()){
   assertFalse(bridge.getTcpNoDelay());InputStream request=StreamIo.input(bridge);assertTrue(bridge.getTcpNoDelay());assertTrue(request instanceof BufferedInputStream);
   byte[] value="GET /media/fixture HTTP/1.1\r\nRange: bytes=123-\r\n\r\n".getBytes(StandardCharsets.US_ASCII);player.getOutputStream().write(value);assertArrayEquals(value,request.readNBytes(value.length));
   bridge.getOutputStream().write(new byte[]{1,2,3});assertArrayEquals(new byte[]{1,2,3},player.getInputStream().readNBytes(3));
  }
 }
 @Test public void playbackPriorityLivesForActiveRequestsAndExpiresAfterPlaybackStops(){StreamActivity t=new StreamActivity();assertFalse(t.active(0));t.touch(10);assertTrue(t.active(10));t.begin(20);t.begin(21);assertTrue(t.active(999999));t.end(1000000);assertTrue(t.active(1000000+StreamActivity.GRACE));t.end(2000000);assertTrue(t.active(2000000+StreamActivity.GRACE-1));assertFalse(t.active(2000000+StreamActivity.GRACE));}
 @Test public void mediaIsRequestedWithoutCompressionAndRangeBytesRemainIdentical()throws Exception{try(NasClientConcurrencyTest.Fixture f=new NasClientConcurrencyTest.Fixture()){NasClient c=f.client();assertArrayEquals(new byte[]{1,2,3},c.readFile("/video/movie.mkv",100));assertEquals("identity",f.streamEncoding);}}
}
