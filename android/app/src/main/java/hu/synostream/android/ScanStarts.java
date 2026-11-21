package hu.synostream.android;
/** Main-thread service start bookkeeping, including duplicate starts during a scan. */
final class ScanStarts {private int latest;void started(int id){latest=Math.max(latest,id);}int completionId(){return latest;}}
