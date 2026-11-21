package hu.synostream.android;
import org.junit.*;
import static org.junit.Assert.*;
import java.nio.charset.*;
import java.util.*;
public class NfoTest {
    private Nfo.Hint parse(String text,boolean movie){return Nfo.parse(text.getBytes(StandardCharsets.UTF_8),movie);}
    @Test public void structuredIdsBeatPlotLinks(){Nfo.Hint hint=parse("<movie><title>Mátrix</title><originaltitle>Matrix</originaltitle><year>1999</year><uniqueid type='imdb'>tt0133093</uniqueid><uniqueid type='tmdb'>603</uniqueid><plot>Like tt0234215</plot></movie>",true);assertEquals(Long.valueOf(603),hint.tmdb);assertEquals("tt0133093",hint.imdb);assertEquals(List.of("Mátrix","Matrix"),hint.titles);assertEquals("1999",hint.year);}
    @Test public void textEncodingsAndBomAreSupported(){String text="Cím: Árvíztűrő tükörfúrógép\nÉv: 1999\ntt0133093";for(String encoding:List.of("UTF-8","UTF-16","windows-1250")){Nfo.Hint hint=Nfo.parse(text.getBytes(Charset.forName(encoding)),true);assertEquals(encoding,List.of("Árvíztűrő tükörfúrógép"),hint.titles);assertEquals("tt0133093",hint.imdb);}}
    @Test public void dosNfoStillProvidesUnambiguousIdentifiers(){Nfo.Hint hint=Nfo.parse("Title: Film\ntt0133093".getBytes(Charset.forName("IBM437")),true);assertEquals("tt0133093",hint.imdb);}
    @Test public void ambiguousIdsAreNotGuessed(){Nfo.Hint hint=parse("tt0133093 tt0234215 https://tmdb.org/movie/1 https://tmdb.org/movie/2",true);assertNull(hint.imdb);assertNull(hint.tmdb);}
    @Test public void episodeAndWrongMediaTypeCannotIdentifySeries(){assertNull(parse("<episodedetails><id>tt0133093</id></episodedetails>",false).imdb);assertNull(parse("<movie><id>tt0133093</id></movie>",false).imdb);assertNull(parse("https://tmdb.org/tv/1399",true).tmdb);}
    @Test public void doctypeAndEntitiesAreRejected(){Nfo.Hint hint=parse("<!DOCTYPE movie [<!ENTITY x SYSTEM 'file:///secret'>]><movie><title>&x;</title><id>tt0133093</id></movie>",true);assertTrue(hint.titles.isEmpty());assertNull(hint.imdb);}
    @Test public void oversizedPayloadDoesNotBecomeAMatch(){byte[] data=new byte[Nfo.MAX_BYTES+1];Arrays.fill(data,(byte)'a');assertTrue(Nfo.parse(data,true).titles.isEmpty());}
    private NasClient.Entry file(String name){return new NasClient.Entry(name,"/video/"+name,false,0);}
    @Test public void exactSidecarWinsInMultiMovieFolder(){NasClient.Entry exact=file("opaque.nfo");assertSame(exact,Nfo.select(List.of(exact,file("other.nfo"),file("opaque.mkv"),file("other.mkv")),"opaque.mkv",true));}
    @Test public void sharedSidecarNotAppliedToSeveralMovies(){assertNull(Nfo.select(List.of(file("movie.nfo"),file("a.mkv"),file("b.mkv")),"a.mkv",true));}
    @Test public void duplicateCaseInsensitiveSidecarsAreAmbiguous(){assertNull(Nfo.select(List.of(file("a.nfo"),file("A.NFO"),file("a.mkv")),"a.mkv",true));}
    @Test public void conventionalSeriesSidecarWorksWithoutVideos(){NasClient.Entry standard=file("tvshow.nfo");assertSame(standard,Nfo.select(List.of(standard),"Show",false));}
    @Test public void nestedEpisodeTitleDoesNotReplaceMovieTitle(){Nfo.Hint hint=parse("<movie><title>Film</title><actor><title>Actor role</title></actor></movie>",true);assertEquals(List.of("Film"),hint.titles);}
}
