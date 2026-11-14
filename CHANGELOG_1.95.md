# SynoStream 1.95

- Beépített Windows-programfrissítés a Beállításokban: kézi és napi háttérellenőrzés.
- A háttérellenőrzés kikapcsolható; új kiadásnál visszafogott állapotjelzés jelenik meg.
- GitHub Releases alapú letöltés, méret- és SHA256-ellenőrzéssel, megszakítási lehetőséggel.
- A felhasználó dönt a frissítés és újraindítás időpontjáról. Aktív lejátszás mellett nem indul telepítés.
- Az új kiadás külön verziószámos mappába kerül a Letöltésekben. Meglévő verziómappát soha nem ír felül.
- A régi program megmarad; az adatmappáról indulás előtt biztonsági másolat készül. Sikertelen induláskor visszaállítja a korábbi adatokat és megpróbálja újraindítani a régi programot.
- A frissítő megvárja a régi program kilépését, és ellenőrzi az új felület sikeres indulását.
- A Letöltésekben SynoStream parancsikon készül/frissül. Más alkalmazás azonos nevű parancsikonját nem írja át.
- A program GitHub-kapcsolata nem használ és nem küld NAS-jelszót, TMDB-kulcsot vagy médiatár-adatokat.

Az 1.95 előtti kiadásokba a frissítő nem kerül visszamenőleg; az 1.95-öt egyszer kézzel kell elindítani. A mobilos verzió frissítését ez a Windows-kiadás nem változtatja meg.
