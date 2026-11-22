# Kiadási és aláírási politika

## Windows

A jelenlegi Windows EXE **nincs Authenticode-aláírással ellátva**. A SHA256 és a frissítési leíró fájlhash-ei integritást ellenőriznek, nem jelentenek kódaláírást vagy vírusvédelmi minősítést.

A SignPath-workflow előkészített infrastruktúra; jelenléte nem jelent aktív tanúsítványt. Egy későbbi aláírási integrációhoz külön beállítás és karbantartói döntés szükséges.

## Android

A 0.5.24-től közzétett APK-k **release buildváltozatok**, kikapcsolt Java- és natív hibakereséssel. A [verify_release.py](android/verify_release.py) az elkészült APK-n ellenőrzi a csomagazonosítót, verziót, `debuggable` és `testOnly` jelzőket, az érvényes aláírást és a meglévő tanúsítvány egyezését. A [publish_android.py](android/publish_android.py) feltöltés előtt kötelezően futtatja ezt az ellenőrzést.

A korábbi telepítésekkel kompatibilis aláírókulcsot megőrizzük. A tanúsítvány történeti neve Android Debug; ez különbözik az APK hibakereshetőségi jelzőjétől. Más kulcsra váltás külön migrációs tervet igényelne. A privát kulcs nincs a GitHub-tárban, az APK-ban vagy a forrás-ZIP-ben.

A Play Protect minősítése független a release buildellenőrzéstől. Figyelmeztetés esetén a pontos jelzést ki kell vizsgálni; téves minősítésnél a Google hivatalos felülvizsgálati eljárása használható.

## Közzététel

1. A forrás és a verziók ellenőrzése, platformnak megfelelő tesztekkel.
2. A kiadási mellékletek és metaadatok tartalmi, aláírási és SHA256-ellenőrzése.
3. Privát adatok, hitelesítő adatok és kulcsok kizárása a forrásból és csomagokból.
4. Feltöltés először draftként; nyilvánossá tétel csak teljes, ellenőrzött mellékletkészlettel.
5. A nyilvános mellékletek és a frissítési csatorna visszaellenőrzése.

A nyilvános mellékleteket nem írjuk felül új tartalommal. A Windows és Android külön tag-/frissítési csatornát használ; Androidnál `make_latest=false` kötelező, hogy a Windows-frissítő továbbra is a Windows-kiadást kapja.

Karbantartó: [@x10ilaci](https://github.com/x10ilaci). Biztonsági hibához: [SECURITY.md](SECURITY.md).
