package hu.synostream.android;

import android.app.Application;
import android.os.*;
import android.util.AtomicFile;
import org.json.*;
import java.util.*;
import java.util.concurrent.*;
import java.lang.ref.WeakReference;
import java.io.*;
import java.nio.charset.StandardCharsets;

public final class SynoApp extends Application {
    public String externalTorrentUri,externalTorrentMime;public final TorrentDraft torrentDraft=new TorrentDraft();public volatile boolean downloadBusy=false;public DownloadStation downloads;public boolean downloadsOpen=false;
    final LibraryRefreshPlan automaticLibraries=new LibraryRefreshPlan();private boolean automaticForeground=false;
    java.util.function.BooleanSupplier automaticCellular=()->this.networkWatch!=null&&!this.networkWatch.allowLocal();
    java.util.function.Consumer<android.content.Intent> scanServiceStarter=intent->startForegroundService(intent);
    long automaticInterval(){return LibraryRefreshPlan.intervalMinutes(store.get("automatic_library_minutes","5"));}
    boolean automaticAllowed(){return LibraryRefreshPlan.allowed(automaticInterval(),automaticCellular.getAsBoolean(),Boolean.parseBoolean(store.get("automatic_library_mobile","false")));}
    void automaticSettingsChanged(){if(scanRunning&&automaticScan)cancelScan(true);automaticLibraries.reset();main.removeCallbacks(automaticTick);if(automaticForeground)main.post(automaticTick);}
    private final Runnable automaticTick=()->checkAutomaticLibraries();
    void automaticForeground(boolean foreground){automaticForeground=foreground;main.removeCallbacks(automaticTick);if(!foreground&&scanRunning&&automaticScan)cancelScan(true);if(foreground)main.postDelayed(automaticTick,1000);}
    private void checkAutomaticLibraries(){
        if(!automaticForeground)return;
        boolean allowed=automaticAllowed();if(automaticInterval()==0)automaticLibraries.prepare(identity+"#"+epoch,List.of(),SystemClock.elapsedRealtime(),0);
        if(allowed&&client!=null&&!demo&&connectionReady()){
            List<String> ids=new ArrayList<>();if(selected()!=null&&!LibraryConfig.paths(selected()).isEmpty())ids.add(selectedLibrary);
            for(int i=0;i<libraries.length();i++){JSONObject library=libraries.optJSONObject(i);if(library!=null&&!LibraryConfig.paths(library).isEmpty())ids.add(library.optString("id"));}
            automaticLibraries.prepare(identity+"#"+epoch,ids,SystemClock.elapsedRealtime(),automaticInterval());
            if(!busy&&!scanRunning&&!downloadBusy&&!metadataBusy){
                String id=automaticLibraries.next();
                if(id!=null){JSONObject chosen=null;for(int i=0;i<libraries.length();i++){JSONObject library=libraries.optJSONObject(i);if(library!=null&&id.equals(library.optString("id")))chosen=library;}
                    if(chosen!=null)scan(chosen);if(chosen==null||!busy)automaticLibraries.complete(id,SystemClock.elapsedRealtime());}
            }
        }
        main.removeCallbacks(automaticTick);main.postDelayed(automaticTick,allowed&&automaticLibraries.waiting()?1000:15000);
    }
    List<Library.Card> previousLibraryCards(JSONObject library,String owner)throws Exception{
        List<Library.Card> result=new ArrayList<>();synchronized(cacheLock){AtomicFile file=new AtomicFile(cacheFile(library,owner));if(file.getBaseFile().exists()){
            try(InputStream input=file.openRead()){JSONArray saved=new JSONArray(new String(NasClient.readBounded(input,20*1024*1024),StandardCharsets.UTF_8));for(int i=0;i<saved.length();i++)result.add(Library.Card.from(saved.getJSONObject(i)));}
        }}return result;
    }
    public Store store; public volatile NasClient client;public String identity="";
    public final CorrectionJournal corrections=new CorrectionJournal();public volatile boolean metadataBusy=false;public final ExecutorService detail=DetailWork.create();
    public final ExecutorService worker=Executors.newSingleThreadExecutor();
    public final ExecutorService cacheIo=CacheIo.create();
    public final ExecutorService scanner=Executors.newSingleThreadExecutor();public volatile boolean scanRunning=false;public volatile boolean automaticScan=false;private volatile java.util.concurrent.Future<?> scanJob;private volatile int scanToken=0;
    public final ExecutorService images=Executors.newFixedThreadPool(3);
    public final Handler main=new Handler(Looper.getMainLooper());
    public List<NasClient.Entry> folders=new ArrayList<>();
    public volatile List<Library.Card> rawCards=new ArrayList<>(),cards=new ArrayList<>();public LocalEdits edits=new LocalEdits("{}");
    public JSONObject libraryDraft=null;public String editorReturnPage="movies";public boolean folderLoaded=false;public int browseGeneration=0;public JSONArray libraries=new JSONArray();
    public volatile String status="";public String query="",page="movies",selectedLibrary="",browsePath="";public int firstVisible=0,scrollOffset=0;
    public volatile boolean busy=false,demo=false;public volatile int epoch=0;
    private final Object cacheLock=new Object();private volatile int loadToken=0;
    final ConnectionRecovery recovery=new ConnectionRecovery();
    private NetworkWatch networkWatch;
    private final ExecutorService reconnectIo=Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"SynoStream-reconnect");t.setDaemon(true);return t;});
    final SessionRetirement retirement=new SessionRetirement((work,millis)->main.postDelayed(work,millis));
    private int reconnectAttempts;
    private WeakReference<MainActivity> ui=new WeakReference<>(null);
    @Override public void onCreate(){super.onCreate();UiLocale.initialize(this);store=new Store(this);libraries=LibraryConfig.migrate(store.libraries());store.libraries(libraries);networkWatch=new NetworkWatch(getSystemService(android.net.ConnectivityManager.class),main,this::networkChanged);networkWatch.start();}
    final ExecutorService profileIo=Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"SynoStream-profile");t.setDaemon(true);return t;});
    final ConnectionDraft connectionDraft=new ConnectionDraft();
    boolean allowLocalNetwork(){return networkWatch==null||networkWatch.allowLocal();}
    String networkKey(){return networkWatch==null?null:networkWatch.key();}
    void connectionEstablished(String startedNetwork){recovery.reset();if(!java.util.Objects.equals(startedNetwork,networkKey()))recovery.requireReconnect();checkNetwork();}
    void checkNetwork(){if(networkWatch!=null)networkWatch.resume(true);}
    boolean connectionReady(){return recovery.state()==ConnectionRecovery.State.READY;}
    void forgetConnection(){recovery.reset();if(client!=null)client.suspendConnection();reconnectAttempts=0;}
    String connectionProblem(){switch(recovery.state()){
        case OFFLINE:return UiText.context(this).getString(R.string.network_offline);
        case AUTH_REQUIRED:return UiText.context(this).getString(R.string.network_auth_required);
        case FAILED:return UiText.context(this).getString(R.string.network_retry_needed);
        default:return UiText.context(this).getString(R.string.network_reconnecting);
    }}
    void networkChanged(String key,boolean cellular,boolean retry){
        ConnectionRecovery.Request request=recovery.observe(key,cellular,client!=null&&!demo,retry);
        if(request==null)return;
        if(!retry)reconnectAttempts=0;
        NasClient root=client;int connectionToken=root.suspendConnection();
        stopService(new android.content.Intent(this,StreamService.class));StreamService.readyUri=null;MainActivity activity=ui.get();if(activity!=null)activity.networkPlaybackStopped();
        if(scanRunning){cancelScan(true);stopService(new android.content.Intent(this,ScanService.class));}
        status=connectionProblem();changed();if(!request.available)return;
        reconnectIo.execute(()->{
            if(!isCurrent(root,request))return;
            NasClient next=null;boolean auth=false;
            try{next=root.reconnectCandidate(request.allowLocal);}catch(SecurityException denied){auth=true;}catch(Exception unavailable){/* No server, address or session data goes into the UI. */}
            NasClient candidate=next;boolean authRequired=auth;
            main.post(()->{
                if(!isCurrent(root,request)){if(candidate!=null)reconnectIo.execute(candidate::logout);return;}
                boolean success=candidate!=null&&retirement.install(root,connectionToken,candidate,reconnectIo);
                recovery.finish(request.token,success,authRequired);
                status=success?root.route:connectionProblem();changed();
                if(!success&&!authRequired&&reconnectAttempts<3){long delay=new long[]{3000,10000,30000}[reconnectAttempts++];main.postDelayed(()->{if(isCurrent(root,request)&&recovery.state()==ConnectionRecovery.State.FAILED)checkNetwork();},delay);}
            });
        });
    }
    private boolean isCurrent(NasClient root,ConnectionRecovery.Request request){return client==root&&recovery.current(request.token);}
    MainActivity currentActivity(){return ui.get();}
    public void attach(MainActivity a){ui=new WeakReference<>(a);}
    public void changed(){main.post(()->{MainActivity activity=ui.get();if(activity!=null&&!activity.isFinishing())activity.render();});}
    public JSONObject selected(){for(int i=0;i<libraries.length();i++){JSONObject l=libraries.optJSONObject(i);if(l!=null&&l.optString("id").equals(selectedLibrary))return l;}return null;}
    public void saveEdits(){store.put("edits:"+identity,edits.toString());refreshEdits();}
    public void refreshEdits(){cards=edits.apply(rawCards,selectedLibrary);changed();}
    interface LibraryFactory {Library create(NasClient client,String key,TmdbApi.Cache cache);}
    LibraryFactory libraryFactory=Library::new;
    private final PairingReadCache scanPairings=new PairingReadCache();private List<Library.Card> scanBase;private String scanBaseLibrary="",scanBaseOwner="";private int scanBaseToken;
    public void scan(JSONObject library){scan(library,false);}
    public void scan(JSONObject library,boolean force){if(library==null||busy||client==null)return;if(!connectionReady()){status=connectionProblem();changed();return;}if(LibraryConfig.paths(library).isEmpty()){status="Válassz forrást ehhez a médiatárhoz.";changed();return;}busy=true;changed();boolean automatic=!force&&automaticLibraries.running(library.optString("id"));if(automatic){if(!automaticForeground||!automaticAllowed()){busy=false;automaticLibraries.reset();return;}runScan(library,()->{},()->{},false);return;}try{scanServiceStarter.accept(new android.content.Intent(this,ScanService.class).putExtra("library",library.toString()).putExtra("force_metadata",force));}catch(Exception e){busy=false;status="A háttérben is futó beolvasás nem indítható. Nyisd meg az alkalmazást, és próbáld újra.";changed();}}
    public void cancelScan(){cancelScan(false);}
    public void cancelScan(boolean keepPending){if(keepPending)automaticLibraries.reset();else automaticLibraries.cancel(SystemClock.elapsedRealtime());rollbackPreview(scanToken);if(!keepPending)store.put("scan_pending","");scanToken++;java.util.concurrent.Future<?> job=scanJob;if(job!=null)job.cancel(true);scanRunning=false;automaticScan=false;busy=false;status="Beolvasás megszakítva. A korábbi lista megmaradt.";changed();}
    private void rollbackPreview(int token){if(scanBase!=null&&scanBaseToken==token&&scanBaseLibrary.equals(selectedLibrary)&&scanBaseOwner.equals(identity)){rawCards=scanBase;cards=edits.apply(rawCards,selectedLibrary);}if(scanBaseToken==token)scanBase=null;}
    private void publishScanBatch(List<String> batch,int generation,int token,String libraryId,long revision){main.post(()->{if(epoch!=generation||scanToken!=token||!selectedLibrary.equals(libraryId))return;try{Map<String,Library.Card> merged=new LinkedHashMap<>();for(Library.Card card:rawCards)merged.put((card.movie?"movie:":"tv:")+card.path,card);List<Library.Card> incoming=new ArrayList<>();for(String json:batch)incoming.add(Library.Card.from(new JSONObject(json)));corrections.applyAfter(incoming,revision);for(Library.Card card:incoming)merged.put((card.movie?"movie:":"tv:")+card.path,card);rawCards=new ArrayList<>(merged.values());cards=edits.apply(rawCards,libraryId);changed();}catch(JSONException invalid){/* A preview never replaces the last committed cache. */}});}
    void runScan(JSONObject library,Runnable progress,Runnable done){runScan(library,progress,done,false);}
    void runScan(JSONObject library,Runnable progress,Runnable done,boolean force){
        if(scanRunning||client==null){done.run();return;}scanRunning=true;store.put("scan_pending",identity+"|"+library.optString("id"));List<String> paths=LibraryConfig.paths(library);if(paths.isEmpty()){status="Válassz forrást ehhez a médiatárhoz.";changed();scanRunning=false;busy=false;done.run();return;}
        boolean automatic=automaticLibraries.running(library.optString("id"));automaticScan=automatic;boolean displayedAtStart=selectedLibrary.equals(library.optString("id"));long startedCorrections=corrections.revision();int generation=epoch,token=++scanToken;NasClient connection=client;busy=true;status=UiText.context(this).getString(R.string.scan_discovering);changed();List<Library.Card> old=new ArrayList<>(rawCards);LocalEdits scanEdits=edits;String scanIdentity=identity;String scanLibraryJson=library.toString();String scanLibrariesJson=libraries.toString();scanBase=displayedAtStart?old:null;scanBaseLibrary=library.optString("id");scanBaseOwner=scanIdentity;scanBaseToken=token;
        scanJob=scanner.submit(()->{
            try{
                List<Library.Card> previous;try{previous=previousLibraryCards(new JSONObject(scanLibraryJson),scanIdentity);}catch(IOException|JSONException invalidCache){previous=new ArrayList<>();}
                if(displayedAtStart)previous=old;
                else {final List<Library.Card> baseline=previous;main.post(()->{if(epoch==generation&&scanToken==token)scanBase=baseline;});}
                Map<String,JSONObject> overrides=scanEdits.overrides();String key=store.secret("tmdb_key");Map<String,Library.Card> all=new LinkedHashMap<>();int matched=0,pairs=0,errors=0,invalid=0;
                ScanUpdates updates=new ScanUpdates(previous,()->System.nanoTime()/1_000_000,batch->publishScanBatch(batch,generation,token,library.optString("id"),startedCorrections));
                for(String path:paths){Library repo=libraryFactory.create(connection,key,force?null:new MetadataCache(this));repo.previous(previous);repo.localOverrides(overrides);repo.forceMetadata(force);repo.reuseConfirmed(automatic);repo.pairingCache(scanPairings,scanIdentity);repo.preview(updates::offer,()->{updates.flush();main.post(()->{if(epoch==generation&&scanToken==token){status=UiText.context(this).getString(R.string.scan_enriching);changed();}});});final int previousCount=all.size();
                    List<Library.Card> found=repo.scan(path,library.optBoolean("movie",true),n->{if(epoch==generation&&scanToken==token&&updates.progress(previousCount+n)){status=(previousCount+n)+" műsor feldolgozva…";changed();progress.run();}});
                    for(Library.Card card:found)all.putIfAbsent((card.movie?"movie:":"tv:")+card.path,card);matched+=repo.matched;pairs+=repo.pairings.events;errors+=repo.metadataErrors;invalid+=repo.pairings.invalid;
                }
                updates.flush();if(epoch!=generation||scanToken!=token)return;
                if(!scanEdits.overrides().isEmpty()){main.post(()->{if(epoch==generation&&scanToken==token){status=UiText.context(this).getString(R.string.scan_syncing);changed();}});PendingSync.retry(scanEdits,new JSONArray(scanLibrariesJson),connection::savePairing);synchronized(SynoApp.this){store.put("edits:"+scanIdentity,scanEdits.toString());}}
                if(epoch!=generation||scanToken!=token)return;List<Library.Card> result=new ArrayList<>(all.values());corrections.applyAfter(result,startedCorrections);try{saveCache(new JSONObject(scanLibraryJson),result,scanIdentity).get();}catch(ExecutionException failed){if(failed.getCause() instanceof Exception)throw (Exception)failed.getCause();throw failed;}store.put("scan_pending","");
                String summary=result.size()+" műsor • "+pairs+" kézi bejegyzés"+(errors>0?" • "+errors+" újrapróbálandó":"")+(invalid>0?" • "+invalid+" hibás párosítás":"");
                main.post(()->{if(epoch==generation&&scanToken==token&&selectedLibrary.equals(library.optString("id"))){if(corrections.applyAfter(result,startedCorrections)){try{saveCache(new JSONObject(scanLibraryJson),result,scanIdentity);}catch(Exception ignored){}}scanBase=null;rawCards=result;cards=edits.apply(result,selectedLibrary);status=summary;changed();}});
            }catch(Exception e){String failure=safeError(e);main.post(()->{if(epoch==generation&&scanToken==token){rollbackPreview(token);status=failure;}});}finally{main.post(()->{if(epoch==generation&&scanToken==token){scanRunning=false;automaticScan=false;busy=false;automaticLibraries.complete(library.optString("id"),SystemClock.elapsedRealtime());changed();}done.run();});}
        });
    }
    Future<?> commitMediaDeletion(Library.Card selected,JSONObject library,MediaDeletion.Result result)throws Exception {
        Set<String> members=new HashSet<>(selected.memberPaths.isEmpty()?List.of(selected.path):selected.memberPaths);
        edits.deletedMedia(result::removed);store.put("edits:"+identity,edits.toString());
        if(!selectedLibrary.equals(library.optString("id"))){removeCache(library);return null;}
        List<Library.Card> kept=new ArrayList<>();
        for(Library.Card original:rawCards){if(result.removed(original.path)||(selected.movie||result.allSeasons)&&members.contains(original.path))continue;Library.Card copy=Library.Card.from(original.json());copy.episodeRoots.removeIf(result::removed);copy.memberPaths.removeIf(result::removed);kept.add(copy);}
        rawCards=kept;cards=edits.apply(kept,selectedLibrary);changed();return saveCache(library,kept,identity);
    }
    public void updatedInfo(Library.Card selected,JSONObject info){
        Set<String> members=new HashSet<>(selected.memberPaths.isEmpty()?List.of(selected.path):selected.memberPaths);for(String path:members)corrections.record(selected.movie,path,info);for(String path:selected.episodeRoots)corrections.record(false,path,info);
        for(Library.Card card:rawCards)if(card.movie==selected.movie&&(members.contains(card.path)||selected.episodeRoots.contains(card.path))){Library.apply(card,info);card.origin="manual";card.lookupState="matched";}
        Library.apply(selected,info);saveEdits();JSONObject library=selected();if(library!=null){try{saveCache(library,rawCards,identity);}catch(Exception ignored){}}
    }
    synchronized File cacheFile(JSONObject library) throws Exception {return cacheFile(library,identity);}
    private File cacheFile(JSONObject library,String owner) throws Exception {String name=CacheKeys.fileName(owner,library);File dir=new File(getFilesDir(),"library-cache");if(!dir.exists()&&!dir.mkdirs())throw new IOException("A gyorsítótár nem hozható létre.");return new File(dir,name);}
    public void removeCache(JSONObject library){if(library==null)return;try{File file=cacheFile(new JSONObject(library.toString()),identity);CacheIo.remove(cacheIo,cacheLock,file);}catch(Exception ignored){}}
    public void cleanCaches(){try{String owner=identity;Set<String> keep=new HashSet<>();for(int i=0;i<libraries.length();i++)keep.add(cacheFile(new JSONObject(libraries.getJSONObject(i).toString()),owner).getName());CacheIo.prune(cacheIo,cacheLock,new File(getFilesDir(),"library-cache"),keep);}catch(Exception ignored){}}
    public void loadCache(JSONObject library,Runnable completed){
        int generation=epoch,token=scanToken,requestLoad=++loadToken;String libraryId=library.optString("id"),owner=identity,request=library.toString();busy=true;status="Korábbi lista betöltése…";rawCards=new ArrayList<>();cards=new ArrayList<>();changed();
        CacheIo.load(cacheIo,()->{List<Library.Card> loaded=new ArrayList<>();String failure=null;try{synchronized(cacheLock){AtomicFile file=new AtomicFile(cacheFile(new JSONObject(request),owner));if(file.getBaseFile().exists()){JSONArray data=new JSONArray(new String(NasClient.readBounded(file.openRead(),20*1024*1024),StandardCharsets.UTF_8));for(int i=0;i<data.length();i++)loaded.add(Library.Card.from(data.getJSONObject(i)));}}}catch(Exception e){loaded.clear();failure="A korábbi lista nem tölthető be. Frissítsd a médiatárat.";}String error=failure;
            main.post(()->{CacheLoadRules.Finish finish=CacheLoadRules.finish(requestLoad,loadToken,CacheLoadRules.canApply(generation,libraryId,token,epoch,selectedLibrary,scanToken),scanRunning);if(!finish.latest)return;if(finish.apply){rawCards=loaded;cards=edits.apply(loaded,libraryId);if(error!=null)status=error;else if(!loaded.isEmpty())status="Korábbi lista • "+cards.size()+" műsor";else status="";}else if(finish.clear){rawCards=new ArrayList<>();cards=new ArrayList<>();status="";}else if("Korábbi lista betöltése…".equals(status))status="";if(finish.busyRelease)busy=false;changed();finish.complete(completed);});
        });
    }
    private Future<?> saveCache(JSONObject library,List<Library.Card> result,String owner)throws Exception {byte[] data=CacheIo.snapshot(result);String request=library.toString();return cacheIo.submit(()->{saveCache(new JSONObject(request),data,owner);return null;});}
    private void saveCache(JSONObject library,byte[] data,String owner) throws Exception {synchronized(cacheLock){AtomicFile file=new AtomicFile(cacheFile(library,owner));FileOutputStream output=file.startWrite();try{output.write(data);file.finishWrite(output);}catch(Exception e){file.failWrite(output);throw e;}}}
    public static String safeError(Exception e){if(e instanceof JSONException)return "A NAS váratlan választ adott.";if(e instanceof java.net.UnknownHostException||e instanceof java.net.SocketTimeoutException||e instanceof java.net.ConnectException)return "A kiszolgáló nem érhető el. Ellenőrizd a hálózatot, majd próbáld újra.";if(e instanceof javax.net.ssl.SSLException)return "A NAS HTTPS-tanúsítványa nem ellenőrizhető.";if(e instanceof InterruptedException)return "Megszakítva.";String message=e.getMessage();return message!=null&&!message.contains("http")&&!message.contains("_sid")&&!message.contains("api_key")?message:"A művelet nem sikerült. Ellenőrizd a kapcsolatot.";}
}
