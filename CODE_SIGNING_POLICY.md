# Code signing policy

The current Windows 1.97 release is **unsigned**. Its SHA256 checksums and update-manifest hashes verify file integrity; they do not constitute Authenticode signing.

The earlier `.github/workflows/signpath-release.yml` is a preparatory workflow for version 1.54. Its presence does not mean that a signing certificate has been activated or that current releases are signed. No SignPath account, approval, token or certificate is required by the current build/update workflow.

If SignPath Foundation signing is enabled in a future release, only executables built from the matching public tagged source may be submitted. Each signing request must receive the maintainer's manual approval. Signing credentials must never be distributed with application files.

## Current release process

1. Update and test the source, entry-point version, build version and `release_version.txt`.
2. Build locally with `build_windows.ps1`, or push the matching version tag to trigger `.github/workflows/windows-release.yml`.
3. Verify the executable, source archive, Windows ZIP, SHA256 file and `update.json` together.
4. The workflow creates a GitHub **draft**. Publish it after reviewing its artifacts. `publish_release.py --directory <release-folder> --publish` performs this final publication when authorized by the maintainer.
5. The Windows updater discovers the latest published stable release through GitHub Releases.

## Maintainer and privacy

Project maintainer: [@x10ilaci](https://github.com/x10ilaci).

SynoStream does not send telemetry or library credentials to the maintainer. Network access includes the configured NAS, TMDB, the MPV download and optional Windows update checks/downloads through GitHub and GitHub's release-asset CDN. Automatic update checks can be disabled in Settings. No GitHub login is needed by application users.
