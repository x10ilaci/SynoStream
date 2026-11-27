# Gyakori kérdések

[Vissza a főoldalra](../README.md) · [Telepítés](INSTALL.md)

## Kell Synology NAS?

Windowson helyi és hálózati médiamappák NAS nélkül is használhatók. Androidon a nyilvános release kiadás használatához NAS-kapcsolat szükséges. A NAS nélküli demó fejlesztői tesztfunkció.

## Kell Video Station vagy külön médiaszerver?

A NAS-os kapcsolat a File Station API-ját használja. Video Station telepítése nem szükséges. A torrentfunkciókhoz Download Station kell.

## Mit tölti le a Download Station?

A NAS-ra hozzáadott torrentfeladatokat a NAS Download Station alkalmazása futtatja. A SynoStream a feladat hozzáadását, a letöltendő fájlok kiválasztását és a feladatok kezelését biztosítja. Az NFO alapból kijelölt lehet; a sample fájlok alapból kimaradnak.

## Miért nincs borító vagy miért téves a cím?

Ellenőrizd a TMDB API-kulcsot és az internetkapcsolatot. A program fájlnév, mappanév és NFO alapján keres, de a kiadói rövidítések és félrevezető nevek okozhatnak hibás találatot. A kártyán kézzel is megadható a médiainformáció. Hibajelentéshez fiktív vagy személyes adatot nem tartalmazó fájlnév/mappanév példa segít.

## Miért külső lejátszó indul?

A SynoStream a médiatárat és a NAS-kapcsolatot kezeli. Windowson az MPV, Androidon a kiválasztott videólejátszó dekódolja a fájlt. Az Android-hangsávválasztás a fájltól és a lejátszó támogatásától is függhet.

## Külön fel kell venni a helyi és a távoli NAS-mappát?

A NAS-forrásmappát egyszer kell kiválasztani. A kapcsolati elérések a NAS-profilhoz tartoznak; a program ezek között választ. [Kapcsolati sorrend és példák](INSTALL.md#nas-kapcsolat)

## Törlés

A kukaikon **valódi fájltörlést** kezdeményez a NAS-on. A tételes lista jóváhagyást kér; sorozatnál évadok választhatók. Az ismeretlen fájlok alapból megmaradnak, törlésükhöz külön jelölés szükséges. A program az üresen maradó mappákat takarítja, de a médiatár gyökerét megőrzi. A NAS lomtárának működése a NAS beállításaitól függ.

Ezzel szemben a kártya elrejtése a megjelenítést kezeli; nem azonos a NAS-fájlok törlésével.

## Telepítési figyelmeztetések

**Windows:** a jelenlegi EXE nincs Authenticode-tanúsítvánnyal aláírva. A kiadási SHA256 ellenőrzőösszeg a fájl egyezését ellenőrzi, nem helyettesíti a vírusellenőrzést. A hivatalos fájlokat ebből a GitHub-tárból töltsd le.

**Android:** a 0.5.26 már nem hibakereshető release build. A korábbi tanúsítványt az adatmegőrző frissítés érdekében megtartottuk; a tanúsítvány történeti neve és az APK hibakereshetősége két külön dolog.

Ha a **Play Protect kártékonynak minősíti vagy letiltja** az alkalmazást, őrizd meg a pontos szöveget, a verziószámot és lehetőleg egy személyes adatot nem tartalmazó képernyőképet. A release build önmagában nem garantál Google-jóváhagyást. Ne kapcsold ki a védelmet az ellenőrzés helyett; a jelzést ki kell vizsgálni. [Google tájékoztató a figyelmeztetésekről](https://developers.google.com/android/play-protect/warning-dev-guidance)

## Miért kér telepítési jóváhagyást az Android-frissítés?

A GitHubról érkező APK-t a rendszer telepítője telepíti, a felhasználó engedélyével. A SynoStream ellenőrzi az azonosítót, verziót, fájlméretet, SHA256-értéket és aláíró tanúsítványt. Ezek nem jelentik a Play Protect vizsgálatának megkerülését.

## Hol jelezzek hibát?

[Nyiss hibajegyet a sablonnal](https://github.com/x10ilaci/SynoStream/issues/new/choose). Add meg a platformot, verziót, a reprodukció lépéseit és a tényleges hibaüzenetet. NAS-jelszót, API-kulcsot, OTP-kódot, munkamenet-azonosítót és teljes privát naplót ne tegyél közzé. Biztonsági hibához a [biztonsági bejelentési útmutatót](../SECURITY.md) használd.
