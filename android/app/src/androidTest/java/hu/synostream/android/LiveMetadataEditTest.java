package hu.synostream.android;
import androidx.test.ext.junit.runners.AndroidJUnit4;import androidx.test.platform.app.InstrumentationRegistry;import androidx.test.uiautomator.*;
import android.content.*;import org.json.*;import org.junit.*;import org.junit.runner.RunWith;
import java.io.*;import java.lang.reflect.*;import java.nio.charset.StandardCharsets;import java.util.*;import java.util.regex.Pattern;import static org.junit.Assert.*;
@RunWith(AndroidJUnit4.class)
public class LiveMetadataEditTest {
    private Object field(NasClient c,String name) throws Exception {Field f=NasClient.class.getDeclaredField(name);f.setAccessible(true);return f.get(c);}
    private void discoverDelete(NasClient c) throws Exception {
        Method json=NasClient.class.getDeclaredMethod("json",String.class,Map.class,boolean.class);json.setAccessible(true);
        JSONObject result=(JSONObject)json.invoke(c,field(c,"base")+"/webapi/query.cgi",Map.of("api","SYNO.API.Info","version","1","method","query","query","SYNO.FileStation.Delete"),false);
        ((JSONObject)field(c,"apis")).put("SYNO.FileStation.Delete",result.getJSONObject("data").getJSONObject("SYNO.FileStation.Delete"));
    }
    @Test public void optionalManualInfoButtonPersistsToIsolatedNasFolder() throws Exception {
        android.app.Instrumentation instrumentation=InstrumentationRegistry.getInstrumentation();Context context=instrumentation.getTargetContext();SynoApp app=(SynoApp)context.getApplicationContext();UiDevice device=UiDevice.getInstance(instrumentation);
        File fixture=new File(context.getFilesDir(),"test_write.json");Assume.assumeTrue("No private NAS fixture injected",fixture.exists());
        JSONObject credentials;try{credentials=new JSONObject(new String(NasClient.readBounded(new FileInputStream(fixture),2*1024*1024),StandardCharsets.UTF_8));}finally{fixture.delete();}
        String parent=credentials.getJSONArray("roots").getJSONObject(0).getString("path");
        String name=".synostream-android03-test-"+UUID.randomUUID().toString().replace("-",""),root=parent+"/"+name;
        assertTrue(name.matches("\\.synostream-android03-test-[0-9a-f]{32}"));assertTrue(MediaLogic.safeRelative(parent.substring(1)));
        NasClient client=new NasClient(new NasClient.Credentials(credentials.getString("address"),"",credentials.getString("user"),credentials.getString("password"),""));client.connect();
        String previousKey=app.store.secret("tmdb_key");boolean cleanup=false;
        try{
            assertFalse(client.list(parent).stream().anyMatch(e->e.name.equals(name)));discoverDelete(client);
            String identifier=UUID.randomUUID().toString().replace("-","");
            JSONObject bootstrap=new JSONObject().put("format_version",1).put("event_id",identifier).put("relative_path","fixture.mkv").put("media_type","movie").put("tmdb_id",603).put("title","SynoStream teszt").put("deleted",false).put("generation",1).put("created_ns",System.currentTimeMillis()*1_000_000L);
            Method upload=NasClient.class.getDeclaredMethod("uploadEvent",String.class,String.class,byte[].class);upload.setAccessible(true);upload.invoke(client,root+"/.synostream/parositasok",identifier+".json",bootstrap.toString().getBytes(StandardCharsets.UTF_8));
            app.store.secret("tmdb_key",credentials.getString("tmdb_key"));
            Library.Card card=new Library.Card(root+"/fixture.mkv","Tesztkártya",true);
            JSONObject library=new JSONObject().put("id","live-metadata-test").put("name","Tesztmédiatár").put("movie",true);LibraryConfig.paths(library,List.of(root));
            instrumentation.runOnMainSync(()->{app.client=client;app.demo=false;app.busy=false;app.libraryDraft=null;app.identity="live-metadata-test";app.edits=new LocalEdits("{}");app.libraries=new JSONArray().put(library);app.selectedLibrary=library.optString("id");app.page="movies";app.query="";app.rawCards=new ArrayList<>(List.of(card));app.cards=new ArrayList<>(List.of(card));});
            context.startActivity(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));
            assertTrue(device.wait(Until.hasObject(By.desc("Tesztkártya")),15000));device.findObject(By.desc("Tesztkártya")).click();
            assertTrue(device.wait(Until.hasObject(By.res("hu.synostream.android:id/detail_info")),5000));device.findObject(By.res("hu.synostream.android:id/detail_info")).click();
            assertTrue(device.wait(Until.hasObject(By.res("hu.synostream.android:id/metadata_query")),5000));device.findObject(By.res("hu.synostream.android:id/metadata_query")).setText("tt0133093");device.findObject(By.res("hu.synostream.android:id/metadata_search")).click();
            assertTrue(device.wait(Until.hasObject(By.text(Pattern.compile("^Mátrix.*"))),30000));device.findObject(By.text(Pattern.compile("^Mátrix.*"))).click();
            long until=System.currentTimeMillis()+60000;boolean[] committed={false};
            while(!committed[0]&&System.currentTimeMillis()<until){instrumentation.runOnMainSync(()->committed[0]=!app.busy&&!app.rawCards.isEmpty()&&app.rawCards.get(0).id==603&&app.edits.overrides().isEmpty());if(!committed[0])Thread.sleep(100);}
            instrumentation.waitForIdleSync();assertTrue("UI and NAS correction committed",committed[0]);
            assertFalse("Metadata save finished",app.busy);assertEquals(603,app.rawCards.get(0).id);assertTrue(app.edits.overrides().isEmpty());
            Pairings records=new Pairings();for(NasClient.Entry e:client.list(root+"/.synostream/parositasok"))records.add(e.name,client.readFile(e.path,16384));
            JSONObject winner=records.get(root,root+"/fixture.mkv",true);assertNotNull(winner);assertEquals(603,winner.getLong("tmdb_id"));assertEquals(2,winner.getLong("generation"));assertEquals("Mátrix",winner.getString("title"));
        }finally{
            instrumentation.waitForIdleSync();app.worker.submit(()->{}).get(60,java.util.concurrent.TimeUnit.SECONDS);instrumentation.waitForIdleSync();
            try{
                // Deletion is restricted to this test's exact random child folder.
                assertEquals(parent+"/"+name,root);assertTrue(name.matches("\\.synostream-android03-test-[0-9a-f]{32}"));
                if(client.list(parent).stream().anyMatch(e->e.name.equals(name))){
                    JSONObject deletion=client.call("SYNO.FileStation.Delete","start",Map.of("path",new JSONArray().put(root).toString(),"recursive","true"));String task=deletion.optString("taskid");
                    if(!task.isEmpty()){for(int i=0;i<60;i++){deletion=client.call("SYNO.FileStation.Delete","status",Map.of("taskid",task));if(deletion.optBoolean("finished"))break;Thread.sleep(250);}assertTrue(deletion.optBoolean("finished"));assertFalse(deletion.has("errors")&&deletion.getJSONArray("errors").length()>0);}
                }
                cleanup=client.list(parent).stream().noneMatch(e->e.name.equals(name));assertTrue("Only the isolated test tree was removed",cleanup);
            }finally{
                app.store.secret("tmdb_key",previousKey);instrumentation.runOnMainSync(()->{app.client=null;app.demo=false;app.busy=false;app.libraries=LibraryConfig.migrate(app.store.libraries());app.selectedLibrary="";app.rawCards=new ArrayList<>();app.cards=new ArrayList<>();app.changed();});client.logout();
                try(FileOutputStream out=new FileOutputStream(new File(context.getFilesDir(),"metadata-write-test-result.json"))){out.write(new JSONObject().put("cleanup",cleanup).put("test_root",root).toString().getBytes(StandardCharsets.UTF_8));}
            }
        }
    }
}
