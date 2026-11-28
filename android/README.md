# SynoStream Android

Synology NAS-on tárolt filmek és sorozatok böngészése, TMDB-médiainformációk, médiatárankénti ajánló, külső videólejátszó indítása és Download Station-kezelés. Magyar és angol felülettel, Android 8.0-tól.

**[Android 0.5.29 release APK letöltése](https://github.com/x10ilaci/SynoStream/releases/download/android-v0.5.29/SynoStream_Android_0.5.29.apk)** · [Kiadási jegyzet és forrás](https://github.com/x10ilaci/SynoStream/releases/tag/android-v0.5.29)

A kész APK-hoz nem kell Android Studio vagy Java-fejlesztőkörnyezet. Azonos aláírással a korábbi verzió fölé telepíthető; frissítés előtt ne távolítsd el a régi appot.

[Projektfőoldal](../README.md) · [Telepítés és NAS-beállítás](../docs/INSTALL.md) · [Gyakori kérdések](../docs/FAQ.md) · [Forrásból fordítás](../docs/DEVELOPMENT.md#android-forrásból)

## Kiadás készítése

Nyilvános terjesztéshez kizárólag a `build_release.ps1` által előállított, `verify_release.py` által ellenőrzött APK használható. Az `assembleDebug` kimenete nem publikálható. A meglévő aláírókulcs szükséges a hivatalos frissítési csatornához, és nem része a forrásnak.

[Kiadási csatorna](UPDATE_CHANNEL.md) · [Kiadási szabályok](AGENTS.md) · [Aláírási politika](../CODE_SIGNING_POLICY.md) · [Legutóbbi ellenőrzés](ELLENORZES.md)
