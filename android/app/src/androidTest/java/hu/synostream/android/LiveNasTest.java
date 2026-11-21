package hu.synostream.android;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import android.content.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.json.*;
import static org.junit.Assert.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
@RunWith(AndroidJUnit4.class)
public class LiveNasTest {
 @Test public void optionalReadOnlyNasProbe() throws Exception {
 Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();File fixture=new File(context.getFilesDir(),"test_connection.json");Assume.assumeTrue("No private live credentials injected",fixture.exists());
 JSONObject j;try{j=new JSONObject(new String(NasClient.readBounded(new FileInputStream(fixture),65536),StandardCharsets.UTF_8));}finally{fixture.delete();}
 NasClient c=new NasClient(new NasClient.Credentials(j.getString("address"),"",j.getString("user"),j.getString("password"),""));
 try{c.connect();assertFalse(c.list("").isEmpty());assertFalse(c.list(j.getString("root")).isEmpty());try(NasClient.Stream stream=c.stream(j.getString("sample"),"bytes=0-1023",false)){assertEquals(206,stream.connection.getResponseCode());assertEquals(1024,NasClient.readBounded(stream.body,1024).length);}
 }finally{c.logout();}
 }
}
