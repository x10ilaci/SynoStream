# Android release channel

Stable feed: https://raw.githubusercontent.com/x10ilaci/SynoStream/main/android/update.json

Use android-vX.Y.Z tags and make_latest=false; Windows remains the repository latest release.

From 0.5.24, public APKs must be built with assembleRelease (build_release.ps1 runs the release tests and lint). verify_release.py MUST pass before upload: expected package/version, debuggable=false, testOnly=false, valid signature, unchanged pinned certificate and valid ZIP. assembleDebug outputs are never distribution artifacts.

The current signing key is retained for in-place upgrades. Its certificate has the historical Android Debug subject name; that name is distinct from the APK debug flag. No signing key or password is shipped in source or release assets. A certificate change requires a separate migration plan.

The feed includes the immutable APK URL, byte size, SHA256, monotonically increasing version_code and pinned signing certificate. Android still requires user permission and installation confirmation.

A correct release build does not guarantee a Play Protect classification. A harmful-app warning must be investigated separately and, if erroneous, appealed through Google's official process.
