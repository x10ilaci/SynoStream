package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;import javax.net.ssl.SSLException;
public class NasAddressTest {
 @Test public void singleWordHostFallbackKeepsHttps(){assertEquals("https://NAS",NasClient.normalizeAddress("HTTPS://NAS/"));assertEquals("https://diskstation",NasClient.directFallback("diskstation"));assertEquals("https://nas:5000",NasClient.directFallback("nas:5000"));}
 @Test public void plaintextSslProvidesExplicitHttpAdvice(){assertTrue(NasClient.sslMessage(new SSLException("Unrecognized SSL message, plaintext connection?")).contains("http://cím:port"));assertTrue(NasClient.sslMessage(new SSLException("certificate expired")).contains("tanúsítványa"));}
 @Test public void directFallbackIsNeverLabelledQuickConnect(){assertEquals("Közvetlen kapcsolat",NasClient.connectionRoute(true,true));assertEquals("QuickConnect",NasClient.connectionRoute(true,false));assertEquals("Közvetlen kapcsolat",NasClient.connectionRoute(false,false));}
}
