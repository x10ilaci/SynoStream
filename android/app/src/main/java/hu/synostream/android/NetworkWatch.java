package hu.synostream.android;
import android.net.*;
import android.os.Handler;
/** Application-scoped default-network observer, independent of Activity lifetime. */
final class NetworkWatch {
 interface Listener {void changed(String key,boolean cellular,boolean retry);}
 private final ConnectivityManager manager;private final Handler main;private final Listener listener;
 private Network network;private boolean cellular;
 private final Runnable deliver;
 NetworkWatch(ConnectivityManager cm,Handler handler,Listener callback){manager=cm;main=handler;listener=callback;deliver=()->listener.changed(key(),cellular,false);}
 boolean allowLocal(){return !cellular;}
 String key(){return network==null?null:network.toString();}
 void start(){
  resume(false);
  manager.registerDefaultNetworkCallback(new ConnectivityManager.NetworkCallback(){
   @Override public void onAvailable(Network value){network=value;cellular=false;schedule();}
   @Override public void onCapabilitiesChanged(Network value,NetworkCapabilities caps){if(value.equals(network)){cellular=caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR);schedule();}}
   @Override public void onLost(Network value){if(value.equals(network)){network=null;cellular=false;schedule();}}
  },main);
 }
 private void schedule(){main.removeCallbacks(deliver);main.postDelayed(deliver,800);}
 void resume(boolean retry){
  // This snapshot is taken outside network callbacks; callbacks use their supplied data.
  network=manager.getActiveNetwork();NetworkCapabilities caps=network==null?null:manager.getNetworkCapabilities(network);
  cellular=caps!=null&&caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR);
  main.removeCallbacks(deliver);listener.changed(network==null?null:network.toString(),cellular,retry);
 }
}
