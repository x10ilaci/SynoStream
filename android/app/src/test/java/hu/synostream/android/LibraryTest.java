package hu.synostream.android;
import org.junit.*;
import org.json.*;
import java.util.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import static org.junit.Assert.*;
public class LibraryTest {
    private static final class Files implements Library.Source {
        final Map<String,List<NasClient.Entry>> folders=new HashMap<>();final Map<String,byte[]> data=new HashMap<>();
        void folder(String path,String... names){List<NasClient.Entry> entries=new ArrayList<>();for(String name:names){boolean directory=name.endsWith("/");if(directory)name=name.substring(0,name.length()-1);entries.add(new NasClient.Entry(name,path+"/"+name,directory,0));}folders.put(path,entries);}
        void text(String path,String value){data.put(path,value.getBytes(StandardCharsets.UTF_8));}
        public List<NasClient.Entry> list(String path) throws Exception {if(!folders.containsKey(path))throw new IOException("Missing folder");return folders.get(path);}
        public byte[] readFile(String path,int limit) throws Exception {if(!data.containsKey(path))throw new IOException("NAS offline");return data.get(path);}
    }
    private JSONObject info(long id,String title,boolean movie) throws Exception {return new JSONObject().put("id",id).put(movie?"title":"name",title).put(movie?"original_title":"original_name",title).put(movie?"release_date":"first_air_date","2020-01-01").put("overview","Leírás");}
    private Recognition.Api searching(Set<String> queries,boolean movie,List<String> seen){return (endpoint,p)->{if(endpoint.startsWith("search/")){String title=p.get("query");seen.add(title);return new JSONObject().put("results",queries.contains(title)?new JSONArray().put(info(1,title,movie)):new JSONArray());}if(endpoint.endsWith("alternative_titles"))return new JSONObject();return info(1,"Magyar cím",movie);};}
    @Test public void noResultFromFilenameStillTriesFullFolderTitle() throws Exception {
        Files f=new Files();f.folder("/movies","Full.Folder.Title.2020/");f.folder("/movies/Full.Folder.Title.2020","opaque.mkv","audio.mkv");List<String> seen=new ArrayList<>();
        Library library=new Library(f,searching(Set.of("Full Folder Title"),true,seen));List<Library.Card> cards=library.scan("/movies",true,n->{});
        assertEquals(2,cards.size());assertEquals(1,cards.get(0).id);assertTrue(seen.contains("opaque"));assertTrue(seen.contains("Full Folder Title"));
    }
    @Test public void nfoTitleFallsBackToFilenameIfItHasNoMatch() throws Exception {
        Files f=new Files();f.folder("/movies","Exact.Title.mkv","Exact.Title.nfo");f.text("/movies/Exact.Title.nfo","Title: Unknown NFO Title");List<String> seen=new ArrayList<>();
        Library library=new Library(f,searching(Set.of("Exact Title"),true,seen));Library.Card card=library.scan("/movies",true,n->{}).get(0);
        assertEquals(1,card.id);assertTrue(seen.contains("Unknown NFO Title"));assertTrue(seen.contains("Exact Title"));
    }
    @Test public void nfoIdIsStrongerThanFilenameAndLocalized() throws Exception {
        Files f=new Files();f.folder("/movies","opaque.mkv","opaque.nfo");f.text("/movies/opaque.nfo","https://www.themoviedb.org/movie/603");
        Library library=new Library(f,(endpoint,p)->{assertEquals("movie/603",endpoint);return info(603,"Mátrix",true);});
        Library.Card card=library.scan("/movies",true,n->{}).get(0);assertEquals("Mátrix",card.title);assertEquals("nfo",card.origin);
    }
    private void pairing(Files f,long id) throws Exception {
        String event="00000000000000000000000000000001";f.folder("/movies","opaque.mkv","opaque.nfo",".synostream/");f.folder("/movies/.synostream","parositasok/");f.folder("/movies/.synostream/parositasok",event+".json");f.text("/movies/.synostream/parositasok/"+event+".json",PairingsTest.event(event,"opaque.mkv",id,1).toString());f.text("/movies/opaque.nfo","tt0133093");
    }
    @Test public void sharedManualPairingOverridesNfoAndFilename() throws Exception {
        Files f=new Files();pairing(f,99);Library library=new Library(f,(endpoint,p)->{assertEquals("movie/99",endpoint);return info(99,"Kézi magyar cím",true);});
        Library.Card card=library.scan("/movies",true,n->{}).get(0);assertEquals(99,card.id);assertEquals("Kézi magyar cím",card.title);assertEquals(0,library.nfosRead);assertEquals(1,library.pairings.events);
    }
    @Test public void pairingTitlesAvailableWithoutApiKey() throws Exception {Files f=new Files();pairing(f,99);Library library=new Library(f,null);Library.Card card=library.scan("/movies",true,n->{}).get(0);assertEquals("Magyar cím",card.title);assertEquals(99,card.id);}
    @Test public void temporaryApiErrorPreservesPreviousSuccessfulMetadata() throws Exception {
        Files f=new Files();f.folder("/movies","Title.mkv");Library library=new Library(f,(endpoint,p)->{throw new IOException("Temporary outage");});
        Library.Card old=new Library.Card("/movies/Title.mkv","Jó cím",true);old.id=99;old.backdrop="background";old.runtime=123;old.rating=8.5;old.genres="Animáció";old.poster="https://image.tmdb.org/t/p/w342/p.jpg";library.previous(List.of(old));Library.Card result=library.scan("/movies",true,n->{}).get(0);
        assertEquals(99,result.id);assertEquals("Jó cím",result.title);assertEquals("background",result.backdrop);assertEquals(123,result.runtime);assertEquals(8.5,result.rating,0);assertEquals("Animáció",result.genres);assertEquals("retry",result.lookupState);assertEquals(1,library.metadataErrors);
    }
    @Test public void repeatedApiFailureDoesNotMakeEveryFileWaitForNetwork() throws Exception {
        Files f=new Files();f.folder("/movies","a.mkv","b.mkv","c.mkv","d.mkv","e.mkv");int[] calls={0};
        Library library=new Library(f,(endpoint,p)->{calls[0]++;throw new IOException("Temporary outage");});List<Library.Card> cards=library.scan("/movies",true,n->{});
        assertEquals(5,cards.size());assertEquals(3,calls[0]);assertEquals(5,library.metadataErrors);for(Library.Card c:cards)assertEquals("retry",c.lookupState);
    }
    @Test public void unreadableNasFolderIsNeverReportedAsEmptySuccess() throws Exception {Files f=new Files();f.folder("/movies","missing/");Library library=new Library(f,null);try{library.scan("/movies",true,n->{});fail();}catch(IOException expected){}}
    @Test public void seasonsAndLooseEpisodesAreGroupedButUnrelatedFoldersAreNot() throws Exception {
        Files f=new Files();f.folder("/shows","A.Show.S01/","A.Show.S02/","Other Show/","Loose.Show.S01E01.mkv","Loose.Show.S01E02.mkv");
        f.folder("/shows/A.Show.S01","01.mkv");f.folder("/shows/A.Show.S02","01.mkv");f.folder("/shows/Other Show","02.mkv");
        Library library=new Library(f,null);List<Library.Card> cards=library.scan("/shows",false,n->{});
        assertEquals(3,cards.size());assertEquals(5,library.videosFound);
        for(Library.Card c:cards)if(c.title.equals("A Show")){assertEquals(2,c.episodeRoots.size());List<NasClient.Entry> episodes=library.episodes(c.episodeRoots);assertEquals(1,episodes.get(0).season);assertEquals(2,episodes.get(1).season);}
    }
    @Test public void sampleAndNasSystemFoldersAreIgnored() throws Exception {
        Files f=new Files();f.folder("/movies","@eaDir/","#recycle/",".hidden.mkv","film.sample.mkv","Real.mkv");Library library=new Library(f,null);assertEquals(1,library.scan("/movies",true,n->{}).size());assertEquals(1,library.foldersRead);
    }
    @Test public void unknownEpisodeNumbersAreDistinctAndDoNotCollideWithExplicitOnes() throws Exception {
        List<NasClient.Entry> files=List.of(new NasClient.Entry("S01E01.mkv","/show/S01E01.mkv",false,0),new NasClient.Entry("opaque-a.mkv","/show/opaque-a.mkv",false,0),new NasClient.Entry("opaque-b.mkv","/show/opaque-b.mkv",false,0));
        Set<Integer> numbers=new HashSet<>();for(EpisodeIndex.Item item:EpisodeIndex.build(files,"/show"))assertTrue(numbers.add(item.episode));assertEquals(Set.of(1,2,3),numbers);
    }

    @Test public void unreadableNfoStillAllowsFilenameSearch() throws Exception {
        Files f=new Files();f.folder("/movies","Exact.Title.mkv","Exact.Title.nfo");Library library=new Library(f,searching(Set.of("Exact Title"),true,new ArrayList<>()));
        Library.Card card=library.scan("/movies",true,n->{}).get(0);assertEquals(1,card.id);assertEquals(1,library.nfoWarnings);assertEquals(0,library.metadataErrors);
    }
    @Test public void ambiguousNamesakeOnlyPreservesAnUnchangedValidPreviousCandidate() throws Exception {
        for(long previousId:List.of(1L,3L)){
            Files f=new Files();f.folder("/movies","Same.Title.2020.mkv");f.folders.get("/movies").get(0).modified=100;
            Library library=new Library(f,(endpoint,p)->endpoint.startsWith("search/")?new JSONObject().put("results",new JSONArray().put(info(1,"Same Title",true)).put(info(2,"Same Title",true))):endpoint.endsWith("alternative_titles")?new JSONObject():info(1,"Magyar cím",true));
            Library.Card previous=new Library.Card("/movies/Same.Title.2020.mkv","Old",true);previous.id=previousId;previous.modified=100;library.previous(List.of(previous));
            assertEquals(previousId==1?1:-1,library.scan("/movies",true,n->{}).get(0).id);
        }
    }

    @Test public void conflictingManualSeriesIdsPreventAutomaticSeasonMerge() throws Exception {
        Files f=new Files();String a="00000000000000000000000000000001",b="00000000000000000000000000000002";
        f.folder("/shows","Same.Show.S01/","Same.Show.S02/",".synostream/");f.folder("/shows/Same.Show.S01","01.mkv");f.folder("/shows/Same.Show.S02","01.mkv");f.folder("/shows/.synostream","parositasok/");f.folder("/shows/.synostream/parositasok",a+".json",b+".json");
        f.text("/shows/.synostream/parositasok/"+a+".json",PairingsTest.event(a,"Same.Show.S01",1,1).put("media_type","tv").toString());f.text("/shows/.synostream/parositasok/"+b+".json",PairingsTest.event(b,"Same.Show.S02",2,1).put("media_type","tv").toString());
        Library library=new Library(f,(endpoint,p)->info(endpoint.equals("tv/1")?1:2,"Kézi sorozat",false));List<Library.Card> cards=library.scan("/shows",false,n->{});
        assertEquals(2,cards.size());assertEquals(Set.of(1L,2L),Set.of(cards.get(0).id,cards.get(1).id));assertEquals(0,library.metadataErrors);
    }
 @Test public void seriesRootExtraDirectoriesNeverBecomeCards()throws Exception{Files f=new Files();f.folder("/shows","Extras/","Trailers/","Good.Show/");for(String name:List.of("Extras","Trailers","Good.Show"))f.folder("/shows/"+name,"S01E01.mkv");List<Library.Card> cards=new Library(f,null).scan("/shows",false,n->{});assertEquals(1,cards.size());assertEquals("/shows/Good.Show",cards.get(0).path);}
 @Test public void loneAmbiguousTeaserMovieIsKeptButRealExtraIsSkipped()throws Exception{Files f=new Files();f.folder("/movies","Film/");f.folder("/movies/Film","A.Teaser.mkv");assertEquals(1,new Library(f,null).scan("/movies",true,n->{}).size());f.folder("/movies/Film","Movie.mkv","Movie-trailer.mkv","Movie.Trailer2.mkv","Movie-featurette-3.mkv","The.Teaser.2019.mkv");assertEquals(2,new Library(f,null).scan("/movies",true,n->{}).size());}
}
