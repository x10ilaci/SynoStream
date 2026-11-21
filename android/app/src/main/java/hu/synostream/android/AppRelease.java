package hu.synostream.android;
import java.net.*;import java.io.*;import java.security.*;import java.util.*;import org.json.*;
/** Strict public release metadata; no NAS credentials are sent to the update channel. */
final class AppRelease {
 static final String FEED="https://raw.githubusercontent.com/x10ilaci/SynoStream/main/android/update.json";
 static final long MAX_APK=150L*1024*1024;
 final String version,url,hash,certificate,notes;final long code,size;final int minSdk;
 AppRelease(JSONObject o)throws Exception{
  version=o.getString("version");code=o.getLong("version_code");size=o.getLong("size");minSdk=o.getInt("min_sdk");url=o.getString("url");hash=o.getString("sha256");certificate=o.getString("signing_certificate_sha256");notes=o.optString("notes","");
  if(o.getInt("format")!=1||!"android".equals(o.getString("platform"))||!"hu.synostream.android".equals(o.getString("application_id"))||!version.matches("[0-9]+(?:\\.[0-9]+){2}")||code<=0||size<=0||size>MAX_APK||minSdk<26||!hash.matches("[a-f0-9]{64}")||!certificate.matches("[a-f0-9]{64}")||notes.length()>32000)throw new IOException("Invalid release metadata");
  String filename="SynoStream_Android_"+version+".apk";
  if(!filename.equals(o.getString("filename"))||!url.equals("https://github.com/x10ilaci/SynoStream/releases/download/android-v"+version+"/"+filename))throw new IOException("Invalid release URL");
 }
 boolean newer(long installed,int sdk){return code>installed&&minSdk<=sdk;}
 interface Progress {void bytes(long count,long total);}
 static String hex(byte[] value){StringBuilder out=new StringBuilder();for(byte b:value)out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}
 static String digest(byte[] data)throws Exception{return hex(MessageDigest.getInstance("SHA-256").digest(data));}
 static String digest(File file)throws Exception{MessageDigest d=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(file)){byte[] b=new byte[32768];for(int n;(n=in.read(b))!=-1;)d.update(b,0,n);}return hex(d.digest());}
 void verify(File file)throws Exception{if(file.length()!=size||!digest(file).equals(hash))throw new IOException("APK checksum mismatch");}
 static boolean allowed(URL u){return "https".equals(u.getProtocol())&&(u.getPort()==-1||u.getPort()==443)&&u.getUserInfo()==null&&Set.of("github.com","raw.githubusercontent.com","release-assets.githubusercontent.com","objects.githubusercontent.com").contains(u.getHost());}
 static HttpURLConnection open(String address)throws Exception{
  URL u=new URL(address);
  for(int redirects=0;redirects<6;redirects++){
   if(!allowed(u))throw new IOException("Unsafe update redirect");HttpURLConnection c=(HttpURLConnection)u.openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(15000);c.setReadTimeout(30000);c.setRequestProperty("Accept","application/octet-stream");c.setRequestProperty("User-Agent","SynoStream-Android-Updater");
   int status=c.getResponseCode();if(status==301||status==302||status==303||status==307||status==308){String next=c.getHeaderField("Location");c.disconnect();if(next==null)throw new IOException("Missing redirect");u=new URL(u,next);continue;}if(status!=200){c.disconnect();throw new IOException("Update HTTP "+status);}return c;
  }throw new IOException("Too many redirects");
 }
 interface Transport {HttpURLConnection open(String url)throws Exception;}
 static AppRelease fetch()throws Exception{return fetch(AppRelease::open);}
 static AppRelease fetch(Transport transport)throws Exception{HttpURLConnection c=transport.open(FEED);try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[4096];for(int n;(n=in.read(b))!=-1;){if(out.size()+n>65536)throw new IOException("Release metadata too large");out.write(b,0,n);}return new AppRelease(new JSONObject(out.toString("UTF-8")));}finally{c.disconnect();}}
 void download(File target,Progress progress)throws Exception{download(target,progress,AppRelease::open);}
 void download(File target,Progress progress,Transport transport)throws Exception{
  File part=new File(target.getParentFile(),"download.part");if(!target.getParentFile().isDirectory()&&!target.getParentFile().mkdirs())throw new IOException("No update directory");HttpURLConnection c=null;
  try{c=transport.open(url);long count=0;try(InputStream in=c.getInputStream();FileOutputStream out=new FileOutputStream(part)){byte[] b=new byte[32768];for(int n;(n=in.read(b))!=-1;){count+=n;if(count>size)throw new IOException("APK exceeds expected size");out.write(b,0,n);progress.bytes(count,size);}out.getFD().sync();}verify(part);if(target.exists()&&!target.delete())throw new IOException("Cannot replace APK");if(!part.renameTo(target))throw new IOException("Cannot finalize APK");}finally{if(c!=null)c.disconnect();if(part.exists())part.delete();}
 }
}
