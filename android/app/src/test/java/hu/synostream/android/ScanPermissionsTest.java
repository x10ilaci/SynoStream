package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;import java.nio.file.*;import java.nio.charset.StandardCharsets;
public class ScanPermissionsTest {
 @Test public void scanKeepsCpuPermissionWithoutWifiStatePermissions()throws Exception{String xml=new String(Files.readAllBytes(Paths.get("src/main/AndroidManifest.xml")),StandardCharsets.UTF_8);assertTrue(xml.contains("android.permission.WAKE_LOCK"));assertTrue(xml.contains("android.permission.FOREGROUND_SERVICE_DATA_SYNC"));assertFalse(xml.contains("android.permission.CHANGE_WIFI_STATE"));assertFalse(xml.contains("android.permission.ACCESS_WIFI_STATE"));}
}
