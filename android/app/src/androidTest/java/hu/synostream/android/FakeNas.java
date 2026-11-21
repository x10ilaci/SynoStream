package hu.synostream.android;
import org.json.*;import java.io.*;import java.net.*;import java.nio.charset.StandardCharsets;import java.util.*;import java.util.concurrent.*;import java.util.regex.*;

/** Test-owned DSM, exercising the real login/source/edit UI without user data. */
final class FakeNas implements AutoCloseable {
    volatile int taskCount=1,taskCap=100;volatile boolean taskPageTotal;
    volatile String gatedFolder="",failedFolder="";final CountDownLatch folderEntered=new CountDownLatch(1),releaseFolder=new CountDownLatch(1);final Map<String,Long> times=new ConcurrentHashMap<>();
    volatile boolean holdUpload;final CountDownLatch uploadEntered=new CountDownLatch(1),releaseUpload=new CountDownLatch(1);
    final ServerSocket server;final Map<String,byte[]> files=new ConcurrentHashMap<>();final Set<String> folders=ConcurrentHashMap.newKeySet();
    final CountDownLatch listRequestRead=new CountDownLatch(1),releaseListResponse=new CountDownLatch(1);volatile boolean holdListResponse=false;
    volatile String lastOtp="",lastSession="";volatile int taskRequests=0;
    volatile int listDelayMillis=0,prepares=0,starts=0,discards=0;volatile boolean selectedNfo=false,selectedSample=false;
    volatile boolean jsonMime=false,rejectNewLogins=false;volatile int authLogins=0,uploadDelayMillis=0;volatile int previewDelayMillis=0;final CountDownLatch torrentRequestRead=new CountDownLatch(1),releaseTorrentResponse=new CountDownLatch(1);volatile boolean holdTorrentResponse=false,dropTorrentResponse=false;volatile byte[] uploadedTorrent;volatile int torrentUploads=0;volatile int uploads=0;volatile String uploadedPath="";volatile boolean validMultipart=false,torrentRouteValid=false;volatile String torrentDestination="";
    volatile int mediaDeletes=0;final List<String> deletedMedia=Collections.synchronizedList(new ArrayList<>());
    private final ExecutorService workers=Executors.newFixedThreadPool(3);
    FakeNas() throws Exception {
        server=new ServerSocket(0,8,InetAddress.getByName("127.0.0.1"));folders.addAll(List.of("/Movies","/Series","/Series/First.Show","/Series/Second.Show"));
        for(String path:List.of("/Movies/Demo.Movie.2020.mkv","/Movies/Another.Movie.2021.mkv","/Series/First.Show/S01E01.mkv","/Series/First.Show/S01E02.mkv","/Series/Second.Show/S01E01.mkv"))files.put(path,new byte[]{0,1,2,3});
        Thread accept=new Thread(()->{while(!server.isClosed())try{Socket socket=server.accept();socket.setSoTimeout(10000);workers.execute(()->handle(socket));}catch(IOException ignored){}});accept.setDaemon(true);accept.start();
    }
    String address(){return "http://127.0.0.1:"+server.getLocalPort();}
    private static String line(InputStream in) throws IOException {ByteArrayOutputStream out=new ByteArrayOutputStream();int c;while((c=in.read())>=0&&c!='\n'){if(c!='\r')out.write(c);if(out.size()>16384)throw new IOException();}return out.toString("US-ASCII");}
    private static Map<String,String> form(String text) throws Exception {Map<String,String> out=new HashMap<>();for(String part:text.split("&")){String[] pair=part.split("=",2);if(pair.length==2)out.put(URLDecoder.decode(pair[0],"UTF-8"),URLDecoder.decode(pair[1],"UTF-8"));}return out;}
    private void handle(Socket socket){
        try(socket){InputStream in=socket.getInputStream();String request=line(in);String[] first=request.split(" ");Map<String,String> headers=new HashMap<>();String h;while(!(h=line(in)).isEmpty()){int colon=h.indexOf(':');if(colon>=0)headers.put(h.substring(0,colon).toLowerCase(Locale.ROOT),h.substring(colon+1).trim());}
            int size=Integer.parseInt(headers.getOrDefault("content-length","0"));byte[] body=new byte[size];int offset=0;while(offset<size){int n=in.read(body,offset,size-offset);if(n<0)break;offset+=n;}
            Map<String,String> p=headers.getOrDefault("content-type","").startsWith("multipart/form-data")?new HashMap<>():form(first[1].contains("?")?first[1].substring(first[1].indexOf('?')+1):new String(body,StandardCharsets.UTF_8));
            JSONObject result;
            if(headers.getOrDefault("content-type","").startsWith("multipart/form-data")){
                String boundary=headers.get("content-type").split("boundary=",2)[1];Map<String,String> fields=new LinkedHashMap<>();String filename=null;byte[] payload=null;boolean fileLast=true;
                for(String part:new String(body,StandardCharsets.ISO_8859_1).split(Pattern.quote("--"+boundary))){
                    int split=part.indexOf("\r\n\r\n");if(split<0)continue;String partHeaders=part.substring(0,split),value=part.substring(split+4);if(value.endsWith("\r\n"))value=value.substring(0,value.length()-2);
                    Matcher name=Pattern.compile("name=\"([^\"]+)\"").matcher(partHeaders);if(!name.find())continue;
                    Matcher file=Pattern.compile("filename=\"([^\"]+)\"").matcher(partHeaders);
                    if(file.find()){filename=file.group(1);payload=value.getBytes(StandardCharsets.ISO_8859_1);}else{if(filename!=null)fileLast=false;fields.put(name.group(1),new String(value.getBytes(StandardCharsets.ISO_8859_1),StandardCharsets.UTF_8));}
                }
                if(DownloadStation.TASK2.equals(fields.get("api"))){Map<String,String> route=form(first[1].contains("?")?first[1].substring(first[1].indexOf('?')+1):"");torrentRouteValid=List.of("api","method","version","_sid").stream().allMatch(key->fields.get(key)!=null&&fields.get(key).equals(route.get(key)));if(!torrentRouteValid){send(socket,"{\"success\":false,\"error\":{\"code\":101}}".getBytes(StandardCharsets.UTF_8),"application/json");return;}torrentDestination=new JSONArray("["+fields.get("destination")+"]").getString(0);if(!"\"file\"".equals(fields.get("type"))||!"[\"torrent\"]".equals(fields.get("file"))||Integer.parseInt(fields.get("size"))!=payload.length)throw new IOException("Invalid torrent JSON parameters");if(!fileLast||filename==null||payload==null||!"true".equals(fields.get("create_list")))throw new IOException("Invalid torrent fixture multipart");uploadedTorrent=payload;torrentUploads++;prepares++;torrentRequestRead.countDown();if(holdTorrentResponse)releaseTorrentResponse.await(10,TimeUnit.SECONDS);if(dropTorrentResponse)return;send(socket,new JSONObject().put("success",true).put("data",new JSONObject().put("list_id",new JSONArray().put("preview-fixture"))).toString().getBytes(StandardCharsets.UTF_8),"application/json");return;}
                validMultipart=fileLast&&"SYNO.FileStation.Upload".equals(fields.get("api"))&&"sid-fixture".equals(fields.get("_sid"))&&"true".equals(fields.get("create_parents"))&&filename!=null&&payload!=null;
                if(!validMultipart)throw new IOException("Invalid multipart");
                String directory=fields.get("path");String parent=directory;while(parent.lastIndexOf('/')>0){folders.add(parent);parent=parent.substring(0,parent.lastIndexOf('/'));}folders.add(parent);
                if(holdUpload){uploadEntered.countDown();releaseUpload.await(15,TimeUnit.SECONDS);}if(uploadDelayMillis>0)Thread.sleep(uploadDelayMillis);uploadedPath=directory+"/"+filename;files.put(uploadedPath,payload);uploads++;result=new JSONObject().put("success",true);
            }else switch(p.getOrDefault("api","")){
                case "SYNO.API.Info":{JSONObject apis=new JSONObject();for(String api:List.of("SYNO.API.Auth","SYNO.FileStation.List","SYNO.FileStation.Download","SYNO.FileStation.Upload","SYNO.FileStation.Delete",DownloadStation.TASK,DownloadStation.TASK2,DownloadStation.LIST,DownloadStation.POLL,DownloadStation.LOCATION))apis.put(api,new JSONObject().put("path",api.equals("SYNO.API.Auth")?"auth.cgi":"entry.cgi").put("minVersion",1).put("maxVersion",6));result=new JSONObject().put("success",true).put("data",apis);break;}
                case "SYNO.API.Auth":if("login".equals(p.get("method"))){authLogins++;lastOtp=p.getOrDefault("otp_code","");lastSession=p.getOrDefault("session","");if(rejectNewLogins){result=new JSONObject().put("success",false).put("error",new JSONObject().put("code",403));break;}}result=new JSONObject().put("success",true).put("data",new JSONObject().put("sid","sid-fixture"));break;
                case "SYNO.FileStation.List":{
                    if(holdListResponse){listRequestRead.countDown();releaseListResponse.await(30,TimeUnit.SECONDS);}if(listDelayMillis>0)Thread.sleep(listDelayMillis);String folder=p.getOrDefault("folder_path","");if(folder.equals(gatedFolder)&&!gatedFolder.isEmpty()){folderEntered.countDown();releaseFolder.await(15,TimeUnit.SECONDS);}if(folder.equals(failedFolder)&&!failedFolder.isEmpty()){result=new JSONObject().put("success",false).put("error",new JSONObject().put("code",407));break;}JSONArray entries=new JSONArray();Set<String> paths=new TreeSet<>();paths.addAll(folders);paths.addAll(files.keySet());
                    for(String path:paths){String parent=path.substring(0,path.lastIndexOf('/'));if(!parent.equals(folder))continue;entries.put(new JSONObject().put("name",path.substring(path.lastIndexOf('/')+1)).put("path",path).put("isdir",folders.contains(path)).put("additional",new JSONObject().put("size",files.containsKey(path)?files.get(path).length:0).put("time",new JSONObject().put("mtime",times.getOrDefault(path,100L)))));}
                    result=new JSONObject().put("success",true).put("data",new JSONObject().put(p.getOrDefault("method","").equals("list_share")?"shares":"files",entries).put("total",entries.length()));break;
                }
                case "SYNO.FileStation.Delete":{
                    if(!"delete".equals(p.get("method"))||!"false".equals(p.get("recursive")))throw new IOException("Only exact nonrecursive fixture deletion is allowed");
                    JSONArray requested=new JSONArray(p.get("path"));boolean valid=true;
                    for(int n=0;n<requested.length();n++){String target=requested.getString(n);if(target.equals("/Movies")||target.equals("/Series"))throw new IOException("Library root protected");if(folders.contains(target)){for(String file:files.keySet())if(file.startsWith(target+"/"))valid=false;for(String folder:folders)if(!folder.equals(target)&&folder.startsWith(target+"/"))valid=false;}}
                    if(valid){mediaDeletes++;for(int n=0;n<requested.length();n++){String target=requested.getString(n);files.remove(target);folders.remove(target);deletedMedia.add(target);}result=new JSONObject().put("success",true).put("data",new JSONObject());}
                    else result=new JSONObject().put("success",false).put("error",new JSONObject().put("code",408));break;
                }
                case "SYNO.FileStation.Download":{byte[] bytes=files.get(p.get("path"));if(bytes==null)throw new IOException();send(socket,bytes,jsonMime&&p.get("path").endsWith(".json")?"application/json":"application/octet-stream");return;}
                case DownloadStation.TASK:{taskRequests++;int taskOffset=Integer.parseInt(p.getOrDefault("offset","0")),limit=Math.min(taskCap,Integer.parseInt(p.getOrDefault("limit","100")));JSONArray tasks=new JSONArray();if("list".equals(p.get("method")))for(int i=taskOffset;i<Math.min(taskCount,taskOffset+limit);i++)tasks.put(new JSONObject().put("id",taskCount==1?"bt-fixture":"bt-fixture-"+i).put("title",taskCount==1?"Fixture torrent":i==taskCount-1?"Latest active torrent":"Fixture torrent "+i).put("size",1024).put("status",taskCount>1&&i==taskCount-1?"downloading":"paused").put("additional",new JSONObject().put("detail",new JSONObject().put("create_time",String.valueOf(i+1))).put("transfer",new JSONObject().put("size_downloaded",128).put("speed_download",32).put("speed_upload",16))));result=new JSONObject().put("success",true).put("data",new JSONObject().put("tasks",tasks).put("total",taskPageTotal?tasks.length():taskCount));break;}
                case DownloadStation.LOCATION:result=new JSONObject().put("success",true).put("data",new JSONObject().put("default_destination","Movies"));break;
                case DownloadStation.TASK2:{if(!"true".equals(p.get("create_list")))throw new IOException("Must prepare metadata only");prepares++;result=new JSONObject().put("success",true).put("data",new JSONObject().put("list_id",new JSONArray().put("preview-fixture")));break;}
                case DownloadStation.LIST:if(previewDelayMillis>0)Thread.sleep(previewDelayMillis);{if("delete".equals(p.get("method")))discards++;JSONArray list=new JSONArray().put(new JSONObject().put("index",0).put("name","Movie.mkv")).put(new JSONObject().put("index",1).put("name","release.nfo")).put(new JSONObject().put("index",2).put("name","Sample/clip.mkv"));result=new JSONObject().put("success",true).put("data",new JSONObject().put("title","Fixture torrent").put("files",list));break;}
                case DownloadStation.POLL:{JSONObject data=new JSONObject();if("download".equals(p.get("method"))){starts++;JSONArray selected=new JSONArray(p.get("selected"));for(int n=0;n<selected.length();n++){selectedNfo|=selected.getInt(n)==1;selectedSample|=selected.getInt(n)==2;}data.put("task_id","ticket-fixture");}else if("download_status".equals(p.get("method")))data.put("finish",true).put("success",true);result=new JSONObject().put("success",true).put("data",data);break;}
                default:throw new IOException("Unexpected API");
            }
            send(socket,result.toString().getBytes(StandardCharsets.UTF_8),"application/json");
        }catch(Exception ignored){}
    }
    private void send(Socket socket,byte[] bytes,String type) throws IOException {OutputStream out=socket.getOutputStream();out.write(("HTTP/1.1 200 OK\r\nContent-Type: "+type+"\r\nContent-Length: "+bytes.length+"\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));out.write(bytes);out.flush();}
    public void close() throws Exception {server.close();workers.shutdownNow();}
}
