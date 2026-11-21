package hu.synostream.android;
import java.util.*;
/** Read-only, account/root-scoped LRU. Unknown timestamps are never trusted. */
final class PairingReadCache {
 private static final int MAX_BYTES=2*1024*1024,MAX_ENTRIES=4096;
 private static final class Value {final long modified,size;final byte[] bytes;Value(NasClient.Entry e,byte[] b){modified=e.modified;size=e.size;bytes=b.clone();}}
 private final LinkedHashMap<String,Value> entries=new LinkedHashMap<>(16,.75f,true);private int bytes;
 synchronized byte[] get(String owner,NasClient.Entry entry){Value value=entries.get(owner+"|"+entry.path);return entry.modified>0&&value!=null&&value.modified==entry.modified&&value.size==entry.size?value.bytes.clone():null;}
 synchronized void put(String owner,NasClient.Entry entry,byte[] data){if(entry.modified<=0||data.length>16384)return;String key=owner+"|"+entry.path;Value old=entries.remove(key);if(old!=null)bytes-=old.bytes.length;entries.put(key,new Value(entry,data));bytes+=data.length;Iterator<Value> it=entries.values().iterator();while((bytes>MAX_BYTES||entries.size()>MAX_ENTRIES)&&it.hasNext()){bytes-=it.next().bytes.length;it.remove();}}
}
