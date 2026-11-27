package hu.synostream.android;
/** Monotonic, request-scoped playback priority; no media paths or credentials. */
final class StreamActivity {
 static final long GRACE=120000;
 private int requests;private long last=-1;
 synchronized void touch(long now){last=now;}
 synchronized void begin(long now){requests++;last=now;}
 synchronized void end(long now){requests=Math.max(0,requests-1);last=now;}
 synchronized boolean active(long now){return requests>0||last>=0&&now>=last&&now-last<GRACE;}
}
