# SynoStream 1.108

- A 2x05HDTV, 2x05v2 és 2x05x264 jelölés ismét megfelelő epizódot ad; a felbontás nem válik évaddá.
- Méretalapú sample-előtag szűrés a beolvasásban, epizódlistában, torrentkijelölésben és törlési tervben. A kétes fájl minta, ha legfeljebb 150 MiB, vagy az ugyanabban a mappában található legnagyobb videó 10%-ánál kisebb. Ismeretlen méretnél marad a korábbi szabály; a torrentkijelölés kézzel módosítható.
- A lassú NAS-bejelentkezés nem tartja zárolva a többi lejátszási profilt. Párhuzamos kapcsolódás és időközben megszüntetett profil kezelése.
- Figyelmeztetés, ha a DSM nem jegyezte meg a kért megbízható eszközt. A device_id, did és otp_code paraméterek kitakarása.
- Megszűnt a kivételosztályok kétszeres naplózása.

888 Windows-teszt sikeres, 6 kihagyott. Élő NAS-on nem történt törlés vagy írás.
