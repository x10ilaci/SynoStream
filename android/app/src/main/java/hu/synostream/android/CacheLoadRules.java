package hu.synostream.android;
/** Reject disk results from a previous session, library, or scan. */
final class CacheLoadRules {
 static boolean canApply(int requestEpoch,String requestLibrary,int requestToken,int epoch,String library,int scanToken){return requestEpoch==epoch&&java.util.Objects.equals(requestLibrary,library)&&requestToken==scanToken;}
 static Finish finish(int requestToken,int latestToken,boolean canApply,boolean scanRunning){boolean latest=requestToken==latestToken;return new Finish(latest,latest&&!scanRunning,latest&&canApply,latest&&!canApply&&!scanRunning);}
 static final class Finish {
  final boolean latest,busyRelease,apply,clear;
  private Finish(boolean latest,boolean busyRelease,boolean apply,boolean clear){this.latest=latest;this.busyRelease=busyRelease;this.apply=apply;this.clear=clear;}
  void complete(Runnable completed){if(latest)completed.run();}
 }
 private CacheLoadRules(){}
}
