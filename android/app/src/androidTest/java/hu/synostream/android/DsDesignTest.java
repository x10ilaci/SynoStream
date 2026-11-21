package hu.synostream.android;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.*;
import android.content.*;import android.graphics.Rect;import org.json.*;import org.junit.*;import org.junit.runner.RunWith;
import java.io.*;import java.util.*;import static org.junit.Assert.*;
@RunWith(AndroidJUnit4.class)
public class DsDesignTest {
    final String pkg="hu.synostream.android";UiDevice d;Context c;SynoApp app;
    void click(String id){assertTrue(id,d.wait(Until.hasObject(By.res(pkg+":id/"+id)),10000));d.findObject(By.res(pkg+":id/"+id)).click();}
    void shot(String name){d.waitForIdle();assertTrue(d.takeScreenshot(new File(c.getFilesDir(),"ds-"+name+".png")));}
    void start(boolean demo){c.startActivity(new Intent(c,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK).putExtra("demo",demo));}
    @After public void reset() throws Exception{if(d!=null){d.setOrientationNatural();d.unfreezeRotation();}}
    @Test public void referenceStructureWorksInPortraitAndLandscape() throws Exception {
        android.app.Instrumentation i=InstrumentationRegistry.getInstrumentation();c=i.getTargetContext();app=(SynoApp)c.getApplicationContext();d=UiDevice.getInstance(i);d.setOrientationNatural();
        c.getSharedPreferences("synostream",0).edit().clear().commit();UiLocale.save(c,"hu");i.runOnMainSync(()->{app.client=null;app.demo=false;app.busy=false;app.query="";app.page="movies";app.libraryDraft=null;app.libraries=LibraryConfig.migrate(new JSONArray());});start(false);assertTrue(d.wait(Until.hasObject(By.res(pkg+":id/login_button")),15000));shot("login");click("demo_button");assertTrue(d.wait(Until.hasObject(By.res(pkg+":id/poster_grid")),10000));
        long until=System.currentTimeMillis()+15000;java.lang.reflect.Field images=MainActivity.class.getDeclaredField("pictures");images.setAccessible(true);while(((android.util.LruCache<?,?>)images.get(null)).size()<6&&System.currentTimeMillis()<until)Thread.sleep(100);
        UiObject2 tile=d.findObject(By.desc("Kubo és a varázshúrok"));assertNotNull(tile);Rect card=tile.getVisibleBounds();UiObject2 label=tile.findObject(By.text("Kubo és a varázshúrok"));assertNotNull(label);assertTrue("Title belongs inside the poster",card.contains(label.getVisibleBounds()));shot("grid-portrait");
        click("menu_button");assertTrue(d.wait(Until.hasObject(By.desc("Filmek médiatár")),5000));Rect nav=d.findObject(By.desc("Filmek médiatár")).getVisibleBounds();Rect toolbar=d.findObject(By.res(pkg+":id/menu_button")).getVisibleBounds();assertTrue("Drawer begins below the toolbar",nav.top>=toolbar.bottom);shot("drawer-portrait");click("menu_button");assertTrue(d.wait(Until.gone(By.desc("Filmek médiatár")),5000));
        d.findObject(By.desc("Keresés")).click();assertTrue(d.wait(Until.hasObject(By.res(pkg+":id/search_box")),5000));d.findObject(By.res(pkg+":id/search_box")).setText("Kubo");assertTrue(d.wait(Until.hasObject(By.desc("Kubo és a varázshúrok")),5000));shot("search");click("menu_button");
        // Return from search using its visible toolbar button, independently of IME handling.
        if(d.hasObject(By.res(pkg+":id/search_box")))click("menu_button");
        assertTrue(d.wait(Until.hasObject(By.desc("Kubo és a varázshúrok")),5000));d.findObject(By.desc("Kubo és a varázshúrok")).click();assertTrue(d.wait(Until.hasObject(By.res(pkg+":id/detail_info")),5000));shot("detail-portrait");
        assertNotNull(d.findObject(By.res(pkg+":id/play_button")));assertNull(d.findObject(By.text("Másik lejátszóval")));
        d.setOrientationLeft();assertTrue(d.wait(Until.hasObject(By.res(pkg+":id/detail_info")),10000));shot("detail-landscape");click("detail_close");assertTrue(d.wait(Until.hasObject(By.res(pkg+":id/poster_grid")),5000));shot("grid-landscape");
        click("menu_button");assertTrue(d.wait(Until.hasObject(By.desc("Filmek médiatár")),5000));shot("drawer-landscape");click("menu_button");
        d.findObject(By.desc("További lehetőségek")).click();assertTrue(d.wait(Until.hasObject(By.text("Rendezési beállítások")),5000));d.findObject(By.text("Rendezési beállítások")).click();assertTrue(d.wait(Until.hasObject(By.text("Cím – Z–A")),5000));d.findObject(By.text("Cím – Z–A")).click();
        assertTrue(d.wait(Until.hasObject(By.text("Mappa szerint")),10000));d.findObject(By.text("Mappa szerint")).click();assertTrue(d.wait(Until.hasObject(By.text("Mappa kiválasztása  ▾")),5000));d.findObject(By.text("Mappa kiválasztása  ▾")).click();assertTrue(d.wait(Until.hasObject(By.text("Összes mappa")),5000));d.findObject(By.text("Összes mappa")).click();
    }
}
