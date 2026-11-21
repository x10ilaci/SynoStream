package hu.synostream.android;

import android.content.*;
import android.security.keystore.*;
import android.util.Base64;
import org.json.*;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;
import java.security.KeyStore;
import java.nio.charset.StandardCharsets;

/** Secrets are encrypted with a device-bound Android Keystore key, never shipped. */
public final class Store implements NasProfile.Storage {
    private final android.content.SharedPreferences prefs;
    public Store(Context c){prefs=c.getSharedPreferences("synostream",Context.MODE_PRIVATE);}
    private javax.crypto.SecretKey key() throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
        if(!store.containsAlias("SynoStream.Secrets")){
            KeyGenerator g=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
            g.init(new KeyGenParameterSpec.Builder("SynoStream.Secrets",KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());g.generateKey();
        }
        return (javax.crypto.SecretKey)store.getKey("SynoStream.Secrets",null);
    }
    public void secret(String name,String value) throws Exception {Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());String result=Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(cipher.doFinal(value.getBytes(StandardCharsets.UTF_8)),Base64.NO_WRAP);if(!prefs.edit().putString(name,result).commit())throw new java.io.IOException("A beállítás mentése nem sikerült.");}
    public String secret(String name) throws Exception {String value=prefs.getString(name,"");if(value.isEmpty())return "";String[] parts=value.split(":",2);Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(parts[0],Base64.NO_WRAP)));return new String(cipher.doFinal(Base64.decode(parts[1],Base64.NO_WRAP)),StandardCharsets.UTF_8);}
    public void forget(String name){prefs.edit().remove(name).apply();}
    public String get(String name,String fallback){return prefs.getString(name,fallback);}
    public void put(String name,String value){prefs.edit().putString(name,value).apply();}
    @Override public void durable(String name,String value){if(!prefs.edit().putString(name,value).commit())throw new IllegalStateException("A torrentművelet állapota nem menthető. Letöltés nem indult.");}
    @Override public void replaceBrokenProfile(String recovered)throws Exception{if(!prefs.edit().putString("nas_profile_recovery",recovered).remove("nas_profile").commit())throw new java.io.IOException("A beállítás mentése nem sikerült.");}
    public void saveCredentials(NasClient.Credentials c,boolean remember) throws Exception {saveProfile(NasProfile.load(this).routes(c),c,remember);}
    void saveProfile(NasProfile profile,NasClient.Credentials c,boolean remember)throws Exception{
        String encrypted="";if(remember){Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());encrypted=Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(cipher.doFinal(c.password.getBytes(StandardCharsets.UTF_8)),Base64.NO_WRAP);}
        android.content.SharedPreferences.Editor edit=prefs.edit().remove("nas_profile_recovery").putString("nas_profile",profile.json(c.user).toString()).putString("address",c.address).putString("local",c.local).putString("ddns",c.ddns).putString("quick",c.quick).putString("user",c.user);
        if(remember)edit.putString("password",encrypted);else edit.remove("password");
        if(!edit.commit())throw new java.io.IOException("A beállítás mentése nem sikerült.");
    }
    public NasClient.Credentials credentials() throws Exception{NasProfile p=NasProfile.load(this);return new NasClient.Credentials(p.address,p.local,p.ddns,p.quick,get("user",""),secret("password"),"");}
    public JSONArray libraries(){try{return new JSONArray(get("libraries","[]"));}catch(Exception e){return new JSONArray();}}
    public void libraries(JSONArray a){put("libraries",a.toString());}
}
