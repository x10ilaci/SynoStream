# SynoStream 1.54 – tesztelési útmutató

## Automatizált logikai tesztek

A csomag `tests` mappája a fájlnévtisztítást, az epizódpozíciók felismerését és a címhasonlóságot ellenőrzi. Futtatás:

```powershell
py -m pip install -r requirements-dev.txt
py -m pytest -q
```

## Kézi Windows-ellenőrzés

Új vagy módosított kiadás előtt ellenőrizd a következőket tiszta, írható alkalmazásmappából:

1. Telepítsd a `requirements.txt` függőségeit, majd indítsd el a `SynoStream_1.54.py` fájlt; külön ellenőrizd az EXE-csomag indítását is.
2. Add meg a TMDB-kulcsot és a NAS-jelszót; ellenőrizd, hogy azok nem olvashatók ki a `config.json` fájlból.
3. Indítsd újra az alkalmazást ugyanazzal a Windows-fiókkal, és ellenőrizd a mentett hitelesítő adatokat.
4. Olvass be helyi film- és TV-mappát; ellenőrizd, hogy a frissítés csak a megnyitott médiatárat olvassa be.
5. Ellenőrizd a TMDB-adatokat, rendezést, megnézett állapotot, lejátszásfolytatást és a következő epizód indítását.
6. Próbáld ki az MPV első letöltését, a hangsáv- és feliratpreferenciát, valamint a lejátszást. Jobb kattintásra ellenőrizd a magyar menüt; válts angolra, és nézd meg, hogy a menü nyelve is vált-e, illetve hogy a hangsáv- és felirat-almenük a fájl sávjait mutatják-e.
7. Böngészd és játssz le médiát a célzott Synology DSM-verziójú NAS-ról.
8. Készíts mentést, ellenőrizd, hogy a `config.json` nem tartalmaz hitelesítő adatokat, majd próbáld ki a visszaállítást.
9. A Beállításokban válts magyar és angol felület között, majd indítsd újra a programot, és ellenőrizd, hogy a választás megmarad. A Névjegy alatt ellenőrizd a verziót és a licencközlést, majd nyisd meg a teljes licencet.
10. Zárd be és indítsd újra az EXE-t; ellenőrizd, hogy a `config.json`, `credentials.dat` és `media_library.db` az EXE mellett marad, nem tűnik el az újraindítás után.
11. A Beállításokban válts a három induláskori frissítési mód között; ellenőrizd, hogy a következő indításkor az utoljára használt, minden, illetve egyetlen médiatár sem frissül automatikusan.
12. Állítsd át a kártyaméretet; az előnézetnek azonnal át kell méreteznie a kártyákat, a kiválasztás pedig automatikusan mentődik.
13. Ellenőrizd a teljes képernyős MPV-indítást, a következő TV-epizód automatikus indításának be- és kikapcsolását, valamint a felirat kikapcsolását.
14. Próbáld ki a `fulcrum-` előtagú filmcímet, a kötőjeles címeket és az `E00701-E00800` jellegű sorozatmappa-nevet; ellenőrizd, hogy a kiadási tagek leválasztódnak, és a korábbi sikertelen TMDB-találat újrapróbálódik.
15. Ellenőrizd, hogy egy epizódmappa nevében szereplő tartomány nem adja ugyanazt a számot minden fájlnak; a szám nélküli fájlok a tartomány kezdőszámától sorban kapjanak epizódszámot.
16. Állítsd a felületet magyarra, és ellenőrizd, hogy egy csak angol címmel szereplő sorozatot az automatikus párosítás angol keresési nyelven is megtalál.
17. Indíts egy távoli NAS-beolvasást, közben kérj frissítést, majd ellenőrizd, hogy a sorba állított frissítés is teljes NAS-ellenőrzést végez.
18. Olyan teljes beolvasásnál, ahol az egyik médiatár hibát jelez, ellenőrizd, hogy a sikeres médiatárak eltávolított elemei és árva plakátjai ettől még takarítódnak, a hibás médiatár adatai pedig megmaradnak.
19. Próbálj médiatárat törölni beolvasás közben; a programnak biztonságosan vissza kell utasítania, majd beolvasás után törléskor el kell távolítania a nézet-, frissítési és kézi összevonási beállításokat is.
20. Állítsd be az útvonalakat, majd szimulálj mentési hibát; a programon belüli konfigurációnak vissza kell állnia az előző állapotra.

## Windows x64 EXE készítése

A megadott PyInstaller-verzióval készülő egyfájlos build:

```powershell
py -m pip install -r requirements-build.txt
.\build_windows.ps1
```

A kész program a `dist\SynoStream_1.54.exe` útvonalon jelenik meg. A `LICENSE`, az alkalmazásikon és az MPV magyar menüszkriptje erőforrásként kerül az EXE-be, a felhasználói adatok pedig az EXE mappájába íródnak.

Az MPV-letöltéshez és a TMDB-adatokhoz internetkapcsolat szükséges. A NAS-os tesztet azon a hálózaton és Synology DSM-verzión végezd, amelyen használni fogod az alkalmazást.
