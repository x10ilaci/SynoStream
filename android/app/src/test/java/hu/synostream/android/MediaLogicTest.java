package hu.synostream.android;
import org.junit.Test;
import static org.junit.Assert.*;
import java.io.*;
import java.util.*;
public class MediaLogicTest {
 @Test public void folderWinsOverAbbreviatedFilename(){assertEquals("Kubo and the Two Strings",MediaLogic.movieName("kubo-720p-hyperx.mkv","Kubo.and.the.Two.Strings.2016.720p.BluRay.DTS.x264.HuN-HyperX",true).title);assertEquals("2016",MediaLogic.movieName("kubo.mkv","Kubo.and.the.Two.Strings.2016.720p",true).year);}
 @Test public void releasePrefixDerivedFromFolder(){assertEquals("Macskak nem tancolnak",MediaLogic.movieName("Pirosasz-Macskak nem tancolnak.mkv","Macskak.Nem.Tancolhatnak.BluRay.1080p.x264.Hun-Pirosasz",true).title);}
 @Test public void samplesExcludedNfoNotVideo(){assertFalse(MediaLogic.video("film.sample.mkv"));assertFalse(MediaLogic.video("film.nfo"));assertTrue(MediaLogic.video("FILM.MKV"));}
 @Test public void genericFoldersDoNotReplaceTitles(){assertEquals("Susi es Tekergo",MediaLogic.movieName("Susi es Tekergo.mkv","Filmek",true).title);}
 @Test public void technicalEpisodeTagsRemoved(){assertEquals("Ernest és Célestine",MediaLogic.clean("Ernest és Célestine S01E01 1080i.mkv",true).title);assertArrayEquals(new int[]{2,12},MediaLogic.episode("Show.S02E012.mkv"));}
 @Test public void accentInsensitiveMatching(){assertEquals(1,MediaLogic.similarity("Chihiro szellemorszagban","Chihiro Szellemországban"),.001);assertEquals(0,MediaLogic.similarity("Kubo","Kubo and the Two Strings"),.001);}
 @Test public void yearMustAgree(){assertTrue(MediaLogic.nearYear("2016-03-01","2016"));assertFalse(MediaLogic.nearYear("1965-03-01","2016"));assertFalse(MediaLogic.nearYear("","2016"));}
 @Test public void pairingPathsRemainInsideRoot(){for(String path:List.of("../film","/film","a/../../b","a//b","a/./b",".synostream/test","a\\b"))assertFalse(path,MediaLogic.safeRelative(path));assertTrue(MediaLogic.safeRelative("film/film.mkv"));assertEquals("film.mkv",MediaLogic.relative("/video","/video/film.mkv"));assertNull(MediaLogic.relative("/video","/video2/film.mkv"));}
 @Test public void embeddedCredentialsRejected(){for(String url:List.of("ftp://nas","https://user:pass@nas","https://nas/path","https://nas?password=x"))try{NasClient.normalizeAddress(url);fail(url);}catch(IllegalArgumentException expected){}assertEquals("https://nas:5001",NasClient.normalizeAddress("nas:5001/"));}
 @Test public void boundedReadsFailInsteadOfTruncating() throws Exception {assertArrayEquals(new byte[]{1,2},NasClient.readBounded(new ByteArrayInputStream(new byte[]{1,2}),2));try{NasClient.readBounded(new ByteArrayInputStream(new byte[]{1,2,3}),2);fail();}catch(IOException expected){}}
}
