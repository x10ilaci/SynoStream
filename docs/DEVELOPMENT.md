# Fejlesztői útmutató

[Vissza a főoldalra](../README.md) · [Közreműködés](../CONTRIBUTING.md)

A kész alkalmazásokhoz nincs szükség fejlesztőkörnyezetre. Ez az oldal a forráskódból való indítást és fordítást írja le.

## A tár felépítése

| Hely | Tartalom |
|---|---|
| `SynoStream_1.106.py` és `synostream_*.py` | Windows alkalmazás és közös feladatokat ellátó Python-modulok |
| `tests/` | Windows-regressziós tesztek |
| `assets/`, `licenses/` | Saját vizuális eszközök és licenctájékoztatók |
| `android/` | Natív Java Android-alkalmazás |
| `android/app/src/test/` | JVM-tesztek |
| `android/app/src/androidTest/` | Emulátoros és eszköztesztek |
| `docs/` | Felhasználói és fejlesztői dokumentáció |
| `.github/` | CI és hibajegysablonok |

## Windows forrásból

Windows 10/11, Python 3.13. A tár gyökerében:

```powershell
py -3.13 -m pip install -r requirements.txt -r requirements-dev.txt
py -3.13 SynoStream_1.106.py
```

Tesztek:

```powershell
py -3.13 -m pytest -q
```

EXE készítése:

```powershell
py -3.13 -m pip install -r requirements-build.txt
./build_windows.ps1 -SkipDependencyInstall
```

A teljes ellenőrzési útmutató: [TESTING.md](../TESTING.md). A tesztek elkülönített adatokat és fake NAS-t használjanak. A valódi NAS-hoz kötött tesztek külön előfeltételeket igényelnek; ne indíts destruktív tesztet saját médiatár ellen.

## Android forrásból

JDK 17 és Android SDK szükséges. A pontos SDK-, build-tools- és függőségverziókat az [app/build.gradle](../android/app/build.gradle) rögzíti. A Gradle Wrapper a tár része.

```powershell
cd android
./gradlew.bat testDebugUnitTest lintDebug
./gradlew.bat assembleDebug
```

Ez fejlesztői build. **Nyilvános APK-hoz kizárólag a release folyamat használható:**

```powershell
./build_release.ps1
```

A script release-változaton futtatja a teszteket és lintet, elkészíti az APK-t, majd meghívja az [APK-ellenőrzőt](../android/verify_release.py). A hibakereshető vagy `testOnly` APK nem publikálható. A helyi aláírókulcs nincs a tárban; más kulccsal készített build nem a hivatalos frissítési csatornához tartozik.

Részletek: [Android kiadási csatorna](../android/UPDATE_CHANNEL.md), [kiadási szabályok](../android/AGENTS.md), [aláírási politika](../CODE_SIGNING_POLICY.md).

## Dokumentáció és kiadás

Dokumentációs módosítás önmagában nem igényel új alkalmazásverziót vagy bináris kiadást. Kiadásnál együtt frissítendő a főoldal letöltési táblázata, az angol README, a letöltőkártyák verziószáma, a telepítési útmutató és a kapcsolódó kiadási jegyzet. A közvetlen linkek a feltöltött, ellenőrzött mellékletekre mutassanak.

A Windows `latest` kiadását az Android-kiadások nem válthatják le. A két platform verziószáma és frissítési csatornája külön kezelt. Egy már nyilvános bináris vagy kiadási melléklet nem írható felül más tartalommal; javításhoz új verzió szükséges.
