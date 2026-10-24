# SynoStream 1.54

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

A Windows x64 futtatható változat a `SynoStream_1.54_Windows_x64.zip` csomagban található. Csomagold ki az egészet egy olyan mappába, amelybe a Windows-felhasználód írhat, majd indítsd el a `SynoStream_1.54.exe` fájlt. Az EXE mellől ne töröld a `BINARY_NOTICES.md` fájlt.

Az alkalmazás beállításai, adatbázisa és plakátgyorsítótára az EXE mappájában maradnak. A TMDB-adatokhoz és az MPV első letöltéséhez internetkapcsolat szükséges.

## Code signing policy

Free code signing provided by [SignPath.io](https://signpath.io), certificate by [SignPath Foundation](https://signpath.org/). The publisher shown in Windows will be SignPath Foundation. Signing is limited to release builds produced from this public source repository and requires manual approval in SignPath.

Project roles and repository links are maintained in [CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md). SynoStream does not send telemetry. Network access is limited to the NAS and TMDB services configured by the operator, plus the MPV download required when the operator starts playback.

## Indítás forráskódból

A forráscsomagban tartsd egy mappában a `SynoStream_1.54.py`, `synostream_logic.py` és `LICENSE` fájlokat. Szükséges: Windows 10 vagy újabb és Python 3.13. PowerShellben, a kicsomagolt mappában futtasd:

```powershell
py -m pip install -r requirements.txt
py SynoStream_1.54.py
```

Az első indítás után a Beállításokban add meg a TMDB API-kulcsot, majd állítsd be a helyi médiamappákat vagy a távoli NAS-kapcsolatot. Az MPV-t a program szükség esetén első lejátszáskor tölti le.

## Adatok és hitelesítő adatok

A beállítások és a lejátszási adatbázis az alkalmazás mappájába kerülnek. A TMDB-kulcsot és a NAS-jelszót a Windows DPAPI védi az aktuális Windows-fiókhoz kötve; ezeket az alkalmazás nem írja a `config.json` fájlba. A másik Windows-fiókra vagy számítógépre átvitt mentés után a hitelesítő adatokat újra meg kell adni.

## Tesztek

A logikai tesztek futtatásához:

```powershell
py -m pip install -r requirements-dev.txt
py -m pytest -q
```

A kézi ellenőrzés lépéseit a [TESTING.md](TESTING.md) tartalmazza.

## Licenc és külső összetevők

A SynoStream licencelése **GNU GPL-3.0-only**. A teljes licenc a [LICENSE](LICENSE) fájlban található; az alkalmazás Névjegy részében is megnyitható. A forrásfüggőségekről a [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), az EXE-ben csomagolt összetevőkről a [BINARY_NOTICES.md](BINARY_NOTICES.md) ad tájékoztatást.

## Kiadási előzmények

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
