package hu.synostream.android;
import java.net.URI;import java.util.*;
/** No DNS lookups: classify only configured values, then try in fixed priority order. */
final class NasRoutes {
 enum Kind { LOCAL, DDNS, DIRECT, QUICKCONNECT }
 static final class Route {
  final Kind kind;final String value;
  Route(Kind k,String v){kind=k;value=v;}
  String key(){return (kind==Kind.QUICKCONNECT?"qc:":"web:")+(kind==Kind.QUICKCONNECT?value:value.toLowerCase(Locale.ROOT));}
 }
 static List<Route> plan(NasClient.Credentials c,boolean allowLocal){
  List<Route> local=new ArrayList<>(),remote=new ArrayList<>(),quick=new ArrayList<>();
  if(!c.local.isBlank())local.add(new Route(Kind.LOCAL,normalizePrivateAddress(c.local)));
  if(!c.ddns.isBlank())remote.add(new Route(Kind.DDNS,NasClient.normalizeAddress(c.ddns)));
  if(!c.quick.isBlank())quick.add(new Route(Kind.QUICKCONNECT,quickId(c.quick)));
  if(!c.address.isBlank()){
   String qc=quickIdOrEmpty(c.address);
   if(!qc.isEmpty())quick.add(0,new Route(Kind.QUICKCONNECT,qc));
   else{String url=normalizePrivateAddress(c.address);String host=URI.create(url).getHost();if(privateHost(host))local.add(new Route(Kind.LOCAL,url));else remote.add(0,new Route(host.matches("[0-9.]+")||host.contains(":")?Kind.DIRECT:Kind.DDNS,url));}
  }
  List<Route> ordered=new ArrayList<>();if(allowLocal)ordered.addAll(local);ordered.addAll(remote);ordered.addAll(quick);
  // Keep explicit primary private endpoints usable with VPNs and for LAN-only profiles.
  if(ordered.isEmpty()&&!c.address.isBlank()&&!local.isEmpty())ordered.add(new Route(Kind.LOCAL,normalizePrivateAddress(c.address)));
  LinkedHashMap<String,Route> unique=new LinkedHashMap<>();for(Route route:ordered)unique.putIfAbsent(route.key(),route);
  if(unique.isEmpty())throw new IllegalArgumentException("Adj meg legalább egy NAS-elérést.");return new ArrayList<>(unique.values());
 }
 static String normalizePrivateAddress(String address){String normalized=NasClient.normalizeAddress(address);URI uri=URI.create(normalized);if(!address.contains("://")&&privateHost(uri.getHost())){normalized=normalized.replaceFirst("^https://","http://");if(uri.getPort()<0)normalized+=":5000";}return normalized;}
 static String quickId(String value){String id=quickIdOrEmpty(value);if(id.isEmpty())throw new IllegalArgumentException("Érvényes QuickConnect-azonosítót adj meg.");return id;}
 static String quickIdOrEmpty(String value){String v=value.trim();if(v.matches("[A-Za-z0-9_-]{1,64}"))return v;try{URI u=URI.create(v);if(("https".equalsIgnoreCase(u.getScheme())||"http".equalsIgnoreCase(u.getScheme()))&&Set.of("quickconnect.to","www.quickconnect.to").contains(Objects.toString(u.getHost(),"").toLowerCase(Locale.ROOT))&&u.getUserInfo()==null&&u.getQuery()==null&&u.getFragment()==null&&u.getPort()==-1){String path=u.getPath();if(path!=null&&path.matches("/[A-Za-z0-9_-]{1,64}/?"))return path.replace("/","");}}catch(IllegalArgumentException invalid){/* Report via normal web-address validation. */}return "";}
 static boolean privateHost(String value){String h=value.toLowerCase(Locale.ROOT).replace("[","").replace("]","");if(h.equals("localhost")||h.endsWith(".local")||h.equals("::1")||h.startsWith("fc")&&h.contains(":")||h.startsWith("fd")&&h.contains(":")||h.startsWith("fe80:"))return true;String[] parts=h.split("\\.");if(parts.length!=4)return false;try{int[] n=new int[4];for(int i=0;i<4;i++){n[i]=Integer.parseInt(parts[i]);if(n[i]<0||n[i]>255)return false;}return n[0]==10||n[0]==127||n[0]==192&&n[1]==168||n[0]==172&&n[1]>=16&&n[1]<=31||n[0]==169&&n[1]==254;}catch(NumberFormatException invalid){return false;}}
 static String routeName(Kind kind){switch(kind){case LOCAL:return "Helyi kapcsolat";case DDNS:return "DDNS";case QUICKCONNECT:return "QuickConnect";default:return "Közvetlen kapcsolat";}}
 private NasRoutes(){}
}
