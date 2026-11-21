package hu.synostream.android;
/** Presentation of the authenticated route, never inferred from the login address. */
enum ConnectionMode {
 LOCAL,DDNS,DIRECT,QUICKCONNECT,UNKNOWN,DISCONNECTED,DEMO;
 static ConnectionMode of(boolean connected,boolean demo,String route){if(demo)return DEMO;if(!connected)return DISCONNECTED;if(route==null)return UNKNOWN;switch(route){case "Helyi kapcsolat":case "Local connection":return LOCAL;case "Közvetlen kapcsolat":case "Direct connection":return DIRECT;case "DDNS":return DDNS;case "QuickConnect":return QUICKCONNECT;default:return UNKNOWN;}}
}
