package hu.synostream.android;
final class StreamIdle {static final long TIMEOUT=30*60*1000L;static boolean expired(long now,long last,int sockets){return sockets==0&&now-last>=TIMEOUT;}private StreamIdle(){}}
