package hu.synostream.android;
import java.net.URI;import java.util.*;
/** Public HTTP remains available; acknowledgement is scoped to each configured endpoint. */
final class HttpConsent {
 static List<String> pending(NasClient.Credentials c,java.util.function.Predicate<String> accepted){List<String> result=new ArrayList<>();for(NasRoutes.Route r:NasRoutes.plan(c,true)){if(r.kind==NasRoutes.Kind.QUICKCONNECT)continue;URI uri=URI.create(r.value);if("http".equals(uri.getScheme())&&!NasRoutes.privateHost(uri.getHost())&&!accepted.test(r.value))result.add(r.value);}return result;}
 private HttpConsent(){}
}
