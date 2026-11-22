package hu.synostream.android;
import java.util.concurrent.*;
/** A rejected dispatch must run the same state cleanup as a finished worker. */
final class ScanSubmission {static Future<?> submit(ExecutorService executor,Runnable work,Runnable rejected){try{return executor.submit(work);}catch(RejectedExecutionException failure){rejected.run();return null;}}}
