package hu.synostream.android;
import java.util.*;import org.json.*;
final class CorrectionJournal {
 private long revision;private final Map<String,Change> changes=new HashMap<>();
 private static final class Change {long revision;JSONObject info;Change(long r,JSONObject i){revision=r;info=i;}}
 synchronized long revision(){return revision;}
 synchronized void record(boolean movie,String path,JSONObject info){try{changes.put((movie?"movie:":"tv:")+path,new Change(++revision,new JSONObject(info.toString())));}catch(JSONException invalid){throw new IllegalArgumentException(invalid);}}
 synchronized boolean applyAfter(List<Library.Card> cards,long started){boolean applied=false;for(Library.Card card:cards){Change latest=changes.get((card.movie?"movie:":"tv:")+card.path);for(String path:card.episodeRoots){Change c=changes.get("tv:"+path);if(c!=null&&(latest==null||c.revision>latest.revision))latest=c;}if(latest!=null&&latest.revision>started){Library.apply(card,latest.info);card.origin="manual";card.lookupState="matched";applied=true;}}return applied;}
}
