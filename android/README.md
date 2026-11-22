# SynoStream Android 0.5.24

Release APK, versionCode 29. Azonos aláírással telepíthető a korábbi verzió fölé; az adatok megmaradnak.

Kiadás: https://github.com/x10ilaci/SynoStream/releases/tag/android-v0.5.24

Terjesztéshez kizárólag a build_release.ps1 által előállított és a verify_release.py által ellenőrzött APK használható. Az assembleDebug kimenete nem publikálható.

A privát aláírókulcs nincs a forráscsomagban. A meglévő tanúsítvány neve történeti okból Android Debug; az APK ettől függetlenül release build, debuggable=false. Új kulcsra váltás külön migrációt igényelne, ezért a jelenlegi kiadás nem cserél kulcsot.
