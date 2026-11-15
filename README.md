# SynoStream 1.102

Nyilvános, forráskódú Windows-alkalmazás helyi és Synology NAS-on tárolt filmek és TV-műsorok böngészéséhez és lejátszásához.

## Főbb funkciók

- Több helyi és távoli médiatár kezelése, kártyás böngészés és keresés; a saját médiatár létrehozásakor kiválasztható, hogy filmeket vagy TV-műsorokat tartalmazzon.
- A számozott videókat tartalmazó sorozatmappák egy TV-műsorkártyán jelennek meg, epizódszám szerinti lejátszással.
- TMDB-alapú videoinformációk és plakátok.
- Rendezés, megnézett állapot, lejátszás folytatása és TV-epizódok sorozatos lejátszása.
- MPV-lejátszás, magyar vagy eredeti hangsáv- és feliratpreferencia.
- Induláskori médiatár-frissítési mód, állítható kártyaméret, teljes képernyős lejátszás, automatikus következő epizód és feliratkikapcsolás.
- Magyar és angol felület, nyelvválasztás a Beállításokban; a TMDB-adatok nyelve is követi a választást.
- Az MPV jobb gombos menüje magyar vagy angol nyelven jelenik meg, és az elérhető hangsávokat/feliratokat is felsorolja.
- Beállítások és médiatár-adatok mentése és visszaállítása.
- Minden médiatár utolsó kártyalistáját helyben megőrzi, ezért műsortárváltáskor az előző lista azonnal megjelenik, miközben a NAS változásainak ellenőrzése a háttérben fut.
- Távoli NAS-filmkönyvtáraknál a program elmenti a mappák állapotát; az ellenőrzés a változatlan, gyorsítótárazott levélmappákat kihagyja.

Egy régi adatbázis első 1.46-os vagy újabb megnyitásakor a program a meglévő TMDB-gyorsítótárból tölti be a korábbi kártyákat, majd frissíti az új kártyalistát. A frissítés ikon teljes ellenőrzést végez az éppen megnyitott médiatárban, így az azonos néven lecserélt videófájl módosítási idejét is ellenőrzi.

## EXE használata

A Windows x64 futtatható változat a `SynoStream_1.102_Windows_x64.zip` csomagban található. Csomagold ki az egészet egy olyan mappába, amelybe a Windows-felhasználód írhat, majd indítsd el a `SynoStream_1.102.exe` fájlt. Az EXE mellől ne töröld a `BINARY_NOTICES.md` fájlt.

Az alkalmazás beállításai, adatbázisa, MPV-je és plakátgyorsítótára alapból a `%LOCALAPPDATA%\SynoStream\data` mappában maradnak, ezért az EXE cseréje nem érinti őket. Hordozható használathoz indítás előtt hozz létre egy üres `portable.flag` fájlt az EXE mellett. Ha az új adatmappa még nem létezik, a program az EXE melletti régi adatokat átmásolja; az eredetit megtartja. Az átvételhez az új EXE-t a régi adatok mellé tedd. Már létező új adatmappát nem ír felül. Másik helyen lévő telepítésnél használd a beépített mentés-visszaállítást. A TMDB-adatokhoz és az MPV első letöltéséhez internetkapcsolat szükséges.

## Indítás forráskódból

A forráscsomag teljes tartalmát tartsd együtt, az összes synostream_*.py modullal, az assets és licenses mappával. Szükséges: Windows 10 vagy újabb és Python 3.13. PowerShellben, a kicsomagolt mappában futtasd:

```powershell
py -m pip install -r requirements.txt
py SynoStream_1.102.py
```

Az első indítás után a Beállításokban add meg a TMDB API-kulcsot, majd állítsd be a helyi médiamappákat vagy a távoli NAS-kapcsolatot. Az MPV-t a program szükség esetén első lejátszáskor tölti le.

## Adatok és hitelesítő adatok

A beállítások és a lejátszási adatbázis a felhasználói adatmappába kerülnek (hordozható módban az EXE mellé). Verzióváltás előtt az `upgrade_backups` almappában konzisztens mentés készül a konfigurációról, az adatbázisról és a helyi DPAPI-hitelesítőadattárról. Ezeket a mentéseket a program nem törli automatikusan. Az adatbázis sémája verziózott; újabb sémát egy régebbi program nem nyit meg. A TMDB-kulcsot és a NAS-jelszót a Windows DPAPI védi az aktuális Windows-fiókhoz kötve; ezeket az alkalmazás nem írja a `config.json` fájlba. A másik Windows-fiókra vagy számítógépre átvitt mentés után a hitelesítő adatokat újra meg kell adni.

## Tesztek

A logikai tesztek futtatásához:

```powershell
py -m pip install -r requirements-dev.txt
py -m pytest -q
```

A kézi ellenőrzés lépéseit a [TESTING.md](TESTING.md) tartalmazza.

## Licenc és külső összetevők

A SynoStream licencelése **GNU GPL-3.0-only**. A teljes licenc a [LICENSE](LICENSE) fájlban található; az alkalmazás Névjegy részében is megnyitható. A forrásfüggőségekről a [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), az EXE-ben csomagolt összetevőkről a [BINARY_NOTICES.md](BINARY_NOTICES.md) ad tájékoztatást.

## Újdonságok az 1.102-ban

- Az induláskori konfiguráció-visszaírás és a kézi beállításmentés egyedi ideiglenes fájlt, teljes kiírást és atomikus cserét használ. Részleges írás vagy sikertelen csere esetén az előző konfiguráció megmarad. Változatlan beállításokat az indulás nem ír újra.
- A saját torrentoldalak bekerültek a beállítási sémába. A név és webcím újraindítás után is megmarad. A szándékosan üres oldallista is megmarad; a régi, oldallista nélküli konfiguráció az nCore alapgombját kapja.
- A távoli lejátszás NAS-profilhoz kötött kapcsolatot használ. Fiók-, jelszó- vagy NAS-váltás után az új lejátszás az új belépési adatokat használja. A már futó MPV-k saját kapcsolatukon folytatódhatnak.
- A helyi streamhivatkozásban nincs felhasználónév, jelszó vagy NAS-SID. A hozzáférhető útvonalakat a program profilonként ellenőrzi. A párhuzamos lejátszások közül csak az utolsó használó kilépése után zárja a hozzá tartozó kapcsolatot; egy idő előtt megszakadó IPC-figyelő sem szünteti meg az élő MPV adatútját.
- Lejárt munkamenet és új NAS-alapcím/API-útvonal esetén a torrentkérés már az újonnan felderített végpontot használja. Bizonytalan íróműveletet továbbra sem ismétel automatikusan.

Az előző verzió által a beállításfájlból már eltávolított torrentoldal-gombokat szükség esetén újra hozzá kell adni. A javítás a meglevő és az ezután elmentett oldallistát megőrzi.


## Korábbi, 1.65-ös ablakbezárási javítás

Javítás a következő bezárási sorrendhez: műsorkártya megnyitása → médiainformáció hozzáadása → a médiainformációs ablak X gombja → a kártya részletezőablakának X gombja. A főablak állapotának meg kell maradnia, nem kerülhet kis méretre a tálcára.

- A saját címsor X gombja párbeszédablaknál közvetlenül a Qt megszakítási útvonalát (reject/done) használja. A főablak X gombja továbbra is a normál alkalmazásbezárást végzi.
- A Windows natív ablakstílusának beállításakor a párbeszédablakok megőrzik a Qt felugróablak-tulajdonságát (WS_POPUP). A főablak asztali/nagyítási beállításait nem alkalmazzuk a hozzá tartozó modális ablakokra.
- A meglévő megszakítási, munkaszál- és lejátszáslezárási kezelők megmaradnak.
- Az 1.64 címsor-, tálca- és mentett ablakállapot-javítása megmarad.


## Korábbi, 1.64-es címsor- és tálcajavítás

Az 1.63 egy korábban mentett, egyszerre nagyított és teljes képernyős Qt-ablakállapotnál elrejtette a címsort. Windows alatt a keret nélküli nagyítás is teljes képernyős állapotként térhetett vissza.

- A mentett geometria mérete és normál helyzete megmarad, a teljes képernyős és minimalizált állapot nem kerül vissza a főablakra. A nagyítási beállítást megtartjuk. A többi beállítást nem kell újra megadni.
- A főablak saját címsora már az ablakgeometria visszaállítása előtt létrejön.
- Windows alatt megmaradnak a natív asztali ablakkezelési tulajdonságok; a natív keret vizuális részét az egyedi címsor váltja fel.
- A nagyítás a monitor munkaterületéhez igazodik. A tálca által lefoglalt területet a kliensfelület szabadon hagyja.
- Ha automatikusan elrejtett vagy hiányzó tálca miatt a munkaterület az egész monitor, egy fizikai pixeles alsó perem akadályozza meg a téves teljesképernyő-felismerést. A Windows tálca saját automatikus elrejtési beállítását nem módosítjuk.
- Az eredeti SynoStream-ikon és a közös sötét címsor a párbeszédablakokon is megmarad.


## Korábbi, 1.63-as fejlesztések

- Egyedi sötét lilásszürke címsor a főablakon és a program párbeszédablakain. A megjelenés független a Windows világos/sötét témájától.
- A címsor a meglévő assets/synostream.ico ikont használja, a program és a felugró ablakok egységes megjelenésével. A párbeszédablakok a saját címüket őrzik meg.
- Főablak: kis méret, nagyítás/visszaállítás, bezárás; dupla kattintásos nagyítás/visszaállítás. A címsorral az ablak a Windows natív mozgatási műveletét használja; a széleken és sarkokon natív átméretezés indítható.
- Párbeszédablakok: azonos fejléc és bezárógomb. A bezárás megőrzi a meglévő megszakítási és háttérművelet-kezelést.
- A torrentablakok, fájlkiválasztó, kérdések, hiba- és tájékoztató ablakok, szövegbeviteli ablakok közös címsort kapnak. A rendszer fájlválasztója helyett a program saját témájával megjelenő Qt-fájlválasztó működik.
- A Qt magyar fordítása a programba van csomagolva. A fájlválasztó feliratai és az ablakvezérlők súgói követik a magyar/angol nyelvet.
- Az ablak tartalma a címsor alatt kezdődik; teljes képernyőn a fejléc és a fenntartott helye eltűnik.


## Korábbi, 1.62-es fejlesztések

- Három színű plakátpótlék a borító nélküli filmekhez és sorozatokhoz: tompa lila, petrolkék és bordó, finom geometriai árnyalással és halvány filmikonnal.
- A szín a média útvonalából képzett, véletlenszerű eloszlású választás. Ugyanahhoz az útvonalhoz mindig ugyanaz tartozik: görgetés, kártya-újrahasznosítás, méretváltás és újraindítás után is. A cím módosítása nem változtatja meg a színt. Áthelyezéskor új színt kaphat.
- A kártyák és a média részletezőablaka ugyanazt a színt használják. A meglévő és később betöltött valódi borítók továbbra is elsőbbséget kapnak.
- A helyettesítők helyben, Qt-rajzolással készülnek. A három szín és a különböző méretek közös, korlátozott méretű gyorsítótárat használnak; nem keletkezik filmenként új képfájl.
- A filmcím és az évszám a kártya alatt marad; a megnézett jelölés és a lejátszási haladás megmarad.


## Korábbi, 1.61-es fejlesztések

- A feladatlista minden oszlopfejléce kattintható: név, állapot, haladás, letöltési és feltöltési sebesség, hátralévő idő. Újabb kattintás megfordítja a sorrendet. A számok és időtartamok tényleges érték szerint rendeződnek. Az ismeretlen hátralévő idő növekvő sorrendben a lista végére kerül.
- A háttérfrissítés megtartja az oszloprendezést és a feladatazonosítóhoz tartozó kijelölést.
- A torrentoldalak gombjai szabadon beállíthatók a Torrentoldalak kezelése ablakban: név, HTTP/HTTPS-webcím, hozzáadás és kijelölt oldal törlése. A Mentés megőrzi a listát, a Mégse elveti a változásokat. Az összes oldal törlése is megmarad újraindításkor.
- A korábbi nCore-gomb kezdőértékként megmarad, és ugyanúgy törölhető. A gombok az oldal nevét mutatják, és a rendszer böngészőjében nyitják meg a megadott címet.
- Az Új letöltés, Frissítés, Szüneteltetés, Folytatás és Feladat eltávolítása egy sorban található; alattuk kapnak helyet a saját torrentoldalak. Sok oldal esetén a gombsor vízszintesen görgethető.
- Az 1.60 fájlkiválasztási és nyelvi javításai megmaradnak.


## Korábbi, 1.60-as fejlesztések

- A szövegbeviteli mezők jobbklikkes menüje mindenütt követi a magyar/angol felületi nyelvet, a szerkeszthető legördülőknél és többsoros mezőknél is.
- Az új torrent ablakából eltűnt a típus és a médiatár választója. A NAS-célmappa tallózható, az utoljára használt cél megmarad.
- A Letöltések oldalról eltűnt a NAS beállítása gomb.
- A Hozzáadás először csak a torrent tartalmát készíti elő. Ezután mappákba rendezett fájlválasztó jelenik meg; a letöltés kizárólag a Kijelöltek letöltése gombbal indul.
- Az .nfo kiterjesztésű és az elérési útjukban sample szót tartalmazó fájlok alapból nincsenek kijelölve, kis- és nagybetűtől függetlenül. A kijelölés kézzel felülírható. Üres kijelöléssel nem indul letöltés.
- A Mégse törli az előkészített listát; letöltési feladat nem indul. Hiányzó NAS-fájlkiválasztási API esetén a program hibát jelez, nem indít automatikusan minden fájlt.
- A Letöltések menüpont az oldalsáv aljára, a médiatárak és a Beállítások közé került, térközzel felette és alatta.


## Download Station

Az oldalsáv új **Letöltések** gombja a médiatárak és a Beállítások közé került. A sötét-lila kezelőoldal közvetlenül a NAS Download Station szolgáltatását használja, külön DownloadStation-munkamenettel.

- Új letöltés: magnet/HTTP/HTTPS-hivatkozás vagy egy/több helyi .torrent fájl. Torrentfájlokat a Letöltések oldalra is behúzhatsz. A fájlonkénti korlát 32 MiB.
- NAS-mappaválasztó, az utoljára használt célmappa megőrzése. Üres célmappánál a Download Station alapértelmezése érvényes.
- Feladatlista állapottal, haladással, le-/feltöltési sebességgel, becsült hátralévő idővel; kijelölt feladatnál célmappa, feltöltött méret és seedarány.
- Kijelölt feladatok szüneteltetése és folytatása; eltávolítás külön megerősítéssel. A befejezetlen adatok sorsát a NAS Download Station beállításai határozzák meg.
- A már kapcsolódott oldal látható állapotban 5, háttérben 15 másodpercenként kérdezi le a listát. Hálózati hibánál ritkítja az ellenőrzést; átfedő kérést nem indít.
- Az észlelt befejezésről a programban jelzés jelenik meg; a letöltési célhoz illeszkedő távoli NAS-médiatárak sorban, teljes ellenőrzéssel frissülnek. A kezdeti listában már kész régi feladatokat nem jelenti új letöltésként.
- Saját torrentoldalak névvel és webcímmel, hozzáadási és törlési lehetőséggel. A megnyitás és a bejelentkezés a rendszer böngészőjében történik.

### Beállítás

A NAS-on legyen telepítve Download Station, és a SynoStream NAS-fiókjának legyen jogosultsága hozzá és a célmappához. A meglévő QuickConnect-belépést használjuk; szükség esetén a Beállításokban módosítható. A letöltési adatforgalmat a NAS végzi, a számítógép csak a feladatokat kezeli.

A program bezárása után a NAS a már elküldött letöltéseket tovább végzi; értesítés és automatikus médiatár-frissítés a futó, már csatlakoztatott SynoStreamben történik. A program a félkész torrentet nem indítja el lejátszásra.

A létrehozó/törlő/szüneteltető műveleteket bizonytalan hálózati válasz esetén nem ismétli meg automatikusan. Ilyenkor előbb frissítsd a feladatlistát, és ellenőrizd, végrehajtotta-e a NAS a műveletet.

## Kiadási előzmények

- **1.102 (2026-11-11):** Download Station kezelőoldal, torrent- és magnet-hozzáadás, NAS-célmappák, feladatműveletek és kész letöltések médiatár-frissítése.

- **1.58 (2026-11-11):** Plakátnézet, képi és állapotgyorsítótár, kártya-újrahasznosítás, külön rendezési/szűrési/elhelyezési lépés, adagolt felületi frissítés.
- **1.57 (2026-11-11):** A teljes kezdőlap eltávolítása.
- **1.56 (2026-11-11):** Az üres NAS-letöltési API-cím javítása.

- **1.54 (2026-10-24):** A frissítés közben sorba állított NAS-frissítés is teljes ellenőrzést végez; részleges hiba mellett a sikeresen beolvasott médiatárak cache-e tovább takarítható; beolvasás közben nem törölhető médiatár; törléskor a hozzá tartozó nézet-, állapot- és kézi összevonási beállítások is eltűnnek; sikertelen útvonalmentés visszaállítja az előző konfigurációt.
- **1.53 (2026-10-24):** Eltávolítva a 4 MiB-os alacsony szintű stream-puffer, mert a QuickConnecten átjátszott filmeknél ronthatta a teljesítményt; a filmek visszaálltak az 1.51-ben használt MPV-pufferbeállításokra.
- **1.52 (2026-10-24):** A hálózatról lejátszott filmek a nagyobb demuxer-cache mellett 4 MiB-os stream-puffert is használnak; ez segíthet a nagy bitrátájú filmek és hálózati fájlok folyamatos olvasásán.
- **1.51 (2026-10-24):** A hálózatról játszott filmek a sorozatepizódoknál nagyobb, 768 MiB-os előre pufferrel és 10 másodperces indulás előtti feltöltéssel indulnak, mert a filmek jellemzően nagyobb bitrátát igényelnek.
- **1.50 (2026-10-24):** Hálózati videóknál az MPV nagyobb előtöltési puffert használ, és röviden előtölt lejátszás előtt, majd szükség esetén újrapufferel, hogy csökkentse az akadozást.
- **1.49 (2026-10-24):** Médiatáranként megjeleníti a kártyaszámot és az utolsó sikeres frissítés idejét; a beolvasási hibákat külön, forgó naplófájlba írja, a kártyák leírásában nem jeleníti meg; a NAS-jelszó mező mutatókapcsolót kapott anélkül, hogy felfedné a korábban elmentett jelszót.
- **1.48 (2026-10-24):** A gyanúsan üres vagy részleges beolvasás most az érintett médiatárhoz rendeli a hibát. A többi sikeres médiatár kártyái és gyorsítótárai tovább frissülnek.
- **1.47 (2026-10-24):** A régi gyorsítótárból betöltött sorozatok a filmkönyvtár megfelelő kártyáihoz is megjelennek; részleges beolvasási hibánál csak az érintett műsortár gyorsítótárának eltávolítási művelete marad el; a nyelvi gyorsítótár-állapot nem jelöl sikertelen beolvasást sikeresnek; a mentés visszaállítása a mentés hitelesítőadat-állapotát állítja vissza, és a mentésben nem szereplő régi hitelesítő adatokat törli.
- **1.46 (2026-10-24):** Minden műsortár utolsó kártyalistája helyben gyorsítótárazódik; műsortárváltáskor az előző lista azonnal megjelenik, az ellenőrzés nem építi újra az összes kártyát, és a korábban csak TMDB-adatként eltárolt médiák is megjelennek az első frissítés előtt.
- **1.45 (2026-10-24):** Korhatár-besorolást kér le a TMDB-ről filmekhez és TV-műsorokhoz. A besorolás megjelenik a részleteknél, a korhatár szerinti rendezés pedig első használatkor háttérben tölti be a hiányzó adatokat.
- **1.44 (2026-10-24):** Egységes, rajzolt ikon és hangsúlyosabb, teljes szélességű gomb a Beállításokhoz; letisztultabb kukaikon a saját médiatárak törléséhez.
- **1.43 (2026-10-24):** A távoli NAS-filmkönyvtárak mappa-pillanatképe az adatbázisban marad. Az első beolvasás felépíti a pillanatképet; utána a változatlan, gyorsítótárazott levélmappák NAS-listázás nélkül jelennek meg. A frissítés ikon teljes ellenőrzést végez az aktuális médiatárban.
- **1.42 (2026-10-24):** A kézi TV-műsor-összevonás célkártyái csak az aktuális médiatárból választhatók; az összevonás és feloldás is kizárólag azt a médiatárat frissíti.
- **1.41 (2026-10-24):** A saját médiatárak film vagy TV-műsor típust kapnak; a régi „sori/sorozat/TV” nevű könyvtárak TV-műsorként állnak át, a frissítés pedig eltávolítja az átsorolt útvonal korábbi, hibás médiatípusú cache-sorait.
- **1.40 (2026-10-24):** Az összes médiatárat érintő induláskori beolvasás legfeljebb négy könyvtárat dolgoz fel párhuzamosan.
- **1.39 (2026-10-24):** A számozott epizódokat tartalmazó almappák a filmbeolvasásban is egy sorozatkártyává állnak össze; az `01.avi` jellegű nevek epizódszámként működnek, a zárójeles alternatív sorozatcímeket külön TMDB-keresés használja.
- **1.38 (2026-10-24):** Új médiatár létrehozásakor helyi vagy távoli NAS-mappa választható; a kiválasztott útvonal közvetlenül az új könyvtárhoz kerül, és csak ez a médiatár frissül.
- **1.37 (2026-10-24):** Magyar felület mellett is angol nyelven próbálja keresni a TMDB-n a csak angol néven elérhető műsorokat; az új keresési szabály újrapróbálja a korábbi sikertelen párosításokat.
- **1.36 (2026-10-24):** A sorozatmappában megadott epizódtartomány nem ismétlődik minden fájlnál; a külön számot nem tartalmazó epizódok a tartomány kezdőszámától sorban számozódnak.
- **1.35 (2026-10-24):** A `fulcrum-` kiadócsoport-előtag leválasztása a TMDB-keresés előtt; a korábban sikertelen párosítások újrapróbálása az új névtisztítási szabállyal.
- **1.34 (2026-10-24):** Felismeri a sorozatcím után álló hosszú epizódtartományokat (pl. `E00701-E00800`), kötőjeles címekkel is próbálkozik a TMDB-keresés, és az új névfelismerés egyszer újrapróbálja a korábban sikertelen párosításokat.
- **1.33 (2026-10-24):** Javítja a kártyaméret-beállítást: a méret azonnal megjelenik és mentődik, a kompakt, normál és nagy kártyák közötti különbség erősebb.
- **1.32 (2026-10-24):** Induláskori frissítés beállítása (utoljára használt, minden vagy egyik médiatár sem), állítható kártyaméret, MPV teljes képernyős indítása, automatikus következő TV-epizód kapcsolója és feliratkikapcsolási lehetőség.
- **1.31 (2026-10-24):** Magyar/angol, sávválasztókat is tartalmazó MPV jobbklikkes menü.
- **1.30 (2026-10-24):** Javítja a beviteli menük teljes magyarítását, a többsoros angol fordítást, a QuickConnect mentési visszajelzését és API-útvonalát; SHA-256 alapján ellenőrzi az MPV-letöltést, a régi kiadások törlési hibája nem szakítja meg a buildet.
- **1.29 (2026-10-24):** A jobb egérgombos szerkesztési menü a felület nyelvén jelenik meg a beviteli mezőkben és a szövegmezőkben.
- **1.28 (2026-10-24):** Javítja a sikertelen TMDB-találatok gyorsítótárazását, a beépített könyvtárak nyelvváltás utáni frissítését, az MPV-indítás hibakezelését és a TV-epizódok felismerését.
- **1.27 (2026-10-24):** Javítja a média címek fordítását, a DPAPI-hitelesítőadatok megőrzését, az MPV IPC indulási hibakezelését és az epizódnév-felismerést; a forráscsomag buildje a gyökérben levő licencekkel is működik.
- **1.26 (2026-10-24):** Javítás az angol felületi lokalizáció indításkori Qt-widget importhibájára.
- **1.25 (2026-10-24):** Magyar és angol felület; a nyelv a Beállításokban módosítható és újraindítás után is megmarad, a TMDB-lekérdezések nyelvével együtt.
- **1.24 (2026-10-24):** Hosszú TV-sorozat-lejátszólisták átadása ideiglenes M3U-fájlon és MPV IPC-n keresztül a Windows parancssor-korlátjának elkerülésére.
- **1.23 (2026-10-24):** Kisebb TV-műsor részletezőablak; pontosított GPL-jogi tájékoztató a Névjegyben.
- **1.22 (2026-10-24):** A TV-műsor részletezőablaka nagyobb epizódlistát mutat; több évad esetén az évadok összecsukva nyílnak meg.
- **1.21 (2026-10-23):** Lila-szürke alkalmazásikon az EXE-hez és az ablakhoz; a kiadási folyamat eltávolítja a korábbi verziófájlokat a Letöltésekből.
- **1.20 (2026-10-23):** Windows x64 EXE-kiadás; a beállítások az EXE mappájában maradnak.
- **1.19 (2026-10-23):** Nyilvános forráskiadás; frissített kiadási dokumentáció és Névjegy.
- **1.18:** GPL-jogi tájékoztató és teljes licencnézegető.
- **1.17:** Mentett hitelesítő adatok védelme Windows DPAPI-val, a titkok kihagyása az exportált mentésből.



## NFO-alapú felismerés (1.102)

A korábban azonosítatlan vagy új műsoroknál a program helyi és NAS-mappákban is megvizsgálja a kapcsolódó NFO-fájlt. Felhasználható adat: IMDb-azonosító (`tt0133093` vagy IMDb-hivatkozás), TMDB-azonosító/hivatkozás, Kodi XML `<title>`, `<originaltitle>`, `<year>`, `<uniqueid>` mezők, illetve szöveges `Title:`, `Original title:`, `Cím:` és `Year:` mezők. Az IMDb-feloldás és a borítók/leírások lekérése továbbra is a beállított TMDB-kulcsot használja.

Tedd az NFO-t a műsor mellé, majd frissítsd a médiatárat. Filmnél a videóval azonos nevű NFO az elsődleges (például `001.mkv` és `001.nfo`). Egyetlen filmet tartalmazó mappában `movie.nfo` vagy más egyetlen NFO is használható. Sorozatnál a sorozat mappájában lévő `tvshow.nfo` is támogatott. Több különböző film mellett közös NFO-ból nem rendel automatikusan azonosítót minden filmhez. Epizód-NFO nem szolgál sorozatazonosítóként.

A kézi párosítás és a meglévő sikeres azonosítás megmarad. A korábban sikertelen felismerés gyorsítótára nem akadályozza egy később mellétett NFO használatát. Sérült vagy hiányzó NFO esetén a program a szokásos névfelismeréssel próbálkozik. A méretkorlát NFO-nként 1 MiB; az NFO nem végrehajtható programként kerül feldolgozásra.

A torrentfájl-választóban az NFO továbbra sincs alapból kijelölve. Ha szeretnéd felhasználni a felismeréshez, a hozzáadáskor az NFO letöltését is jelöld be.


## Filmfelismerés mappanévből (1.102)

Egyetlen főfilmet tartalmazó, címmel és évszámmal nevezett kiadási mappában a teljes mappanév pontosítja a rövidített fájlnevet. Például a `Kubo.and.the.Two.Strings.2016.../kubo-720p-hyperx.mkv` fájlhoz a `Kubo and the Two Strings` cím és a 2016-os év, a `Lady.and.the.Tramp.1955.../latt.720p-trinity.mkv` fájlhoz a `Lady and the Tramp` cím és az 1955-ös év lesz a keresési támpont. A sample-videó nem számít külön főfilmnek.

A film évszámától több mint egy évvel eltérő találat nem fogadható el, az évszám nélküli tartalék keresésben sem. Többfilmes vagy általános gyűjtőmappa nem adható minden benne lévő film címének. Ha a fájlnév már tartalmaz évszámot, azt használja.

Az ilyen mappák korábbi automatikus találatait frissítéskor újraellenőrzi. A kézi párosítások és az NFO-azonosítók elsőbbsége megmarad. Telepítés után frissítsd az érintett médiatárat; kézi adatbázis- vagy gyorsítótár-törlés nem szükséges.


## Hordozható kézi párosítások (1.102)

A kiválasztott médiatármappa gyökerében, a `.synostream/parositasok` alkönyvtárban tárolja a kézi párosítások hordozható változatát. Egy módosítás egy saját, egyedi nevű JSON-fájlt kap. A médiatárban közvetlenül elhelyezett filmfájlokat is támogatja. A film/torrent saját könyvtárába nem tesz új fájlt, ha a beállított médiatárgyökér azon kívül van.

Használat:

1. A meglévő gépen indíts médiatár-frissítést, vagy a Beállítások / Hordozható médiapárosítások résznél kattints a Párosítások szinkronizálása gombra. A korábbi kézi párosítások is kikerülnek a közös mappába.
2. Ellenőrizd az állapotjelzésben, hogy nincs mentésre váró vagy sikertelen művelet. A helyi párosítás hiba esetén is megmarad, a következő frissítés újrapróbálja a közös mentést.
3. A másik gépen is legalább 1.102-es SynoStreamet használj, és ugyanazt a fizikai médiatárgyökeret válaszd ki. Az elérési út lehet más meghajtóbetű vagy másik gép saját NAS-elérése; a közös bejegyzések relatívak. Más könyvtárszint kiválasztásakor a relatív útvonalak eltérnek.
4. Frissítsd a médiatárat. A közös párosításokat az automatikus keresés előtt átveszi, és a saját TMDB-kulcsoddal betölti a médiainformációkat.

Az új és a visszavont kézi párosításokat is továbbadja. A két gép különböző műsorokra vonatkozó módosításai együtt megmaradnak. Ugyanazon műsor egyidejű, eltérő párosítását determinisztikus verziós sorrend oldja fel; szükség esetén a szinkronizálás után ismét válaszd ki a kívánt párosítást. Az előzményfájlokat ne szerkeszd kézzel.

A közös mappa nem tartalmaz beállításokat, jelszót, NAS-felhasználónevet, API-kulcsot, lejátszási pozíciót vagy megtekintési jelölést. A helyi SQLite-adatbázis megmarad, és nem válik közösen megnyitott NAS-adatbázissá. A média könyvtárszerkezetének mozgatásakor a `.synostream` mappát is vidd magaddal; a filmek/sorozatok átnevezése után a régi relatív párosítás önmagában nem találja ki az új nevet.

A NAS-on az első gépnek írási joga kell a médiatárgyökérhez, a másik gépnek legalább olvasási joga. Az üres médiatárba nem hoz létre közös fájlokat addig, amíg nincs hordozható párosítás. A szinkronizáláskor hiányzó közös fájlokat a helyben ismert előzményekből újra ki tudja menteni.


## Magyar főcím és javított szinkronizálás (1.102)

A felismeréshez az eredeti cím, mappanév és NFO-azonosító is használható, de a megjelenített adatokhoz a megtalált TMDB-adatlapot a beállított nyelven kéri le. Magyar nyelvű használatnál a magyar cím/név és magyar leírás az elsődleges. Hiányzó magyar leírásnál angol leírást is megjeleníthet, de emiatt a magyar főcímet nem cseréli angolra. Ha a TMDB nem tartalmaz magyar címet, az elérhető cím marad; a program nem készít saját fordítást.

A régebbi, eredeti címmel tárolt találatokat médiatár-frissítéssel lehet javítani, azonosító alapján, új kézi párosítás nélkül. Ez a kézi és az NFO-ból származó találatokra, valamint a NAS inkrementális beolvasására is érvényes. Az első ellenőrzés több TMDB-kérést igényelhet. Hálózati hibánál megtartja a korábbi használható adatot és később újrapróbálja.

A közös párosítások frissítése már a gyökérben lévő junction almappák logikai útvonalát kezeli. A film típusú médiatárban sorozatként felismert elem is közvetlenül exportálható. A Beállítások / Párosítások szinkronizálása művelet meglévő közös rekordokra is tartalomellenőrzést végez; az egyértelműen sérült rekordot ismert érvényes helyi példányból helyreállítja. Ha egy rekord továbbra is érvényes JSON, de ugyanazon azonosítóval eltérő adatot tartalmaz, ezt ütközésként jelzi és megőrzi a változatot.

## Médiatárankénti ajánló (1.102)

Minden médiatár felső sávjában az Ajánló gomb nyitja a saját válogatását. A Fedezz fel fülön az Új válogatás másik adagot kér; az Érdekel fül őrzi a mentett címeket. A Nem érdekel művelet az adott médiatárban rejti el a címet, az Elrejtve fülön visszaállítható. A már meglévő címek az összes beállított médiatár alapján kizárásra kerülnek. A kizárás a felismert TMDB-azonosítókon alapul; egy még azonosítatlan fájl tartalma ebből nem állapítható meg.

Az ajánló a meglévő TMDB API-kulcsot használja, külső LLM nélkül. Az adatbázisban helyben tárolja az ajánlói gyorsítótárat, a megjelenített címek előzményeit és a médiatárankénti visszajelzéseket. Ezek az alkalmazásfrissítés után is megmaradnak, és az adatbázist tartalmazó mentésbe is bekerülnek. A NAS-on tárolt közös kézi médiapárosításoktól külön, az adott gép felhasználói adatai.

Az ajánlások forrása a TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB. A TMDB API nem üzleti célú használatának feltételeit lásd: https://developer.themoviedb.org/docs/faq

## Magyar adatlapok előnyben (1.102)

A Beállítások → Ajánló csoportban kapcsolható. Alapértelmezetten bekapcsolt; a módosítást a Beállítások mentése gombbal lehet menteni. Magyar leírással igazolt címek nagyobb eséllyel kerülnek a következő válogatásba, és a kiválasztott adagon belül előrébb láthatók. A többi cím nem kerül kizárásra, a válogatás továbbra is változik.

A magyar adatlap nem bizonyít magyar szinkront. A jelölés alapja a TMDB magyar fordításának nem üres leírása; az eredetivel azonos cím nem hátrány. Az ellenőrzés válogatásonként legfeljebb nyolc extra TMDB-kérést jelent, helyi hétnapos gyorsítótárral. Kikapcsolva nincs ilyen extra lekérés. Hálózati hiba vagy megszakítás esetén a hiányzó bizonyíték nem válik negatív minősítéssé.

## Windows-ikonok (1.102)

A program verziófüggetlen Windows-alkalmazásazonosítót használ. Az ikon képi adatait memóriában tartja, a natív ablakikonokat ablaknyitás és állapotváltás után, továbbá öt másodpercenként ellenőrzi. Az ellenőrzés csak eltérés esetén állítja vissza az ikont; az ablak méretét és kicsinyített vagy nagyított állapotát nem változtatja meg.

## Beépített programfrissítés (1.95)

A Beállítások → Programfrissítés alatt kézzel kereshető új stabil Windows-kiadás. A napi háttérellenőrzés ugyanitt kikapcsolható; alapértelmezetten bekapcsolt. Új kiadásnál a Beállítások gombja és az állapotsáv jelez, lejátszás közben nem nyit felugró ablakot. A letöltés és a csomag ellenőrzése háttérszálon történik, és megszakítható. A telepítéshez külön meg kell nyomni a Frissítés és újraindítás gombot.

Az új verzió a Windows által megadott Letöltések mappa saját verziószámos alkönyvtárába kerül. Meglévő verziómappát nem ír felül, az eredeti v1.54 változatlan marad. A Letöltésekben lévő SynoStream parancsikon a sikeresen indult új verzióra mutat. A frissítő nem módosítja más program azonos nevű parancsikonját vagy a felhasználó egyéb parancsikonjait.

Az adatok a meglévő felhasználói adatmappában maradnak. A frissítő kilépés után külön mentést készít a konfigurációról, a hitelesítőadat-fájlról és az adatbázisról. Ha az új program indulás közben kilép, a frissítő zárolás mellett visszaállítja a mentést és megpróbálja elindítani a régi programot. Ha az új program még fut, de nem jelzett vissza, a frissítő nem írja felül az aktív program adatait. A korábbi kiadás és a mentés megmarad.

A frissítés a https://github.com/x10ilaci/SynoStream nyilvános kiadásait használja. Ehhez a GitHub és a kiadási fájlokat kiszolgáló GitHub CDN felé létesít HTTPS-kapcsolatot. Nem küld NAS-jelszót, TMDB-kulcsot, médiatárlistát vagy megtekintési adatot. A csomag méretét és SHA256-ellenőrzőösszegét ellenőrzi; ez nem helyettesít Windows-kódaláírást. A jelen kiadás digitálisan nincs aláírva.

A frissítő az 1.95-ös Windows-kiadástól használható. A korábbi kiadásokhoz egyszer kézzel kell letölteni és elindítani az 1.95-öt. A mobilos program frissítési rendszere ettől független.

## Frissítőjavítások és kiadási védelem (1.96)

Sikertelen indulás után a hibás program külön mappába kerül, így ugyanaz a kiadás újra letölthető. A lezárt frissítési munkamappák ellenőrzés után törlődnek; a programadatok és mentések megmaradnak. A telepítés megkezdése előtt újra ellenőrzi az EXE-t, az indulási visszajelzést pedig a tényleges frissítési feladathoz köti.

A kiadás közzététele előtt ellenőrzi a csomagok fájlneveit, tartalmát és a PyInstaller EXE kibontott programkódját is. A kiadási eszköz csak a név szerint kijelölt EXE-t, két ZIP-et, SHA256-fájlt és update.json leírót tölti fel.

## Gyorsabb ajánló (1.97)

A TMDB-ajánlások és a magyar fordítási adatok ellenőrzése legfeljebb négy párhuzamos kéréssel fut, a korábbi összesített kérési keret megtartásával. Az első használható találatok korán megjelennek; a felület nem vár a teljes ajánlói és fordítási sorozat végére. A mentett készletből az Új válogatás azonnal választ, miközben a háttérben frissül a készlet. A már megjelenített kártyák a frissítéskor megmaradnak, és csak a szükséges adataik frissülnek.

A borítók négyes párhuzamos letöltést használnak. Az azonos kártyák átrendezése és adatfrissítése nem indítja újra a még futó képbetöltést. A magyar nyelvi gyorsítótárból az aktuális találati készlet adatait olvassa ki. A megnézett előzmény nem számolja kétszer ugyanazt a korán és véglegesen megjelenített válogatást.

## Egyszerűbb frissítés és forrásösszerendelés (1.98, helyi kiadás)

A frissítési ablak Frissítés és újraindítás gombja letöltést, ellenőrzést, telepítést és újraindítást végez; a Később gomb megszakítja vagy elhalasztja a műveletet. Az 1.102-es kiadás a GitHub Releases oldalon is elérhető.

Ha ugyanaz a NAS-mappa és helyi hálózati elérése eddig külön forrássorként szerepelt, a Forrásmappák ablak Mentés művelete az egyező megosztás/almappa útvonalaknál rákérdez az összerendelésre. Csak akkor válassz Igent, ha valóban ugyanannak a mappának két eléréséről van szó. Ekkor a kártyák egy példányban jelennek meg, a kézi párosítások és lejátszási állapot megőrzésével. Két különböző kézi párosítás ütközésekor a program megállítja a mentést, és nem választ helyetted.

Összerendelt forrásnál az elérhető helyi SMB-fájlt részesíti előnyben. Az induláskor frissen ellenőrzi az elérést. Hiányzó vagy elérhetetlen helyi fájlnál továbbra is használható a NAS / QuickConnect kapcsolat; a csak QuickConnecttel elérhető USB-források támogatása megmarad. A tényleges útvonalválasztás kategóriája lejátszás közben az állapotsávon látható.

## Forrásmappák mentése háttérművelet közben (1.102)

A szerkesztő megőrzi a jóváhagyott összevonást. Ha egy korábban indult beolvasás, párosításszinkron, kézi párosítás vagy lejátszás még foglalja az adatokat, megvárja annak végét, majd automatikusan ment. A szerkesztő megnyitása alatt új beolvasás és párosításszinkron nem indul; az elhalasztott frissítés az ablak bezárása után folytatódik. A Mégse megszakítja a várakozást, így bezárás után nincs későbbi háttérmentés. Aktív lejátszásnál előbb zárd be az MPV-t.

## Közvetlen NAS-elérés (1.102)

A Távoli NAS ablakban a Közvetlen NAS-cím mezőbe HTTPS-cím adható meg, például https://nas.pelda.hu:5001. A QuickConnect ID megmaradhat tartaléknak. Az összerendelt, elérhető helyi forrás az elsődleges; távoli kapcsolatnál a közvetlen címet próbálja először a program. A címnek elérhető DSM/File Station API-ra kell mutatnia, érvényes tanúsítvánnyal. A DDNS beállítása nem igényel új médiatári útvonalakat.

## Egyszer megadott NAS-források (1.102)

1. Beállítások → NAS-kapcsolat → NAS-kapcsolat beállítása. Add meg a felhasználónevet, jelszót és legalább egy elérést. Helyi cím példa: http://192.168.1.2:5000; DDNS példa: https://nas.pelda.hu:5001. A QuickConnect ID további tartalék lehet. A Kapcsolat ellenőrzése és mentése gomb kipróbálja az elérési sorrendet.
2. Beállítások → Médiatár és adatok → Forrásmappák → Mappa hozzáadása → NAS-mappa tallózása. A mappát egyszer válaszd ki; nem kell külön SMB-, DDNS- és QuickConnect-forrás.
3. Az elérési sorrend: automatikus helyi SMB, helyi File Station API, DDNS HTTPS, QuickConnect. Az USB-s meghajtókhoz is használható a helyi File Station API, SMB-megosztás nélkül.

A mappák és fájlok azonosítójában nincs kapcsolatcím, így az elérési mód váltása nem hoz létre új kártyát. Az adott NAS ismert helyi címével egyező, korábbi UNC-forrásokat és NAS-forrásokat a program egyesíti, az előzményekkel és kézi párosításokkal együtt. Eltérő NAS-neveket és tetszőlegesen átnevezett megosztásokat nem tekint automatikusan azonosnak; a korábbi jóváhagyott összerendelések megmaradnak.

## NAS-címek és automatikus frissítés (1.102)

Helyi NAS-cím: elég a 192.168.1.2, amelyből http://192.168.1.2:5000 lesz. HTTPS vagy egyedi port esetén teljes címet adj meg. DDNS / közvetlen cím: http:// és https:// is megadható, a ténylegesen elérhető külső porttal. Protokoll nélküli DDNS-cím HTTPS-t jelent; nincs automatikus visszalépés HTTP-re. A korábbi kiadások HTTPS-kizárólagosságát ez felváltja.

Beállítások → Programfrissítés → Automatikus frissítés bekapcsolása. Alapból kikapcsolt. Bekapcsolva az új verzió ellenőrzött csomagja a háttérben letöltődik, és a következő programindításkor települ. Az aktuális használatot és lejátszást a letöltés nem szakítja meg. Kikapcsolás után a már letöltött frissítés sem indul el automatikusan. A kézi frissítés továbbra is elérhető. Telepítés az EXE-változatban támogatott.
