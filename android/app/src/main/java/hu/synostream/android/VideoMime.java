package hu.synostream.android;
import java.util.Locale;
final class VideoMime {
 static String of(String path){String p=path.toLowerCase(Locale.ROOT);int dot=p.lastIndexOf('.');String ext=dot<0?"":p.substring(dot+1);switch(ext){case "mkv":return "video/x-matroska";case "avi":return "video/x-msvideo";case "webm":return "video/webm";case "ts":case "mts":case "m2ts":return "video/mp2t";case "mov":return "video/quicktime";case "wmv":return "video/x-ms-wmv";case "mpg":case "mpeg":return "video/mpeg";default:return "video/mp4";}}
 private VideoMime(){}
}
