# Ellenőrzés és tesztelés

[Fejlesztői útmutató](docs/DEVELOPMENT.md) · [Kiadási és aláírási politika](CODE_SIGNING_POLICY.md)

## Legutóbbi dokumentált eredmények

2026-11-22-i állapot; ezek a megnevezett kiadások ellenőrzései, nem minden későbbi commitra vonatkozó garanciák.

| Kiadás | Ellenőrzés | Eredmény |
|---|---|---|
| Windows 1.106 | Teljes pytest-készlet | 813 sikeres, 6 feltételes kihagyás |
| Windows 1.106 | Csomagolt EXE | 3 offscreen és 2 natív indulási/ablak-/ikonpróba sikeres; sérült verziójelző kezelése ellenőrzött |
| Android 0.5.24 | `testReleaseUnitTest` | 632 sikeres |
| Android 0.5.24 | `lintRelease` | 0 hiba, 17 korábbi figyelmeztetés |
| Android 0.5.24 | APK-ellenőrző | Nem hibakereshető, nem testOnly, érvényes és változatlan aláírás; a korábbi debug APK visszautasítása ellenőrzött |
| Android 0.5.24 | API 36 emulátoros frissítés | A debug 0.5.23 fölé települt; a privát tesztadat megmaradt, a telepített APK byte-ra egyezett a kiadási fájllal |

A Windows ZIP-ek tartalma, a forrásegyezés, az EXE-be került javított modulok, a nyilvános mellékletek mérete és SHA256-értéke ellenőrzött. Az Android 0.5.22-n végzett korábbi teljes emulátoros készletet a 0.5.24-re nem ismételtük meg.

**Korlátok:** valódi NAS-on destruktív törlési próba, fizikai telefonos Play Protect-vizsgálat és hosszú, változó valós hálózati terheléses teszt nem történt. A működési tesztek nem jelentenek vírusvédelmi minősítést.

## Windows-tesztek futtatása

A tár gyökerében, Python 3.13-mal:

```powershell
py -3.13 -m pip install -r requirements.txt -r requirements-dev.txt
py -3.13 -m pytest -q
```

A tesztek elkülönített adatmappát, szintetikus médiaadatokat és helyi fake NAS-végpontokat használnak. A valódi MPV-t vagy natív Windows-felületet igénylő esetek további előfeltételekhez kötöttek. A dekódolási próbához a `SYNOSTREAM_TEST_MPV` környezeti változóban adható meg egy telepített `mpv.exe`.

A fontosabb regressziók: cím-/év-/évadfelismerés; beállításmentés és visszaállítás; munkamenet-megújítás; QuickConnect-címellenőrzés; stream és mappalista párhuzamossága; törlési tervek, fizikai útvonalak és ismeretlen fájlok; MPV-telepítő könyvtárcseréje és visszaállítása; modális ablakok és főablakállapot.

## Android-tesztek futtatása

JDK 17 és a projektben rögzített Android SDK szükséges:

```powershell
cd android
./gradlew.bat testDebugUnitTest lintDebug
```

Kiadási változat és terjesztési ellenőrzés:

```powershell
./build_release.ps1
```

A JVM-készlet többek között a párosításmentés alatti párhuzamos lekéréseket, egyszeri munkamenet-megújítást, sample-szabályokat, törlési hibakategóriákat, megszakítást és részleges törlési hibát vizsgálja. A NAS-törlések fake végpontokon vagy memóriabeli fájlrendszeren történnek.

Az `app/src/androidTest` alatti élő NAS-t igénylő osztályok csak elkülönített, erre létrehozott teszt-NAS-sal futtathatók. Személyes médiatár vagy privát hitelesítő adat nem lehet tesztfixture.

## Kézi kiadásellenőrzés

- Tiszta indulás és frissítés meglévő alkalmazásadatokkal.
- Film- és sorozatnézet, keresés, rendezés, részletezőablakok bezárása.
- Helyi hálózat, DDNS és QuickConnect közti váltás, megszakadt kapcsolat.
- Új és eltávolított tartalom ellenőrzése, meglévő médiainformációk megőrzése.
- Lejátszás a tényleges MPV-/Android-lejátszóval, eltérő konténerek és hangsávok.
- Download Station-előkészítés, fájlkijelölés és megszakítás.
- NAS-törlés kizárólag külön, feláldozható tesztmappán.
- Kiadási mellékletek, aláírás, SHA256 és frissítési csatorna ellenőrzése.

A konkrét próbák eredményét és a kimaradt előfeltételeket a kiadás mellett kell rögzíteni.
