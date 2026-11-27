# SynoStream Android 0.5.27

- Az MTS videókat a törlési terv is felismeri: az évadválasztás és a hozzájuk tartozó kiegészítő fájlok takarítása nem hagyja ki őket.
- A protokoll és port nélkül megadott helyi IP-cím / .local cím a DSM helyi HTTP 5000-es portját használja. A teljesen megadott HTTP/HTTPS-cím és egyéni port változatlan marad, a DDNS HTTPS-alapértelmezése is megmarad.
- A regressziós tesztek minden böngészhető videóformátumhoz törlési tervet készítenek, és ellenőrzik a helyi címek útvonalválasztását.

Release, nem hibakereshető APK; a korábbi aláírás megtartásával. Valódi NAS-on nem történt írás vagy törlés.
