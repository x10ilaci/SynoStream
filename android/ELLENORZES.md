# Ellenőrzés – Android 0.5.20

2026-11-21

- JVM: 600 teszt, 0 hiba/kihagyás; 12 új ajánlási teszt. Lint: 0 hiba / 17 korábbi figyelmeztetés.
- API 36 emulátoron 15 célzott próba: három új Ajánló-folyamat és a 12 korábbi NAS-törlési/torrent-/médiatár-regresszió.
- Ellenőrzött: meglévő TMDB-azonosítók kizárása más médiatárból is; mentett érdeklődés megőrzése és médiatárak elkülönítése; új csomag ismétlés nélkül elegendő jelölt mellett; Vissza gomb a médiatárhoz; hiányzó API-kulcs üzenete.
- Unit szinten: típusazonosság, cache és lejárat/nyelvi elválasztás, pozitív/negatív visszajelzés és visszaállítás, részleges hálózati hiba, megszakítás, üres találat cache-elése, legfeljebb 4 párhuzamos kérés, magyar fordítás ellenőrzése, már meglévő címek kihagyása a nyelvi ellenőrzésből.
- Az emulátor kezdeti System UI ANR-ablaka és egy tesztben rögzített hibás médiatár-azonosító javítása után a végső célzott újrafuttatás sikeres.
- A fő APK és a telepített példány byte-egyezése, az aláírás folytonossága, ZIP/SHA256 integritás és személyes titkoktól való mentesség külön ellenőrzött.
- A felületi próbák mesterséges NAS/TMDB-adatokkal futottak; valódi NAS-törlés és fizikai telefonos próba nem történt.
- A közzétett GitHub-kiadásból a 0.5.19-es app frissítését a publikálás után külön ellenőrizzük; a nyilvános kiadási csatorna stabil Android update.json címe megmaradt.
