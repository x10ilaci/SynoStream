package hu.synostream.android;
import java.util.Locale;
final class TorrentInputRules {
 static boolean torrentMime(String mime){String type=mime==null?"":mime.split(";",2)[0].trim().toLowerCase(Locale.ROOT);return type.equals("application/x-bittorrent")||type.equals("application/x-torrent");}
 static boolean accepts(String name,String mime){return name!=null&&name.toLowerCase(Locale.ROOT).endsWith(".torrent")||torrentMime(mime);}
 static String filename(String name,String mime){if(!accepts(name,mime))throw new IllegalArgumentException(".torrent kiterjesztésű fájlt válassz.");String value=name==null||name.isBlank()?"Megnyitott torrent":name;return value.toLowerCase(Locale.ROOT).endsWith(".torrent")?value:value+".torrent";}
 static boolean acceptsScheme(String scheme){return "content".equalsIgnoreCase(scheme);}
 static boolean looksLikeTorrent(byte[] bytes){if(bytes==null||bytes.length<16||bytes[0]!='d')return false;byte[] marker={'4',':','i','n','f','o'};outer:for(int i=0;i<=bytes.length-marker.length;i++){for(int k=0;k<marker.length;k++)if(bytes[i+k]!=marker[k])continue outer;return true;}return false;}
 private TorrentInputRules(){}
}
