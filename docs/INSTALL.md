# Telepítés és első beállítás

[Vissza a főoldalra](../README.md) · [Gyakori kérdések](FAQ.md)

## Windows

**Windows 10 / 11, 64 bites rendszer szükséges.** A kész EXE használatához Python telepítése nem kell.

1. [Töltsd le a Windows ZIP-csomagot](https://github.com/x10ilaci/SynoStream/releases/download/v1.107/SynoStream_1.107_Windows_x64.zip).
2. Csomagold ki egy saját, írható mappába. A csomag a futtatható program mellett a licenceket és a szükséges tájékoztatókat is tartalmazza.
3. Indítsd el a `SynoStream_1.107.exe` fájlt.
4. A Beállításokban válaszd ki a nyelvet, állítsd be a médiatárakat, és igény szerint add meg a TMDB API-kulcsot.

Az MPV-t szükség esetén a program tölti le. Meglévő MPV elérési útja is megadható. Az MPV lejátszási beállításai a SynoStream Beállítások részében érhetők el.

### Helyi médiatár

A médiatár forrásmappáinál tallózd be a filmeket vagy sorozatokat tartalmazó mappát. Hálózati meghajtó is választható. A forrásokat a **Beállítások → Médiatár és adatok → Forrásmappák** részben kezelheted.

## Android

**Android 8.0 vagy újabb rendszer és egy videólejátszó alkalmazás szükséges.** Az Android-változat a NAS-on tárolt médiatárhoz kapcsolódik.

1. [Töltsd le az Android APK-t](https://github.com/x10ilaci/SynoStream/releases/download/android-v0.5.25/SynoStream_Android_0.5.25.apk).
2. Nyisd meg a letöltött fájlt. Ha Android külön engedélyt kér az adott forrásból való telepítéshez, azt az általad választott böngészőnek vagy telepítőnek adhatod meg.
3. Nyisd meg a SynoStreamet, és állítsd be a NAS-kapcsolatot.
4. Válaszd ki a médiatár mappáját. Lejátszáskor választhatsz a telefon videólejátszói közül.

A nyilvános Android release kiadásban a saját médiatárhoz NAS-kapcsolat szükséges. A NAS nélküli demó a fejlesztői build tesztfunkciója.

## NAS-kapcsolat

A NAS-on a **File Station** legyen elérhető, a megadott felhasználó pedig rendelkezzen a kiválasztott mappához szükséges jogosultsággal. A torrentkezeléshez külön **Download Station** szükséges. Video Station nem követelmény.

| Elérés | Mikor használod? | Példa |
|---|---|---|
| Helyi hálózat | Otthon, a NAS hálózatán | `192.168.1.10`, egyedi portnál teljes cím |
| DDNS / közvetlen cím | Távolról, a ténylegesen elérhető NAS-végponthoz | `https://nas.pelda.hu:5001` |
| QuickConnect | Alternatív távoli kapcsolat | A saját QuickConnect-azonosítód |

Az elérési sorrend **helyi hálózat → DDNS / közvetlen cím → QuickConnect**. Windowson az összerendelt, elérhető helyi SMB-forrás is használható. A médiatár NAS-mappáját egyszer válaszd ki; nem kell külön mappaként felvenni minden kapcsolati módhoz. Az SMB-n nem elérhető meghajtók a File Station útján is kezelhetők, ha a NAS engedélyezi az elérésüket.

Helyi Windows NAS-címnél a `192.168.1.10` alakból a program alapértelmezett HTTP-címet képez. Androidon és egyedi protokoll/port esetén teljes címet adj meg. DDNS-nél használd a tényleges külső protokollt és portot. Távoli kapcsolathoz érvényes tanúsítványú HTTPS ajánlott; a HTTP a jelszót és a munkamenetet sem titkosítja.

A kétlépcsős NAS-azonosításhoz a program által kért egyszer használatos kódot add meg. Jelszót, API-kulcsot vagy kódot ne írj GitHub-hibajegybe.

## Médiainformációk és ajánló

A plakátokhoz, leírásokhoz és ajánlásokhoz saját [TMDB API-kulcs](https://www.themoviedb.org/settings/api) állítható be. A SynoStream a fájl- és mappanévből, valamint az elérhető NFO-adatokból próbálja azonosítani a tartalmat. A téves vagy hiányzó találat kézzel javítható.

## Frissítés

**Windows:** a Beállítások frissítési részében kézzel kereshetsz új verziót, vagy bekapcsolhatod az automatikus frissítést. A program letölti és ellenőrzi a csomagot. A kézi művelet frissít és újraindít; automatikus módban a telepítés a következő indításkor történik.

**Android:** kézi és indításkori automatikus ellenőrzés érhető el. A frissítés elfogadása után az app letölti és ellenőrzi az APK-t, majd az Android telepítőjét nyitja meg. A rendszer jóváhagyása szükséges; ez nem csendes telepítés.

Azonos Android-aláírás mellett az új APK a régi fölé telepíthető. **Frissítés előtt nem kell eltávolítani a régi alkalmazást.** Az eltávolítás az alkalmazás helyi adatainak elvesztésével járhat.

### Hol maradnak az adatok?

Windowson alapértelmezés szerint a `%LOCALAPPDATA%\SynoStream\data` mappában. Az EXE cseréje ezért nem törli a beállításokat. Hordozható módhoz az EXE mellett létrehozott üres `portable.flag` használható; az adatok ilyenkor a program mappájához kötődnek.

Androidon az adatok az alkalmazás saját tárhelyén maradnak. A NAS-médiatár gyökerében tárolt kézi párosítások a NAS-adatok részei, elkülönítve a filmek torrentmappáitól.

A Windows-mentés másik gépre átvitelekor a géphez/fiókhoz kötött titkosítás miatt a jelszót és API-kulcsot ismét meg kellhet adni.


### Windows és kétlépcsős NAS-belépés

A NAS-kapcsolat ablakában választható a megbízható eszköz megjegyzése. Sikeres egyszeri kódos belépés után a DSM eszköz-tokenjét a Windows titkosítva tárolja az adott NAS-profilhoz. Így a beolvasás és a többi háttérművelet új munkamenetet is létrehozhat. A token a DSM-ben visszavonható; ezután ismételt bejelentkezés szükséges. Az egyszeri kód nem kerül mentésre.
