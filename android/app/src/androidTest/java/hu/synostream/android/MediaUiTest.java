package hu.synostream.android;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.*;
import android.content.*;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.regex.Pattern;
import static org.junit.Assert.*;
@RunWith(AndroidJUnit4.class)
public class MediaUiTest {
    @Test public void optionalActualNasSeriesCanSelectEpisodeAndCloseDetail() throws Exception {
        android.app.Instrumentation instrumentation=InstrumentationRegistry.getInstrumentation();Context context=instrumentation.getTargetContext();
        File fixture=new File(context.getFilesDir(),"test_ui.json");Assume.assumeTrue("No private UI test credentials injected",fixture.exists());
        JSONObject credentials;try{credentials=new JSONObject(new String(NasClient.readBounded(new FileInputStream(fixture),2*1024*1024),StandardCharsets.UTF_8));}finally{fixture.delete();}
        JSONObject audit=new JSONObject(new String(NasClient.readBounded(new FileInputStream(new File(context.getFilesDir(),"audit020.json")),4*1024*1024),StandardCharsets.UTF_8));
        Library.Card card=null;JSONArray roots=audit.getJSONArray("roots");
        for(int i=0;i<roots.length();i++){JSONObject root=roots.getJSONObject(i);if(!root.getBoolean("movie")&&root.getJSONArray("cards").length()>0){card=Library.Card.from(root.getJSONArray("cards").getJSONObject(0));break;}}
        assertNotNull(card);final Library.Card selected=card;
        NasClient client=new NasClient(new NasClient.Credentials(credentials.getString("address"),"",credentials.getString("user"),credentials.getString("password"),""));client.connect();
        SynoApp app=(SynoApp)context.getApplicationContext();UiDevice device=UiDevice.getInstance(instrumentation);
        try{
            instrumentation.runOnMainSync(()->{app.client=client;app.demo=false;app.busy=false;app.page="shows";app.query="";app.selectedLibrary="live-ui";app.libraries=new JSONArray();app.rawCards=new ArrayList<>(List.of(selected));app.cards=new ArrayList<>(List.of(selected));app.status="Élő felületellenőrzés";});
            context.startActivity(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));
            assertTrue(device.wait(Until.hasObject(By.desc(selected.title)),15000));device.findObject(By.desc(selected.title)).click();
            assertTrue(device.wait(Until.hasObject(By.res("hu.synostream.android:id/detail_info")),5000));
            
            assertTrue(device.wait(Until.hasObject(By.text(Pattern.compile("^S\\d+E\\d+\\s.*"))),30000));
            UiObject2 play=device.findObject(By.res("hu.synostream.android:id/play_button"));assertNotNull(play);assertFalse(play.isEnabled());
            device.findObject(By.text(Pattern.compile("^S\\d+E\\d+\\s.*"))).click();assertTrue(play.isEnabled());
            device.findObject(By.res("hu.synostream.android:id/detail_close")).click();assertTrue(device.wait(Until.hasObject(By.res("hu.synostream.android:id/poster_grid")),5000));
        }finally{
            instrumentation.runOnMainSync(()->{app.client=null;app.demo=false;app.cards=new ArrayList<>();app.libraries=app.store.libraries();app.selectedLibrary="";app.status="";app.changed();});
            client.logout();
        }
    }
}
