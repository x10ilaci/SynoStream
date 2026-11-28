package hu.synostream.android;
import java.util.*;
/** Anonymous aggregates only; never stores request parameters. */
final class NasTimings {
 static final class Stat {long count,nanos;}
 private static final Map<String,Stat> totals=new TreeMap<>();
 static void record(String api,String method,long started){if(!api.matches("SYNO\\.[A-Za-z.]+"))api="NAS";if(!method.matches("[A-Za-z_]{1,32}"))method="request";synchronized(totals){Stat s=totals.computeIfAbsent(api+" "+method,k->new Stat());s.count++;s.nanos+=System.nanoTime()-started;}}
 static Map<String,long[]> snapshot(){synchronized(totals){Map<String,long[]> out=new TreeMap<>();for(Map.Entry<String,Stat> e:totals.entrySet())out.put(e.getKey(),new long[]{e.getValue().count,e.getValue().nanos});return out;}}
 static void summary(){if(BuildConfig.DEBUG)for(Map.Entry<String,long[]> e:snapshot().entrySet())android.util.Log.d("SynoStreamTiming",e.getKey()+" count="+e.getValue()[0]+" ms="+e.getValue()[1]/1000000);}
}
