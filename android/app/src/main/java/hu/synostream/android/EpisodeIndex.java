package hu.synostream.android;

import java.util.*;
import java.util.regex.*;

/** Episode ordering compatible with SxxExx, Hungarian seasons and absolute packs. */
public final class EpisodeIndex {
    private static final Pattern RANGE=Pattern.compile("(?i)(?:^|[^a-z0-9])E0*(\\d{3,5})[ ._-]*[-–][ ._-]*E?0*(\\d{3,5})(?=$|[^0-9])");
    public static final class Position {public final int season,episode;public final boolean explicit;Position(int s,int e,boolean x){season=s;episode=e;explicit=x;}}
    public static final class Range {public final String scope;public final int first,last;Range(String s,int f,int l){scope=s;first=f;last=l;}}
    private static Matcher match(String pattern,String text){Matcher m=Pattern.compile(pattern,Pattern.CASE_INSENSITIVE|Pattern.UNICODE_CASE).matcher(text);return m.find()?m:null;}
    private static Integer season(String text){
        for(String pattern:List.of("\\bseason[ ._-]*0*(\\d{1,3})(?!\\d)","(?<!\\d)0*(\\d{1,3})\\s*\\.?\\s*(?:évad|evad)\\b")){
            Matcher m=match(pattern,text);if(m!=null)return Integer.parseInt(m.group(1));
        }
        Matcher m=match("\\b(?:évad|evad)[ ._-]*0*(\\d{1,3})(?!\\d)",text);
        if(m==null)return null;String rest=text.substring(m.end());
        if(match("^\\s*\\.?\\s*(?:rész|resz|epizód|epizod)\\b",rest)!=null&&match("^\\s*\\.?\\s*(?:rész|resz|epizód|epizod)\\s*0*\\d{1,4}(?!\\d)",rest)==null)return null;
        return Integer.parseInt(m.group(1));
    }
    public static Range range(String path){
        String[] parts=path.replace('\\','/').split("/");if(parts.length==0)return null;
        for(int i=parts.length-1;i>=0;i--){String name=i==parts.length-1?parts[i].replaceFirst("\\.[^.]+$",""):parts[i];Matcher m=RANGE.matcher(name);if(m.find()){int end=i==parts.length-1?i:i+1;String scope=String.join("/",Arrays.copyOfRange(parts,0,end)).toLowerCase(Locale.ROOT);return new Range(scope.isEmpty()?".":scope,Integer.parseInt(m.group(1)),Integer.parseInt(m.group(2)));}}
        return null;
    }
    public static Position parse(String path){
        String normalized=path.replace('\\','/');String[] parts=normalized.split("/");String filename=(parts.length==0?normalized:parts[parts.length-1]).replaceFirst("\\.[^.]+$","");
        int season=1;boolean explicitSeason=false;
        for(int i=0;i<parts.length-1;i++){Integer value=season(parts[i]);if(value!=null){season=value;explicitSeason=true;continue;}Matcher m=match("(?:^|[^a-z])S[ ._-]*0*(\\d{1,2})(?:[^0-9]|$)",parts[i]);if(m!=null){season=Integer.parseInt(m.group(1));explicitSeason=true;}}
        Integer inline=season(filename);if(inline!=null){season=inline;explicitSeason=true;}
        Matcher m=RANGE.matcher(filename);
        if(m.find()){Matcher sm=match("(?:^|[^a-z0-9])S[ ._-]*0*(\\d{1,2})[ ._-]*E",filename);return new Position(sm==null?season:Integer.parseInt(sm.group(1)),0,false);}
        Range range=range(path);
        if(range!=null){
            m=match("(?:^|[^a-z0-9])(?:EPISODE|EP|E)[ ._-]*0*(\\d{1,5})(?!\\d)",filename);
            if(m!=null){int number=Integer.parseInt(m.group(1));if(number>=range.first&&number<=range.last)return new Position(season,number,true);if(number>=1&&number<=range.last-range.first+1)return new Position(season,range.first+number-1,true);}
            if(filename.trim().matches("\\d{1,4}")){int number=Integer.parseInt(filename.trim());if(number>=1&&number<=range.last-range.first+1)return new Position(season,range.first+number-1,true);}
        }
        m=match("S[ ._-]*0*(\\d{1,2})[ ._-]*E[ ._-]*0*(\\d{1,5})",normalized);if(m!=null)return new Position(Integer.parseInt(m.group(1)),Integer.parseInt(m.group(2)),true);
        m=match("(?:^|[^a-z0-9])E(\\d{5,})(?!\\d)",filename);if(m!=null)return new Position(season,Integer.parseInt(m.group(1)),true);
        m=match("(?<![A-Za-z0-9])(\\d{1,2})\\s*x\\s*0*(\\d{1,3})(?!\\d)",normalized);if(m!=null)return new Position(Integer.parseInt(m.group(1)),Integer.parseInt(m.group(2)),true);
        m=match("(?:^|[^a-z])E(\\d{3,4})(?=$|[^0-9])",normalized);
        if(m!=null&&!normalized.substring(m.end()).matches("(?i)^[pi]\\b.*")){
            String digits=m.group(1);if(digits.length()==3&&digits.charAt(0)<='6'&&!explicitSeason)return new Position(1,Integer.parseInt(digits),true);
            int number=Integer.parseInt(digits.substring(digits.length()-2)),s=explicitSeason?season:Integer.parseInt(digits.substring(0,digits.length()-2));
            if(s>0&&number>0)return new Position(s,number,true);
        }
        m=match("(?:^|[^a-z])(?:E|EP|EPISODE|RÉSZ)[ ._-]*0*(\\d{1,4})(?!\\d)(?![pi]\\b)",filename);if(m!=null)return new Position(season,Integer.parseInt(m.group(1)),true);
        if(filename.trim().matches("\\d{1,3}")&&Integer.parseInt(filename.trim())>0)return new Position(season,Integer.parseInt(filename.trim()),true);
        m=match("^\\s*0*(\\d{1,3})\\s*[-–.]\\s*",filename);if(m!=null&&Integer.parseInt(m.group(1))>0)return new Position(season,Integer.parseInt(m.group(1)),true);
        m=match("(?<!\\d)[ ._-]0*(\\d{2,3})$",filename);
        if(m!=null&&inline==null&&!(parts.length>1&&MediaLogic.normalize(parts[parts.length-2]).equals(MediaLogic.normalize(filename)))&&Integer.parseInt(m.group(1))>0)return new Position(season,Integer.parseInt(m.group(1)),true);
        m=match("(?<!\\d)0*(\\d{1,4})\\s*\\.?\\s*(?:rész|resz|epizód|epizod)\\b",filename);if(m!=null)return new Position(season,Integer.parseInt(m.group(1)),true);
        m=match("(?<!\\d)[–-]\\s*0*(\\d{1,3})(?=\\s*(?:$|[\\[({]))",filename);if(m!=null)return new Position(season,Integer.parseInt(m.group(1)),true);
        return new Position(season,0,false);
    }
    public static final class Item {
        public final NasClient.Entry file;public final int season,episode;public final boolean explicit;
        Item(NasClient.Entry f,int s,int e,boolean x){file=f;season=s;episode=e;explicit=x;}
        public String label(){return String.format(Locale.ROOT,"S%02dE%02d  •  %s",season,episode,file.name);}
    }
    public static List<Item> build(List<NasClient.Entry> files,String root){
        List<NasClient.Entry> sorted=new ArrayList<>(files);sorted.sort(Comparator.comparing(e->e.path));
        Map<String,Position> positions=new HashMap<>();Map<Integer,Set<Integer>> used=new HashMap<>();
        for(NasClient.Entry file:sorted){String relative=MediaLogic.relative(root,file.path);Position p=parse(relative==null?file.path:relative);positions.put(file.path,p);if(p.explicit)used.computeIfAbsent(p.season,k->new HashSet<>()).add(p.episode);}
        Map<String,Integer> next=new HashMap<>();List<Item> out=new ArrayList<>();
        for(NasClient.Entry file:sorted){Position p=positions.get(file.path);int episode=p.episode;if(!p.explicit){
            String relative=MediaLogic.relative(root,file.path);Range range=range(relative==null?file.path:relative);String scope=p.season+":"+(range==null?"":range.scope);
            episode=next.getOrDefault(scope,range==null?1:range.first);Set<Integer> numbers=used.computeIfAbsent(p.season,k->new HashSet<>());while(numbers.contains(episode))episode++;numbers.add(episode);next.put(scope,episode+1);
        }out.add(new Item(file,p.season,episode,p.explicit));}
        out.sort(Comparator.comparingInt((Item i)->i.season).thenComparingInt(i->i.episode).thenComparing(i->i.file.path));return out;
    }
    public static String groupTitle(String name,boolean file){
        String stem=file?name.replaceFirst("\\.[^.]+$",""):name;
        List<String> patterns=List.of("(?:^|[\\W_])S\\d{1,2}(?:[\\W_]*E\\d{1,3})?(?=$|[\\W_])","(?:^|[\\W_])E0*\\d{3,5}(?:[\\W_]*[-–][\\W_]*E?0*\\d{3,5})?(?=$|[\\W_])","(?:^|[\\W_])\\d{1,2}x\\d{1,3}(?=$|[\\W_])","(?:^|[\\W_])(?:season|évad|evad|saison|temporada|сезон)[\\W_]*\\d{1,3}(?=$|[\\W_])","(?:^|[\\W_])\\d{1,3}\\.?[\\W_]*(?:season|évad|evad|saison|temporada|сезон)(?=$|[\\W_])","(?:^|[\\W_])\\d{1,4}\\.?[\\W_]*(?:rész|resz|epizód|epizod)(?=$|[\\W_])","(?:^|[\\W_])[-–]\\s*\\d{1,3}(?=$|[\\W_])");
        Matcher first=null;for(String pattern:patterns){Matcher m=match(pattern,stem);if(m!=null&&(first==null||m.start()<first.start()))first=m;}
        if(first==null)return null;
        String before=stem.substring(0,first.start()).replaceAll("^[ ._\\-\\[\\](){}]+|[ ._\\-\\[\\](){}]+$",""),after=stem.substring(first.end()).replaceAll("^[ ._\\-\\[\\](){}]+|[ ._\\-\\[\\](){}]+$","");
        String title=MediaLogic.clean(before.isEmpty()?after:before,false).title.trim();return title.isEmpty()?null:title;
    }
}
