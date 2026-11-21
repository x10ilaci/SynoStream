# Változások – Android 0.5.22

1. A kísérőfájlt a megfelelő mappában lévő, leghosszabb egyező videótörzsnévhez rendeli. A közös Subs/Extras mappák hozzárendelése is ellenőrzött.
2. Az owned mappák ismeretlen fájljai külön listában jelennek meg és alapból megmaradnak. Törlésükhöz minden új ablakban külön, alapból üres jelölőnégyzetet kell bekapcsolni. A végrehajtás az elfogadott listát újraellenőrzi.
3. Hiányzó fizikai útvonalnál nincs törlés. A kiválasztott gyökér és a gyermekek fizikai elhelyezkedését a konfigurált médiatárhoz ellenőrzi; a gyökérmappás és azonos mappán belüli linkek sem kerülhetik meg az ellenőrzést. A megosztáslista a saját dokumentált mezőit kéri. A törlési API verziója az API.Info tartományához igazodik, külön 120 másodperces olvasási időkorláttal; bizonytalan írás nem ismétlődik.
4. Automatikus médiatár-frissítés: Ki / 5 / 15 / 60 perc, alapból 5 perc. Mobilhálózaton alapból tiltott. Az automatikus ág nem indít ScanService-t vagy állandó értesítést; háttérbe kerüléskor megszakad, a függő jelzés megmarad. A kézi/force beolvasás előtér-szolgáltatása változatlan.
5. Az ajánló a cache-ből kapott elemek másolatát lokalizálja. A megjelenített visszajelzés megőrizhető anélkül, hogy az eredeti cache-címet és -leírást átírná.
6. Az új ajánlói leírás legfeljebb 600 karakter, szóhatáron rövidítve. Az állapot olvasása és feldolgozása háttérszálon történik, Betöltés… felülettel; a korábbi mentett állapot olvasható marad.

A HTTP-sémakezelés, a Vissza-kezelés, a megjelölt védett modulok, a frissítő, a manifest, a targetSdk, a függőségek és az aláírási beállítások változatlanok. A frissítő aláírása és a korábbi alkalmazásadatok megmaradnak.

7. A korábbi megjelenítés által átírt ajánló-cache érintett válaszait újratölti, a visszajelzéseket megőrizve. Lejárt magyar fordítás nem írhatja felül az új találatot; a magyar leírás mérete is korlátozott.
