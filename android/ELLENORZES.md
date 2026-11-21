# Ellenőrzés – Android 0.5.22

618 JVM teszt sikeres; lint 0 hiba, 17 korábbi figyelmeztetés.

32 Android-tesztosztály: 121 sikeres, 4 feltételes kihagyás, 0 hiba. Az első kör három sikertelen esetét az emulátor indulási elakadása és a felületi próbával párhuzamos, tesztállapotot átíró automatikus beolvasás okozta; a felületi tesztekben a beolvasást kikapcsoltuk, az automatikus működés tesztjében külön bekapcsoltuk. Az érintett teljes csoportok sikeres ismétlése szerepel a végső összesítésben. A tiltott telepítési engedély ága külön további 1/1 sikeres. Élő NAS-t igénylő tesztet nem indítottunk. Valódi NAS-on törlés, fizikai telefon és mobilhálózati forgalom nem volt tesztelve.

Az ajánló korábban átírt cache-válaszait újratölti a visszajelzések elvesztése nélkül; lejárt fordítást nem alkalmaz és a lokalizált leírásokat is korlátozza. Ezek külön regressziós teszteket kaptak.

A védett modulok, manifest, SDK, függőségek, aláírási beállítások és Vissza-kezelés változatlanok. A frissítési csatorna a közzététel után külön ellenőrzést kap.
