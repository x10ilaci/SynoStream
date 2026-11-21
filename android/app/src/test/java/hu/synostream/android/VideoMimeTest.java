package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;
public class VideoMimeTest {
 @Test public void everySupportedExtensionUsesCorrectMime(){String[][] cases={{"mkv","x-matroska"},{"mp4","mp4"},{"avi","x-msvideo"},{"m4v","mp4"},{"mov","quicktime"},{"wmv","x-ms-wmv"},{"ts","mp2t"},{"mts","mp2t"},{"m2ts","mp2t"},{"mpg","mpeg"},{"mpeg","mpeg"},{"webm","webm"}};for(String[] c:cases){assertTrue(MediaLogic.video("film."+c[0]));assertEquals("video/"+c[1],VideoMime.of("/video/FILM."+c[0].toUpperCase(java.util.Locale.ROOT)));}assertEquals("video/mp4",VideoMime.of("unknown"));}
}
