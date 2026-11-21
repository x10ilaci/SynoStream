package hu.synostream.android;
import java.util.Objects;
/** Pure state machine. All calls are serialized by the Android main handler. */
final class ConnectionRecovery {
 enum State { READY, OFFLINE, CONNECTING, FAILED, AUTH_REQUIRED }
 static final class Request {
  final long token;final boolean available,allowLocal;
  Request(long t,boolean a,boolean l){token=t;available=a;allowLocal=l;}
 }
 private String network;private boolean cellular,initialized;private volatile long generation;
 private State state=State.READY;
 State state(){return state;}
 long generation(){return generation;}
 Request observe(String key,boolean mobile,boolean connected,boolean retry){
  boolean changed=initialized&&(!Objects.equals(network,key)||cellular!=mobile);
  initialized=true;network=key;cellular=mobile;
  if(!connected){reset();return null;}
  if(!changed&&!(retry&&(state==State.FAILED||state==State.OFFLINE)))return null;
  state=key==null?State.OFFLINE:State.CONNECTING;
  return new Request(++generation,key!=null,!mobile);
 }
 boolean current(long token){return token==generation;}
 boolean finish(long token,boolean success,boolean auth){if(!current(token))return false;state=success?State.READY:auth?State.AUTH_REQUIRED:State.FAILED;return true;}
 void requireReconnect(){state=State.FAILED;}
 void reset(){generation++;state=State.READY;}
}
