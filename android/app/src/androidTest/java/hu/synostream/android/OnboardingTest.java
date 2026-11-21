package hu.synostream.android;
import androidx.test.ext.junit.runners.AndroidJUnit4;import androidx.test.platform.app.InstrumentationRegistry;import androidx.test.uiautomator.*;
import android.content.*;import org.junit.*;import org.junit.runner.RunWith;import org.json.*;import java.util.*;import static org.junit.Assert.*;
@RunWith(AndroidJUnit4.class)
public class OnboardingTest {
    private static final String PKG="hu.synostream.android";private UiDevice device;private Context context;private SynoApp app;
    private void visible(String id) throws Exception {assertTrue(id,device.wait(Until.hasObject(By.res(PKG+":id/"+id)),15000));}
    private void click(String id) throws Exception {visible(id);device.findObject(By.res(PKG+":id/"+id)).click();}
    private void tapText(String label){assertTrue(label,device.wait(Until.hasObject(By.text(label)),10000));device.findObject(By.text(label)).click();}
    private void text(String id,String text) throws Exception {visible(id);device.findObject(By.res(PKG+":id/"+id)).setText(text);}
    private void source(String label) throws Exception {
        click("library_add_source");assertTrue(device.wait(Until.hasObject(By.text("▱  "+label)),15000));device.findObject(By.text("▱  "+label)).click();
        assertTrue(device.wait(Until.hasObject(By.res(PKG+":id/source_choose").enabled(true)),15000));click("source_choose");visible("library_save");
    }
    @Test public void realLoginUiCanConfigureDefaultsEditAndDeleteWithoutDuplicates() throws Exception {
        context=InstrumentationRegistry.getInstrumentation().getTargetContext();app=(SynoApp)context.getApplicationContext();device=UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
        try(FakeNas nas=new FakeNas()){
            context.getSharedPreferences("synostream",0).edit().clear().commit();UiLocale.save(context,"hu");
            InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{app.client=null;app.demo=false;app.busy=false;app.page="movies";app.selectedLibrary="";app.libraries=LibraryConfig.migrate(new JSONArray());app.rawCards=new ArrayList<>();app.cards=new ArrayList<>();app.status="";app.libraryDraft=null;});
            context.startActivity(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));
            text("login_address",nas.address());text("login_user","fixture-user");text("login_password","fixture-password");
            click("login_button");visible("configure_source");
            click("configure_source");source("Movies");click("library_save");assertTrue(device.wait(Until.hasObject(By.desc("Demo Movie")),15000));
            assertEquals(2,app.libraries.length());assertEquals(List.of("/Movies"),LibraryConfig.paths(LibraryConfig.defaultLibrary(app.libraries,true)));assertTrue(LibraryConfig.paths(LibraryConfig.defaultLibrary(app.libraries,false)).isEmpty());
            click("menu_button");assertTrue(device.wait(Until.hasObject(By.text("TV műsorok")),5000));device.findObject(By.text("TV műsorok")).click();click("configure_source");source("Series");click("library_save");assertTrue(device.wait(Until.hasObject(By.desc("First Show")),15000));assertEquals(2,app.libraries.length());
            click("menu_button");tapText("＋  Új médiatár");text("library_name","Saját filmek");source("Movies");click("library_save");assertTrue(device.wait(Until.hasObject(By.desc("Demo Movie")),15000));assertEquals(3,app.libraries.length());
            device.findObject(By.desc("További lehetőségek")).click();tapText("Médiatár szerkesztése");text("library_name","Átnevezett filmek");click("library_save");assertTrue(device.wait(Until.hasObject(By.desc("Demo Movie")),15000));assertEquals(3,app.libraries.length());
            device.findObject(By.desc("További lehetőségek")).click();tapText("Médiatár szerkesztése");click("library_delete");assertTrue(device.wait(Until.hasObject(By.res("android:id/button1")),5000));device.findObject(By.res("android:id/button1")).click();assertTrue(device.wait(Until.hasObject(By.desc("Demo Movie")),15000));assertEquals(2,app.libraries.length());
        }finally{NasClient old=app.client;app.client=null;if(old!=null)old.logout();}
    }
    @Test public void manualMetadataPublishesValidWindowsEventAndReadsItBack() throws Exception {
        try(FakeNas nas=new FakeNas()){NasClient client=new NasClient(new NasClient.Credentials(nas.address(),"","fixture-user","fixture-password",""));client.connect();try{JSONObject info=new JSONObject().put("id",603).put("title","Árvíztűrő cím");client.savePairing("/Movies","/Movies/Demo.Movie.2020.mkv",true,info);assertEquals(1,nas.uploads);assertTrue(nas.validMultipart);JSONObject event=Pairings.validate(nas.uploadedPath.substring(nas.uploadedPath.lastIndexOf('/')+1),nas.files.get(nas.uploadedPath));assertNotNull(event);assertEquals(603,event.getLong("tmdb_id"));assertEquals(1,event.getLong("generation"));client.savePairing("/Movies","/Movies/Demo.Movie.2020.mkv",true,info);assertEquals(2,nas.uploads);event=Pairings.validate(nas.uploadedPath.substring(nas.uploadedPath.lastIndexOf('/')+1),nas.files.get(nas.uploadedPath));assertEquals(2,event.getLong("generation"));}finally{client.logout();}}
    }
}
