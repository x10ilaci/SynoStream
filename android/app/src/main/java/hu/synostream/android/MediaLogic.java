package hu.synostream.android;

import java.text.Normalizer;
import java.util.*;
import java.util.regex.*;

/** Pure, testable recognition rules. No NAS writes and no per-film exceptions. */
public final class MediaLogic {
    public static boolean extra(String name){return extra(name,false);}
    public static boolean extra(String name,boolean onlyVideo){String value=name.toLowerCase(java.util.Locale.ROOT).trim();if(java.util.Set.of("extras","trailers","featurettes","behind the scenes","deleted scenes","bonus").contains(value))return true;int dot=value.lastIndexOf('.');if(dot>=0&&video(value))value=value.substring(0,dot);else return false;java.util.regex.Matcher match=java.util.regex.Pattern.compile("^(.*)[-.](?:trailer|teaser|featurette)(?:[-. ]?[0-9]{1,2})?$").matcher(value);if(!match.matches())return false;String before=match.group(1);return !onlyVideo||before.split("[. _-]+").length>1;}


    public static final Pattern VIDEO=Pattern.compile("(?i).*\\.(mkv|mp4|avi|m4v|mov|wmv|ts|mts|m2ts|mpg|mpeg|webm)$");
    private static final Pattern NOISE=Pattern.compile("(?i)\\b(?:2160p|1080[pi]|720p|576[pi]|480p|4k|uhd|web[ -]?dl|web[ -]?rip|hdrip|brrip|bdrip|dvdrip|hdtv|blu[ -]?ray|remux|x ?26[45]|h ?26[45]|xvid|divx|hevc|avc|aac|ac3|dts(?:-hd)?|dd ?p? ?\\d ?\\d|atmos|hdr(?:10\\+?)?|10 ?bit|dovi|dolby[ ._-]?vision|S\\d{1,2}(?:E\\d{0,3})?|season\\s*\\d{1,3}|\\d{1,3}\\s*\\.?\\s*(?:évad|evad)|E0*\\d{3,5}(?:[ ._-]*[-–][ ._-]*E?0*\\d{3,5})?)\\b");
    public static final class Name {public final String title,year;public Name(String t,String y){title=t;year=y;}}
    public static boolean video(String name){return VIDEO.matcher(name).matches()&&!sample(name)&&!ignored(name);}
    public static boolean sample(String name){return Pattern.compile("(?i)(?:^|[ ._-])sample(?:[ ._-]|$)").matcher(name).find();}
    public static boolean ignored(String name){String n=name.toLowerCase(Locale.ROOT);return n.startsWith(".")||n.startsWith("@")||Set.of("#recycle","recycler","system volume information","$recycle.bin","lost+found").contains(n);}
    public static String normalize(String value){return Normalizer.normalize(value==null?"":value,Normalizer.Form.NFKD).replaceAll("\\p{M}","").toLowerCase(Locale.ROOT).replaceAll("[^\\p{L}\\p{N}]+"," ").trim().replaceAll("\\s+"," ");}
    public static Name clean(String name,boolean file){
        String value=file?name.replaceFirst("\\.[^.]+$",""):name;
        value=value.replaceAll("\\[[^\\]]*\\]|\\{[^}]*\\}"," ").replaceAll("[._()]"," ");
        Matcher noise=NOISE.matcher(value);boolean technical=noise.find();if(technical){int start=noise.start();Matcher language=Pattern.compile("(?i)\\b(?:hun|eng|multi)\\b").matcher(value);if(language.find()&&language.start()<start&&!value.substring(0,language.start()).replace("-","").trim().isEmpty())start=language.start();if(start>0&&!value.substring(0,start).replace("-","").trim().isEmpty())value=value.substring(0,start);}
        String year=null;Matcher years=Pattern.compile("\\b(19\\d\\d|20[0-2]\\d)\\b").matcher(value);int cut=-1;
        while(years.find())if(!value.substring(0,years.start()).trim().isEmpty()){year=years.group(1);cut=years.start();}
        if(cut>=0)value=value.substring(0,cut);
        value=value.trim().replaceAll("^[ -]+|[ -]+$","").replaceAll("\\s+"," ");
        if(technical)value=value.replaceAll("(?i)\\s+(?:complete|full series|all seasons)$","");
        return new Name(value.isBlank()?name:value,year);
    }
    public static Name movieName(String file,String folder,boolean single){
        Name f=clean(file,true),d=clean(folder,false);
        Set<String> generic=GENERIC;
        boolean collection=normalize(d.title).matches(".*\\b(collection|collections|gyujtemeny|complete|pack)\\b.*");
        if(single&&!generic.contains(normalize(d.title))&&!collection&&d.year!=null&&(f.year==null||f.year.equals(d.year)))return d;
        Matcher tag=Pattern.compile("-([A-Za-z0-9_]{2,30})$").matcher(folder);
        if(tag.find()&&Pattern.compile("^"+Pattern.quote(tag.group(1))+"[-_. ]+",Pattern.CASE_INSENSITIVE).matcher(file).find()){
            Name stripped=clean(file.substring(tag.group(1).length()).replaceFirst("^[-_. ]+",""),true);
            return new Name(stripped.title,stripped.year==null?d.year:stripped.year);
        }
        return f;
    }
    private static final Set<String> GENERIC=Set.of("movie","movies","film","films","filmek","media","video","videos","download","downloads","letoltes","letoltesek","animation","animations","animacio","animacios","animated","cartoons","kids","gyerek","gyerekfilmek","collection","collections","gyujtemeny","pack","complete","pixar","disney","rajzfilmek");
    public static boolean generic(String title){String n=normalize(title);return GENERIC.contains(n)||n.matches(".*\\b(collection|collections|gyujtemeny|pack|complete)\\b.*");}
    public static List<String> titleVariants(String title){LinkedHashSet<String> out=new LinkedHashSet<>();out.add(title.replaceAll("\\s+"," ").trim());if(Pattern.compile("(?i)\\b(?:és|es)\\b").matcher(title).find())for(String connector:List.of("and","et","&",""))out.add(title.replaceAll("(?i)\\b(?:és|es)\\b",connector).replaceAll("\\s+"," ").trim());out.remove("");return new ArrayList<>(out);}
    public static List<Name> aliases(String source,boolean file){List<Name> out=new ArrayList<>();String stem=file?source.replaceFirst("\\.[^.]+$",""):source;Name all=clean(source,file);Matcher m=Pattern.compile("\\(([^()]+)\\)").matcher(stem);if(m.find()){List<String> parts=new ArrayList<>();parts.add(stem.replaceAll("\\([^()]*\\)"," "));m.reset();while(m.find())parts.add(m.group(1));for(String value:parts){if(value.trim().matches("(?i)(?:(?:19|20)\\d{2}|(?:season|évad|evad|saison|temporada)\\s*\\d+)"))continue;Name n=clean(value,false);if(!n.title.isBlank())out.add(new Name(n.title,n.year==null?all.year:n.year));}}if(out.isEmpty())out.add(all);return out;}
    public static double similarity(String query,String title){
        String q=normalize(query),t=normalize(title);if(q.isEmpty()||t.isEmpty())return 0;if(q.equals(t))return 1;
        Set<String> a=tokens(q),b=tokens(t);Set<String> overlap=new HashSet<>(a);overlap.retainAll(b);
        double dice=2.0*overlap.size()/(a.size()+b.size()),characters=characterSimilarity(q,t);
        double score=characters>=.70||dice==1?dice:0;
        if(Math.min(q.length(),t.length())>=7){if(characters>=.90)score=Math.max(score,characters);else if(characters>=.72&&!q.contains(" ")&&!t.contains(" ")&&(q.startsWith(t)||t.startsWith(q)))score=Math.max(score,.80);}
        return score;
    }
    private static Set<String> tokens(String text){Set<String> set=new HashSet<>(Arrays.asList(text.split(" ")));set.removeAll(Set.of("the","a","an","of","and","az","egy"));if(set.isEmpty())set.addAll(Arrays.asList(text.split(" ")));return set;}
    /** Ratcliff/Obershelp matching blocks, as used by the Windows title matcher. */
    public static double characterSimilarity(String a,String b){if(a.isEmpty()&&b.isEmpty())return 1;return 2.0*matching(a,0,a.length(),b,0,b.length())/(a.length()+b.length());}
    private static int matching(String a,int alo,int ahi,String b,int blo,int bhi){int best=0,ai=alo,bj=blo;int[] previous=new int[bhi-blo+1];for(int i=alo;i<ahi;i++){int[] row=new int[previous.length];for(int j=blo;j<bhi;j++)if(a.charAt(i)==b.charAt(j)){int length=previous[j-blo]+1;row[j-blo+1]=length;if(length>best){best=length;ai=i-length+1;bj=j-length+1;}}previous=row;}if(best==0)return 0;return best+matching(a,alo,ai,b,blo,bj)+matching(a,ai+best,ahi,b,bj+best,bhi);}
    public static boolean nearYear(String date,String year){if(year==null)return true;try{return Math.abs(Integer.parseInt(date.substring(0,4))-Integer.parseInt(year))<=1;}catch(Exception e){return false;}}
    public static int[] episode(String filename){Matcher m=Pattern.compile("(?i)S(\\d{1,2})[ ._-]*E(\\d{1,3})").matcher(filename);if(m.find())return new int[]{Integer.parseInt(m.group(1)),Integer.parseInt(m.group(2))};return new int[]{1,0};}
    public static String relative(String root,String path){String r=root.replaceAll("/+$","");return path.equals(r)?".":path.startsWith(r+"/")?path.substring(r.length()+1):null;}
    public static boolean safeRelative(String path){if(path==null||path.isEmpty()||path.length()>2048||path.startsWith("/")||path.contains("\\")||path.contains(":")||Pattern.compile("[\\x00-\\x1f]").matcher(path).find())return false;for(String p:path.split("/"))if(p.equals("..")||p.equalsIgnoreCase(".synostream")||p.isEmpty()||p.equals(".")&&!path.equals("."))return false;return true;}
}
