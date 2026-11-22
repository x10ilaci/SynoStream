# Android distribution requirements

- Public GitHub APKs must use the release build variant, never assembleDebug output.
- Use build_release.ps1 and verify_release.py. The actual APK manifest must be non-debuggable and not testOnly; verify its package/version and pinned signing certificate before publication.
- Publish through publish_android.py from the repository checkout; its verification gate is mandatory. Keep make_latest=false so Android releases cannot replace the Windows latest release.
- Preserve the existing signing key for in-place updates. Never publish signing keys, local.properties, user data or credentials. A key/certificate migration requires a separate explicit decision.
- Do not claim a successful release build proves Play Protect approval.
