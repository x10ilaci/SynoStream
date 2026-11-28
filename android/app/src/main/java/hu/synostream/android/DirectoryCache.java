package hu.synostream.android;
import java.util.*;import java.util.function.LongSupplier;
final class DirectoryCache {
 interface Source {NasClient.DirectoryPage page(String path,int offset)throws Exception;}
 private static final class Saved {long at;NasClient.DirectoryPage page;Saved(long a,NasClient.DirectoryPage p){at=a;page=p;}}
 private final Map<String,Saved> values=new HashMap<>();private final LongSupplier clock;private String profile="";
 DirectoryCache(){this(()->System.nanoTime()/1000000);}
 DirectoryCache(LongSupplier c){clock=c;}
 synchronized void profile(String p){if(!profile.equals(p)){values.clear();profile=p;}}
 synchronized void clear(){values.clear();}
 NasClient.DirectoryPage get(String path,int offset,Source source)throws Exception{
  String key=path+"\n"+offset,owner; synchronized(this){owner=profile;Saved old=values.get(key);if(old!=null&&clock.getAsLong()-old.at<60000)return old.page;}
  try{NasClient.DirectoryPage page=source.page(path,offset);synchronized(this){if(owner.equals(profile))values.put(key,new Saved(clock.getAsLong(),page));}return page;}catch(Exception failure){clear();throw failure;}
 }
}
