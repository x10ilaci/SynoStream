# Közreműködés

Köszönjük, ha hibajelentéssel, teszteléssel, dokumentációval vagy javítással segíted a SynoStreamet. Magyarul és angolul is lehet hibajegyet nyitni.

## Hibajelentés

Használd a [hibajegysablont](https://github.com/x10ilaci/SynoStream/issues/new/choose). Írd le:

- a platformot, az alkalmazás és az operációs rendszer verzióját;
- a reprodukció lépéseit, a várt és a tényleges eredményt;
- NAS-hibánál az elérési módot, privát címek és belépési adatok nélkül;
- felismerési hibánál egy személyes adatot nem tartalmazó fájl-/mappanév példát.

**Ne tölts fel jelszót, API-kulcsot, OTP-kódot, munkamenet-azonosítót, teljes beállításfájlt vagy nyers privát naplót.** Biztonsági hibát a [privát bejelentési útvonalon](SECURITY.md) jelezz.

## Fejlesztési javaslat

A kívánt funkció mellett azt is írd le, milyen használati problémát oldana meg, és melyik platformot érinti. Nagyobb átalakítás előtt érdemes egyeztetni a megközelítést egy hibajegyben.

## Kód és dokumentáció

1. Dolgozz külön ágon.
2. Tartsd a változtatást a javítandó problémára szűken.
3. Viselkedésmódosításhoz adj értelmes regressziós tesztet, és futtasd az érintett ellenőrzéseket.
4. A PR-ben írd le a problémát, a javított működést és az ellenőrzés eredményét.

A futtatási és fordítási lépések a [fejlesztői útmutatóban](docs/DEVELOPMENT.md) találhatók. A felhasználói szövegek magyar és angol nyelvi kezelését tartsd meg. Privát adat vagy aláírókulcs nem kerülhet commitba. A projekt licence GPL-3.0-only; a hozzájárulásnak ezzel összeegyeztethetőnek kell lennie.
