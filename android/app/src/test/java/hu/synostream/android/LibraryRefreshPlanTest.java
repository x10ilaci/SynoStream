package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;import java.util.*;
public class LibraryRefreshPlanTest {
 @Test public void allLibrariesOnceThenInterval(){LibraryRefreshPlan p=new LibraryRefreshPlan();p.prepare("a",List.of("movies","shows","custom","movies"),0);assertEquals("movies",p.next());assertNull(p.next());p.complete("movies",1);assertEquals("shows",p.next());p.complete("shows",2);assertEquals("custom",p.next());p.complete("custom",3);assertFalse(p.waiting());p.prepare("a",List.of("movies"),1000);assertNull(p.next());p.prepare("a",List.of("movies"),300003);assertEquals("movies",p.next());}
 @Test public void accountSwitchAndCancellation(){LibraryRefreshPlan p=new LibraryRefreshPlan();p.prepare("a",List.of("a","b"),0);assertEquals("a",p.next());p.prepare("other",List.of("c"),1);assertEquals("c",p.next());p.complete("a",2);assertNull(p.next());p.cancel(3);p.prepare("other",List.of("c"),4);assertNull(p.next());p.reset();p.prepare("other",List.of("c"),5);assertEquals("c",p.next());}
 @Test public void emptyAndMissingLibrariesAreSafe(){LibraryRefreshPlan p=new LibraryRefreshPlan();p.prepare("a",List.of(),0);assertNull(p.next());assertFalse(p.waiting());p.prepare("a",List.of("new"),300000);assertEquals("new",p.next());}
}
