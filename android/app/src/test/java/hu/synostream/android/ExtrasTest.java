package hu.synostream.android;
import org.junit.Test;import static org.junit.Assert.*;
public class ExtrasTest {
 @Test public void preciseExtraNamesDoNotHideRealTitles(){for(String name:new String[]{"Extras","TRAILERS","featurettes","behind the scenes","deleted scenes","bonus","Film-trailer.mkv","Film.trailer2.mp4","Film-teaser-1.mov","Film-featurette.mkv"})assertTrue(name,MediaLogic.extra(name));for(String name:new String[]{"Trailer Park Boys","Trailer Park Boys.mkv","A Bonus Film.mkv","Extras.mkv","Featurette Story.mkv","Film-trailer-story.mkv"})assertFalse(name,MediaLogic.extra(name));}
 @Test public void yearsAreNeverTrailerSequenceNumbers(){assertFalse(MediaLogic.extra("The.Teaser.2019.mkv"));assertFalse(MediaLogic.extra("A.Featurette.2020.mkv"));for(String name:new String[]{"Movie-trailer.mkv","Movie.Trailer2.mkv","Movie-featurette-3.mkv","Movie.trailer.12.mkv"})assertTrue(name,MediaLogic.extra(name));assertFalse(MediaLogic.extra("Trailer Park Boys"));assertFalse(MediaLogic.extra("Movie.trailer.123.mkv"));}
 @Test public void ambiguousOneWordPrefixIsKeptWhenOnlyVideo(){assertFalse(MediaLogic.extra("Movie-trailer.mkv",true));assertFalse(MediaLogic.extra("A.Teaser.mkv",true));assertTrue(MediaLogic.extra("Movie-trailer.mkv",false));assertTrue(MediaLogic.extra("A.Movie-trailer.mkv",true));}
}
