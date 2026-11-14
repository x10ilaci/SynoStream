# SynoStream 1.97 – ellenőrzés

## Automatizált tesztek

Python 3.13 alatt, a teljes forráscsomag gyökerében:

```powershell
py -3.13 -m pip install -r requirements.txt -r requirements-dev.txt
py -3.13 -m pytest -q
```

A valódi MPV-dekódolási próbához a SYNOSTREAM_TEST_MPV környezeti változóban adj meg egy telepített mpv.exe fájlt. E nélkül kizárólag ez az egy teszt kimarad. A tesztek elkülönített adatmappát és helyi DSM-tesztszervert használnak, tényleges NAS-hitelesítő adat nélkül.

Lefedett esetek: névfelismerés, epizódszámozás, NAS-kapcsolódás és újrapróbálkozás, munkamenet-megújítás, lapozott mappalista, teljes kliens–helyi proxy–MPV adatútvonal, Range-kérések, Qt-megszakítás, mentés-visszaállítás, adatköltöztetés, részleges beolvasási hiba, lejátszási állapotok, 10 000 elemes kártyanézet, memóriagyorsítótár méretkorlátja és fájlváltozás, sérült kép takarítása, kártya-újrahasznosítás és kattintási cél, közös állapot-pillanatkép frissítése, rendezési eredmény újrahasználata, adagolt beolvasási sor és lezárási sorrend.

## Csomagolt EXE indulási próba

Állítsd a SYNOSTREAM_DATA_DIR környezeti változót egy üres tesztmappára, a QT_QPA_PLATFORM értékét offscreen-re, majd indítsd a programot --smoke-test paraméterrel. A program létrehozza az adatbázist és a médiatárnézetet, smoke_test.json jelentést ír a tesztmappába, majd kilép. Kifejezett adatmappa nélkül a próba 2-es kóddal leáll.

## Kézi célgépes ellenőrzés

Az 1.97-ös regressziók a `tests/test_fixes175.py` fájlban vannak. A tényleges részletező adatai kézi párosítás után újratöltődnek; az előző lekérés késői válasza nem kerülhet bele. A hiányos File Station és Download Station lapozási eredmény hibára fut. A hibás útvonaloszlopú vagy elsődleges kulcsú mentések elutasításra kerülnek, a támogatott régi szerkezet migrálható. Az első adatmappa párhuzamos létrehozását szálakkal és két külön Python-folyamattal is ellenőrizzük, elkülönített felhasználói könyvtárban.

Az 1.97-es regressziók a `tests/test_fixes174.py` fájlban vannak: beolvasás közbeni kézi párosítás, elavult sorba állított eredmények, tartós kártyapillanatkép, korhatár újratöltése másik azonosítóhoz, készülő borító védelme, illetve 20 001 elemes helyi és NAS párosítási fájllisták. A hálózati időzítéseket tesztpéldányok és szálesemények vezérlik; ezek nem élő NAS-terhelésmérések.

- A legutóbb használt médiatár nyíljon meg; helyi és NAS-os filmek és sorozatok is működjenek.
- Mindhárom kártyaméretben ellenőrizd a borítók arányát, címek levágását és eszköztippjét, évszámot, megnézett állapotot és haladási sávot.
- Görgess gyorsan oda-vissza, majd válassz kártyát. A részletező és a lejátszás a kiválasztott elemhez tartozzon.
- Keress, rendezz év, cím és korhatár szerint, méretezd át az ablakot, és frissíts médiatárat. A változások frissítsék a találatokat és a rendezést.
- Beolvasás közben válts másik médiatárra, kérj újabb frissítést, majd zárd be az alkalmazást. A részlegesen hibás médiatár adatai maradjanak meg.
- Videó folytatása, végignézése vagy megnézett állapotának módosítása után a kártya állapota is frissüljön. Ellenőrizd a következő epizódot, hangsávokat és feliratokat.
- Válts magyar és angol felület között; a kártyák állapotszövege és a keresés is maradjon helyes.
- Készíts és állíts vissza mentést. A felhasználói adatmappa és a portable.flag működése maradjon meg.
- Az EXE újraindítása őrizze meg a médiatárakat, pozíciókat, beállításokat; a v1.54 mappa érintetlen maradjon.

## Build

```powershell
py -3.13 -m pip install -r requirements-build.txt
.\build_windows.ps1
```

Alapértelmezett kimenet: Downloads\SynoStream v1.97. A build védi az eredeti v1.54 mappát, és nem törli a korábbi kiadásokat.

Az élő DSM-verzió és az internetkapcsolat viselkedését célgépen is ellenőrizni kell. A helyi teljesítménymérés nem a NAS sebességét méri, és nem garantál azonos eredményt más gépen.


## Download Station – 1.97

A test_download_station.py helyi DSM-tesztszerverrel ellenőrzi a saját DownloadStation-munkamenetet, API-felderítést, lapozást, munkamenet-megújítást, hivatkozásos feladatot és multipart torrentfeltöltést, kiválasztott feladatműveleteket, jogosultsági hibákat, támogatott API-verziókat, valamint azt, hogy bizonytalan íróművelet nem ismétlődik meg. Qt-tesztek ellenőrzik a navigációt, stabil feladatazonosító szerinti kijelölést, befejezési jelzést és célzott médiatár-frissítést, több torrent hozzáadását, mappaböngészést, alapértelmezések mentését, fiókváltást és bezárást.

Az élő NAS-on saját, háromfájlos teszttorrenttel ellenőriztük az előkészítést: a jóváhagyás előtt nem jött létre letöltési feladat. A kijelölt filmfájl indítása után a NAS natív wanted jelölése a filmnél igaz, az NFO- és sample-fájlnál hamis volt. A saját tesztfeladatot és tesztmappát eltávolítottuk; meglévő felhasználói feladatot nem módosítottunk.

A test_selection_and_menus.py ellenőrzi a fájlszűrést, ritka fájlindexek pontos átadását, üres/hibás kijelölést, megszakítást, hiányzó API esetét, bizonytalan indítás ismétlésének tiltását, valamint a magyar/angol szerkesztőmenüket és oldalsávtérközöket.

Kézi ellenőrzés: Hozzáadás után jelenjen meg a tartalomlista; NFO és sample alapból kikapcsolva. A kijelölés átállítható, a Mégse ne indítson feladatot. A típus-/médiatárválasztó és a NAS beállítása gomb hiányozzon. A jobbklikkes menük kövessék a felületi nyelvet.

## 1.97 rendezés és torrentoldalak

A test_task_sort_and_sites.py minden oszlopnál tényleges fejléc-kattintással ellenőrzi a két rendezési irányt, valamint frissítéskor a sorrend és a feladatkijelölés megtartását. Ellenőrzi az oldal hozzáadását, törlését, mentését, új ablakban betöltését, pontos URL megnyitását, üres lista megőrzését, hibás webcímek elutasítását és sikertelen mentés visszaállítását.

Kézi ellenőrzés: műveletgombok egy sorban, alattuk saját oldalgombok; sok oldalnál vízszintes görgetés. A kezelőablak magyar és angol szövegei kövessék a felületi nyelvet.

## 1.97 plakátpótlékok

A korábbi kártya-újrahasznosítási teszt már a helyes elemhez tartozó plakátpótlékot ellenőrzi. Új ellenőrzések: 1000 különböző média mindhárom színre oszlik, a kiosztás gyorsítótár-törlés után is állandó, azonos méretnél mindössze három megosztott kép készül, méretváltáskor a szín megmarad, és a valódi borító felülírja a helyettesítőt. A médiatár előnézetét 1280×850 és 1000×720 méretben ellenőriztük.

## 1.97 egyedi címsor

A test_window_chrome.py hét párbeszédablak-típuson ellenőrzi a közös címsort, eredeti ikont, címfrissítést, átméretezést és a bezárás/megszakítás eredményét. Ellenőrzi a főablak nagyítását, dupla kattintásos visszaállítását, kis méretét, teljes képernyős margóit, az átméretezési széleket, a Qt-fájlválasztó használatát és a nyelvváltást. Kritikus, nem kezelt Qt-hiba esetén a címsorteszt sikertelen.

Natív Windows-próba elkülönített adatmappával: nagyítás, munkaterület/tálca határának megtartása, dupla kattintásos visszaállítás, kis méret, visszaállítás és bezárás sikeres. A natív mozgatás/átméretezés Qt startSystemMove/startSystemResize műveleteket használ; a különböző Windows-verziók többmonitoros és eltérő DPI-s viselkedését célgépen érdemes ellenőrizni.

Képi ellenőrzés: főablak két méretben, új torrent, torrentoldalak, üzenet, fájlválasztó és beviteli ablak.

Az újraindítási regressziós teszt három külön folyamatban egymás után indítja és zárja be az alkalmazást, ugyanazzal az elkülönített adatmappával. A Qt által C++-ból létrehozott statikus fájlválasztó saját címsoros bezárását is ellenőrzi. A címsorok Python-wrapperét az alkalmazás élettartamához kötjük; az ablakot Qt-szülőkapcsolatból érjük el, és kilépéskor még a Python-leállás előtt takarítjuk.

## 1.97 – mentett teljesképernyős állapot és natív nagyítás

Négy mentett állapotból (teljes képernyő, nagyított + teljes képernyő, kis méret, mindhárom) ellenőrizzük a látható címsoros indulást és az újabb megnyitást. A natív Windows-regresszió külön folyamatban indul: teljes képernyős + nagyított mentést készít, az új főablak visszaállítja, majd a Win32 klienskoordináták alapján ellenőrzi, hogy a felület a monitor munkaterületén belül van. A Qt-ablak nagyított marad, teljes képernyős jelölés nélkül, látható címsorral.

A konkrét hibás állapotot külön natív próbával is reprodukáltuk (1.63: rejtett címsor és WindowFullScreen; 1.97: látható címsor, csak WindowMaximized). A nagyítás/visszaállítás, dupla kattintás és kis méret natív próbája is sikeres. A teljes tesztcsomag és a csomagolt EXE-próbák futtatandók a kiadás előtt.

## 1.97 – médiainformációs ablak, majd részletezőablak bezárása

A test_modal_owner_state.py a valós open_media_detail → információs gomb → információs ablak bezárása → részletező X gomb útvonalat ellenőrzi. Tizenkét kombináció: film/sorozat, normál/nagyított főablak, belső X/Esc/Mégse. Ellenőrzi a főablak láthatóságát, a megelőző ablakállapot megtartását és a címsort a törlési események feldolgozása után is.

Külön natív Windows-folyamat mind a tizenkét esetet kétszer futtatja; a natív párbeszédablak-stílus megőrzését is ellenőrzi. Ez kiegészíti a valódi egérkattintásos kézi próbát, amelyben film és sorozat esetén is az információs ablak, majd a részletezőablak X gombját nyomtuk meg. A javított főablak látható maradt.

## 1.97 – auditban feltárt hibák

A test_audit_fixes.py külön alkalmazásfolyamatban ellenőrzi a saját és a szándékosan üres torrentoldal-lista visszatöltését. Ellenőrzi a régi konfiguráció nCore-alapértékét és a változatlan fájl újraírásának mellőzését.

Négy hibatűrési eset: indulási/kézi mentés közbeni részleges kiírás és sikertelen fájlcsere. Mindegyiknél a korábbi állomány bájtpontosan megmarad, az ideiglenes fájl eltűnik.

Helyi proxy és teszt-NAS ellenőrzi az A/B fiókváltást, a régi URL saját profilhoz kötését, a profilok közötti útvonal-hozzáférés tiltását, az azonos útvonal párhuzamos használatát és a profilok felszabadítását. A valódi MPV-s próba a teljes play_with_mpv → IPC → lejátszás vége → kapcsolatfelszabadítás utat is ellenőrzi. Külön eset vizsgálja, hogy élő MPV mellett az IPC-figyelés vége nem zárja be a streamet.

Az API-próba lejárt SID után módosított alapcímmel, API-útvonallal és új SID-del ellenőrzi az olvasó és az író kérések célját. A korábbi bizonytalan írási műveletek egyszeri elküldésének tesztjei is megmaradnak. Éles NAS-fiókot a próbák nem használnak.
