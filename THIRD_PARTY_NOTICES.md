# Third-party software notices

SynoStream's source package contains no third-party binaries. Its runtime dependencies are installed separately using `requirements.txt`; review each installed package's own license and notices when redistributing a built application.

- **PyQt6** — Riverbank's free PyQt distribution is licensed under GPLv3; the alternative is a commercial license. The PyQt Windows wheels also include Qt libraries with their own license terms. SynoStream is distributed under GPL-3.0-only. See [Riverbank's PyQt license information](https://www.riverbankcomputing.com/software/pyqt/intro).
- **Requests** — Apache License 2.0. Its transitive dependencies have separate licenses. See the [Requests project](https://github.com/psf/requests).
- **mpv** — downloaded separately by the app on first playback and not included in this source archive. Upstream mpv is GPL-2.0-or-later by default; the exact binary build can have additional linked-library notices. See [mpv's licensing notes](https://github.com/mpv-player/mpv/blob/master/Copyright).

Before distributing an installer or bundled binary, record the exact dependency and mpv build versions and include all notices required by those specific builds.
