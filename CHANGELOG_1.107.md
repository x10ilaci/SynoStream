# SynoStream 1.107

- A videófelbontás (például 720x480) nem válik évad- és epizódszámmá; a 2x05 és S100E01 jelölés továbbra is működik.
- A sample-szűrés közös szabályt használ a beolvasásban, törlésben és torrentválasztásban. A médiatár és a műsor gyökérmappájának neve nem minősít mintának egy teljes műsort.
- Kétlépcsős NAS-bejelentkezéshez választható megbízható eszköz: az egyszeri kódot nem mentjük, a DSM eszköz-tokenjét Windows DPAPI védi, NAS-profilhoz kötve. A háttérműveletek ezt használhatják. Visszavonás a DSM-ben, újraengedélyezés a NAS-kapcsolat beállításaiban.
- Az utolsó HTTP-hibás bejelentkezési kísérlet érthető hibát ad; hibás QuickConnect-közvetítő nem rejti el az érvényeseket.
- Angol MPV-telepítési feliratok; csendes megszakítás; csak 24 óránál régebbi, pontosan azonosított telepítési maradványok biztonságos takarítása.
- A diagnosztika kivételosztályt naplóz, érzékeny hibaüzenetet nem.

A tényleges DSM 2FA / eszköz-token működését ezen a körön belül szimulált NAS-válaszokkal ellenőriztük; élő 2FA-s NAS-próba nem történt.
