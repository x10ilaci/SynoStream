# SynoStream Android 0.5.23

- A párosításmentés külön zárral és esemény-gyorsítótárral dolgozik; hálózati várakozás közben nem fogja a kliens közös monitorát.
- A párhuzamos stream- és feltöltési kérések csak egyszer újítják meg a lejárt munkamenetet.
- Pontosabb sample-felismerés; a médiatár és a kártya saját neve nem kizáró ok.
- Nyilvános HTTP-címekhez egyszer elfogadható figyelmeztetés; a HTTP továbbra is használható.
- Külön hibajelzés a biztosan elutasított és a bizonytalan eredményű törléshez; megszakításkor nincs újabb törlési köteg.
- Záró perjelre normalizált fizikai útvonalak, változatlan szigorú ellenőrzéssel.
- A stream tokenje és útvonala együtt cserélődik; a beolvasás elutasított indítása nem hagy beragadt állapotot.
