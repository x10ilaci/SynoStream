# Ellenőrzés – Android 0.5.19

2026-11-21

- JVM: 588 teszt, 0 hiba/kihagyás; ebből 8 új frissítési/protokollteszt. Lint: 0 hiba / 17 korábbi figyelmeztetés.
- Az APK és az instrumentációs csomag offline fordítása sikeres.
- API 36 emulátoron 17 célzott próba: 5 új ellenőrzés (verzió/aláírás, szűkített fájlmegosztás, beállításkapcsoló, telepítő-intent, egyszeri automatikus és kézi ellenőrzés) és 12 korábbi NAS-törlési/torrent-/médiatár-regresszió.
- Külön, tiltott telepítési engedéllyel 1 sikeres beállításmegnyitási próba. Az engedély módosítása folyamaton kívül történt, mert Android az engedély visszavonásakor leállíthatja a folyamatot. A rendszer nagybetűs gombszövege miatt a teszt kis-/nagybetűtől független keresést használ.
- Külön 2 sikeres próba: valódi nyilvános GitHub-feed és APK letöltése az app Java hálózati kódjával, valamint ellenőrzőösszeg/aláírás elutasítása hibás adatoknál.
- A frissítővel egy 23-as verziókódú, ugyanebből a forrásból fordított tesztalapról az Android rendszertelepítőjével ténylegesen felment a végleges, 24-es verziókódú APK. A telepítés után a tesztadat megmaradt. A teszt nem valódi felhasználói profilt használt.
- A telepített, emulátorról visszaolvasott és kiadott APK byte-azonos. Az aláírás megegyezik az előző kiadáséval.
- A félbehagyott, túl nagy, sérült letöltések, hibás metaadatok és nem engedélyezett URL-ek kezelése tesztelt. Valódi NAS-adatok törlése nem történt.
- Fizikai telefonos és minden Android-verzióra kiterjedő telepítési próba nem történt. A rendszer felhasználói jóváhagyását az app nem kerüli meg.
- A forrás-ZIP build/adat/privát aláírókulcs nélküli; integritás és személyes titkok vizsgálata külön ellenőrzött.
