package hu.synostream.android;
import java.util.*;
/** Group only actual playable NAS entries; unknown numbering is kept separate from season zero. */
public final class EpisodeGroups {
    private EpisodeGroups(){}
    public static TreeMap<Integer,List<NasClient.Entry>> of(List<NasClient.Entry> entries){TreeMap<Integer,List<NasClient.Entry>> groups=new TreeMap<>(Comparator.comparingInt(n->n<0?Integer.MAX_VALUE:n));for(NasClient.Entry e:entries)groups.computeIfAbsent(e.season,n->new ArrayList<>()).add(e);return groups;}
}
