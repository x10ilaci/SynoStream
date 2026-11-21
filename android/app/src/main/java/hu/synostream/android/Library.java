package hu.synostream.android;

import org.json.*;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.io.IOException;

/** Read-only NAS inventory and independently testable recognition orchestration. */
public final class Library {
    public interface Source {List<NasClient.Entry> list(String path) throws Exception;byte[] readFile(String path,int limit) throws Exception;}
    public static final class Card {
        public String path,title,overview="",poster="",backdrop="",date="",lookupState="pending",origin="name";public boolean movie;public long id=-1,modified=0;public int runtime=0;public double rating=0;public String genres="";
        public String nfoPath="",nfoToken="";public long nfoModified=-1,nfoSize=-1,metadataAt=0;
        public final List<String> episodeRoots=new ArrayList<>(),memberPaths=new ArrayList<>();public String manualGroupId="";
        public Card(String p,String t,boolean m){path=p;title=t;movie=m;}
        public JSONObject json() throws JSONException {return new JSONObject().put("path",path).put("title",title).put("movie",movie).put("overview",overview).put("poster",poster).put("backdrop",backdrop).put("runtime",runtime).put("rating",rating).put("genres",genres).put("date",date).put("id",id).put("episode_roots",new JSONArray(episodeRoots)).put("lookup_state",lookupState).put("origin",origin).put("modified",modified).put("metadata_at",metadataAt).put("nfo_path",nfoPath).put("nfo_modified",nfoModified).put("nfo_size",nfoSize).put("nfo_token",nfoToken).put("members",new JSONArray(memberPaths)).put("manual_group",manualGroupId);}
        public static Card from(JSONObject j){Card c=new Card(j.optString("path"),j.optString("title"),j.optBoolean("movie"));c.id=j.optLong("id",-1);c.modified=j.optLong("modified");c.metadataAt=j.optLong("metadata_at");c.nfoPath=j.optString("nfo_path");c.nfoModified=j.optLong("nfo_modified",-1);c.nfoSize=j.optLong("nfo_size",-1);c.nfoToken=j.optString("nfo_token");c.manualGroupId=j.optString("manual_group");JSONArray members=j.optJSONArray("members");if(members!=null)for(int i=0;i<members.length();i++)c.memberPaths.add(members.optString(i));c.overview=j.optString("overview");c.poster=j.optString("poster");c.backdrop=j.optString("backdrop");c.runtime=j.optInt("runtime");c.rating=j.optDouble("rating",0);c.genres=j.optString("genres");c.date=j.optString("date");c.lookupState=j.optString("lookup_state","pending");c.origin=j.optString("origin","name");JSONArray roots=j.optJSONArray("episode_roots");if(roots!=null)for(int i=0;i<roots.length();i++)c.episodeRoots.add(roots.optString(i));return c;}
    }
    public interface Progress {void update(int count);}
    public final Pairings pairings=new Pairings();
    public int foldersRead=0,videosFound=0,nfosRead=0,nfosIgnored=0,nfoWarnings=0,metadataErrors=0,matched=0;
    private final Source nas;private final Recognition recognition;
    private final Map<String,List<NasClient.Entry>> listings=new HashMap<>();
    private final Map<String,Card> previous=new HashMap<>();
    public interface Preview {void update(Card card)throws Exception;}
    private Preview preview;private Runnable inventoryFinished=()->{};private boolean inventory,force;
    private java.util.function.LongSupplier clock=System::currentTimeMillis;private PairingReadCache pairingCache;private String cacheOwner="";
    public void preview(Preview callback,Runnable finished){preview=callback;inventoryFinished=finished;}
    void clock(java.util.function.LongSupplier value){clock=value;}
    private boolean reuseConfirmed=false;
    void reuseConfirmed(boolean value){reuseConfirmed=value;}
    private long reuseTime(Card old){return reuseConfirmed&&old!=null&&old.id>0&&old.metadataAt>0?old.metadataAt:clock.getAsLong();}
    void forceMetadata(boolean value){force=value;}
    void pairingCache(PairingReadCache cache,String owner){pairingCache=cache;cacheOwner=owner;}
    private int metadataFailures=0;private Map<String,JSONObject> localOverrides=new HashMap<>();
    public void localOverrides(Map<String,JSONObject> values){localOverrides=new HashMap<>(values);}
    public Library(NasClient n,String key){this(n,key,null);}
    public Library(NasClient n,String key,TmdbApi.Cache cache){this((Source)n,key.isBlank()?null:new TmdbApi(key,cache));}
    public Library(Source source,Recognition.Api api){nas=source;recognition=api==null?null:new Recognition(api);}
    public void previous(List<Card> cards){for(Card c:cards)previous.put((c.movie?"movie:":"tv:")+c.path,c);}
    private List<NasClient.Entry> list(String path) throws Exception {check();List<NasClient.Entry> entries=listings.get(path);if(entries==null){entries=nas.list(path);listings.put(path,entries);foldersRead++;}return entries;}
    public List<Card> scan(String root,boolean movie,Progress progress) throws Exception {
        if(root==null||!root.startsWith("/")||root.contains("/../"))throw new IOException("Érvénytelen médiatári gyökér.");
        listings.clear();pairings.winners.clear();pairings.events=pairings.invalid=0;foldersRead=videosFound=nfosRead=nfosIgnored=nfoWarnings=metadataErrors=matched=metadataFailures=0;
        if(preview!=null){inventory=true;try{List<Card> discovered=new ArrayList<>();if(movie)scanMovies(root,root,0,discovered,n->{});else scanShows(root,discovered,n->{});}finally{inventory=false;}videosFound=0;inventoryFinished.run();}
        readPairs(root);List<Card> cards=new ArrayList<>();
        if(movie)scanMovies(root,root,0,cards,progress);else scanShows(root,cards,progress);
        cards.sort(Comparator.comparing(c->MediaLogic.normalize(c.title)));return cards;
    }
    private void scanMovies(String root,String folder,int depth,List<Card> cards,Progress progress) throws Exception {
        check();if(depth>24||cards.size()>=10000)throw new IOException("A médiatár túl nagy vagy túl mély; a korábbi lista megmarad.");
        List<NasClient.Entry> entries=list(folder);long videoCount=entries.stream().filter(e->!e.directory&&MediaLogic.video(e.name)&&!MediaLogic.ignored(e.name)&&!MediaLogic.sample(e.name)).count();long count=entries.stream().filter(e->!e.directory&&MediaLogic.video(e.name)&&!MediaLogic.sample(e.name)&&!MediaLogic.extra(e.name,videoCount==1)).count();
        String folderName=folder.substring(folder.lastIndexOf('/')+1);
        for(NasClient.Entry e:recent(entries)){check();if(MediaLogic.ignored(e.name)||MediaLogic.sample(e.name)||MediaLogic.extra(e.name,!e.directory&&videoCount==1))continue;
            if(e.directory)scanMovies(root,e.path,depth+1,cards,progress);
            else if(MediaLogic.video(e.name)){
                videosFound++;MediaLogic.Name name=MediaLogic.movieName(e.name,folderName,count==1);
                Card card=new Card(e.path,name.title,true);card.modified=e.modified;identifySafely(card,root,name,e.name,folderName,entries);cards.add(card);if(preview!=null)preview.update(card);if(!inventory)progress.update(cards.size());
            }
        }
    }
    private void scanShows(String root,List<Card> cards,Progress progress) throws Exception {
        Map<String,Card> groups=new LinkedHashMap<>();Map<String,String> sourceNames=new HashMap<>();
        List<NasClient.Entry> rootEntries=list(root);long rootVideoCount=rootEntries.stream().filter(e->!e.directory&&MediaLogic.video(e.name)&&!MediaLogic.ignored(e.name)&&!MediaLogic.sample(e.name)).count();for(NasClient.Entry entry:rootEntries){
            check();if(MediaLogic.ignored(entry.name)||MediaLogic.sample(entry.name)||MediaLogic.extra(entry.name,!entry.directory&&rootVideoCount==1)||!entry.directory&&!MediaLogic.video(entry.name))continue;
            String group=EpisodeIndex.groupTitle(entry.name,!entry.directory);
            String key=group==null?entry.path:"group:"+MediaLogic.normalize(group);
            Card card=groups.get(key);if(card==null){card=new Card(entry.path,group==null?MediaLogic.clean(entry.name,!entry.directory).title:group,false);groups.put(key,card);sourceNames.put(card.path,entry.name);}
            card.episodeRoots.add(entry.path);
        }
        List<Card> showCards=new ArrayList<>();
        for(Card group:groups.values()){
            Set<Long> ids=new HashSet<>();
            for(String path:group.episodeRoots){JSONObject event=pairings.get(root,path,false);if(event!=null&&!event.optBoolean("deleted"))ids.add(event.optLong("tmdb_id"));}
            if(ids.size()<=1)showCards.add(group);
            else for(String path:group.episodeRoots){
                Card separate=new Card(path,group.title,false);separate.episodeRoots.add(path);showCards.add(separate);
                sourceNames.put(path,path.substring(path.lastIndexOf('/')+1));
            }
        }
        Map<String,Long> times=new HashMap<>();for(NasClient.Entry e:rootEntries)times.put(e.path,e.modified);for(Card c:showCards)for(String p:c.episodeRoots)c.modified=Math.max(c.modified,times.getOrDefault(p,0L));
        showCards.sort(Comparator.comparingLong((Card c)->c.modified).reversed());
        for(Card card:showCards){
            if(cards.size()>=10000)throw new IOException("Túl nagy sorozatmédiatár.");
            if(inventory){boolean found=previous.containsKey("tv:"+card.path);if(!found)for(String folder:card.episodeRoots){if(MediaLogic.VIDEO.matcher(folder).matches()||containsVideo(folder,0)){found=true;break;}}if(found){Card old=previous.get("tv:"+card.path);if(old!=null)LibraryRefresh.copy(old,card,clock.getAsLong());cards.add(card);if(preview!=null)preview.update(card);}continue;}
            List<NasClient.Entry> episodes=new ArrayList<>();for(String folder:card.episodeRoots){if(MediaLogic.VIDEO.matcher(folder).matches())episodes.add(new NasClient.Entry(folder.substring(folder.lastIndexOf('/')+1),folder,false,0));else walk(folder,0,episodes);}
            if(episodes.isEmpty())continue;videosFound+=episodes.size();
            String source=sourceNames.get(card.path);List<NasClient.Entry> siblings=MediaLogic.VIDEO.matcher(card.path).matches()?list(root):list(card.path);
            identifySafely(card,root,MediaLogic.clean(card.title,false),source,"",siblings);cards.add(card);if(preview!=null)preview.update(card);if(!inventory)progress.update(cards.size());
        }
    }
    private void readPairs(String root) throws Exception {
        if(list(root).stream().noneMatch(e->e.directory&&e.name.equals(".synostream")))return;
        if(list(root+"/.synostream").stream().noneMatch(e->e.directory&&e.name.equals("parositasok")))return;
        for(NasClient.Entry e:list(root+"/.synostream/parositasok")){
            check();if(e.directory||!e.name.matches("[0-9a-f]{32}\\.json"))continue;
            if(e.size>16384){pairings.invalid++;continue;}
            try{byte[] data=pairingCache==null?null:pairingCache.get(cacheOwner,e);if(data==null){data=nas.readFile(e.path,16384);if(pairingCache!=null&&Pairings.validate(e.name,data)!=null)pairingCache.put(cacheOwner,e,data);}pairings.add(e.name,data);}catch(NasClient.ResponseTooLargeException invalid){pairings.invalid++;}
        }
    }
    private void identifySafely(Card card,String root,MediaLogic.Name name,String source,String folderName,List<NasClient.Entry> siblings) throws Exception {
        if(inventory){Card old=previous.get((card.movie?"movie:":"tv:")+card.path);if(old!=null)LibraryRefresh.copy(old,card,clock.getAsLong());return;}
        try{identify(card,root,name,source,folderName,siblings);if(card.metadataAt==0&&recognition!=null)card.metadataAt=clock.getAsLong();metadataFailures=0;if(card.id>0){matched++;card.lookupState="matched";}else card.lookupState=recognition==null?"no_key":"no_result";}
        catch(InterruptedException e){throw e;}
        catch(Exception unavailable){
            metadataErrors++;metadataFailures++;card.lookupState="retry";
            Card old=previous.get((card.movie?"movie:":"tv:")+card.path);
            JSONObject manual=pairings.get(root,card.path,card.movie);
            if(old!=null&&old.id>0&&(manual==null||!manual.optBoolean("deleted")&&manual.optLong("tmdb_id")==old.id)){
                card.id=old.id;card.title=old.title;card.overview=old.overview;card.poster=old.poster;card.backdrop=old.backdrop;card.runtime=old.runtime;card.rating=old.rating;card.genres=old.genres;card.date=old.date;card.origin=old.origin;
            }
            // Repeated API failures cannot produce thousands of blocking network calls.
            // Further cards retain their titles/pairings and are explicitly retryable.
        }
    }
    private JSONObject manual(Card card,String root) throws IOException {
        List<JSONObject> events=new ArrayList<>();JSONObject direct=pairings.get(root,card.path,card.movie);if(direct!=null)events.add(direct);
        if(!card.movie)for(String path:card.episodeRoots){JSONObject event=pairings.get(root,path,false);if(event!=null&&!events.contains(event))events.add(event);}
        Set<Long> ids=new HashSet<>();for(JSONObject event:events)if(!event.optBoolean("deleted"))ids.add(event.optLong("tmdb_id"));
        if(ids.size()>1)throw new IOException("Az összevont sorozat párosításai eltérnek.");
        for(JSONObject event:events)if(!event.optBoolean("deleted"))return event;
        return events.isEmpty()?null:events.get(0);
    }
    private void identify(Card card,String root,MediaLogic.Name name,String source,String folderName,List<NasClient.Entry> siblings) throws Exception {
        Card cached=previous.get((card.movie?"movie:":"tv:")+card.path);String filename=card.path.substring(card.path.lastIndexOf('/')+1);NasClient.Entry nfo=Nfo.select(siblings,card.movie?filename:source,card.movie);
        if(nfo!=null){card.nfoPath=nfo.path;card.nfoModified=nfo.modified;card.nfoSize=nfo.size;}
        JSONObject local=localOverrides.get((card.movie?"movie:":"tv:")+card.path);if(local==null&&!card.movie)for(String path:card.episodeRoots)if(localOverrides.containsKey("tv:"+path)){local=localOverrides.get("tv:"+path);break;}if(local!=null){apply(card,local);card.origin="manual";return;}
        JSONObject pair=manual(card,root);
        if(pair!=null&&!pair.optBoolean("deleted")){
            card.id=pair.getLong("tmdb_id");card.title=pair.optString("title").isBlank()?card.title:pair.getString("title");card.origin="manual";
            if(recognition!=null){if(!force&&cached!=null&&cached.id==card.id&&LibraryRefresh.fresh(cached,reuseTime(cached))){LibraryRefresh.copy(cached,card,clock.getAsLong());card.origin="manual";return;}if(metadataFailures>=3)throw new IOException("A médiaadat-szolgáltatás átmenetileg nem érhető el.");JSONObject info=recognition.details(card.id,card.movie);if(info==null){card.lookupState="retry";throw new IOException("A kézi párosítás azonosítója nem található.");}apply(card,info);}return;
        }
        if((!force||recognition==null)&&LibraryRefresh.unchanged(cached,card,nfo,reuseTime(cached))){LibraryRefresh.copy(cached,card,clock.getAsLong());card.nfoToken=cached.nfoToken;return;}
        if(recognition==null)return;
        if(metadataFailures>=3)throw new IOException("A médiaadat-szolgáltatás átmenetileg nem érhető el.");
        if(nfo!=null){
            if(nfo.size>Nfo.MAX_BYTES)nfosIgnored++;
            else{
                Nfo.Hint hint=null;try{hint=Nfo.parse(nas.readFile(nfo.path,Nfo.MAX_BYTES),card.movie);nfosRead++;}catch(NasClient.ResponseTooLargeException invalid){nfosIgnored++;}catch(IOException unavailable){nfoWarnings++;Card old=previous.get((card.movie?"movie:":"tv:")+card.path);if(old!=null&&old.id>0&&old.origin.equals("nfo"))throw unavailable;}
                if(hint!=null){card.nfoToken=hint.tmdb!=null?"tmdb:"+hint.tmdb:hint.imdb!=null?"imdb:"+hint.imdb:"titles:"+hint.year+":"+new JSONArray(hint.titles).toString();
                    if(!force&&LibraryRefresh.fresh(cached,reuseTime(cached))&&(hint.tmdb!=null&&cached.id==hint.tmdb||cached.origin.equals("nfo")&&!cached.nfoToken.isEmpty()&&cached.nfoToken.equals(card.nfoToken))){LibraryRefresh.copy(cached,card,clock.getAsLong());card.origin="nfo";return;}
                    JSONObject info=null;if(hint.tmdb!=null)info=recognition.details(hint.tmdb,card.movie);if(info==null&&hint.imdb!=null)info=recognition.imdb(hint.imdb,card.movie);
                    for(String title:hint.titles)if(info==null)info=recognition.find(title,hint.year,card.movie);
                    if(info!=null){apply(card,info);card.origin="nfo";return;}
                }
            }
        }
        LinkedHashMap<String,MediaLogic.Name> candidates=new LinkedHashMap<>();
        add(candidates,name);
        boolean fromFolder=card.movie&&name.title.equals(MediaLogic.clean(folderName,false).title)&&!name.title.equals(MediaLogic.clean(filename,true).title);
        for(MediaLogic.Name alias:MediaLogic.aliases(fromFolder?folderName:source,card.movie&&!fromFolder))add(candidates,new MediaLogic.Name(alias.title,alias.year==null?name.year:alias.year));
        if(card.movie){
            String parent=card.path.substring(0,card.path.lastIndexOf('/'));MediaLogic.Name folder=MediaLogic.clean(folderName,false);
            if(!parent.equals(root)&&!MediaLogic.generic(folder.title)){for(MediaLogic.Name alias:MediaLogic.aliases(folderName,false))add(candidates,alias);}
            add(candidates,MediaLogic.movieName(filename,folderName,false));
            MediaLogic.Name file=MediaLogic.clean(filename,true);add(candidates,new MediaLogic.Name(file.title,file.year==null?name.year:file.year));
        }
        for(MediaLogic.Name candidate:candidates.values()){
            JSONObject info=recognition.find(candidate.title,candidate.year,card.movie);
            if(info!=null){apply(card,info);card.origin="name";return;}
            Card old=previous.get((card.movie?"movie:":"tv:")+card.path);
            if(old!=null&&recognition.ambiguousIds.contains(old.id)&&(!card.movie||card.modified>0&&card.modified==old.modified)){
                JSONObject localized=recognition.details(old.id,card.movie);if(localized!=null){apply(card,localized);card.origin="name";return;}
            }
        }
    }
    private static void add(Map<String,MediaLogic.Name> candidates,MediaLogic.Name name){if(name!=null&&!name.title.isBlank())candidates.putIfAbsent(MediaLogic.normalize(name.title)+":"+name.year,name);}
    public static void apply(Card c,JSONObject info){if(info.optLong("id")<=0)return;c.id=info.optLong("id");c.runtime=info.optInt("runtime");c.rating=info.optDouble("vote_average",0);List<String> genreNames=new ArrayList<>();JSONArray genreList=info.optJSONArray("genres");if(genreList!=null)for(int i=0;i<genreList.length();i++){JSONObject genre=genreList.optJSONObject(i);if(genre!=null&&!genre.optString("name").isBlank())genreNames.add(genre.optString("name"));}c.genres=String.join(", ",genreNames);String title=info.optString(c.movie?"title":"name");if(title.isBlank())title=info.optString(c.movie?"original_title":"original_name");if(!title.isBlank())c.title=title;c.overview=info.optString("overview");c.date=info.optString(c.movie?"release_date":"first_air_date");String p=info.optString("poster_path");c.poster=p.startsWith("/")?"https://image.tmdb.org/t/p/w342"+p:"";String b=info.optString("backdrop_path");c.backdrop=b.startsWith("/")?"https://image.tmdb.org/t/p/w780"+b:"";}
    public List<NasClient.Entry> episodes(String root) throws Exception {return episodes(List.of(root));}
    public List<NasClient.Entry> episodes(List<String> roots) throws Exception {
        List<NasClient.Entry> files=new ArrayList<>();for(String root:roots){if(MediaLogic.VIDEO.matcher(root).matches())files.add(new NasClient.Entry(root.substring(root.lastIndexOf('/')+1),root,false,0));else walk(root,0,files);}
        Set<String> seen=new HashSet<>();files.removeIf(e->!seen.add(e.path));
        String common=roots.get(0);if(MediaLogic.VIDEO.matcher(common).matches())common=common.substring(0,common.lastIndexOf('/'));
        if(roots.size()>1){while(!common.isEmpty()){boolean same=true;for(String root:roots)if(!root.equals(common)&&!root.startsWith(common+"/")){same=false;break;}if(same)break;int slash=common.lastIndexOf('/');common=slash<0?"":common.substring(0,slash);}}
        List<NasClient.Entry> result=new ArrayList<>();for(EpisodeIndex.Item item:EpisodeIndex.build(files,common)){NasClient.Entry e=new NasClient.Entry(item.file.name,item.file.path,false,item.file.size);e.season=item.season;e.episode=item.episode;result.add(e);}return result;
    }
    private void walk(String root,int depth,List<NasClient.Entry> result) throws Exception {check();if(depth>24||result.size()>=10000)throw new IOException("Túl nagy epizódlista; a korábbi lista megmarad.");List<NasClient.Entry> entries=list(root);long videoCount=entries.stream().filter(e->!e.directory&&MediaLogic.video(e.name)&&!MediaLogic.ignored(e.name)&&!MediaLogic.sample(e.name)).count();for(NasClient.Entry e:entries){if(MediaLogic.ignored(e.name)||MediaLogic.sample(e.name)||MediaLogic.extra(e.name,!e.directory&&videoCount==1))continue;if(e.directory)walk(e.path,depth+1,result);else if(MediaLogic.video(e.name))result.add(e);}}
    private static List<NasClient.Entry> recent(List<NasClient.Entry> entries){List<NasClient.Entry> ordered=new ArrayList<>(entries);ordered.sort(Comparator.comparingLong((NasClient.Entry e)->e.modified).reversed());return ordered;}
    private boolean containsVideo(String root,int depth)throws Exception{check();if(depth>24||listings.size()>=100000)throw new IOException("Túl nagy epizódlista; a korábbi lista megmaradt.");List<NasClient.Entry> entries=list(root);long count=entries.stream().filter(e->!e.directory&&MediaLogic.video(e.name)&&!MediaLogic.ignored(e.name)&&!MediaLogic.sample(e.name)).count();for(NasClient.Entry e:entries){if(MediaLogic.ignored(e.name)||MediaLogic.sample(e.name)||MediaLogic.extra(e.name,!e.directory&&count==1))continue;if(!e.directory&&MediaLogic.video(e.name)||e.directory&&containsVideo(e.path,depth+1))return true;}return false;}
    private static void check() throws InterruptedException {if(Thread.currentThread().isInterrupted())throw new InterruptedException();}
}
