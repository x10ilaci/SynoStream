# Code signing policy

Free code signing provided by [SignPath.io](https://signpath.io), certificate by [SignPath Foundation](https://signpath.org/).

## Signed artifacts

Only the Windows x64 SynoStream release executable is submitted for signing. Each signed file must be built by the GitHub Actions workflow in this repository from the matching release source. A release signing request must receive manual approval in SignPath before the signed artifact is distributed.

## Project roles

Project roles are held by the repository maintainer:

- Author and reviewer: [@x10ilaci](https://github.com/x10ilaci). Contributions from people without commit access are reviewed by the maintainer before merging.
- Signing approver: [@x10ilaci](https://github.com/x10ilaci). Each release signing request is reviewed and approved by the maintainer.

All repository and SignPath accounts used for signing must have multi-factor authentication enabled. Changes from contributors without commit access must be reviewed before merging. Release signing requests must be reviewed and approved by an authorized project maintainer.

## Privacy

SynoStream does not send telemetry. Its network access is limited to the NAS and TMDB services configured by the operator, plus the MPV download required when the operator starts playback. The application does not transmit library credentials to the project maintainers.

## Release process

1. Build the release from the matching tagged source using the GitHub-hosted workflow in `.github/workflows/signpath-release.yml`.
2. Submit only the unsigned executable produced by that workflow to the SignPath release policy.
3. Review and approve the signing request in SignPath.
4. Review the workflow artifact containing the signed executable, matching source archive, notices, and SHA-256 checksums before publishing it as a release.
