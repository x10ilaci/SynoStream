package hu.synostream.android;
final class TorrentDraft {
 boolean open=false,fileTab=false;String link="",destination="",filename="";byte[] bytes;
 void reset(){open=true;fileTab=false;link=destination=filename="";bytes=null;}
 void close(){open=false;bytes=null;filename="";}
}
