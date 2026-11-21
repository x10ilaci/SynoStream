package hu.synostream.android;
import org.json.*;import java.nio.charset.StandardCharsets;import java.util.concurrent.*;import java.io.File;import java.util.*;
/** Disk-only cache queue. The executor argument keeps scheduling testable without Android. */
final class CacheIo {
 static ExecutorService create(){return Executors.newSingleThreadExecutor(task->{Thread thread=new Thread(task,"SynoStream-cache-io");thread.setDaemon(true);return thread;});}
 static void load(Executor executor,Runnable read){executor.execute(read);}
 static void remove(Executor executor,Object lock,File file){executor.execute(()->{synchronized(lock){try{CacheFiles.remove(file);}catch(Exception ignored){}}});}
 static void prune(Executor executor,Object lock,File directory,Set<String> keep){Set<String> snapshot=new HashSet<>(keep);executor.execute(()->{synchronized(lock){try{CacheFiles.prune(directory,snapshot);}catch(Exception ignored){}}});}
 static byte[] snapshot(List<Library.Card> cards)throws JSONException{JSONArray data=new JSONArray();for(Library.Card card:cards)data.put(card.json());return data.toString().getBytes(StandardCharsets.UTF_8);}
 private CacheIo(){}
}
