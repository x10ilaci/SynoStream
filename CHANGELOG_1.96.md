# SynoStream 1.96

- Javítva: sikertelen frissítés után a hibásan indult program mappája többé nem blokkolja az újrapróbálást. A hibás példány külön néven megmarad.
- Javítva: a sikeres frissítések ideiglenes segédfájljai nem halmozódnak korlátlanul. A program csak a saját, ellenőrzött és már lezárt frissítési munkamappáit takarítja; az adatokhoz és mentésekhez nem nyúl.
- Telepítés előtt még a futó program újra ellenőrzi a letöltött EXE-t. Hiányzó vagy megváltoztatott fájl miatt nem zárja be magát.
- Az indulási visszajelzés csak a Letöltések mappában lévő, megfelelő verzióhoz és azonosítóhoz tartozó frissítési feladatba írható.
- A Programfrissítés beállításai azonnal követik a kezelőfelület nyelvváltását.
- Megerősített kiadási ellenőrzés: felhasználói adatfájlok és másolataik, adatbázisok, naplók, környezeti fájlok, privát kulcsok és tokenminták tiltása. A tömörített csomagok tartalmát és az EXE-be csomagolt Python-kódot is ellenőrzi.
- A feltöltés előtti ellenőrzések optimalizált Python-futtatásnál sem kapcsolhatók ki. A GitHubra továbbra is csak a név szerint engedélyezett öt kiadási fájl tölthető fel.

Az 1.95-ös Windows-verzió beépített frissítőjéből telepíthető. A beállítások, hitelesítőadatok és médiapárosítások megmaradnak. A korábbi kiadások és az eredeti v1.54 változatlanok.
