package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;import java.util.*;
public class NasRoutesTest {
 NasClient.Credentials c(String a,String l,String d,String q){return new NasClient.Credentials(a,l,d,q,"user","password","");}
 List<NasRoutes.Kind> kinds(NasClient.Credentials c,boolean local){List<NasRoutes.Kind> k=new ArrayList<>();for(NasRoutes.Route r:NasRoutes.plan(c,local))k.add(r.kind);return k;}
 @Test public void allThreeArePrioritizedAndQuickConnectIsDeduplicated(){assertEquals(List.of(NasRoutes.Kind.LOCAL,NasRoutes.Kind.DDNS,NasRoutes.Kind.QUICKCONNECT),kinds(c("fixture-qc","http://192.168.1.2:5000","https://nas.example.org:5001","fixture-qc"),true));}
 @Test public void mobileSkipsLocalButKeepsDdnsAndQuickConnect(){assertEquals(List.of(NasRoutes.Kind.DDNS,NasRoutes.Kind.QUICKCONNECT),kinds(c("192.168.1.2","http://192.168.1.3","https://nas.example.org","fixture-qc"),false));}
 @Test public void optionalLocalHasPriorityOverPrivatePrimary(){List<NasRoutes.Route> routes=NasRoutes.plan(c("http://127.0.0.1:5001","http://127.0.0.1:5000","",""),true);assertEquals("http://127.0.0.1:5000",routes.get(0).value);assertEquals("http://127.0.0.1:5001",NasRoutes.plan(c("http://127.0.0.1:5001","http://127.0.0.1:5000","",""),false).get(0).value);}
 @Test public void onlyAdvancedRoutesAreAccepted(){assertEquals(List.of(NasRoutes.Kind.DDNS,NasRoutes.Kind.QUICKCONNECT),kinds(c("","","https://nas.example.org","fixture-qc"),true));}
 @Test public void quickConnectBrowserLinkIsRecognized(){assertEquals("fixture-qc",NasRoutes.plan(c("https://quickconnect.to/fixture-qc/","","",""),true).get(0).value);}
 @Test public void bareDdnsUsesExistingHttpsDefault(){assertEquals("https://nas.example.org",NasRoutes.plan(c("nas.example.org","","",""),true).get(0).value);}
 @Test public void explicitProtocolAndPortRemainUnchanged(){assertEquals("http://nas.example.org:5555",NasRoutes.plan(c("http://nas.example.org:5555/","","",""),true).get(0).value);}
 @Test public void dnsCaseDuplicatesAreRemoved(){assertEquals(1,NasRoutes.plan(c("https://NAS.example.org","","https://nas.example.org/",""),true).size());}
 @Test public void malformedExtraRouteIsNotSilentlySaved(){assertThrows(IllegalArgumentException.class,()->NasRoutes.plan(c("fixture-qc","http://127.0.0.1","https://nas.example.org/path",""),true));}
 @Test public void invalidQuickConnectIsRejected(){assertThrows(IllegalArgumentException.class,()->NasRoutes.plan(c("","","","bad id"),true));}
 @Test public void emptyProfileIsRejected(){assertThrows(IllegalArgumentException.class,()->NasRoutes.plan(c("","","",""),true));}
 @Test public void credentialsInAddressAreRejected(){assertThrows(IllegalArgumentException.class,()->NasRoutes.plan(c("https://user:password@nas.example.org","","",""),true));}
 @Test public void privateHostsAreClassifiedWithoutDns(){for(String h:List.of("10.0.0.1","172.16.0.1","172.31.255.254","192.168.1.2","127.0.0.1","169.254.1.2","localhost","nas.local","[fd00::1]","[::1]"))assertTrue(h,NasRoutes.privateHost(h));for(String h:List.of("172.15.0.1","172.32.0.1","192.0.2.1","nas.example.org","999.1.1.1"))assertFalse(h,NasRoutes.privateHost(h));}
 @Test public void privatePrimaryStillWorksWithoutRemoteConfiguration(){assertEquals("http://192.168.1.2:5000",NasRoutes.plan(c("http://192.168.1.2:5000","","",""),false).get(0).value);}
}
