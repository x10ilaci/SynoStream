package hu.synostream.android;
/** One immutable playback capability; a new playback deliberately revokes the old URL. */
final class StreamIdentity {final String path,token;StreamIdentity(String p,String t){path=p;token=t;}}
