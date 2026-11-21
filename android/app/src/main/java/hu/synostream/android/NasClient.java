package hu.synostream.android;

import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** File Station only: never uses Video Station or a transcoding endpoint. */
public final class NasClient implements Library.Source {
    static final class OtpRequiredException extends SecurityException {OtpRequiredException(String message){super(message);}}
    public static final class ApiRejectedException extends IOException {ApiRejectedException(String message){super(message);}}
    public static final class ResponseTooLargeException extends IOException {ResponseTooLargeException(){super("A válasz túl nagy.");}}
    public static final class Credentials {
        public final String address,local,ddns,quick,user,password,otp;
        public Credentials(String a,String l,String u,String p,String o){this(a,l,"","",u,p,o);}
        public Credentials(String a,String l,String d,String q,String u,String p,String o){address=a.trim();local=l.trim();ddns=d.trim();quick=q.trim();user=u.trim();password=p;otp=o.trim();}
        Credentials withoutOtp(){return new Credentials(address,local,ddns,quick,user,password,"");}
    }
    public static final class Entry {
        public final String name,path; public final boolean directory; public final long size;
        public int season=-1,episode=-1;public long modified=0;public boolean symbolic=false;public String realPath="";
        public String label(){return season<0?name:String.format(Locale.ROOT,"S%02dE%02d  •  %s",season,episode,name);}
        public Entry(String n,String p,boolean d,long s){name=n;path=p;directory=d;size=s;}
    }
    public static final class Stream implements AutoCloseable {
        public final HttpURLConnection connection; public final InputStream body;
        Stream(HttpURLConnection c) throws IOException {this(c,c.getInputStream());}
        Stream(HttpURLConnection c,InputStream buffered){connection=c;body=buffered;}
        public void close(){try{body.close();}catch(IOException ignored){}connection.disconnect();}
    }
    interface QuickResolver {List<String> resolve(String id)throws Exception;}
    interface EndpointProbe {boolean connect(String endpoint)throws Exception;}
    private final EndpointProbe endpointProbe;
    private final Credentials credentials;private final QuickResolver quickResolver;private boolean otpAttempted;private String authSession="SynoStreamAndroid";
    Credentials settingsCredentials(){NasClient next=replacement;return next==null?credentials:next.settingsCredentials();}
    public NasClient fork(String session){NasClient copy=new NasClient(settingsCredentials(),quickResolver,endpointProbe);copy.authSession=session;return copy;}
    private final CookieManager cookies=new CookieManager(null,CookiePolicy.ACCEPT_ALL);
    private JSONObject apis=new JSONObject();
    private String base="",sid="",authPath="auth.cgi";
    public volatile String route="";
    // A stable facade is shared by scanner, playback and Download Station. Old in-flight
    // requests finish on their original session; only new calls use the replacement.
    private final Object connectionLock=new Object();
    private volatile NasClient replacement;
    private volatile boolean suspended;
    private int connectionGeneration,retirementRevision;
    private final Set<NasClient> superseded=Collections.newSetFromMap(new IdentityHashMap<>());
    int suspendConnection(){synchronized(connectionLock){suspended=true;return ++connectionGeneration;}}
    boolean installConnection(int generation,NasClient next){synchronized(connectionLock){if(generation!=connectionGeneration)return false;if(replacement!=null&&replacement!=next)superseded.add(replacement);replacement=next;retirementRevision++;route=next.route;suspended=false;return true;}}
    private NasClient current()throws IOException{if(suspended)throw new IOException("A hálózati kapcsolat változik. Várd meg az újracsatlakozást.");return replacement;}
    NasClient reconnectCandidate(boolean allowLocal)throws Exception{
        // An OTP is one-use data: never replay the code entered at the original login.
        NasClient next=new NasClient(settingsCredentials().withoutOtp(),quickResolver,endpointProbe);
        next.authSession="SynoStreamAndroid_"+UUID.randomUUID().toString().replace("-","");
        next.connect(allowLocal);return next;
    }
    public NasClient(Credentials c){this(c,null);}
    NasClient(Credentials c,QuickResolver resolver){this(c,resolver,null);}
    NasClient(Credentials c,QuickResolver resolver,EndpointProbe probe){credentials=c;quickResolver=resolver;endpointProbe=probe;}
    public static String normalizeAddress(String address){
        String value=address.trim().replaceFirst("(?i)^https://","https://").replaceFirst("(?i)^http://","http://");
        if(!value.contains("://"))value="https://"+value;
        URI uri=URI.create(value);
        if(!Set.of("http","https").contains(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null||uri.getQuery()!=null||uri.getFragment()!=null||!(uri.getPath().isEmpty()||uri.getPath().equals("/")))
            throw new IllegalArgumentException("A NAS címéhez HTTP- vagy HTTPS-kiszolgálócím szükséges, jelszó és útvonal nélkül.");
        return value.replaceAll("/+$","");
    }
    public synchronized void connect() throws Exception {connect(true);}
    synchronized void connect(boolean allowLocal) throws Exception {
        if(credentials.user.isBlank()||credentials.password.isEmpty())throw new IOException("Add meg a NAS címét, a felhasználónevet és a jelszót.");
        Exception last=null;
        for(NasRoutes.Route candidate:NasRoutes.plan(credentials,allowLocal))try{if(connectRoute(candidate))return;}catch(SecurityException rejected){throw rejected;}catch(Exception unavailable){last=unavailable;}
        if(last instanceof javax.net.ssl.SSLException)throw new IOException(sslMessage(last));
        throw new IOException("A NAS nem érhető el. Ellenőrizd a címet, a hálózatot és a File Station jogosultságát.");
    }
    static final class Endpoint {final String value;final NasRoutes.Kind kind;Endpoint(String v,NasRoutes.Kind k){value=v;kind=k;}}
    static List<Endpoint> quickEndpoints(String id,List<String> resolved){
        List<Endpoint> values=new ArrayList<>();for(String value:resolved)values.add(new Endpoint(value,NasRoutes.Kind.QUICKCONNECT));
        if(values.isEmpty()){String direct=directFallback(id);values.add(new Endpoint(direct,directKind(direct)));}return values;
    }
    static NasRoutes.Kind directKind(String value){String host=URI.create(value).getHost();if(NasRoutes.privateHost(host))return NasRoutes.Kind.LOCAL;if(host.matches("[0-9.]+")||host.contains(":"))return NasRoutes.Kind.DIRECT;return host.contains(".")?NasRoutes.Kind.DDNS:NasRoutes.Kind.LOCAL;}
    private boolean connectRoute(NasRoutes.Route route)throws Exception{
        List<Endpoint> endpoints=route.kind==NasRoutes.Kind.QUICKCONNECT?(quickResolver==null?quickConnectBases(route.value):quickEndpoints(route.value,quickResolver.resolve(route.value))):List.of(new Endpoint(route.value,route.kind));
        Set<String> tried=new HashSet<>();Exception last=null;
        for(Endpoint endpoint:endpoints)if(tried.add(endpoint.value))try{if(endpointProbe==null?tryConnect(endpoint.value):endpointProbe.connect(endpoint.value)){this.route=NasRoutes.routeName(endpoint.kind);return true;}}catch(SecurityException rejected){throw rejected;}catch(Exception unavailable){last=unavailable;}
        if(last!=null)throw last;return false;
    }
    private List<Endpoint> quickConnectBases(String id)throws Exception{
        JSONObject command=new JSONObject().put("version",1).put("command","get_server_info").put("stop_when_error",false).put("stop_when_success",false).put("id","dsm_portal_https").put("serverID",id).put("is_gofile",false);
        byte[] response;try{response=requestBytes("https://global.quickconnect.to/Serv.php","POST",new JSONArray().put(command).toString().getBytes(StandardCharsets.UTF_8),"application/json",65536,15000);}catch(IOException unavailable){response="[]".getBytes(StandardCharsets.UTF_8);}
        JSONArray rows=new JSONArray(new String(response,StandardCharsets.UTF_8));List<String> bases=new ArrayList<>();
        for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i),env=row.optJSONObject("env");String region=env==null?"":env.optString("relay_region");if(row.optInt("errno",-1)==0&&region.matches("[a-z0-9-]+"))bases.add("https://"+id+"."+region+".quickconnect.to");}
        return quickEndpoints(id,bases);
    }
    enum CheckStatus { SUCCESS, CODE_REQUIRED, AUTH_FAILED, UNAVAILABLE, SKIPPED }
    static final class ConnectionCheck {final NasRoutes.Kind kind;final CheckStatus status;ConnectionCheck(NasRoutes.Kind k,CheckStatus s){kind=k;status=s;}}
    List<ConnectionCheck> checkConnections(boolean allowLocal)throws Exception{
        List<NasRoutes.Route> all=NasRoutes.plan(credentials,true),usable;try{usable=NasRoutes.plan(credentials,allowLocal);}catch(IllegalArgumentException noRemote){usable=List.of();}Set<String> keys=new HashSet<>();for(NasRoutes.Route r:usable)keys.add(r.key());List<ConnectionCheck> results=new ArrayList<>();
        for(NasRoutes.Route r:all){if(Thread.currentThread().isInterrupted())throw new InterruptedException();if(!keys.contains(r.key())){results.add(new ConnectionCheck(r.kind,CheckStatus.SKIPPED));continue;}
            NasClient test=new NasClient(credentials.withoutOtp(),quickResolver,endpointProbe).fork("SynoStreamCheck_"+UUID.randomUUID().toString().replace("-",""));CheckStatus result=CheckStatus.UNAVAILABLE;
            try{if(test.connectRoute(r))result=CheckStatus.SUCCESS;}catch(OtpRequiredException code){result=CheckStatus.CODE_REQUIRED;}catch(SecurityException auth){result=CheckStatus.AUTH_FAILED;}catch(Exception unavailable){/* No endpoint or credential is returned. */}finally{if(!test.sid.isEmpty())test.logout();}
            results.add(new ConnectionCheck(r.kind,result));
        }return results;
    }
    static String sslMessage(Throwable error){String text=Objects.toString(error.getMessage(),"").toLowerCase(Locale.ROOT);if(text.contains("plaintext")||text.contains("unrecognized ssl message"))return "A NAS valószínűleg HTTP-n figyel. Add meg kifejezetten: http://cím:port";return "A NAS tanúsítványa nem ellenőrizhető. Használj érvényes HTTPS-címet, vagy kifejezetten megadott helyi HTTP-címet.";}
    static String connectionRoute(boolean quick,boolean directFallback){return quick&&!directFallback?"QuickConnect":"Közvetlen kapcsolat";}
    static String directFallback(String address){return normalizeAddress(address);}
    private boolean tryConnect(String candidate) throws Exception {
        base=candidate;
        if(base.contains(".quickconnect.to"))requestBytes(base+"/","GET",null,null,2*1024*1024,12000);
        JSONObject data=json(base+"/webapi/query.cgi",Map.of("api","SYNO.API.Info","version","1","method","query","query","SYNO.API.Auth,SYNO.FileStation.List,SYNO.FileStation.Download"),false);
        apis=data.optJSONObject("data");
        if(!data.optBoolean("success")||apis==null||!apis.has("SYNO.FileStation.List")||!apis.has("SYNO.FileStation.Download"))return false;
        JSONObject auth=apis.optJSONObject("SYNO.API.Auth");authPath=auth==null?"auth.cgi":auth.optString("path","auth.cgi");
        login();return true;
    }
    private void login() throws Exception {
        if((!sid.isEmpty()||otpAttempted)&&!credentials.otp.isBlank())throw new SecurityException("A kétlépcsős NAS-munkamenet lejárt. Jelentkezz be új kóddal.");
        Map<String,String> p=new LinkedHashMap<>(Map.of("api","SYNO.API.Auth","version","6","method","login","account",credentials.user,"passwd",credentials.password,"session",authSession,"format","sid"));
        if(!credentials.otp.isBlank())p.put("otp_code",credentials.otp);
        if(!credentials.otp.isBlank())otpAttempted=true;
        JSONObject result=json(endpoint(authPath),p,true);
        if(!result.optBoolean("success")){
            int code=result.optJSONObject("error")==null?-1:result.getJSONObject("error").optInt("code");
            if(code==403)throw new OtpRequiredException("A NAS kétlépcsős belépési kódot kér, vagy a megadott kód lejárt.");
            if(code==404)throw new SecurityException("A NAS kétlépcsős belépési kódot kér, vagy a megadott kód lejárt.");
            throw new SecurityException("A NAS elutasította a bejelentkezést ("+code+").");
        }
        sid=result.getJSONObject("data").getString("sid");if(sid.isBlank())throw new IOException("A NAS nem adott érvényes munkamenetet.");
    }
    private String endpoint(String path) throws IOException {
        if(path.startsWith("/")||path.contains("..")||path.contains(":")||path.contains("?"))throw new IOException("Érvénytelen NAS API-útvonal.");
        return base+"/webapi/"+path;
    }
    public JSONObject call(String api,String method,Map<String,String> params) throws Exception {
        NasClient next=current();if(next!=null)return next.call(api,method,params);
        for(int attempt=0;attempt<2;attempt++){
            NasClient selected=current();if(selected!=null)return selected.call(api,method,params);
            ApiState state;synchronized(this){state=new ApiState(endpoint(apis.getJSONObject(api).getString("path")),base,sid);}
            Map<String,String> p=new LinkedHashMap<>(params);p.put("api",api);p.put("method",method);p.put("version","2");p.put("_sid",state.session);
            JSONObject response=new JSONObject(new String(requestBytes(state.url+"?"+form(p),"GET",null,"application/x-www-form-urlencoded",8*1024*1024,15000,state.server),StandardCharsets.UTF_8));
            if(response.optBoolean("success"))return response.optJSONObject("data")==null?new JSONObject():response.getJSONObject("data");
            int code=response.optJSONObject("error")==null?-1:response.getJSONObject("error").optInt("code");
            if(attempt==0&&(code==106||code==107||code==119)){synchronized(this){if(state.session.equals(sid))login();}continue;}
            throw new IOException(code==101&&api.equals("SYNO.FileStation.List")?"A NAS a mappalista kérését elutasította (101; "+(method.equals("list_share")?"megosztások lekérése":"mappa tartalmának lekérése")+").":"A NAS-művelet nem sikerült ("+code+").");
        }
        throw new IOException("A NAS-munkamenet lejárt.");
    }
    public List<Entry> list(String path) throws Exception {return listInternal(path,false);}
    public List<Entry> listForDeletion(String path)throws Exception{return listInternal(path,true);}
    private List<Entry> listInternal(String path,boolean deletion)throws Exception {
        NasClient next=current();if(next!=null)return deletion?next.listForDeletion(path):next.list(path);
        List<Entry> result=new ArrayList<>();Set<String> seen=new HashSet<>();int offset=0;
        while(true){
            if(Thread.currentThread().isInterrupted())throw new InterruptedException();
            Map<String,String> p=new LinkedHashMap<>(Map.of("offset",String.valueOf(offset),"limit","500","additional",path.isEmpty()?"[\"time\"]":deletion?"[\"size\",\"time\",\"real_path\"]":"[\"size\",\"time\"]"));if(!path.isEmpty())p.put("folder_path",path);
            JSONObject data=call("SYNO.FileStation.List",path.isEmpty()?"list_share":"list",p);
            JSONArray files=data.optJSONArray(path.isEmpty()?"shares":"files");if(files==null)throw new IOException("Hiányos NAS-mappalista.");
            for(int i=0;i<files.length();i++){
                JSONObject f=files.getJSONObject(i);String n=f.getString("name"),full=f.optString("path",path+"/"+n);
                if(!seen.add(full))throw new IOException("Ismétlődő NAS-mappalista.");
                JSONObject extra=f.optJSONObject("additional");Entry entry=new Entry(n,full,f.optBoolean("isdir"),extra==null?0:extra.optLong("size"));if(extra!=null&&extra.optJSONObject("time")!=null)entry.modified=extra.getJSONObject("time").optLong("mtime");entry.symbolic=f.optBoolean("islink",false);if(extra!=null){Object physical=extra.opt("real_path");if(physical instanceof String)entry.realPath=(String)physical;else if(physical instanceof JSONObject)entry.realPath=((JSONObject)physical).optString("real_path","");}result.add(entry);
            }
            offset+=files.length();int total=data.optInt("total",-1);
            if(files.length()==0){if(total>offset)throw new IOException("A NAS hiányos mappalistát adott.");break;}
            if(total>=0?offset>=total:files.length()<500)break;
            if(offset>=100000)throw new IOException("A mappa túl sok elemet tartalmaz.");
        }
        return result;
    }
    public Stream stream(String path,String range,boolean head) throws Exception {
        NasClient next=current();if(next!=null)return next.stream(path,range,head);
        for(int attempt=0;attempt<2;attempt++){
            String url; synchronized(this){url=endpoint(apis.getJSONObject("SYNO.FileStation.Download").getString("path"))+"?"+form(Map.of("api","SYNO.FileStation.Download","version","2","method","download","path",path,"mode","open","_sid",sid));}
            HttpURLConnection c=open(url,head?"HEAD":"GET",30000);if(range!=null)c.setRequestProperty("Range",range);
            int status=c.getResponseCode();storeCookies(c);
            if(!head&&c.getContentType()!=null&&c.getContentType().toLowerCase(Locale.ROOT).contains("json")){
                byte[] body;try{InputStream response=status>=400?c.getErrorStream():c.getInputStream();if(response==null)throw new IOException("A fájl nem olvasható (HTTP "+status+").");body=readBounded(response,65536);}catch(Exception e){c.disconnect();throw e;}
                JSONObject failure=downloadFailure(body);
                if(failure==null){if(status!=200&&status!=206){c.disconnect();throw new IOException("A fájl nem olvasható (HTTP "+status+").");}return new Stream(c,new ByteArrayInputStream(body));}
                c.disconnect();int code=failure.optJSONObject("error")==null?-1:failure.getJSONObject("error").optInt("code");
                if(attempt==0&&(code==106||code==107||code==119)){synchronized(this){login();}continue;}
                throw new IOException("A NAS nem engedélyezi a fájl olvasását ("+code+").");
            }
            if(status!=200&&status!=206){c.disconnect();throw new IOException("A fájl nem olvasható (HTTP "+status+").");}
            return new Stream(c);
        }
        throw new IOException("A NAS-munkamenet lejárt.");
    }
    static JSONObject downloadFailure(byte[] body){try{JSONObject value=new JSONObject(new String(body,StandardCharsets.UTF_8));return Boolean.FALSE.equals(value.opt("success"))?value:null;}catch(JSONException notObject){return null;}}
    public byte[] readFile(String path,int limit) throws Exception {try(Stream s=stream(path,null,false)){return readBounded(s.body,limit);}}
    public synchronized void savePairing(String root,String mediaPath,boolean movie,JSONObject info) throws Exception {
        NasClient next=current();if(next!=null){next.savePairing(root,mediaPath,movie,info);return;}
        String relative=MediaLogic.relative(root,mediaPath);
        if(!MediaLogic.safeRelative(relative)||relative.equals(".")&&movie||info.optLong("id")<=0)throw new IOException("A párosítás nem tartozik a kiválasztott médiatárhoz.");
        String directory=root+"/.synostream/parositasok";long generation=0;
        if(list(root).stream().anyMatch(e->e.directory&&e.name.equals(".synostream"))&&list(root+"/.synostream").stream().anyMatch(e->e.directory&&e.name.equals("parositasok"))){
            for(Entry entry:list(directory))if(!entry.directory&&entry.name.matches("[0-9a-f]{32}\\.json")&&entry.size<=16384){
                JSONObject event=Pairings.validate(entry.name,readFile(entry.path,16384));
                if(event!=null&&event.optString("relative_path").equals(relative)&&event.optString("media_type").equals(movie?"movie":"tv"))generation=Math.max(generation,event.optLong("generation"));
            }
        }
        String identifier=UUID.randomUUID().toString().replace("-","");
        JSONObject event=new JSONObject().put("format_version",1).put("event_id",identifier).put("relative_path",relative).put("media_type",movie?"movie":"tv").put("tmdb_id",info.getLong("id")).put("title",info.optString(movie?"title":"name")).put("deleted",false).put("generation",generation+1).put("created_ns",System.currentTimeMillis()*1_000_000L);
        byte[] payload=event.toString().getBytes(StandardCharsets.UTF_8);String filename=identifier+".json";
        if(Pairings.validate(filename,payload)==null)throw new IOException("A párosítási rekord nem érvényes.");
        uploadEvent(directory,filename,payload);
        if(!java.security.MessageDigest.isEqual(payload,readFile(directory+"/"+filename,16384)))throw new IOException("A NAS-ra mentett párosítás nem ellenőrizhető. A helyi korrekció megmarad.");
    }
    private synchronized void uploadEvent(String directory,String filename,byte[] payload) throws Exception {
        if(!directory.endsWith("/.synostream/parositasok")||!filename.matches("[0-9a-f]{32}\\.json")||payload.length>16384)throw new IOException("Érvénytelen párosítási cél.");
        String api="SYNO.FileStation.Upload";
        if(!apis.has(api)){
            JSONObject discovery=json(base+"/webapi/query.cgi",Map.of("api","SYNO.API.Info","version","1","method","query","query",api),false);
            JSONObject data=discovery.optJSONObject("data");if(!discovery.optBoolean("success")||data==null||!data.has(api))throw new IOException("A NAS nem támogatja a párosítás mentését.");
            apis.put(api,data.getJSONObject(api));
        }
        for(int attempt=0;attempt<2;attempt++){
            String boundary="SynoStream"+UUID.randomUUID().toString().replace("-","");ByteArrayOutputStream body=new ByteArrayOutputStream();
            Map<String,String> values=new LinkedHashMap<>();values.put("api",api);values.put("version","2");values.put("method","upload");values.put("_sid",sid);values.put("path",directory);values.put("create_parents","true");values.put("overwrite","true");
            for(Map.Entry<String,String> field:values.entrySet())body.write(("--"+boundary+"\r\nContent-Disposition: form-data; name=\""+field.getKey()+"\"\r\n\r\n"+field.getValue()+"\r\n").getBytes(StandardCharsets.UTF_8));
            body.write(("--"+boundary+"\r\nContent-Disposition: form-data; name=\"file\"; filename=\""+filename+"\"\r\nContent-Type: application/json\r\n\r\n").getBytes(StandardCharsets.UTF_8));body.write(payload);body.write(("\r\n--"+boundary+"--\r\n").getBytes(StandardCharsets.UTF_8));
            JSONObject response=new JSONObject(new String(requestBytes(endpoint(apis.getJSONObject(api).getString("path")),"POST",body.toByteArray(),"multipart/form-data; boundary="+boundary,65536,45000),StandardCharsets.UTF_8));
            if(response.optBoolean("success"))return;int code=response.optJSONObject("error")==null?-1:response.getJSONObject("error").optInt("code");
            if(attempt==0&&(code==106||code==107||code==119)){login();continue;}
            throw new IOException("A NAS nem tudta menteni a párosítást ("+code+"). A helyi korrekció megmarad.");
        }
    }

    private static final class ApiState {final String url,server,session;ApiState(String u,String b,String s){url=u;server=b;session=s;}}
    // Called only while holding the client monitor; the returned strings are immutable.
    private ApiState knownApiState(String api,int version)throws Exception{JSONObject info=apis.getJSONObject(api);if(info.optInt("maxVersion",version)<version)throw new IOException("A NAS nem támogatja az indulás előtti fájlválasztást. A letöltés nem indult el.");return new ApiState(endpoint(info.getString("path")),base,sid);}
    private ApiState apiState(String api,int version)throws Exception{
        for(int lookup=0;lookup<2;lookup++){String server;synchronized(this){if(apis.has(api))return knownApiState(api,version);server=base;}
            String url=server+"/webapi/query.cgi?"+form(Map.of("api","SYNO.API.Info","version","1","method","query","query",api));JSONObject discovery=new JSONObject(new String(requestBytes(url,"GET",null,"application/x-www-form-urlencoded",8*1024*1024,15000,server),StandardCharsets.UTF_8));
            synchronized(this){if(!base.equals(server))continue;JSONObject data=discovery.optJSONObject("data");if(!discovery.optBoolean("success")||data==null||!data.has(api))throw new IOException("A NAS nem támogatja ezt a Download Station-műveletet. Letöltés kijelölés nélkül nem indul.");if(!apis.has(api))apis.put(api,data.getJSONObject(api));return knownApiState(api,version);}
        }throw new IOException("A NAS-munkamenet lejárt.");
    }
    public JSONObject apiRequest(String api,String method,int version,boolean readonly,Map<String,String> params,String filename,byte[] upload,String uploadField)throws Exception {
        NasClient next;
        try{next=current();}catch(IOException paused){
            // No request has been sent. In particular, DownloadStation.start may safely
            // retain its editable preview rather than mark an unsent task uncertain.
            if(!readonly)throw new ApiRejectedException(paused.getMessage());throw paused;
        }
        if(next!=null)return next.apiRequest(api,method,version,readonly,params,filename,upload,uploadField);
        for(int attempt=0;attempt<2;attempt++){
            ApiState state=apiState(api,version);Map<String,String> values=new LinkedHashMap<>();values.put("api",api);values.put("method",method);values.put("version",String.valueOf(version));values.put("_sid",state.session);for(Map.Entry<String,String> param:params.entrySet())values.putIfAbsent(param.getKey(),param.getValue());JSONObject response;
            try{if(upload==null){String form=form(values);response=new JSONObject(new String(requestBytes(readonly?state.url+"?"+form:state.url,readonly?"GET":"POST",readonly?null:form.getBytes(StandardCharsets.UTF_8),"application/x-www-form-urlencoded",8*1024*1024,15000,state.server,!readonly),StandardCharsets.UTF_8));}else{if(upload.length>32*1024*1024||filename==null||filename.contains("\r")||filename.contains("\n")||filename.contains("\""))throw new IOException("Érvénytelen torrentfájl.");String boundary="SynoStream"+UUID.randomUUID().toString().replace("-","");byte[] body=TorrentMultipart.encode(boundary,values,uploadField,filename,upload);response=new JSONObject(new String(requestBytes(state.url+"?"+form(Map.of("api",api,"method",method,"version",String.valueOf(version),"_sid",state.session)),"POST",body,"multipart/form-data; boundary="+boundary,8*1024*1024,60000,state.server,!readonly),StandardCharsets.UTF_8));}}
            catch(Exception e){if(readonly&&attempt==0)continue;throw new IOException(readonly?"A Download Station most nem érhető el. A korábbi lista megmaradt.":"Nem érkezett biztos NAS-visszaigazolás. Ellenőrizd a feladatlistát; a műveletet nem ismételtem meg automatikusan.");}
            if(response.optBoolean("success")){Object data=response.opt("data");if(data instanceof JSONArray){JSONArray rows=(JSONArray)data;for(int i=0;i<rows.length();i++)if(rows.getJSONObject(i).optInt("error")!=0)throw new IOException("Néhány feladat művelete nem sikerült. Frissítsd a listát.");return new JSONObject();}return data instanceof JSONObject?(JSONObject)data:new JSONObject();}
            int code=response.optJSONObject("error")==null?-1:response.getJSONObject("error").optInt("code");if(attempt==0&&(code==106||code==107||code==119)){synchronized(this){if(!base.equals(state.server))throw new IOException("A NAS-munkamenet lejárt.");if(sid.equals(state.session))login();}continue;}throw new ApiRejectedException(code==101?"A NAS érvénytelen kérési paramétert jelzett (101; "+downloadOperation(api,method)+"). A műveletet nem ismételtem meg automatikusan.":"A Download Station-művelet nem sikerült ("+code+"). Ellenőrizd a NAS jogosultságait és a feladatlistát.");
        }throw new IOException("A NAS-munkamenet lejárt.");
    }

    public void deleteMediaPaths(List<String> paths)throws Exception {
        if(paths.isEmpty()||paths.size()>64)throw new IOException("Érvénytelen törlési fájllista.");
        for(String path:paths)if(MediaDeletion.path(path).substring(1).split("/").length<2||MediaDeletion.blocked(path))throw new IOException("Megosztás vagy védett mappa nem törölhető.");
        try{JSONObject result=apiRequest("SYNO.FileStation.Delete","delete",2,false,Map.of("path",new JSONArray(paths).toString(),"recursive","false"),null,null,null);JSONArray errors=result.optJSONArray("errors");if(errors!=null&&errors.length()>0)throw new IOException("Részleges törlési hiba.");}
        catch(Exception error){throw new IOException("A NAS-törlés eredménye nem igazolható. Frissítsd a médiatárat; a műveletet nem ismételtem meg automatikusan.");}
    }

    private static String downloadOperation(String api,String method){if(api.equals("SYNO.DownloadStation2.Task")&&method.equals("create"))return "torrent előkészítése";if(api.equals("SYNO.DownloadStation2.Settings.Location")&&method.equals("get"))return "alapértelmezett célmappa lekérése";if(api.equals("SYNO.DownloadStation2.Task.List")&&method.equals("get"))return "torrent fájllistájának lekérése";if(api.equals("SYNO.DownloadStation2.Task.List.Polling")){if(method.equals("download"))return "kijelölt fájlok indítása";if(method.equals("download_status"))return "indítás visszaigazolása";}return "Download Station-kérés";}
    int retirementRevision(){synchronized(connectionLock){return retirementRevision;}}
    void retireSuperseded(){retireSuperseded(-1);}
    void retireSuperseded(int expectedRevision){
        List<NasClient> old;boolean own;
        synchronized(connectionLock){if(expectedRevision!=-1&&expectedRevision!=retirementRevision)return;old=new ArrayList<>(superseded);superseded.clear();own=replacement!=null;}
        if(own)logoutOwn();for(NasClient client:old)client.logout();
    }
    private synchronized void logoutOwn(){String session=sid;if(session.isEmpty())return;sid="";
        try{json(endpoint(authPath),Map.of("api","SYNO.API.Auth","version","6","method","logout","session",authSession,"_sid",session),true);}catch(Exception ignored){}
    }
    public void logout(){
        List<NasClient> old;
        synchronized(connectionLock){suspended=true;connectionGeneration++;Set<NasClient> all=Collections.newSetFromMap(new IdentityHashMap<>());all.addAll(superseded);superseded.clear();if(replacement!=null)all.add(replacement);old=new ArrayList<>(all);}
        logoutOwn();for(NasClient client:old)client.logout();
    }
    private JSONObject json(String url,Map<String,String> values,boolean post) throws Exception {
        byte[] result=requestBytes(post?url:url+"?"+form(values),post?"POST":"GET",post?form(values).getBytes(StandardCharsets.UTF_8):null,"application/x-www-form-urlencoded",8*1024*1024,15000);
        return new JSONObject(new String(result,StandardCharsets.UTF_8));
    }
    private HttpURLConnection open(String url,String method,int timeout) throws Exception {return open(url,method,timeout,base);}
    private HttpURLConnection open(String url,String method,int timeout,String requestBase) throws Exception {
        HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();c.setConnectTimeout(7000);c.setReadTimeout(timeout);c.setRequestMethod(method);
        c.setRequestProperty("User-Agent","SynoStreamAndroid/"+BuildConfig.VERSION_NAME);
        if(requestBase.contains(".quickconnect.to"))c.setRequestProperty("Referer",requestBase+"/");
        synchronized(cookies){for(var e:cookies.get(URI.create(url),Map.of()).entrySet())c.setRequestProperty(e.getKey(),String.join("; ",e.getValue()));}
        return c;
    }
    private void storeCookies(HttpURLConnection c) throws IOException {synchronized(cookies){cookies.put(URI.create(c.getURL().toString()),c.getHeaderFields());}}
    private byte[] requestBytes(String url,String method,byte[] body,String type,int limit,int timeout) throws Exception {
        return requestBytes(url,method,body,type,limit,timeout,base);
    }
    private byte[] requestBytes(String url,String method,byte[] body,String type,int limit,int timeout,String requestBase)throws Exception{return requestBytes(url,method,body,type,limit,timeout,requestBase,false);}
    private byte[] requestBytes(String url,String method,byte[] body,String type,int limit,int timeout,String requestBase,boolean noReplay)throws Exception{
        HttpURLConnection c=open(url,method,timeout,requestBase);
        try{if(body!=null){if(noReplay)c.setFixedLengthStreamingMode(body.length);c.setDoOutput(true);c.setRequestProperty("Content-Type",type);try(OutputStream out=c.getOutputStream()){out.write(body);}}
            int status=c.getResponseCode();storeCookies(c);if(status<200||status>=300)throw new IOException("A hálózati kérés nem sikerült (HTTP "+status+").");
            return readBounded(c.getInputStream(),limit);
        }finally{c.disconnect();}
    }
    public static byte[] readBounded(InputStream in,int limit) throws IOException {try(in;ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[8192];int count;while((count=in.read(b))!=-1){if(out.size()+count>limit)throw new ResponseTooLargeException();out.write(b,0,count);}return out.toByteArray();}}
    public static String form(Map<String,String> values){StringJoiner j=new StringJoiner("&");for(var e:values.entrySet())j.add(encode(e.getKey())+"="+encode(e.getValue()));return j.toString();}
    private static String encode(String text){try{return URLEncoder.encode(text,"UTF-8");}catch(Exception e){throw new IllegalStateException(e);}}
}
