# Claude-javaslatok javítása – kiadás nélküli munkapéldány

A javításokból Windows 1.106 és Android 0.5.23 / versionCode 28 kiadás készül. A tesztek és csomagellenőrzések után külön Windows- és Android-csatornán publikáljuk. Valódi NAS-on nem történt módosítás. A korábban kiadott mappák és a v1.54 érintetlenek.

## Windows

- W1: QuickConnect ID és régió szigorú ellenőrzése, ellenőrzött HTTPS-relaycím, a diagnosztikai útvonalon is. Hibás ID-val nincs hálózati kérés; hibás resolver-régióval nincs NAS-kérés. A konfiguráció betöltése a hibás ID-t üríti és jelzi; mentés/visszaállítás elutasítja.
- W2: sample-ellenőrzés csak a fájlnéven és a kártyagyökér ALATTI mappakomponenseken. A médiatár és a kártya saját neve nem kizáró ok. A szóhatáros egyezés mellé egy konzervatív címvédelem került: a Sample szóval kezdődő, további címszót tartalmazó név nem önmagában mintajelzés. Így a Sample Size cím sem vész el; a Show.sample és az önálló sample.mkv továbbra is minta.
- W3: önálló S02 a fájlnévben és háromjegyű évadok, S100E01.
- W4: évszám 1900..aktuális év+2; a távolabbi szám a cím része marad.
- W5: MPV letöltés, ellenőrzés és kicsomagolás QThreadben. Elkülönített ideiglenes telepítés, teljes könyvtárcsere, hibánál visszaállítás. Nincs régi DLL-ekre másolás. ADS/kilépő útvonal és link tiltott. A beállításmentés hibája látható. A zárolt régi .old-* könyvtár megmaradhat; az új telepítés ettől teljes.
- W6: aktuális diagnosztikai szöveg, hiányzó SID esetén nincs mappalista/kijelentkezési kérés.
- W7: API.Info szerinti végpont; a stream hálózati várakozása nem tartja a közös zárat; magyar nem-JSON hiba. A biztonságos olvasás kapcsolatváltási lehetősége megmarad.
- W8: DSM 403 után a NAS-kapcsolati ablak egyszer használatos kódot kér. Nincs kódmentés vagy automatikus hálózati újraküldés ugyanazzal a kóddal.
- W9: kimaradt, nincs aláírási/kulcskezelési átállítás.
- A kivételkezelés 32 eredeti helyének táblázata a KIVETELEK_ATVIZSGALASA.md fájlban. 16 szándékos kezelés változatlan, 16 hibaelnyelő hely statikus, titokmentes figyelmeztetést kapott.

## Android

- A1: azonos, kártyagyökérhez viszonyított sample-szabály.
- A2: külön párosításmentési zár; a hálózati olvasás/feltöltés nem a kliens közös monitorában történik. A már ismert eseményekhez tulajdonos-, méret- és időbélyeg szerinti PairingReadCache használata. Az elsőként látott UUID-esemény tartalmát el kell olvasni, mert a fájlnév nem tartalmaz médiaazonosítót vagy generációt. Ismeretlen időbélyegnél továbbra is újraolvas, a helyesség érdekében. A gyorsítótár meglévő méretkorlátja megmaradt.
- A3: stream és párosításfeltöltés csak akkor jelentkezik újra, ha a hibás kéréshez használt SID még aktuális. Párhuzamos stream/stream és stream/upload teszt bizonyítja az egyszeri megújítást.
- A4: a HTTP és a manifest változatlan. Nyilvános HTTP-végpontnál egyszer elfogadható figyelmeztetés; elutasítás után nincs kapcsolódás. Az elfogadás végpontonként megmarad. Az SSL-hibaüzenet a HTTPS-cím/port/tanúsítvány ellenőrzését kéri, nem ajánl nyilvános HTTP-t.
- A5: előzetes hiba és biztos NAS-elutasítás: a törlés nem indult el. Bizonytalan, elküldött kérés: külön bizonytalansági üzenet és nincs ismétlés. InterruptedException továbbadása megtartott megszakításjelzővel. A lecserélt kliensen való továbbítás is megőrzi a helyes hibakategóriát.
- A6: fizikai útvonalak záró perjele normalizált; a teljes fizikai hely ellenőrzése változatlanul szigorú.
- A7: a beolvasó worker normál/hiba/megszakítás ága finally-kezelést kapott már korábban; a munkamenetváltás és a cancel a tervezőt visszaállítja. Az elutasított executor-feladat új, külön takarítási ágat kapott, így nem marad beragadt running/busy állapot. Új lejátszás szándékosan érvényteleníti az előző URL-t; a token és útvonal most egyetlen immutable StreamIdentity pillanatképben cserélődik. A manifest octet-stream szűrője megmaradt: számos torrentfájl-szolgáltató ezzel a MIME-típussal ad át fájlt, a tartalomellenőrzés továbbra is kötelező.
- Fake NAS és memóriabeli fájlrendszer vizsgálja a változott listát, a második törlési köteg hibáját, megszakítást és a nem ismételt bizonytalan írást.

## Végső ellenőrzés

Windows: py -3.13 -m pytest -q → 813 sikeres, 6 feltételes kihagyás; egy meglévő, szándékos duplikált ZIP-tag tesztfigyelmeztetés.
Android: testDebugUnitTest → 632 sikeres, 0 hiba. lintDebug → 0 hiba, 17 korábbi figyelmeztetés.
A védett Android-modulok, manifest, SDK, függőségek, aláírás és verziók változatlanok. A 20 fájlt érintő változatlansági ellenőrzés sikeres.

A javítások regressziós ellenőrzése forrásszinten történt. Új emulátoros/fizikai telefonos kör, valódi DSM-OTP, valódi NAS-törlés és élő MPV-letöltés nem történt. A Windows Qt-worker és mentési hibajelzés helyi, offscreen tesztben ellenőrzött; a hálózati regressziók kizárólag mock/fake végpontokat használnak.
