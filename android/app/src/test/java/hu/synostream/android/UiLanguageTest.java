package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;
public class UiLanguageTest {
 @Test public void initialChoiceKeepsLegacyAndFollowsSystemOnFreshInstall(){Object[][] cases={{true,"en","hu"},{true,"hu","hu"},{false,"hu","hu"},{false,"en","en"}};for(Object[] row:cases)assertEquals(row[2],UiLanguage.initial((Boolean)row[0],(String)row[1]));}
 @Test public void nonHungarianSystemsDefaultToEnglishOnlyOnFreshInstall(){for(String value:new String[]{null,"","de","fr","es","ja"}){assertEquals("en",UiLanguage.initial(false,value));assertEquals("hu",UiLanguage.initial(true,value));}}

 @Test public void existingInstallsKeepHungarian(){assertEquals("hu",UiLanguage.normalize(null));assertEquals("hu",UiLanguage.normalize(""));}
 @Test public void supportedChoicesAreStable(){assertEquals("hu",UiLanguage.normalize("hu"));assertEquals("en",UiLanguage.normalize("en"));}
 @Test public void unsupportedOrCorruptPreferenceHasSafeFallback(){for(String value:new String[]{"de","en-US","../../","HU","unknown"})assertEquals("hu",UiLanguage.normalize(value));}
}
