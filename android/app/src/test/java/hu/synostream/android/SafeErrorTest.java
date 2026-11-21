package hu.synostream.android;
import org.junit.Test;import org.json.JSONException;import static org.junit.Assert.*;
public class SafeErrorTest {@Test public void jsonDetailsNeverLeak(){assertEquals("A NAS váratlan választ adott.",SynoApp.safeError(new JSONException("private malformed field")));}}
