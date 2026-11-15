# SynoStream 1.102

- Helyi NAS-címként elegendő az IP-cím vagy helyi gépnév: a 192.168.1.2 automatikusan http://192.168.1.2:5000 lesz. Egyedi port és kifejezetten megadott HTTPS-cím továbbra is használható.
- A DDNS / közvetlen cím mező HTTP-t és HTTPS-t is elfogad. Protokoll nélküli DDNS-címnél a HTTPS marad az alapértelmezés; HTTPS-hibánál nem vált automatikusan HTTP-re.
- Új, alapból kikapcsolt Automatikus frissítés bekapcsolása beállítás. Bekapcsolva a program a háttérben letölti és ellenőrzi a frissítést, majd a következő indításkor telepíti és elindítja az új verziót.
- A várakozó frissítés újraindítások között megmarad; kikapcsolt automatikus frissítésnél nem települ. Telepítés előtt a programfájlt ismét ellenőrzi. Hiba esetén a régi verzió használható marad.
- A kézi Frissítés és újraindítás / Később működés továbbra is használható. Új verziók külön mappába kerülnek a Letöltések között; a felhasználói beállítások megmaradnak.
- A frissítési beállítások forrásmappa-módosítás után is az aktuális konfigurációba mentődnek.

HTTP használatakor a kapcsolat titkosítatlan. HTTPS továbbra is választható, érvényes tanúsítvánnyal. A helyi hálózat → DDNS → QuickConnect sorrend megmaradt.
