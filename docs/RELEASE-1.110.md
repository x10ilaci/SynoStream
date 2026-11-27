# SynoStream 1.110 / Android 0.5.28

## Lejátszás

- A Windows-proxy 1 MiB helyett legfeljebb 32 KiB-os egységekben továbbít. A kontrollált tesztben a régi kód egy már megérkezett 64 KiB-os adagot is visszatartott, amíg a nagyobb blokkra várt; a javított kód a teljes adat megérkezése előtt továbbít.
- TCP_NODELAY a loopback kapcsolatokon, Androidon pufferelt HTTP-fejléc-olvasás. A média eredeti bájtjait identity kódolással kérjük, a Range és Content-Length helyességéhez.
- Aktív lejátszásnál az automatikus médiatár-frissítés, és a Windows háttérben maradt torrentoldalának pollja elhalasztódik. A kézi műveletek használhatók.
- A Windows napló az aktuális NAS-útvonal típusát is rögzíti, cím és belépési adat nélkül.

Az időszakos kép- és hangakadás teljes okát még nem sikerült valós eszközön bizonyítani. A korábban futó Windows-lejátszás rövid mérése kb. 120 másodperces puffert, nulla képkockaeldobást és minimális A/V-eltérést mutatott. A laboreredmények nem bizonyítják minden akadás megszűnését.

## Kiadási automatizmus

Az 1.107–1.109 tagfutások a verzióellenőrzésnél hibáztak: a release_version.txt 1.106 maradt. A frissített automatizmus közös verziófájlból épít, és a program APP_VERSION értékét, entry pointját, changelogját, valamint a tag nevét is ellenőrzi. A pre-push hook is megállítja az eltérést. A Windows és Android kiadási Python-tesztek külön könyvtárból indulnak.

[GitHubon ellenőrzött futás](https://github.com/x10ilaci/SynoStream/actions/runs/46000146714). A régi hibás futások történeti bejegyzések; a korábbi kiadási fájlokat nem írtuk felül.

Helyi ellenőrzés: 912 Windows alkalmazásteszt (MPV-próbákkal), 651 Android release JVM-teszt, 31 kiadási Python-teszt, továbbá a verzióellenőrző új regressziós tesztjei sikeresek. A kész EXE indítása és a csomagok privátadat-vizsgálata sikeres. Az APK nem hibakereshető és nem testOnly, aláírása a korábbi kiadásokéval egyezik.
