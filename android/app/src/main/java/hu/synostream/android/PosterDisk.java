package hu.synostream.android;
import java.io.*;import java.util.*;import java.security.*;import java.nio.charset.StandardCharsets;
final class PosterDisk {
 private final File dir;private final long limit;
 PosterDisk(File dir,long limit){this.dir=dir;this.limit=limit;}
 static String key(String url)throws Exception{byte[] hash=MessageDigest.getInstance("SHA-256").digest(url.getBytes(StandardCharsets.UTF_8));StringBuilder b=new StringBuilder();for(byte v:hash)b.append(String.format(Locale.ROOT,"%02x",v));return b.toString();}
 synchronized byte[] get(String url){try{File f=new File(dir,key(url));if(!f.isFile())return null;byte[] bytes=NasClient.readBounded(new FileInputStream(f),8*1024*1024);f.setLastModified(System.currentTimeMillis());return bytes;}catch(Exception ignored){return null;}}
 synchronized void put(String url,byte[] bytes){try{if(bytes.length>limit||bytes.length>8*1024*1024)return;if(!dir.isDirectory()&&!dir.mkdirs())return;File target=new File(dir,key(url)),temp=new File(dir,target.getName()+".new");try(FileOutputStream out=new FileOutputStream(temp)){out.write(bytes);}if(!temp.renameTo(target)){temp.delete();return;}prune(dir,limit);}catch(Exception ignored){}}
 static void prune(File dir,long limit){File[] files=dir.listFiles(File::isFile);if(files==null)return;Arrays.sort(files,Comparator.comparingLong(File::lastModified).thenComparing(File::getName));long total=0;for(File f:files)total+=f.length();for(File f:files)if(total>limit){long size=f.length();if(f.delete())total-=size;}}
}
