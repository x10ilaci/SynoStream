# Android 0.5.25 ellenőrzés

639 JVM release teszt, 19 kiadási Python-teszt; lintRelease és assembleRelease sikeres.
Az APK manifestje nem hibakereshető és nem testOnly. Aláírása a korábbi kiadásokéval egyezik. Minden melléklet SHA256 értékét, a tiszta Git-munkafát és az APK-hoz tartozó fordítási commitot publikálás előtt ellenőrizzük. A build-provenance.json tartalmazza a tényleges fordítás commitját.
A Play Protect minősítését ez nem garantálja. Élő NAS-módosítást vagy törlést nem végeztünk; ezek szimulált kiszolgálóval teszteltek.
