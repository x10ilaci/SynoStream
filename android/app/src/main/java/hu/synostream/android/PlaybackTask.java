package hu.synostream.android;
import java.util.concurrent.Future;
final class PlaybackTask {
 volatile boolean cancelled;private Future<?> future;private AutoCloseable resource;
 synchronized void bind(Future<?> value){future=value;if(cancelled)value.cancel(true);}
 synchronized void resource(AutoCloseable value){resource=value;if(cancelled)closeAsync(value);}
 synchronized void cancel(){if(cancelled)return;cancelled=true;if(future!=null)future.cancel(true);if(resource!=null)closeAsync(resource);}
 private static void closeAsync(AutoCloseable value){Thread t=new Thread(()->{try{value.close();}catch(Exception ignored){}},"SynoStream-cancel");t.setDaemon(true);t.start();}
}
