package hu.synostream.android;
/** Reuse only confirmed results with unchanged inputs; failures remain retryable. */
final class LibraryRefresh {
 static final long MATCH_AGE=30L*24*60*60*1000,NO_RESULT_AGE=60L*60*1000;
 static boolean fresh(Library.Card old,long now){return old!=null&&old.id>0&&old.lookupState.equals("matched")&&(!old.origin.equals("manual")||old.metadataAt>0||!old.overview.isBlank()||!old.poster.isBlank()||!old.date.isBlank()||old.runtime>0)&&(old.metadataAt==0||now>=old.metadataAt&&now-old.metadataAt<MATCH_AGE);}
 static boolean unchanged(Library.Card old,Library.Card card,NasClient.Entry nfo,long now){
  if(old==null||!old.path.equals(card.path)||old.movie!=card.movie||old.origin.equals("manual"))return false;
  if(card.movie&&old.modified>0&&card.modified>0&&old.modified!=card.modified)return false;
  if(nfo==null){if(!old.nfoPath.isEmpty()||old.origin.equals("nfo"))return false;}
  else if(nfo.modified<=0||!old.nfoPath.equals(nfo.path)||old.nfoModified!=nfo.modified||old.nfoSize!=nfo.size)return false;
  return fresh(old,now)||old.id<=0&&old.lookupState.equals("no_result")&&old.metadataAt>0&&now>=old.metadataAt&&now-old.metadataAt<NO_RESULT_AGE;
 }
 static void copy(Library.Card from,Library.Card to,long now){to.id=from.id;to.title=from.title;to.overview=from.overview;to.poster=from.poster;to.backdrop=from.backdrop;to.runtime=from.runtime;to.rating=from.rating;to.genres=from.genres;to.date=from.date;to.origin=from.origin;to.lookupState=from.lookupState;to.metadataAt=from.metadataAt>0?from.metadataAt:now;}
 private LibraryRefresh(){}
}
