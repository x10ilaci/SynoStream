package hu.synostream.android;

import android.content.Context;
import android.util.AtomicFile;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Bounded atomic local cache, separate from user settings and NAS sidecars. */
public final class MetadataCache implements TmdbApi.Cache {
    private final File directory;
    public MetadataCache(Context c){directory=new File(c.getCacheDir(),"tmdb-v2");directory.mkdirs();}
    private File file(String key) throws Exception {byte[] bytes=MessageDigest.getInstance("SHA-256").digest(key.getBytes(StandardCharsets.UTF_8));StringBuilder name=new StringBuilder();for(byte b:bytes)name.append(String.format(Locale.ROOT,"%02x",b));return new File(directory,name+".json");}
    public JSONObject get(String key,long ttl){
        try{AtomicFile file=new AtomicFile(file(key));if(!file.getBaseFile().exists())return null;
            JSONObject envelope=new JSONObject(new String(NasClient.readBounded(file.openRead(),3*1024*1024),StandardCharsets.UTF_8));
            long age=System.currentTimeMillis()-envelope.getLong("time");return age>=0&&age<ttl?envelope.getJSONObject("value"):null;
        }catch(Exception invalid){return null;}
    }
    public void put(String key,JSONObject value){
        try{AtomicFile file=new AtomicFile(file(key));FileOutputStream output=file.startWrite();
            try{output.write(new JSONObject().put("time",System.currentTimeMillis()).put("value",value).toString().getBytes(StandardCharsets.UTF_8));file.finishWrite(output);}catch(Exception e){file.failWrite(output);}
            File[] files=directory.listFiles((d,n)->n.endsWith(".json"));if(files!=null){
                long total=0;for(File f:files)total+=f.length();
                if(files.length>4096||total>64L*1024*1024){
                    Arrays.sort(files,Comparator.comparingLong(File::lastModified));int count=files.length;
                    for(File f:files){if(count<=3500&&total<=48L*1024*1024)break;long bytes=f.length();if(f.delete()){count--;total-=bytes;}}
                }
            }
        }catch(Exception ignored){/* An optional cache failure must not invalidate media. */}
    }
}
