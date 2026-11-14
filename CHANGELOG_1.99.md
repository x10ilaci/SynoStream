# SynoStream 1.99 – forrásmappák mentésének javítása

- A forrásmappák mentése megőrzi a már jóváhagyott összevonást, ha még tart a beolvasás, párosításszinkron vagy lejátszás.
- A mentés ilyen esetben normál várakozási jelzést mutat, majd a háttérművelet befejezése után automatikusan megtörténik; nem kell újra összevonni vagy a Mentésre kattintani.
- A forrásmappa-szerkesztő megnyitása alatt nem indul új beolvasás vagy párosításszinkron. Az elhalasztott kérések az ablak bezárása után folytatódnak, a teljes ellenőrzés kérésének megőrzésével.
- A Mégse és az ablak bezárása törli a várakozó mentést. Tényleges mentési hiba esetén a jóváhagyott összevonás megmarad az újrapróbáláshoz.

Lejátszás közben az elérések biztonságos módosításához továbbra is be kell zárni a lejátszót. Aktív adatbázis-műveletet a program nem szakít félbe.

A kiadás a beépített frissítőből is letölthető. A korábbi kiadások és az eredeti v1.54 változatlanok.
