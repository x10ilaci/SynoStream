package hu.synostream.android;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.IBinder;
import android.util.Base64;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import java.util.concurrent.*;

/** Opaque loopback HTTP bridge: external players never receive NAS credentials. */
public final class StreamService extends Service {
    public static volatile Map<Long,Byte> audioPatch=Map.of();public static volatile Uri readyUri;public static volatile String readyPath="";
    private volatile boolean running;private volatile String path="",token="";
    private volatile long lastRequest;private final ScheduledExecutorService idle=Executors.newSingleThreadScheduledExecutor();
    private NasClient client;private ServerSocket server;
    private final Set<Socket> sockets=ConcurrentHashMap.newKeySet();
    private final ExecutorService pool=new ThreadPoolExecutor(2,4,30,TimeUnit.SECONDS,new ArrayBlockingQueue<>(8));
    @Override public void onCreate(){super.onCreate();lastRequest=android.os.SystemClock.elapsedRealtime();idle.scheduleWithFixedDelay(()->{if(StreamIdle.expired(android.os.SystemClock.elapsedRealtime(),lastRequest,sockets.size()))stopSelf();},60,60,TimeUnit.SECONDS);
        NotificationManager manager=getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("stream",UiText.context(this).getString(R.string.msg_video_streaming_53c860),NotificationManager.IMPORTANCE_LOW));
        Intent stop=new Intent(this,StreamService.class).setAction("STOP");
        PendingIntent pending=PendingIntent.getService(this,1,stop,PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent open=PendingIntent.getActivity(this,2,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        startForeground(41,new Notification.Builder(this,"stream").setSmallIcon(android.R.drawable.ic_media_play).setContentTitle(UiText.context(this).getString(R.string.stream_notification_title)).setContentText(UiText.context(this).getString(R.string.msg_streaming_original_video_to_the_player_cb96aa)).setContentIntent(open).addAction(new Notification.Action.Builder(null,UiText.context(this).getString(R.string.msg_stop_edfff6),pending).build()).setOngoing(true).build());
        try{server=new ServerSocket(0,8,InetAddress.getByName("127.0.0.1"));running=true;
            Thread accept=new Thread(()->{while(running)try{Socket socket=server.accept();socket.setSoTimeout(30000);sockets.add(socket);try{pool.execute(()->serve(socket));}catch(RejectedExecutionException e){sockets.remove(socket);socket.close();}}catch(IOException ignored){if(!running)break;}},"SynoStream-loopback");accept.start();
        }catch(IOException e){stopSelf();}
    }
    @Override public int onStartCommand(Intent intent,int flags,int startId){
        if(intent==null||"STOP".equals(intent.getAction())){stopSelf();return START_NOT_STICKY;}
        SynoApp app=(SynoApp)getApplication();client=app.client;
        if(client==null||!app.connectionReady()||server==null){stopSelf();return START_NOT_STICKY;}
        lastRequest=android.os.SystemClock.elapsedRealtime();path=intent.getStringExtra("path");if(path==null||!path.startsWith("/")){stopSelf();return START_NOT_STICKY;}
        byte[] bytes=new byte[32];new SecureRandom().nextBytes(bytes);token=Base64.encodeToString(bytes,Base64.URL_SAFE|Base64.NO_PADDING|Base64.NO_WRAP);
        audioPatch=Map.of();readyPath=path;readyUri=Uri.parse("http://127.0.0.1:"+server.getLocalPort()+"/media/"+token+"/"+Uri.encode(path.substring(path.lastIndexOf('/')+1)));
        return START_NOT_STICKY;
    }
    private void serve(Socket socket){lastRequest=android.os.SystemClock.elapsedRealtime();
        try(socket){
            InputStream in=socket.getInputStream();OutputStream out=socket.getOutputStream();
            String first=line(in);String[] request=first.split(" ");if(request.length!=3){reply(out,400);return;}
            boolean head=request[0].equals("HEAD");if(!head&&!request[0].equals("GET")){reply(out,405);return;}
            String expected=token,current=path;String[] segments=request[1].split("/",5);
            if(segments.length<4||!segments[1].equals("media")||expected.isEmpty()||!MessageDigest.isEqual(segments[2].getBytes(StandardCharsets.UTF_8),expected.getBytes(StandardCharsets.UTF_8))){reply(out,403);return;}
            Map<Long,Byte> patch=audioPatch;String range=null;int total=0;
            while(true){String header=line(in);total+=header.length();if(total>32768){reply(out,431);return;}if(header.isEmpty())break;
                if(header.toLowerCase(Locale.ROOT).startsWith("range:")){String value=header.substring(6).trim();if(range!=null||!value.matches("bytes=(?:[0-9]+-[0-9]*|-[0-9]+)")){reply(out,416);return;}range=value;}
            }
            try(NasClient.Stream stream=client.stream(current,range,head)){
                HttpURLConnection c=stream.connection;int status=c.getResponseCode();
                StringBuilder headers=new StringBuilder("HTTP/1.1 "+status+(status==206?" Partial Content":" OK")+"\r\nConnection: close\r\nContent-Type: "+mime(current)+"\r\n");
                for(String key:List.of("Content-Length","Content-Range","Accept-Ranges")){String value=c.getHeaderField(key);if(value!=null&&!value.contains("\r")&&!value.contains("\n"))headers.append(key).append(": ").append(value).append("\r\n");}
                out.write(headers.append("\r\n").toString().getBytes(StandardCharsets.US_ASCII));out.flush();
                if(!head){long offset=0;String cr=c.getHeaderField("Content-Range");if(status==206&&cr!=null){java.util.regex.Matcher match=java.util.regex.Pattern.compile("bytes ([0-9]+)-.*").matcher(cr);if(match.matches())offset=Long.parseLong(match.group(1));else throw new IOException("Invalid content range");}byte[] buffer=new byte[65536];int count;while(running&&(count=stream.body.read(buffer))!=-1){MatroskaAudio.patch(buffer,count,offset,patch);out.write(buffer,0,count);offset+=count;}out.flush();}
            }
        }catch(Exception ignored){/* Closing a player connection is normal; no URL/token logging. */}
        finally{lastRequest=android.os.SystemClock.elapsedRealtime();sockets.remove(socket);}
    }
    private static String line(InputStream in) throws IOException {ByteArrayOutputStream b=new ByteArrayOutputStream();int c;while((c=in.read())!=-1){if(c=='\n')break;if(c!='\r')b.write(c);if(b.size()>8192)throw new IOException("Long header");}if(c==-1&&b.size()==0)throw new EOFException();return b.toString(StandardCharsets.US_ASCII.name());}
    private static void reply(OutputStream out,int status) throws IOException {out.write(("HTTP/1.1 "+status+" Error\r\nContent-Length: 0\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));}
    public static String mime(String path){return VideoMime.of(path);}
    @Override public IBinder onBind(Intent intent){return null;}
    @Override public void onDestroy(){idle.shutdownNow();running=false;audioPatch=Map.of();readyUri=null;readyPath="";try{if(server!=null)server.close();}catch(IOException ignored){}for(Socket s:sockets)try{s.close();}catch(IOException ignored){}pool.shutdownNow();super.onDestroy();}
}
