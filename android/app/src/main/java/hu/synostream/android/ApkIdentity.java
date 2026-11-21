package hu.synostream.android;
import android.content.*;import android.content.pm.*;import android.os.*;import java.io.*;import java.util.*;
final class ApkIdentity {
 @SuppressWarnings("deprecation") static Set<String> certificates(PackageInfo info)throws Exception{Set<String> values=new HashSet<>();Signature[] signatures=Build.VERSION.SDK_INT>=28&&info.signingInfo!=null?info.signingInfo.getApkContentsSigners():info.signatures;if(signatures!=null)for(Signature s:signatures)values.add(AppRelease.digest(s.toByteArray()));return values;}
 @SuppressWarnings("deprecation") static void verify(Context c,File file,AppRelease release)throws Exception{
  release.verify(file);PackageManager pm=c.getPackageManager();int flags=Build.VERSION.SDK_INT>=28?PackageManager.GET_SIGNING_CERTIFICATES:PackageManager.GET_SIGNATURES;
  PackageInfo installed=pm.getPackageInfo(c.getPackageName(),flags),apk=pm.getPackageArchiveInfo(file.getAbsolutePath(),flags);long current=Build.VERSION.SDK_INT>=28?installed.getLongVersionCode():installed.versionCode;
  if(apk==null||apk.applicationInfo==null||apk.applicationInfo.minSdkVersion>Build.VERSION.SDK_INT||apk.applicationInfo.minSdkVersion!=release.minSdk||!c.getPackageName().equals(apk.packageName)||!release.version.equals(apk.versionName)||(Build.VERSION.SDK_INT>=28?apk.getLongVersionCode():apk.versionCode)!=release.code||release.code<=current||!release.newer(current,Build.VERSION.SDK_INT))throw new IOException("Invalid APK identity/version");
  Set<String> own=certificates(installed),other=certificates(apk);if(own.isEmpty()||!own.equals(other)||!own.contains(release.certificate))throw new IOException("APK signature differs");
 }
}
