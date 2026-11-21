package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;import java.util.*;import java.io.*;
public class TmdbStatusTest {
 @Test public void statusMessagesAndNoCredentialLeak()throws Exception{for(int code:new int[]{401,403,429,500})try(HttpFixture f=new HttpFixture(code,"{}")){TmdbApi api=new TmdbApi("private-fixture-key",null,f.base());try{api.get("movie/1",Map.of());fail();}catch(IOException e){assertFalse(e.getMessage().contains("private-fixture-key"));assertFalse(e.getMessage().contains("api_key"));assertTrue(e.getMessage().contains(code==429?"túl sok":code==500?"átmenetileg":"API-kulcsot"));}}}
 @Test public void missingResponseIsNotCached()throws Exception{try(HttpFixture f=new HttpFixture(404,"{}")){TmdbApi api=new TmdbApi("fixture",null,f.base());assertEquals(0,api.get("movie/1",Map.of()).length());api.get("movie/1",Map.of());assertEquals(2,f.calls.get());assertEquals("SynoStreamAndroid/"+BuildConfig.VERSION_NAME,f.userAgent);}}
}
