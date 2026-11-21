# Android release channel

Current APKs are published in this repository under separate `android-vX.Y.Z` release tags. Desktop tags remain `vX.Y`; Android releases must use `make_latest=false` so the existing Windows update channel stays intact.

Stable metadata URL: https://raw.githubusercontent.com/x10ilaci/SynoStream/main/android/update.json

The metadata includes application ID, monotonically increasing version_code, version, minimum SDK, immutable release asset URL, byte size, SHA256 and signing certificate SHA256. The identical metadata is also attached to each Android release as android-update.json.

The current app does not yet consume this feed. A future updater must check the application ID, installed versionCode, HTTPS origin, download size/hash and APK signing certificate before requesting installation through Android. Installation requires Android's user confirmation and permission to install from this source; do not promise silent updates.

APK signing keys are private and are not in the repository or source ZIP. Existing installations use the current debug certificate shown in update.json; preserve that key for updates to those installations. A build signed with another key cannot replace those installations.
