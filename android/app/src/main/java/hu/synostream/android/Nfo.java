package hu.synostream.android;

import java.io.*;
import java.nio.*;
import java.nio.charset.*;
import java.util.*;
import java.util.regex.*;
import javax.xml.parsers.*;
import org.w3c.dom.*;
import org.xml.sax.*;

/** Bounded sidecar parsing; follows the Windows parser, without external XML IO. */
public final class Nfo {
    public static final int MAX_BYTES=1024*1024;
    public static final class Hint {
        public final List<String> titles=new ArrayList<>();
        public String year=null,imdb=null;public Long tmdb=null;
    }
    public static String decode(byte[] bytes){
        if(bytes.length>MAX_BYTES)return "";
        List<String> encodings=bytes.length>=2&&((bytes[0]==(byte)0xff&&bytes[1]==(byte)0xfe)||(bytes[0]==(byte)0xfe&&bytes[1]==(byte)0xff))?List.of("UTF-16"):List.of("UTF-8","windows-1250","IBM437");
        for(String encoding:encodings)try{return Charset.forName(encoding).newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString().replaceFirst("^\ufeff","");}catch(Exception ignored){}
        return "";
    }
    private static String tag(Node node){String value=node.getLocalName();return (value==null?node.getNodeName():value).toLowerCase(Locale.ROOT);}
    public static Hint parse(byte[] bytes,boolean movie){
        Hint hint=new Hint();String text=decode(bytes);
        if(text.isEmpty()||Pattern.compile("(?i)<!\\s*(doctype|entity)").matcher(text).find())return hint;
        Set<String> imdb=new LinkedHashSet<>(),years=new LinkedHashSet<>();Set<Long> tmdb=new LinkedHashSet<>();List<String> titles=new ArrayList<>();
        Document document=null;
        try{
            DocumentBuilderFactory factory=DocumentBuilderFactory.newInstance();factory.setNamespaceAware(true);factory.setExpandEntityReferences(false);
            try{factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);}catch(ParserConfigurationException ignored){}
            try{factory.setFeature("http://xml.org/sax/features/external-general-entities",false);factory.setFeature("http://xml.org/sax/features/external-parameter-entities",false);}catch(ParserConfigurationException ignored){}
            DocumentBuilder builder=factory.newDocumentBuilder();
            builder.setEntityResolver((publicId,systemId)->new InputSource(new StringReader("")));
            builder.setErrorHandler(new org.xml.sax.helpers.DefaultHandler());
            document=builder.parse(new InputSource(new StringReader(text.trim())));
        }catch(Exception invalidXml){/* Text release NFOs are expected as well. */}
        if(document!=null){
            Element root=document.getDocumentElement();String type=tag(root);
            if(type.equals("episodedetails")||(type.equals("movie")||type.equals("tvshow"))&&type.equals("movie")!=movie)return hint;
            NodeList nodes=root.getElementsByTagName("*");
            for(int i=0;i<nodes.getLength();i++){
                Element e=(Element)nodes.item(i);String name=tag(e),value=e.getTextContent().trim();
                if((name.equals("title")||name.equals("originaltitle"))&&e.getParentNode()==root)titles.add(value);
                else if(name.equals("year"))years.add(value);
                else if(name.equals("uniqueid")){
                    if(e.getAttribute("type").equalsIgnoreCase("tmdb"))addId(tmdb,value);
                    if(e.getAttribute("type").equalsIgnoreCase("imdb")&&value.matches("(?i)tt\\d{7,10}"))imdb.add(value.toLowerCase(Locale.ROOT));
                }else if(name.equals("tmdbid"))addId(tmdb,value);
                else if((name.equals("imdbid")||name.equals("id"))&&value.matches("(?i)tt\\d{7,10}"))imdb.add(value.toLowerCase(Locale.ROOT));
            }
        }else{
            Matcher labels=Pattern.compile("(?im)^\\s*[|\\[\\]* ._-]*(original\\s*title|movie\\s*title|title|cím|cim|eredeti\\s*cím|eredeti\\s*cim|year|év|ev)\\s*[:=]\\s*(.+?)\\s*$").matcher(text);
            while(labels.find()){
                String label=labels.group(1).toLowerCase(Locale.ROOT),value=labels.group(2).replaceAll("^[ |\\[\\]]+|[ |\\[\\]]+$","");
                if(Set.of("year","év","ev").contains(label))years.add(value);else titles.add(value);
            }
        }
        if(imdb.isEmpty()){Matcher ids=Pattern.compile("(?i)\\btt\\d{7,10}\\b").matcher(text);while(ids.find())imdb.add(ids.group().toLowerCase(Locale.ROOT));}
        if(tmdb.isEmpty()){
            Matcher ids=Pattern.compile("(?i)(?:themoviedb\\.org|tmdb\\.org)/(movie|tv)/(\\d+)").matcher(text);
            while(ids.find())if(ids.group(1).equalsIgnoreCase(movie?"movie":"tv"))addId(tmdb,ids.group(2));
        }
        if(imdb.size()==1)hint.imdb=imdb.iterator().next();if(tmdb.size()==1)hint.tmdb=tmdb.iterator().next();
        for(String title:new LinkedHashSet<>(titles))if(!title.isEmpty()&&title.length()<=500&&!Pattern.compile("[\\x00-\\x1f]").matcher(title).find()&&hint.titles.size()<2)hint.titles.add(title);
        years.removeIf(y->!y.matches("(?:18|19|20|21)\\d{2}"));if(years.size()==1)hint.year=years.iterator().next();
        return hint;
    }
    private static void addId(Set<Long> ids,String value){if(value.matches("[1-9]\\d{0,9}"))try{ids.add(Long.parseLong(value));}catch(NumberFormatException ignored){}}
    public static NasClient.Entry select(List<NasClient.Entry> siblings,String media,boolean movie){
        List<NasClient.Entry> nfos=new ArrayList<>();int videos=0;
        for(NasClient.Entry e:siblings)if(!e.directory){if(e.name.toLowerCase(Locale.ROOT).endsWith(".nfo"))nfos.add(e);if(MediaLogic.video(e.name))videos++;}
        String stem=movie?media.replaceFirst("\\.[^.]+$",""):media;
        List<NasClient.Entry> exact=new ArrayList<>();for(NasClient.Entry e:nfos)if(e.name.equalsIgnoreCase(stem+".nfo"))exact.add(e);
        if(!exact.isEmpty())return exact.size()==1?exact.get(0):null;
        if(!movie||videos==1){
            List<NasClient.Entry> standard=new ArrayList<>();for(NasClient.Entry e:nfos)if(e.name.equalsIgnoreCase(movie?"movie.nfo":"tvshow.nfo"))standard.add(e);
            if(!standard.isEmpty())return standard.size()==1?standard.get(0):null;
            if(nfos.size()==1)return nfos.get(0);
        }
        return null;
    }
}
