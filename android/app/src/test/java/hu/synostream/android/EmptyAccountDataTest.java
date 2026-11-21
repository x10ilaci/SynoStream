package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;
public class EmptyAccountDataTest {
 @Test public void recursivelyEmptyStructuresAreEmpty(){for(String value:new String[]{"", "{}", "[]", "\"\"", "{\"hidden\":{},\"manual\":{}}", "{\"hidden\":{},\"manual\":{},\"groups\":{}}", "{\"a\":[{},[],\"\",{\"b\":[]}]}","[{},[[]],\"\"]"})assertTrue(value,AccountIdentity.empty(value));}
 @Test public void everyRealLeafIsPreserved(){for(String value:new String[]{"{\"hidden\":{\"movie:/a\":\"X\"}}", "{\"a\":[{},0]}", "{\"a\":false}", "{\"a\":null}", "\"X\"", "{\"a\":\" \"}", "{} trailing", "["})assertFalse(value,AccountIdentity.empty(value));}
 @Test public void migrationReplacesSkeletonButNeverRealData(){TorrentRulesTest.Memory store=new TorrentRulesTest.Memory();store.put("libraries_owner","nas|FixtureCase");String original="{\"hidden\":{\"movie:/a\":\"X\"}}";store.put("edits:nas|FixtureCase",original);store.put("edits:nas|fixturecase","{\"hidden\":{},\"manual\":{},\"groups\":{}}");AccountIdentity.migrateKeys(store,"nas","fixturecase");assertEquals(original,store.get("edits:nas|fixturecase",""));String newer="{\"manual\":{\"movie:/b\":{\"id\":52}}}";store.put("edits:nas|fixturecase",newer);AccountIdentity.migrateKeys(store,"nas","FIXTURECASE");assertEquals(newer,store.get("edits:nas|fixturecase",""));}
}
