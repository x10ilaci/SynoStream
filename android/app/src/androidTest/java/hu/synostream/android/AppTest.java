package hu.synostream.android;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.*;
import android.content.*;
import org.junit.*;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
@RunWith(AndroidJUnit4.class)
public class AppTest {
 @Test public void encryptedSecretsRoundTrip() throws Exception {Context c=InstrumentationRegistry.getInstrumentation().getTargetContext();Store s=new Store(c);s.secret("test_only","not-a-real-password");assertEquals("not-a-real-password",s.secret("test_only"));assertFalse(c.getSharedPreferences("synostream",0).getAll().toString().contains("not-a-real-password"));s.forget("test_only");}
 @Test public void demoSearchSurvivesRotation() throws Exception {Context c=InstrumentationRegistry.getInstrumentation().getTargetContext();UiDevice d=UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());c.startActivity(new Intent(c,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK).putExtra("demo",true));assertTrue(d.wait(Until.hasObject(By.desc("Keresés")),15000));d.findObject(By.desc("Keresés")).click();assertTrue(d.wait(Until.hasObject(By.res("hu.synostream.android:id/search_box")),5000));UiObject2 search=d.findObject(By.res("hu.synostream.android:id/search_box"));search.setText("Kubo");assertTrue("Filtered movie visible",d.wait(Until.hasObject(By.desc("Kubo és a varázshúrok")),5000));d.setOrientationLeft();assertTrue(d.wait(Until.hasObject(By.res("hu.synostream.android:id/search_box")),5000));assertEquals("Kubo",d.findObject(By.res("hu.synostream.android:id/search_box")).getText());d.setOrientationNatural();d.unfreezeRotation();}
}
