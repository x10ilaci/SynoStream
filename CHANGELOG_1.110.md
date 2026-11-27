# SynoStream 1.110 – helyi lejátszási próbaverzió

- A NAS-proxy 1 MiB helyett legfeljebb 32 KiB-os blokkokban továbbít; a kiszolgáló nem vár egy teljes megabájtra, miközben kisebb adag már elérhető. Kontrollált, megakasztott feltöltésű teszt reprodukálta a korábbi késleltetést mindkét proxyban.
- TCP_NODELAY a loopback lejátszási kapcsolatokon; a média eredeti bájtjait Accept-Encoding: identity kéréssel olvassuk.
- Aktív MPV-lejátszás alatt elhalasztja az időszakos médiatár-beolvasást. A háttérben maradt torrentoldal sem kérdezgeti a NAS-t, ha a külső lejátszó aktív; a kézi műveletek elérhetők maradnak.
- A lejátszási napló a ténylegesen létrejött NAS-útvonal típusát rögzíti, cím és belépési adat nélkül.

A jelentett időszakos kép- és hangakadás teljes okát még nem sikerült valós eszközön reprodukálni. A futó Windows-lejátszás rövid, csak olvasó MPV-mérése körülbelül 120 másodperces előrepuffert, nulla eldobott képkockát és minimális A/V-eltérést mutatott. A teszt javítható továbbítási késleltetést igazolt; nem bizonyítja minden akadás megszűnését.
