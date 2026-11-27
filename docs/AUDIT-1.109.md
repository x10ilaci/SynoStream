# SynoStream 1.109 / Android 0.5.27 – önálló hibakeresés

A javítás előtti célzott futás 11 hibás Windows-tesztesetet és 2 hibás Android-tesztet adott. A javítás után a teljes Windows-kör 907 sikeres és 0 kihagyott teszt, az Android-kör 648 sikeres release JVM-teszt. A kiadási Python-kör 31 tesztje sikeres.

| Terület | Reprodukált hiba | Javítás és ellenőrzés |
|---|---|---|
| Windows beolvasás | A műsor alatti Samples/Extras videói külön kártyára / epizódlistába kerültek. | Helyi és NAS-listázás a kártya gyökere alatti mappákat szűri; a Samples nevű médiatár és műsor megmarad. |
| Formátumok | A Windows kihagyta a WMV/MTS/M2TS/MPG/MPEG/WebM videókat; az Android törlés nem ismerte az MTS-t. | Közös Windows-formátumlista; Android törlési terv mind a 12 böngészhető formátumra tesztelve. A formátumtesztek felismerést és törlési tervet vizsgálnak, nem az összes kodek dekódolását. |
| Windows NAS-stream | Olvasási hibánál az upstream nem zárult be, és második HTTP-válasz kerülhetett a videófolyamba. | Mindkét proxy biztosan bezárja a választ; a megkezdett videófolyamba nem ír HTTP-hibaoldalt. Valódi socketes megszakítási tesztek és MPV-dekódolás helyi tesztadatfolyamon. |
| Android helyi kapcsolat | A protokoll nélküli privát IP a 443-as portra mutatott. | DSM helyi HTTP 5000 alapértelmezés a pusztán megadott privát címnél; explicit URL/port és DDNS változatlan. |
| Windows felirat | Hibás karakterkódolású helyi NAS-cím hibaüzenet. | Olvasható magyar szöveg és ellenőrzött angol fordítás. |

A NAS-próbák fake fájlrendszert / helyi tesztkiszolgálót használnak. Valódi NAS-on nem történt írás vagy törlés. Az APK release, nem hibakereshető, nem testOnly, és a korábbi tanúsítvánnyal aláírt. A Play Protect besorolást ez nem garantálja.
