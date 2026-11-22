# Ellenőrzés – SynoStream Android 0.5.23

632 JVM-regressziós teszt sikeres, 0 hiba. lintDebug: 0 hiba, 17 korábbi figyelmeztetés. A fordítás és az APK-aláírás ellenőrzése sikeres; az aláíró tanúsítvány egyezik a korábbi kiadásokéval.

A javítások mock/fake NAS-on vizsgálják a párhuzamos munkamenet-megújítást, a párosítási olvasás alatti párhuzamos lekérést, az esemény-cache-t, a sample-szabályokat, az útvonalellenőrzést, a törlési hibakategóriákat és a részleges/megszakított törlést.

A manifest, SDK, függőségek és az aláírási konfiguráció változatlan. Az app/build.gradle kizárólag versionCode 28 / versionName 0.5.23 értékekben változott. A védett felismerési/cache/frissítési modulok változatlanok.

API 36 emulátoron a telepítés, az indulás és a NAS nélküli demó megnyitása sikeres; nem volt alkalmazásösszeomlás. A hidegindításkor megakadt Android System UI a Várakozás után helyreállt; ez nem a SynoStream folyamata. A telepített és visszaolvasott APK byte-ra egyezik a kiadott APK-val. A korábbi 0.5.22 teljes, 125 esetből álló emulátoros körét erre a verzióra nem ismételtük meg. Fizikai telefonon, valódi DSM-OTP-val vagy NAS-törléssel nem teszteltük. Valódi NAS-adatot nem módosítottunk.
