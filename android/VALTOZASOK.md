# SynoStream Android 0.5.28 – helyi lejátszási próbaverzió

- TCP_NODELAY és pufferelt HTTP-fejléc olvasás a helyi streamhídon, a kis adatblokkok indokolatlan várakoztatásának csökkentésére.
- A médiafájlokat tömörítés nélkül kérjük, hogy a Range-eltolások és Content-Length az eredeti bájtokhoz tartozzanak.
- Aktív stream és rövid lejátszási türelmi idő alatt az automatikus médiatár-beolvasás halasztódik. A kézzel indított műveleteket nem tiltjuk le.

A több eszközön jelzett időszakos akadás teljes okát még nem bizonyítottuk. A módosításokat byte-azonossági, valódi loopback socketes és regressziós tesztek ellenőrzik; készülékes összehasonlító próba szükséges. Release APK, korábbi aláírással.
