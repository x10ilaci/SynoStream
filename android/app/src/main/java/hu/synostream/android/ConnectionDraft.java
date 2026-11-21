package hu.synostream.android;
/** Unsaved editor data lives only in process memory, including an unremembered password. */
final class ConnectionDraft {
 long generation;
 void begin(){generation++;open=true;}
 boolean current(long token){return open&&generation==token;}
 boolean open,expanded,remember;NasProfile profile;NasClient.Credentials credentials;
 void close(){generation++;open=false;expanded=false;remember=false;profile=null;credentials=null;}
}
