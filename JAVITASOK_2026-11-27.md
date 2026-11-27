# Forrásjavítások – 2026-11-27

A javítások a Windows 1.108 és az Android 0.5.26 kiadásba kerültek. A korábbi kiadások fájljai változatlanok.

- Windows NxM epizódjelölés: a HDTV, v2 és x264 folytatás elfogadott; a külön p/i felbontásjelölés továbbra sem epizódszám.
- Közös méretalapú sample-előtag kezelés mindkét platformon: legfeljebb 150 × 1024 × 1024 bájt, vagy az ugyanazon mappa legnagyobb videójának szigorúan 10%-a alatt. Méret nélkül marad a korábbi névszabály. Beolvasás, epizódlista, torrentajánlott kijelölés és törlési terv használja. A torrentfájlok kézzel továbbra is kijelölhetők.
- Windows: a hálózati lejátszási bejelentkezés a globális zár kívül fut; párhuzamos kérésnél egy kliens marad, a felesleges / időközben érvénytelenített kliens bezárul.
- Windows: megszűnt a duplázott kivételosztály-naplózás. A device_id, did és otp_code URL-paraméterek kitakarva jelennek meg. Ha a DSM nem jegyzi meg a kért eszközt, magyar/angol figyelmeztetés jelenik meg.
- Android: záró perjeles könyvtárgyökér normalizálása. Ismeretlen NAS-fájlméret nem számít méretbizonyítéknak.
- Android kiadási eszköz: a tároló és a kiadási melléklet feedjének összes frissítési adatát összeveti. Azonos kiadásnál az eltérés hiba. Hiányzó, illetve verzió és verziókód szerint egyaránt korábbi feednél figyelmeztet, mert az élő feed a publikálás után áll át. A feedből a build_commit elhagyható, a kiadási mellékletből nem.

Ellenőrzés: 888 sikeres Windows-teszt, 6 kihagyott; 645 sikeres Android release JVM-teszt; 31 sikeres Python kiadásellenőrző teszt. Az egy Windows-figyelmeztetés egy szándékosan hibás ZIP-tesztfájlhoz tartozik. Valódi NAS-on nem történt törlés vagy írás. A manifest, SDK, függőségek és aláírás változatlanok.
