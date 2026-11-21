# Matroska CRC – csak ellenőrzés

A MatroskaAudio.java nem változott a 0.5.1-hez képest. SHA-256: c65a4732204916dc14451c1ab20287b58af749e71352d036047397a06e04b5da

A MatroskaCrcAuditTest két tesztje lefutott és sikeres:

- 200 determinisztikusan véletlenített szintetikus EBML-fejléc, fejlécenként 2–6 hangsáv. A CRC-elemek a Tracks és a TrackEntry szinteken, változó helyen szerepelnek. A mezősorrend, a jelzők és a kitöltés változik; egy- és többbájtos hosszmezők is előfordulnak. Minden hangsáv kiválasztásának patch-e után minden érintett CRC egyezik egy külön, bitenkénti CRC32-számítással.
- Teljes Segment CRC esetén a meglévő megvalósítás biztonságosan nem patch-el. A változatlan fejléc ellenőrzőösszegei függetlenül ellenőrizve érvényesek.

A vizsgált esetekben nem találtam CRC-hibát. Ez véges, szintetikus tesztkészlet, nem minden lehetséges médiakonténerre vonatkozó formális bizonyítás és nem valódi filmlejátszási teszt. A kérés szerint CRC-javítás nem történt.
