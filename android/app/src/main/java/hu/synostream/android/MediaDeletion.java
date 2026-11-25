package hu.synostream.android;
import java.util.*;import java.io.*;
/** Exact, reviewable file deletion. Directory cleanup is always non-recursive. */
final class MediaDeletion {
 interface Source {List<NasClient.Entry> list(String path)throws Exception;}
 interface Delete {void paths(List<String> values)throws Exception;}
 static final Set<String> VIDEO=Set.of(".mkv",".mp4",".avi",".mov",".wmv",".m4v",".ts",".m2ts",".mpg",".mpeg",".webm");
 static final Set<String> AUX=Set.of(".nfo",".srt",".ass",".ssa",".sub",".idx",".vtt",".sup",".jpg",".jpeg",".png",".txt",".sfv",".srr",".md5",".url",".torrent",".log");
 static final Set<String> EXTRA=Set.of("sample","samples","subs","subtitles","extras","proof","extrafanart");
 static String path(String value){if(value==null||!value.startsWith("/")||value.contains("\\")||value.chars().anyMatch(c->c<32))throw new IllegalArgumentException("Érvénytelen NAS-törlési útvonal.");String[] parts=value.substring(1).split("/",-1);for(String p:parts)if(p.isEmpty()||p.equals(".")||p.equals(".."))throw new IllegalArgumentException("Érvénytelen NAS-törlési útvonal.");return value;}
 static String parent(String path){int n=path.lastIndexOf('/');return n<=0?"/":path.substring(0,n);}
 static String name(String p){return p.substring(p.lastIndexOf('/')+1);}
 static String ext(String p){int n=name(p).lastIndexOf('.');return n<0?"":name(p).substring(n).toLowerCase(Locale.ROOT);}
 static String stem(String p){String n=name(p);int i=n.lastIndexOf('.');return (i<0?n:n.substring(0,i)).toLowerCase(Locale.ROOT);}
 static boolean within(String p,String root){return p.equals(root)||p.startsWith(root+"/");}
 static boolean video(String p){return VIDEO.contains(ext(p));}
 static boolean sample(String p){return sample(p,List.of());}
 static boolean sample(String p,Collection<String> cardRoots){String root=cardRoots.stream().filter(r->within(p,r)).max(Comparator.comparingInt(String::length)).orElse(null);return MediaLogic.samplePath(p,root,false,false);}

 static String real(String value){return value.replaceFirst("/+$","");}
 boolean isSample(String p){List<String> anchors=new ArrayList<>();for(String seed:seeds)anchors.add(video(seed)?parent(seed):seed);return sample(p,anchors);}

 static boolean blocked(String p){for(String part:p.split("/"))if(Set.of(".synostream","#recycle","@eadir","@snapshot").contains(part.toLowerCase(Locale.ROOT)))return true;return false;}
 static Integer explicitSeason(String p){java.util.regex.Matcher m=java.util.regex.Pattern.compile("(?i)(?:\\bS(\\d{1,3})\\b|season[ ._-]*(\\d+)|(\\d+)[ ._-]*(?:évad|evad))").matcher(name(p));if(!m.find())return null;for(int n=1;n<=3;n++)if(m.group(n)!=null)return Integer.parseInt(m.group(n));return null;}
 static String stamp(NasClient.Entry e){return e.path+"\0"+e.directory+"\0"+e.size+"\0"+e.modified+"\0"+e.symbolic+"\0"+e.realPath;}
 static final class Plan {
  final List<String> files,folders,unknown;final Set<Integer> seasons;final boolean allSeasons,includeUnknown;
  Plan(Collection<String> f,Collection<String> d,Collection<String> u,Set<Integer> s,boolean all,boolean include){List<String> unknowns=new ArrayList<>(u);Collections.sort(unknowns);unknown=List.copyOf(unknowns);includeUnknown=include;List<String> fs=new ArrayList<>(f),ds=new ArrayList<>(d);Collections.sort(fs);ds.sort(Comparator.<String>comparingInt(x->-x.split("/").length).thenComparing(x->x));files=List.copyOf(fs);folders=List.copyOf(ds);seasons=Set.copyOf(s);allSeasons=all;}
 }
 static final class Result {final List<String> files,folders;final boolean allSeasons;Result(Plan p,List<String> d){files=p.files;folders=List.copyOf(d);allSeasons=p.allSeasons;}boolean removed(String p){for(String f:files)if(p.equals(f))return true;for(String d:folders)if(within(p,d))return true;return false;}}
 final List<String> seeds,libraryRoots,protectedPaths,roots=new ArrayList<>();final boolean movie;Source source;
 final Map<String,List<String>> fingerprints=new HashMap<>();final Map<String,List<NasClient.Entry>> listings=new LinkedHashMap<>();final Map<String,NasClient.Entry> entries=new LinkedHashMap<>();final Map<String,Integer> videos=new LinkedHashMap<>();final SortedSet<Integer> seasons=new TreeSet<>();
 MediaDeletion(List<String> wanted,List<String> libraries,boolean isMovie,Source src,List<String> protect)throws Exception {
  seeds=List.copyOf(new LinkedHashSet<>(wanted));libraryRoots=List.copyOf(libraries);protectedPaths=List.copyOf(protect);movie=isMovie;source=src;
  if(seeds.isEmpty()||libraryRoots.isEmpty())throw new IOException("A törléshez beállított NAS-forrásmappa szükséges.");for(String r:libraryRoots)path(r);
  for(String seed:seeds){path(seed);if(blocked(seed)||libraryRoots.stream().noneMatch(r->within(seed,r)))throw new IOException("A műsor nem a kiválasztott NAS-forrásban található.");if(!movie&&libraryRoots.contains(seed)&&!video(seed))throw new IOException("A teljes médiatár gyökere nem törölhető műsorkártyaként.");String root=video(seed)?parent(seed):seed;
   while(!libraryRoots.contains(root)){String p=parent(root);if(libraryRoots.contains(p)||libraryRoots.stream().noneMatch(r->within(p,r)))break;boolean allow=true;
    for(NasClient.Entry e:list(p)){if(e.path.equals(root))continue;if(e.directory){if(!EXTRA.contains(name(e.path).toLowerCase(Locale.ROOT))&&seeds.stream().noneMatch(s->within(s,e.path))&&(blocked(e.path)||!list(e.path).isEmpty())){allow=false;break;}}else if(video(e.path)&&!seeds.contains(e.path)&&!isSample(e.path)){allow=false;break;}else if(!AUX.contains(ext(e.path))){allow=false;break;}}
    if(!allow)break;root=p;
   }if(!roots.contains(root))roots.add(root);
  }
  List<String> all=new ArrayList<>(roots);roots.removeIf(r->all.stream().anyMatch(o->!r.equals(o)&&within(r,o)));
  for(String r:roots){String p=parent(r);list(p.equals("/")?"":p);walk(r,0,!libraryRoots.contains(r));}
  for(String seed:seeds)if(video(seed)&&!entries.containsKey(seed))throw new IOException("A kijelölt fájl már nem található a NAS-on.");
  for(NasClient.Entry e:entries.values())if(!e.directory&&video(e.path)&&!isSample(e.path)&&!isProtected(e.path)&&(movie||seeds.stream().anyMatch(s->video(s)?e.path.equals(s):within(e.path,s)))){int n=EpisodeIndex.parse(e.path).season;videos.put(e.path,n);if(!movie)seasons.add(n);}
  if(!movie&&videos.isEmpty())throw new IOException("A kártyához nem található törölhető epizód.");
 }
 boolean isProtected(String p){return blocked(p)||protectedPaths.stream().anyMatch(r->within(p,r)||within(r,p));}
 List<NasClient.Entry> list(String root)throws Exception {if(Thread.currentThread().isInterrupted())throw new InterruptedException();if(!listings.containsKey(root)){List<NasClient.Entry> rows=new ArrayList<>();Set<String> seen=new HashSet<>();for(NasClient.Entry e:source.list(root)){path(e.path);if(!parent(e.path).equals(root.isEmpty()?"/":root)||!seen.add(e.path))throw new IOException("A NAS nem egyértelmű mappalistát adott.");if(e.realPath==null||e.realPath.isBlank())throw new IOException("A NAS nem adta meg a fizikai útvonalat; a törlés nem végezhető el biztonságosan.");if(e.symbolic)throw new IOException("Szimbolikus hivatkozást tartalmazó mappa nem törölhető automatikusan.");rows.add(e);}listings.put(root,List.copyOf(rows));List<String> stamps=new ArrayList<>();for(NasClient.Entry e:rows)stamps.add(stamp(e));Collections.sort(stamps);fingerprints.put(root,List.copyOf(stamps));}return listings.get(root);}
 String physicalPath(String logical)throws Exception{String folder=parent(logical);for(NasClient.Entry e:list(folder.equals("/")?"":folder))if(e.path.equals(logical))return real(e.realPath);throw new IOException("A NAS nem adta meg a fizikai útvonalat; a törlés nem végezhető el biztonságosan.");}
 void walk(String root,int depth,boolean recursive)throws Exception {if(depth>32||entries.size()>20000)throw new IOException("Túl nagy törlési terület.");String physical="";for(NasClient.Entry e:listings.getOrDefault(parent(root).equals("/")?"":parent(root),List.of()))if(e.path.equals(root))physical=real(e.realPath);
  if(physical.isBlank())throw new IOException("A NAS nem adta meg a fizikai útvonalat; a törlés nem végezhető el biztonságosan.");
  String anchor=libraryRoots.stream().filter(r->within(root,r)).max(Comparator.comparingInt(String::length)).orElseThrow();String expectedRoot=physicalPath(anchor)+root.substring(anchor.length());if(!physical.equals(expectedRoot))throw new IOException("A mappa másik helyre mutató hivatkozást tartalmaz; a törlés nem indult el.");
  for(NasClient.Entry e:list(root)){if(!real(e.realPath).equals(physical+"/"+name(e.path)))throw new IOException("A mappa másik helyre mutató hivatkozást tartalmaz; a törlés nem indult el.");entries.put(e.path,e);if(entries.size()>20000)throw new IOException("Túl nagy törlési terület.");if(e.directory&&(recursive||EXTRA.contains(name(e.path).toLowerCase(Locale.ROOT)))&&!blocked(e.path))walk(e.path,depth+1,true);}
 }
 Plan plan(Set<Integer> chosen)throws Exception{return plan(chosen,false);}
 Plan plan(Set<Integer> chosen,boolean includeUnknown)throws Exception {Set<Integer> selectedSeasons=chosen==null?new TreeSet<>(seasons):new TreeSet<>(chosen);Set<String> selected=new HashSet<>();if(movie)selected.addAll(seeds);else for(Map.Entry<String,Integer> e:videos.entrySet())if(selectedSeasons.contains(e.getValue()))selected.add(e.getKey());if(selected.isEmpty())throw new IOException("Válassz legalább egy évadot.");
  Set<String> unknown=new HashSet<>(),files=new HashSet<>(selected),folders=new HashSet<>(),allVideos=new HashSet<>();List<String> candidates=new ArrayList<>(roots),owned=new ArrayList<>();for(NasClient.Entry e:entries.values()){if(e.directory)candidates.add(e.path);else if(video(e.path)&&!isSample(e.path))allVideos.add(e.path);}
  for(String d:candidates){if(libraryRoots.contains(d)||blocked(d)||isProtected(d))continue;Set<String> below=new HashSet<>();for(String p:allVideos)if(within(p,d))below.add(p);if(!below.isEmpty()&&selected.containsAll(below))owned.add(d);}
  for(NasClient.Entry e:entries.values()){String p=e.path;if(e.directory||isProtected(p))continue;if(owned.stream().anyMatch(d->within(p,d))){if(VIDEO.contains(ext(p))||AUX.contains(ext(p)))files.add(p);else{unknown.add(p);if(includeUnknown)files.add(p);}continue;}if(AUX.contains(ext(p))){String auxStem=stem(p),videoFolder=EXTRA.contains(name(parent(p)).toLowerCase(Locale.ROOT))?parent(parent(p)):parent(p);String assigned=entries.values().stream().filter(v->!v.directory&&video(v.path)&&parent(v.path).equals(videoFolder)).map(v->v.path).filter(v->auxStem.equals(stem(v))||auxStem.startsWith(stem(v)+".")).sorted(Comparator.<String>comparingInt(v->-stem(v).length()).thenComparing(v->v)).findFirst().orElse(null);if(assigned!=null&&selected.contains(assigned))files.add(p);
    Integer tag=explicitSeason(p);if(!movie&&!libraryRoots.contains(parent(p))&&tag!=null&&selectedSeasons.contains(tag))files.add(p);
   }}
  for(NasClient.Entry e:entries.values())if(e.directory&&!isProtected(e.path)&&!libraryRoots.contains(e.path)&&owned.stream().anyMatch(d->within(e.path,d)))folders.add(e.path);
  for(String p:files){if(isProtected(p))throw new IOException("A kijelölés más médiakártya fájlját érintené.");String d=parent(p);while(!libraryRoots.contains(d)){final String f=d;if(libraryRoots.stream().noneMatch(r->within(f,r)))break;folders.add(d);d=parent(d);}}
  return new Plan(files,folders,unknown,selectedSeasons,!movie&&selectedSeasons.containsAll(seasons),includeUnknown);
 }
 static void checkCancelled()throws InterruptedException{if(Thread.currentThread().isInterrupted())throw new InterruptedException("A törlés megszakadt.");}
 Result execute(Plan plan,Delete delete)throws Exception {checkCancelled();Plan expected=plan(movie?null:plan.seasons,plan.includeUnknown);if(!expected.unknown.equals(plan.unknown)||!expected.files.equals(plan.files)||!expected.folders.equals(plan.folders)||expected.allSeasons!=plan.allSeasons)throw new IOException("A törlési terv megváltozott.");
  for(Map.Entry<String,List<NasClient.Entry>> saved:listings.entrySet()){checkCancelled();List<String> a=new ArrayList<>(),b=new ArrayList<>();a.addAll(fingerprints.get(saved.getKey()));for(NasClient.Entry e:source.list(saved.getKey()))b.add(stamp(e));Collections.sort(a);Collections.sort(b);if(!a.equals(b))throw new IOException("A NAS tartalma megváltozott. A törlési listát újra meg kell nyitni.");}
  for(int n=0;n<plan.files.size();n+=64){checkCancelled();delete.paths(plan.files.subList(n,Math.min(n+64,plan.files.size())));}
  List<String> removed=new ArrayList<>();for(String d:plan.folders){checkCancelled();if(source.list(d).isEmpty()){delete.paths(List.of(d));removed.add(d);}}return new Result(plan,removed);
 }
}
