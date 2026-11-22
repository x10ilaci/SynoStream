# Ellenőrzés – SynoStream Android 0.5.24

A build_release.ps1 a testReleaseUnitTest, lintRelease és assembleRelease feladatokat futtatja. 632 release JVM-teszt sikeres; lint 0 hiba, 17 korábbi figyelmeztetés.

Az elkészült APK tényleges manifestjét és aláírását a verify_release.py ellenőrzi: application_id hu.synostream.android, versionCode 29, versionName 0.5.24, debuggable=false, testOnly=false. Az aláírás érvényes és egyezik a korábbi telepítések tanúsítványával. A 0.5.23 debug APK elutasításával az ellenőrzés negatív ága is tesztelt.

A tanúsítvány történeti neve Android Debug; a kulcsot a kompatibilis frissítéshez tartjuk meg. Ez nem teszi hibakereshetővé a release változatot. Nincs új privát kulcs a nyilvános csomagban, és nincs kulcscsere.

A publish_android.py minden feltöltés előtt újra lefuttatja az APK-ellenőrzést, összeveti a feed metaadatait és SHA256-értékét, majd ellenőrzi az összes mellékletet. Android-kiadás nem válthatja le a Windows latest kiadást.

API 36 emulátoron a 0.5.23 debug változat fölé telepítettük a 0.5.24 release APK-t. A privát tesztadat megmaradt, a versionCode 28-ról 29-re nőtt, a run-as az új csomagot helyesen visszautasította mint nem hibakereshető alkalmazást. A telepített APK visszaolvasva byte-ra egyezik a kiadási fájllal.

A Google Play Protect minősítése ettől külön áll. A release build és a sikeres tesztek nem garantálják a korábbi tiltás megszűnését. Fizikai telefonos Play Protect-próba nem történt.
