package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;import java.util.*;
public class EpisodeGroupsTest {
    NasClient.Entry episode(String path,int season,int number){NasClient.Entry e=new NasClient.Entry(path,path,false,1);e.season=season;e.episode=number;return e;}
    @Test public void groupsOnlyExistingFilesAndSeparatesUnknownFromSpecials(){List<NasClient.Entry> actual=List.of(episode("/video/unknown.mkv",-1,-1),episode("/video/S02E03.mkv",2,3),episode("/video/special.mkv",0,1),episode("/video/S01E01.mkv",1,1));TreeMap<Integer,List<NasClient.Entry>> groups=EpisodeGroups.of(actual);assertEquals(List.of(0,1,2,-1),new ArrayList<>(groups.keySet()));assertEquals(4,groups.values().stream().mapToInt(List::size).sum());assertEquals(1,groups.get(2).size());assertSame(actual.get(1),groups.get(2).get(0));}
}
