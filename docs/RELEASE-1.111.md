# SynoStream 1.111 / Android 0.5.29

A kiadás a NAS-mappaválasztó és a médiatár-frissítés gyorsítását, valamint a kapcsolódó hibajavításokat tartalmazza. A kész binárisok a [Windows](https://github.com/x10ilaci/SynoStream/releases/tag/v1.111) és [Android](https://github.com/x10ilaci/SynoStream/releases/tag/android-v0.5.29) kiadási oldalon érhetők el.

## Ellenőrzés

- Helyben 944 Windows-teszt, 665 Android JVM-teszt és 38 Android kiadási eszközteszt sikeres. A Windows kiadást a GitHub Actions állította elő, saját regressziós és adatvédelmi ellenőrzéseivel.
- A [kiadási Actions-futás](https://github.com/x10ilaci/SynoStream/actions/runs/46134585843) sikeres. A korábbi hibás futások történeti bejegyzések; a kiadási verzió és a tag ellenőrzése megmaradt.
- A GitHubon elkészült Windows EXE külön indulási próbákon is átment, fej nélküli és natív Windows módban. A ZIP-ek sértetlensége, a forrásazonosság, a privát adatok kizárása és az SHA256-értékek ellenőrzöttek.
- Az Android release build, lint és a manifest/aláírás kapuja sikeres. Az APK nem debuggable és nem testOnly. Az aláíró tanúsítvány változatlan; a már telepített hivatalos verzió fölé telepíthető. A nyilvános APK-t visszatöltve is ellenőriztük.
- A kiadások fájljai nem tartalmaznak felhasználói beállításokat, jelszavakat, API-kulcsokat vagy aláírókulcsot. A forrás és a Git-előzmény, valamint a mellékletek adatvédelmi vizsgálata sikeres.

## Teljesítmény

80 ms/kérés késleltetésű szimulált NAS-on a Windows mappaválasztó 10 helyett 1 kérést használt (0,81 helyett 0,08 s). A 40 almappás Windows-bejárás 3,30 helyett 0,90 s; a 30 almappás Android-kontroll 2,90 helyett 1,03 s volt. Androidon 30 változatlan levélmappa frissítése 31 helyett 1 listázást, egy megváltozott mappa 2 listázást igényelt. Ezek nem valós NAS-on mért sebességígéretek.

A törlés fizikaiútvonal-ellenőrzése és az írások bizonytalan kimenetel utáni megismétlésének tilalma megmaradt. A QuickConnect előzetes felébresztő kérését valós NAS-mérés nélkül nem hagytuk el. A korábban jelzett időszakos lejátszási akadás minden eszközön való megszűnését ez a kiadás nem bizonyítja.
