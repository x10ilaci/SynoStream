# SynoStream Android 0.5.25

- Közös sample-szűrés a médiabeolvasásban, törlésben és torrent-fájlkiválasztásban; a médiatár és a műsor gyökere nem sample-almappa.
- Pontos API-specifikus hiba, ha a NAS-on nem érhető el törlés, feltöltés vagy Download Station.
- A nyilvános HTTP-kapcsolathoz szükséges jóváhagyás újracsatlakozáskor is érvényesül; magyar és angol figyelmeztetés.
- A párosítási gyorsítótár és írási zárolás a munkamenetek között is közös. Kompakt generációindex csökkenti a nagy párosítási állományhalmaz újraolvasását; ismeretlen módosítási időnél nem bízunk a gyorsítótárban.
- A kiadási ellenőrzés minden melléklet hashét, a tiszta Git-munkafát, a fordítás commitját és az APK tényleges metaadatait ellenőrzi, még hálózati feltöltés előtt.

Release, nem hibakereshető APK; a korábbi aláírás megmarad. Kulcscsere és a meglévő privát kulcs jelszavának módosítása nem történt.
