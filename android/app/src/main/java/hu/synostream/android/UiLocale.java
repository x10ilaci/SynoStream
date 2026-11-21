package hu.synostream.android;
import android.content.*;import android.content.res.Configuration;import android.os.LocaleList;import java.util.Locale;
final class UiLocale {
 // Remember installation origin, never an automatically selected language. Application seeds library keys on startup.
 private static final String EXISTING_INSTALL="ui_existing_install";
 static synchronized void initialize(Context c){SharedPreferences prefs=c.getSharedPreferences("synostream",Context.MODE_PRIVATE);if(!prefs.contains(EXISTING_INSTALL)){boolean existing=!prefs.getAll().isEmpty();prefs.edit().putBoolean(EXISTING_INSTALL,existing).apply();}}
 static String language(Context c){SharedPreferences prefs=c.getSharedPreferences("synostream",Context.MODE_PRIVATE);if(prefs.contains("ui_language"))return UiLanguage.normalize(prefs.getString("ui_language",null));initialize(c);String systemLanguage=android.content.res.Resources.getSystem().getConfiguration().getLocales().get(0).getLanguage();return UiLanguage.initial(prefs.getBoolean(EXISTING_INSTALL,true),systemLanguage);}
 static Context wrap(Context c){Configuration config=new Configuration(c.getResources().getConfiguration());Locale language=Locale.forLanguageTag(language(c));config.setLocale(language);config.setLocales(new LocaleList(language));config.setLayoutDirection(language);return c.createConfigurationContext(config);}
 static boolean save(Context c,String value){return c.getSharedPreferences("synostream",Context.MODE_PRIVATE).edit().putString("ui_language",UiLanguage.normalize(value)).commit();}
 private UiLocale(){}
}
