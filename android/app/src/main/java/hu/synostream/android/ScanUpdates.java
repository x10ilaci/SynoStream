package hu.synostream.android;
import java.util.*;import java.util.function.*;
/** Scanner-owned immutable batches; never hands live Card objects to the UI thread. */
final class ScanUpdates {
 private final Set<String> known=new HashSet<>();private final LinkedHashMap<String,String> pending=new LinkedHashMap<>();private final Consumer<List<String>> sink;private final LongSupplier clock;private long last,lastProgress;private boolean published;
 ScanUpdates(List<Library.Card> previous,LongSupplier time,Consumer<List<String>> target){clock=time;sink=target;for(Library.Card card:previous){known.add(key(card.movie,card.path));for(String path:card.memberPaths)known.add(key(card.movie,path));for(String path:card.episodeRoots)known.add(key(false,path));}}
 private static String key(boolean movie,String path){return (movie?"movie:":"tv:")+path;}
 void offer(Library.Card card)throws Exception{if(known.contains(key(card.movie,card.path)))return;if(!card.movie)for(String root:card.episodeRoots)if(known.contains(key(false,root)))return;pending.put(key(card.movie,card.path),card.json().toString());long now=clock.getAsLong();if(!published||pending.size()>=256||now-last>=250)flush();}
 void flush(){if(pending.isEmpty())return;List<String> batch=List.copyOf(pending.values());pending.clear();published=true;last=clock.getAsLong();sink.accept(batch);}
 boolean progress(int count){long now=clock.getAsLong();if(count==1||now-lastProgress>=250||count%256==0){lastProgress=now;return true;}return false;}
}
