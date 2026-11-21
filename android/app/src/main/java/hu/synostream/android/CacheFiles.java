package hu.synostream.android;
import java.io.*;import java.util.*;
final class CacheFiles {
 static void prune(File dir,Set<String> keep){File[] files=dir.listFiles();if(files==null)return;for(File f:files)if(f.isFile()){String name=f.getName().replaceFirst("\\.(bak|new)$","");if(!keep.contains(name))f.delete();}}
 static void remove(File file){file.delete();new File(file.getPath()+".bak").delete();new File(file.getPath()+".new").delete();}
 private CacheFiles(){}
}
