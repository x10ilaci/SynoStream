package hu.synostream.android;
import java.util.*;import java.nio.charset.StandardCharsets;import java.io.IOException;
/** Exactly one final body allocation; the caller's torrent bytes are copied once. */
final class TorrentMultipart {
 static byte[] encode(String boundary,Map<String,String> fields,String field,String filename,byte[] file)throws IOException{
  List<byte[]> headers=new ArrayList<>();long size=file.length;
  for(Map.Entry<String,String> value:fields.entrySet()){byte[] header=("--"+boundary+"\r\nContent-Disposition: form-data; name=\""+value.getKey()+"\"\r\n\r\n"+value.getValue()+"\r\n").getBytes(StandardCharsets.UTF_8);headers.add(header);size+=header.length;}
  byte[] fileHeader=("--"+boundary+"\r\nContent-Disposition: form-data; name=\""+field+"\"; filename=\""+filename+"\"\r\nContent-Type: application/x-bittorrent\r\n\r\n").getBytes(StandardCharsets.UTF_8),end=("\r\n--"+boundary+"--\r\n").getBytes(StandardCharsets.UTF_8);size+=fileHeader.length+end.length;if(size>Integer.MAX_VALUE)throw new IOException("A torrentfeltöltés túl nagy.");byte[] body=new byte[(int)size];int offset=0;for(byte[] header:headers){System.arraycopy(header,0,body,offset,header.length);offset+=header.length;}System.arraycopy(fileHeader,0,body,offset,fileHeader.length);offset+=fileHeader.length;System.arraycopy(file,0,body,offset,file.length);offset+=file.length;System.arraycopy(end,0,body,offset,end.length);return body;
 }
 private TorrentMultipart(){}
}
