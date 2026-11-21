# SynoStream 1.105

- NAS-törléskor a kísérőfájlokat a leghosszabb egyező videónévhez rendeli, a közös Subs mappákban is.
- Az ismeretlen fájlok alapból megmaradnak; törlésükhöz minden alkalommal külön jelölés szükséges.
- A törlés ellenőrzi a teljes fizikai útvonalat, a médiatárgyökeret és a fájlokra mutató átirányításokat. Hiányzó fizikai adatnál nincs törlés.
- A File Station csak dokumentált mezőket kér; a törlési API verziója a NAS támogatásához igazodik, külön 120 másodperces olvasási időkorláttal.
- 778 sikeres automatizált teszt, 6 feltételes kihagyás. Valódi NAS-on törlési próba nem történt.
