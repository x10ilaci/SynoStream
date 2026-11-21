package hu.synostream.android;
import java.net.*;import java.io.*;import java.nio.charset.StandardCharsets;import java.util.concurrent.atomic.AtomicInteger;
final class HttpFixture implements AutoCloseable {
 final ServerSocket server;final AtomicInteger calls=new AtomicInteger();volatile String userAgent="";
 HttpFixture(int status,String body)throws Exception{server=new ServerSocket(0,8,InetAddress.getByName("127.0.0.1"));Thread t=new Thread(()->{while(!server.isClosed())try(Socket socket=server.accept()){BufferedReader r=new BufferedReader(new InputStreamReader(socket.getInputStream(),StandardCharsets.UTF_8));r.readLine();String h;while((h=r.readLine())!=null&&!h.isEmpty())if(h.toLowerCase().startsWith("user-agent:"))userAgent=h.substring(11).trim();calls.incrementAndGet();byte[] b=body.getBytes(StandardCharsets.UTF_8);socket.getOutputStream().write(("HTTP/1.1 "+status+" Test\r\nContent-Type: application/json\r\nContent-Length: "+b.length+"\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));socket.getOutputStream().write(b);}catch(IOException ignored){}});t.setDaemon(true);t.start();}
 String base(){return "http://127.0.0.1:"+server.getLocalPort()+"/";}
 public void close()throws IOException{server.close();}
}
