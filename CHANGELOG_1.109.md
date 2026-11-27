# SynoStream 1.109

- A műsor alatti Sample/Samples/Extras/Proof mappák videói nem kerülnek külön kártyára vagy az epizódlistába. A médiatár vagy a műsor saját, Samples nevű gyökere továbbra is használható. Helyi és NAS-beolvasás egyaránt javítva.
- Egységes videóformátum-lista: a WMV, MTS, M2TS, MPG, MPEG és WebM fájlok is megjelennek a Windows médiatárban, és a törlési terv videóként kezeli őket.
- Megszakadó NAS-streamnél az upstream kapcsolat minden esetben bezárul. A proxy nem ír második HTTP-hibaválaszt a már megkezdett videófolyamba. Mindkét lejátszási proxy javítva.
- Helyreállított magyar helyi NAS-cím validációs üzenet, angol fordítással.

A hibákat célzott tesztek reprodukálták a javítás előtt. Valódi NAS-on nem történt írás vagy törlés; a NAS-próbák helyi tesztkiszolgálót használnak.
