# Ellenőrzés – Android 0.5.18

2026-11-21

- JVM: 580 teszt, 0 hiba/kihagyás. Lint: 0 hiba / 17 korábbi figyelmeztetés.
- Offline assembleDebug és assembleDebugAndroidTest sikeres.
- Android API 36 emulátoron 12 célzott műszeres teszt: a törlés megerősítése és megszakítása; másik film megőrzése; egy évad törlése a másik és a közös NFO megőrzésével; megváltozott mappa esetén nulla törlési írás; továbbá a 0.5.16–0.5.17 kilenc frissítési/torrent/cache regressziója.
- A korábbi futtatásokat a hidegen indult emulátor System UI ANR-ablaka és tesztfixture-időzítési hibák zavarták meg (függő szolgáltatás idő előtti leállítása; kattintás utáni aszinkron indítás kivárása). A fixture-ek javítása után a végleges csomag teljes célzott próbája sikeres. A szolgáltatás minden indításkor külön is megerősíti az előtérbeli állapotát.
- Recognition, MediaLogic, EpisodeIndex, Nfo, Pairings, NasRoutes, NasProfile, Store, CacheIo, CacheKeys és LibraryRefresh változatlan az előző kiadáshoz képest.
- A buildelt, az emulátorról visszaolvasott és a kiadott APK byte-azonos; az aláírás egyezik az előző verzióéval.
- Valódi NAS-adatok törlése nem történt. A törlési próbák kizárólag helyi, mesterséges NAS-fixture-ön futottak; fizikai telefonos próba nem történt.
- A forrás-ZIP build/adat/privát aláírókulcs nélküli; integritása és az APK-val együtt a személyes titkoktól való mentessége ellenőrzött.
- GitHub-publikálás nem történt. Az előző verzió mappája változatlan.
