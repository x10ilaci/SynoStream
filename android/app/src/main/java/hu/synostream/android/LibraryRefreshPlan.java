package hu.synostream.android;
import java.util.*;
/** Foreground-only all-library reconciliation queue, independent of metadata lookup. */
final class LibraryRefreshPlan {
 static final long INTERVAL=5*60*1000L;
 private String owner="",running=null;private long finished=-1;private final Deque<String> pending=new ArrayDeque<>();
 synchronized void prepare(String identity,List<String> ids,long now){
  if(!owner.equals(identity)){owner=identity;pending.clear();running=null;finished=-1;}
  if(running!=null||!pending.isEmpty()||finished>=0&&now-finished<INTERVAL)return;
  pending.addAll(new LinkedHashSet<>(ids));if(pending.isEmpty())finished=now;
 }
 synchronized String next(){if(running!=null)return null;running=pending.pollFirst();return running;}
 synchronized void complete(String id,long now){if(!Objects.equals(running,id))return;running=null;if(pending.isEmpty())finished=now;}
 synchronized void cancel(long now){pending.clear();running=null;finished=now;}
 synchronized void reset(){owner="";pending.clear();running=null;finished=-1;}
 synchronized boolean running(String id){return Objects.equals(running,id);}
 synchronized boolean waiting(){return running!=null||!pending.isEmpty();}
}
