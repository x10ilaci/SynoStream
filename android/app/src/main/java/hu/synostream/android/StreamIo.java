package hu.synostream.android;
import java.net.Socket;import java.io.*;
/** Prompt loopback delivery, including the small reads produced by HTTP/TLS. */
final class StreamIo {
 static InputStream input(Socket socket)throws IOException{socket.setTcpNoDelay(true);return new BufferedInputStream(socket.getInputStream(),16384);}
 private StreamIo(){}
}
