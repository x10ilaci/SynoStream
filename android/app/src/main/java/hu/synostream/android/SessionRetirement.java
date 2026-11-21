package hu.synostream.android;
import java.util.concurrent.Executor;
/** No thread sleeps: the grace period and dispatch are independently injectable. */
final class SessionRetirement {
 interface Delay {void later(Runnable work,long millis);}
 private final Delay delay;static final long GRACE_MILLIS=30_000;
 SessionRetirement(Delay scheduler){delay=scheduler;}
 void schedule(NasClient root,Executor io){int revision=root.retirementRevision();delay.later(()->io.execute(()->{root.retireSuperseded(revision);}),GRACE_MILLIS);}
 boolean install(NasClient root,int token,NasClient candidate,Executor io){boolean installed=root.installConnection(token,candidate);if(installed)schedule(root,io);else io.execute(candidate::logout);return installed;}
}
