# SynoStream 1.111

- Gyorsabb torrent-célmappaválasztó: csak mappák lekérése, 200-as lapozás, 60 másodperces gyorsítótár, indulás a megadott célmappából.
- A foglalt letöltési oldal mellett megnyitott mappaválasztó sorba állítja a kérését; bezáráskor eldobja/megszakítja.
- Megbízható eszköztoken átadása a Download Stationnek; pontosabb OTP-figyelmeztetés és a visszautasított token elfelejtése.
- NAS-útvonalak és hitelesített olvasási munkamenetek újrafelhasználása; legfeljebb négy párhuzamos mappalistázás, változatlan TMDB-korlátozással.
- A kétes Sample-előtagú fájlokat már nem minősíti mintának pusztán a kis méretük miatt.
- Kevesebb kiegészítő NAS-mező beolvasáskor. A törlés fizikaiútvonal-ellenőrzése és a bizonytalan írások megismétlésének tilalma megmaradt.
- Név nélküli kérés- és időösszesítések a diagnosztikához. A gyorsulást késleltetett NAS-szimulációban ellenőriztük; valós NAS-on nem mértünk garantált gyorsulást.
