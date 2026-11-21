package hu.synostream.android;
/** Stable preference independent of NAS accounts and metadata language. */
final class UiLanguage {static String initial(boolean existingInstall,String systemLanguage){return existingInstall||"hu".equals(systemLanguage)?"hu":"en";}static String normalize(String value){return "en".equals(value)?"en":"hu";}private UiLanguage(){}}
