package hu.synostream.android;
import androidx.test.ext.junit.runners.AndroidJUnit4;import androidx.test.platform.app.InstrumentationRegistry;import androidx.test.uiautomator.*;
import android.content.*;import org.json.*;import org.junit.*;import org.junit.runner.RunWith;import java.io.*;import java.util.*;import static org.junit.Assert.*;
@RunWith(AndroidJUnit4.class)
public class PreviewTest {
    @Test public void capturePublicDemoPortraitLandscapeAndSources() throws Exception {
        android.app.Instrumentation instrumentation=InstrumentationRegistry.getInstrumentation();Context context=instrumentation.getTargetContext();SynoApp app=(SynoApp)context.getApplicationContext();UiDevice device=UiDevice.getInstance(instrumentation);
        device.setOrientationNatural();
        instrumentation.runOnMainSync(()->{app.client=null;app.demo=true;app.busy=false;app.libraryDraft=null;app.page="shows";app.query="";app.identity="public-preview";app.edits=new LocalEdits("{}");app.libraries=LibraryConfig.migrate(new JSONArray());app.selectedLibrary=LibraryConfig.defaultLibrary(app.libraries,false).optString("id");Library.Card card=new Library.Card("/demo/series","Bemutató sorozat",false);card.date="2024";card.overview="A leírás és a műsor adatai itt jelennek meg. Az epizódok külön görgethető listából választhatók ki. A felső ikonokkal módosíthatók a médiaadatok, elrejthető a kártya, vagy összevonható másik sorozattal.";card.episodeRoots.add(card.path);app.rawCards=new ArrayList<>(List.of(card));app.cards=new ArrayList<>(app.rawCards);app.status="Bemutató";});
        context.startActivity(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));
        assertTrue(device.wait(Until.hasObject(By.desc("Bemutató sorozat")),15000));device.findObject(By.desc("Bemutató sorozat")).click();assertTrue(device.wait(Until.hasObject(By.res("hu.synostream.android:id/detail_info")),5000));device.waitForIdle();
        assertTrue(device.takeScreenshot(new File(context.getFilesDir(),"preview-portrait.png")));
        device.setOrientationLeft();long deadline=System.currentTimeMillis()+5000;while(device.getDisplayWidth()<=device.getDisplayHeight()&&System.currentTimeMillis()<deadline)Thread.sleep(50);device.waitForIdle();assertTrue(device.wait(Until.hasObject(By.res("hu.synostream.android:id/detail_info")),5000));
        assertTrue(device.takeScreenshot(new File(context.getFilesDir(),"preview-landscape.png")));
        device.findObject(By.res("hu.synostream.android:id/detail_close")).click();device.setOrientationNatural();device.waitForIdle();
        instrumentation.runOnMainSync(()->{try{JSONObject library=LibraryConfig.defaultLibrary(app.libraries,true);LibraryConfig.paths(library,List.of("/video/Filmek"));app.libraryDraft=new JSONObject(library.toString());}catch(Exception e){throw new RuntimeException(e);}});
        // Open an editor through a real visible Activity, using its main-thread attachment.
        MainActivity[] activity={null};instrumentation.runOnMainSync(()->{try{java.lang.reflect.Field field=SynoApp.class.getDeclaredField("ui");field.setAccessible(true);activity[0]=(MainActivity)((java.lang.ref.WeakReference<?>)field.get(app)).get();if(activity[0]!=null)new LibraryUi(activity[0]).show();}catch(Exception e){throw new RuntimeException(e);}});
        assertTrue(device.wait(Until.hasObject(By.res("hu.synostream.android:id/library_save")),5000));device.waitForIdle();assertTrue(device.takeScreenshot(new File(context.getFilesDir(),"preview-sources.png")));
        device.findObject(By.res("hu.synostream.android:id/detail_close")).click();device.unfreezeRotation();
    }
}
