package hu.synostream.android;
import androidx.test.ext.junit.runners.AndroidJUnit4;import androidx.test.platform.app.InstrumentationRegistry;import androidx.test.uiautomator.*;
import android.content.*;import android.graphics.Rect;import org.json.*;import org.junit.*;import org.junit.runner.RunWith;import java.util.*;import java.util.regex.Pattern;import static org.junit.Assert.*;
@RunWith(AndroidJUnit4.class)
public class PhoneLayoutTest {
    private static final String PKG="hu.synostream.android";private UiDevice device;private Context context;private SynoApp app;
    private void click(String id){assertTrue(id,device.wait(Until.hasObject(By.res(PKG+":id/"+id)),10000));device.findObject(By.res(PKG+":id/"+id)).click();}
    private void start() throws Exception {
        context=InstrumentationRegistry.getInstrumentation().getTargetContext();app=(SynoApp)context.getApplicationContext();device=UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
        UiLocale.save(context,"hu");device.setOrientationNatural();device.unfreezeRotation();
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
            app.client=null;app.demo=true;app.busy=false;app.libraryDraft=null;app.page="shows";app.query="";app.identity="layout-test";app.libraries=LibraryConfig.migrate(new JSONArray());app.selectedLibrary=LibraryConfig.defaultLibrary(app.libraries,false).optString("id");app.edits=new LocalEdits("{}");app.rawCards=new ArrayList<>();
            Library.Card first=new Library.Card("/demo/first","Első sorozat",false);first.id=1;first.episodeRoots.add(first.path);
            Library.Card second=new Library.Card("/demo/second","Második sorozat",false);second.id=2;second.episodeRoots.add(second.path);app.rawCards.add(first);app.rawCards.add(second);app.cards=new ArrayList<>(app.rawCards);
        });
        context.startActivity(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));assertTrue(device.wait(Until.hasObject(By.desc("Első sorozat")),15000));
    }
    private String selectedEpisode(){String[] result={""};InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{try{java.lang.reflect.Field field=SynoApp.class.getDeclaredField("ui");field.setAccessible(true);MainActivity activity=(MainActivity)((java.lang.ref.WeakReference<?>)field.get(app)).get();result[0]=activity.detailEpisodePath;}catch(Exception error){throw new RuntimeException(error);}});return result[0];}
    @After public void orientation() throws Exception {if(device!=null){device.setOrientationNatural();device.unfreezeRotation();}}
    @Test public void landscapeKeepsPhoneNavigationAndReachableDetailControls() throws Exception {
        start();device.setOrientationLeft();assertTrue(device.wait(Until.hasObject(By.res(PKG+":id/menu_button")),10000));
        assertTrue(device.getDisplayWidth()>device.getDisplayHeight());
        assertTrue(device.findObject(By.res(PKG+":id/menu_button")).getVisibleBounds().width()>0);
        assertNull("Phone landscape must not lock open a tablet sidebar",device.findObject(By.text("SynoStream")));
        device.findObject(By.desc("Első sorozat")).click();assertTrue(device.wait(Until.hasObject(By.res(PKG+":id/detail_info")),5000));
        for(String id:List.of("detail_info","detail_hide","detail_merge","detail_close")){
            UiObject2 view=device.findObject(By.res(PKG+":id/"+id));assertNotNull(id,view);Rect bounds=view.getVisibleBounds();assertTrue(id,bounds.width()>0&&bounds.height()>0&&bounds.top>=0&&bounds.bottom<=device.getDisplayHeight());
        }
        assertNull("Old three-button dialog removed",device.findObject(By.res("android:id/button3")));
        device.findObject(By.desc("Sorozat epizódjai")).click();assertTrue(device.wait(Until.hasObject(By.text(Pattern.compile(".*1\\. évad"))),5000));device.findObject(By.text(Pattern.compile(".*1\\. évad"))).click();UiObject2 episodes=device.findObject(By.res(PKG+":id/episode_list"));assertNotNull(episodes);assertTrue(episodes.getVisibleBounds().height()>70);episodes.scroll(Direction.DOWN,.8f);
        UiObject2 item=device.findObject(By.desc(Pattern.compile("^S\\d+E\\d+\\s.*")));assertNotNull(item);item.click();
        String selected=selectedEpisode();assertFalse(selected.isEmpty());
        device.setOrientationNatural();assertTrue(device.wait(Until.hasObject(By.res(PKG+":id/detail_info")),10000));assertTrue(device.wait(Until.hasObject(By.desc("Sorozat epizódjai")),10000));assertEquals(selected,selectedEpisode());
        click("detail_close");assertTrue(device.wait(Until.hasObject(By.res(PKG+":id/poster_grid")),5000));
    }
    @Test public void cornerButtonsCanMergeUnmergeAndHideWithoutRenamingPrompt() throws Exception {
        start();device.findObject(By.desc("Első sorozat")).click();click("detail_merge");assertTrue(device.wait(Until.hasObject(By.text("Második sorozat")),5000));device.findObject(By.text("Második sorozat")).click();
        assertTrue(device.wait(Until.hasObject(By.res(PKG+":id/poster_grid")),5000));assertEquals(1,app.cards.size());assertEquals("Második sorozat",app.cards.get(0).title);assertEquals(2,app.cards.get(0).episodeRoots.size());
        device.findObject(By.desc("Második sorozat")).click();click("detail_unmerge");assertTrue(device.wait(Until.hasObject(By.desc("Első sorozat")),5000));assertEquals(2,app.cards.size());
        device.findObject(By.desc("Első sorozat")).click();click("detail_hide");assertTrue(device.wait(Until.hasObject(By.res("android:id/button1")),5000));device.findObject(By.res("android:id/button1")).click();assertTrue(device.wait(Until.hasObject(By.res(PKG+":id/poster_grid")),5000));assertEquals(1,app.cards.size());assertEquals(2,app.rawCards.size());
    }

    @Test public void landscapeKeyboardDoesNotReplaceTheEditorOrCoverSave() throws Exception {
        start();device.setOrientationLeft();device.waitForIdle();
        final JSONObject library=new JSONObject().put("id","keyboard-test").put("name","Saját médiatár").put("movie",true).put("builtin",false);LibraryConfig.paths(library,List.of("/Movies"));
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{try{java.lang.reflect.Field f=SynoApp.class.getDeclaredField("ui");f.setAccessible(true);MainActivity activity=(MainActivity)((java.lang.ref.WeakReference<?>)f.get(app)).get();new LibraryUi(activity).edit(library);}catch(Exception e){throw new RuntimeException(e);}});
        assertTrue(device.wait(Until.hasObject(By.res(PKG+":id/library_name")),5000));device.findObject(By.res(PKG+":id/library_name")).click();device.waitForIdle();
        assertNull("No fullscreen landscape IME extraction",device.findObject(By.res("android:id/extractEditText")));
        UiObject2 save=device.findObject(By.res(PKG+":id/library_save"));assertNotNull(save);Rect bounds=save.getVisibleBounds();assertTrue(bounds.height()>0&&bounds.bottom<=device.getDisplayHeight());
        assertTrue(device.findObject(By.res(PKG+":id/library_name")).getVisibleBounds().height()>0);click("detail_close");
    }
}
