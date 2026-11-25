# SynoStream is a Windows media-library and playback application.
# Copyright (C) 2026 Lőrincz László
# SPDX-License-Identifier: GPL-3.0-only
# Modified version: SynoStream 1.107, 2026-11-11.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, version 3 only. This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See LICENSE.

import contextlib
import copy
import ctypes
from difflib import SequenceMatcher
import math
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import logging
import os
import posixpath
import re
import secrets
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
import uuid
import threading
import tempfile
import traceback
from types import SimpleNamespace
from logging.handlers import RotatingFileHandler

import zipfile
# The installer must run before Qt and before the normal application's data
# directory lock. It is a copy of this executable, not a downloaded script.
if __name__ == '__main__' and len(sys.argv) == 3 and sys.argv[1] == '--install-update':
    from synostream_updates import helper_main
    sys.exit(helper_main(sys.argv[2]))
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, urlsplit

import requests
from synostream_nas import RemoteNASClient as _RemoteNASClient, validate_quickconnect_id, quickconnect_url, nas_device_key, trusted_device_id
from synostream_sources import SourceRouter, RoutedNASClient, parse_pairs, expand_mapped_path, automatic_pairs
from synostream_source_migration import migrate_database as migrate_source_database, canonicalize_config, resolve_pending_cases
from synostream_source_ui import SourcePairsDialog
from synostream_source_folders import SourceFoldersDialog, records_from_settings, clean_records, FolderMigrationRouter, SourcesBusy, unify_records
import synostream_recommendations as recommendations
from synostream_recommendation_ui import RecommendationsDialog
from synostream_window_identity import configure_windows_identity, load_application_icon
from synostream_update_ui import UpdateController
from synostream_updates import acknowledge_update, cleanup_completed_updates
import synostream_pairings as portable_pairs
from synostream_nfo import parse_nfo, select_nfo_names, MAX_NFO_BYTES
from synostream_playback import MpvPlaybackMonitor as _MpvPlaybackMonitor
from synostream_download_ui import DownloadPage
from synostream_downloads import normalize_destination
from synostream_delete_ui import DeleteMediaDialog
from synostream_deletion import within as deletion_within
from synostream_performance import PosterPixmapCache, PlaybackDisplaySnapshot, placeholder_pixmap
from synostream_library import CardRecord, visible_range
from synostream_storage import data_directory, backup_before_upgrade, commit_data_version, migrate_schema, settings_transaction, recover_settings_transaction, acquire_application_lock, DataDirectoryInUse


def RemoteNASClient(credentials=None, should_stop=None, extra_apis=()):
    factory = lambda: _RemoteNASClient(config if credentials is None else credentials, should_stop, extra_apis=extra_apis)
    router = source_router()
    return RoutedNASClient(router, factory) if router.pairs else factory()


from synostream_logic import (
    movie_search_context, is_sample_video, release_filename_candidate,
    clean_name, normalize_title, parse_episode_position, parse_episode_range_hint,
    title_similarity,
)
from PyQt6.QtCore import QEvent, QTranslator, Qt, QSize, QByteArray, QThread, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QDesktopServices, QIcon, QImage, QKeySequence, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication as _QtApplication, QCheckBox as _QtCheckBox, QComboBox as _QtComboBox,
    QDialog as _QtDialog, QDialogButtonBox as _QtDialogButtonBox,
    QFormLayout as _QtFormLayout, QFrame,
    QGridLayout, QGroupBox as _QtGroupBox, QHBoxLayout, QLabel as _QtLabel,
    QLineEdit as _QtLineEdit, QListWidget, QListWidgetItem as _QtListWidgetItem,
    QMainWindow as _QtMainWindow, QMessageBox as _QtMessageBox,
    QMenu, QProgressBar, QPushButton as _QtPushButton, QScrollArea, QStackedWidget,
    QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QFileDialog as _QtFileDialog,
    QInputDialog as _QtInputDialog, QPlainTextEdit as _QtPlainTextEdit, QTextEdit as _QtTextEdit,
    QTabWidget as _QtTabWidget, QTreeWidget as _QtTreeWidget,
    QTreeWidgetItem as _QtTreeWidgetItem,
)


# ==========================================
# FELÜLETI LOKALIZÁCIÓ
# ==========================================
UI_LANGUAGE = "hu"
_UI_TEXTS_EN = {
    'NAS-kapcsolat beállítása': 'Configure NAS connection',
    'Helyi NAS-cím:': 'Local NAS address:',
    'DDNS / közvetlen cím:': 'DDNS / direct HTTPS:',
    'Kapcsolat ellenőrzése és mentése': 'Test and save connection',
    'Lejátszás: NAS (automatikus kapcsolat)': 'Playback: NAS (automatic connection)',
    'Válaszd ki egyszer a forrásmappát. NAS-mappánál a helyi hálózatot, a DDNS-t és a QuickConnectet automatikusan kezeljük.': 'Select the source folder once. Local network, DDNS and QuickConnect access are handled automatically for NAS folders.',
    'A NAS elérési címeit a Beállítások / NAS-kapcsolat alatt lehet egyszer megadni. Az ezen a gépen tárolt mappák továbbra is külön használhatók.': 'Configure NAS addresses once under Settings / NAS connection. Folders stored on this computer can still be used separately.',
    'Válassz médiatárat, majd tallózással adj hozzá forrásmappát. Minden mappát egyszer adj hozzá; a NAS-kapcsolatot automatikusan választjuk ki.': 'Choose a library and browse to add a source folder. Add each folder once; the NAS connection is selected automatically.',
    'Add meg egyszer a NAS eléréseit. A sorrend: helyi hálózat, DDNS, QuickConnect. Elég egy működő elérés; a többi tartalék. A forrásmappákat minden kapcsolaton ugyanazzal az útvonallal használjuk.': 'Configure NAS access once. Priority: local network, DDNS, QuickConnect. One working address is enough; the others are fallbacks. Source folders use the same path on every connection.',
    'Kapcsolódva – helyi hálózat': 'Connected – local network',
    'Kapcsolódva – DDNS / közvetlen NAS': 'Connected – DDNS / direct NAS',
    'Kapcsolódva – QuickConnect': 'Connected – QuickConnect',
    'A háttérművelet befejezésére várunk. A jóváhagyott módosításokat utána automatikusan mentjük. Lejátszás esetén előbb zárd be a lejátszót.': 'Waiting for the background operation to finish. Your approved changes will then be saved automatically. If playback is active, close the player first.',
    'Ugyanaz a forrásmappa?': 'Same source folder?',
    'Ez a helyi hálózati mappa a megadott NAS-mappa másik elérése?': 'Is this local network folder another way to access the listed NAS folder?',
    'Összerendeléskor egy példányban jelennek meg a műsorok, és az elérhető helyi kapcsolatot használjuk.': 'Linking shows each title once and uses the local connection when available.',
    'Lejátszás: helyi hálózat': 'Playback: local network',
    'Lejátszás: NAS / QuickConnect': 'Playback: NAS / QuickConnect',
    'Lejátszás: helyi fájl': 'Playback: local file',
    'Lejátszás: helyi és NAS elérés': 'Playback: local and NAS sources',
    'Magyar adatlapok előnyben': 'Prefer Hungarian metadata',
    'A TMDB-n magyar leírással rendelkező ajánlások nagyobb eséllyel kerülnek a válogatás elejére. Más címek is megjelenhetnek. Ez nem igazolja a magyar szinkront.': 'Recommendations with Hungarian descriptions on TMDB are more likely to appear near the top. Other titles can still appear. This does not confirm Hungarian dubbing.',
    'Magyar adatlap': 'Hungarian metadata',
    'Magyar leírás található a TMDB-n. Ez nem igazolja a szinkront.': 'A Hungarian description is available on TMDB. This does not confirm dubbing.',

    'Ajánló': 'Recommendations',
    'Ajánlások ennek a médiatárnak a műsorai alapján': 'Recommendations based on this library',
    'Ajánlatok a médiatárad alapján': 'Recommendations based on your library',
    'Médiatáranként külön válogatás. A már meglévő műsorokat az összes médiatárból kiszűrjük.': 'A separate selection for each library. Titles already owned in any library are excluded.',
    'Fedezz fel': 'Discover',
    'Érdekel': 'Interested',
    'Elrejtve': 'Hidden',
    'Új válogatás': 'New selection',
    'Következő oldal': 'Next page',
    'Adatforrás: TMDB': 'Data source: TMDB',
    'Ebben a médiatárban még nincs azonosított műsor. Előbb frissítsd a médiatárat vagy add meg a médiainformációkat.': 'There are no identified titles in this library yet. Refresh the library or add media information first.',
    'Az ajánló helyi adatainak betöltése nem sikerült.': 'Could not load local recommendation data.',
    'Ajánlások frissítése… A korábbi válogatás közben is böngészhető.': 'Updating recommendations… You can keep browsing the previous selection.',
    'Ajánlások alapjául szolgáló műsorok: {count}.': 'Titles used for recommendations: {count}.',
    'A TMDB-frissítés egy része nem sikerült. A mentett ajánlások továbbra is böngészhetők.': 'Some TMDB requests failed. Saved recommendations remain available.',
    'Ebben a válogatásban nincs új találat. Az Új válogatás további műsorokból is kereshet ajánlásokat.': 'This selection has no new results. New selection can look for recommendations from more titles.',
    'Az ajánlások frissítése nem sikerült. Ellenőrizd a TMDB-kulcsot és az internetkapcsolatot.': 'Could not update recommendations. Check your TMDB key and internet connection.',
    'Itt még nincs megjeleníthető műsor.': 'There are no titles to show here yet.',
    'Film': 'Movie',
    'Sorozat': 'TV show',
    'Ez alapján:': 'Based on:',
    'Részletek': 'Details',
    'Eltávolítás a listáról': 'Remove from list',
    'Visszaállítás': 'Restore',
    'Nem érdekel': 'Not interested',
    'A visszajelzés mentése nem sikerült.': 'Could not save your feedback.',
    'Ehhez a műsorhoz nincs elérhető leírás.': 'No description is available for this title.',
    'Megnyitás a TMDB-n': 'Open on TMDB',

    'Forrásmappák': 'Source folders',
    'Forrásmappa': 'Source folder',
    'Médiatárak – forrásmappák': 'Libraries – source folders',
    'Válassz médiatárat, majd tallózással adj hozzá forrásmappát. A helyi és a NAS-elérés egy sorban kezelhető.': 'Choose a library, then browse to add a source folder. Local and NAS access are managed in one entry.',
    'Tallózd be a mappát ezen a gépen vagy a NAS-on. Ugyanahhoz a mappához mindkét elérést is megadhatod.': 'Browse for the folder on this computer or on the NAS. You can add both access paths for the same folder.',
    'Ezen a gépen / helyi hálózaton:': 'On this computer / local network:',
    'A NAS-on:': 'On the NAS:',
    'Helyi mappa tallózása…': 'Browse local folders…',
    'NAS-mappa tallózása…': 'Browse NAS folders…',
    'Ha mindkét elérés meg van adva, az elérhető helyi hálózati kapcsolatot használjuk, egyébként a NAS-kapcsolatot. Csak ugyanannak a mappának a két elérését válaszd ki.': 'When both paths are set, we use local network access when available, otherwise the NAS connection. Select two paths to the same folder.',
    'Útvonal megadása kézzel…': 'Enter a path manually…',
    'Helyi, hálózati vagy syno:/// mappaútvonal:': 'Local, network or syno:/// folder path:',
    'Kész': 'Done',
    'Mappa hozzáadása': 'Add folder',
    'Módosítás': 'Edit',
    'Helyi:': 'Local:',
    'NAS-bejelentkezés és böngészés': 'NAS login and browsing',
    'A forrásmappák mentve. Frissítsd a médiatárat a kapcsolat ellenőrzéséhez.': 'Source folders saved. Refresh the library to check connectivity.',
    'Válassz legalább egy mappát az új médiatárhoz.': 'Select at least one folder for the new library.',
    'Ez a mappa már szerepel ebben a médiatárban.': 'This folder is already in this library.',
    'Válassz legalább egy forrásmappát.': 'Select at least one source folder.',
    'Teljes helyi vagy hálózati mappaútvonalat adj meg.': 'Enter a full local or network folder path.',
    'Válassz egy megosztott mappát a hálózati gépen.': 'Select a shared folder on the network computer.',

    "Részleges találatok": "Partial results",
    "Az MPV hibával leállt, mielőtt létrejött volna a lejátszókapcsolat.": "MPV exited with an error before the player connection was established.",
    "Az MPV hibával leállt a videó elindítása előtt.": "MPV exited with an error before the video started.",
    "Kihagyott fájlok és műsorok": "Excluded files and shows",
    "A fájlok a helyükön maradnak. Jelöld ki a visszaállítandó elemeket.": "Files stay in place. Select the items to restore.",
    "Kijelöltek visszaállítása": "Restore selected items",
    "Kihagyás a médiatárból – a fájl megmarad": "Exclude from library – keep the file",
    "Helyreállított közös fájlok: {count}.": "Repaired shared files: {count}.",
    "Hordozható médiapárosítások": "Portable media matches",
    "Párosítások szinkronizálása": "Sync media matches",
    "A kézi párosításokat a médiatár gyökerének .synostream mappája tárolja. Másik gépen ugyanazt a médiatárgyökeret válaszd ki, majd frissítsd a médiatárat.": "Manual matches are stored in .synostream at the library root. Select that same library root on another computer and refresh its library.",
    "Párosítások: {imported} átvett, {written} mentett, {pending} mentésre vár.": "Matches: {imported} imported, {written} saved, {pending} pending.",
    "A párosítás helyben mentve. A médiatári közös mentés nem sikerült; frissítéskor újrapróbálom.": "The match is saved locally. Library storage is unavailable; retrying on refresh.",
    "Szinkronizálás folyamatban…": "Synchronizing…",
    "A párosítások szinkronizálása a következő frissítéskor indul.": "Matches will synchronize on the next library refresh.",
    "A párosítás csak helyben menthető, mert nem tartozik beállított médiatárhoz.": "The match can only be saved locally because it is outside the configured libraries.",
    "Kapcsolódás / mappalista betöltése…": "Connecting / loading folders…",
    "Megszakítás": "Cancel",
    "Letöltések": "Downloads",
    "Elkészült letöltés: {titles}": "Download complete: {titles}",
    "Folytatható": "In progress", "elem": "items", "+ Új médiatár": "+ Add library",
    "Filmek": "Movies", "TV Műsorok": "TV Shows",
    "Filmek Műsortár": "Movie Library", "TV Műsorok Műsortár": "TV Shows Library",
    "Beállítások": "Settings", "Új médiatár hozzáadása": "Add a library",
    "Médiatár állapota": "Library status", "Beolvasási hibanapló": "Scan error log",
    "Kártyák": "Cards", "Utolsó sikeres frissítés": "Last successful refresh",
    "Még nem volt sikeres frissítés": "No successful refresh yet",
    "A kártyaszám a legutóbb betöltött listát mutatja.": "Card count reflects the most recently loaded list.",
    "Mentett jelszó használata (üresen hagyva)": "Use saved password (leave blank)",
    "Jelszó megadása": "Enter password", "Mutat": "Show",
    "Nincs megjeleníthető elem ebben a médiatárban.": "There are no items to display in this library.",
    "Hibanapló megnyitása": "Open error log",
    "Új médiatár": "New library", "Médiatár neve:": "Library name:",
    "Médiatár neve": "Library name", "Médiatár": "Library",
    "Médiatár típusa": "Library type", "Mit tartalmaz ez a médiatár?": "What type of media will this library contain?",
    "Médiatár és adatok": "Library and data", "Médiatárak": "Libraries",
    "Médiatár helye": "Library location",
    "Helyi mappát vagy távoli NAS mappát szeretnél hozzáadni?": "Would you like to add a local folder or a remote NAS folder?",
    "Helyi mappa": "Local folder", "Távoli NAS mappa": "Remote NAS folder",
    "Mappa hozzáadása az új médiatárhoz": "Add folder to the new library",
    "Mappa kiválasztása": "Select folder",
    "Kapcsolódj a NAS-hoz, tallózd be a kívánt megosztott mappát, majd válaszd a „Mappa hozzáadása az új médiatárhoz” gombot. A NAS-jelszót Windows-fiókodhoz kötött védelem tárolja.": "Connect to the NAS, browse to the shared folder, then choose “Add folder to the new library”. The NAS password is protected using your Windows account.",
    "Válassz előbb egy megosztott mappát.": "Select a shared folder first.",
    "Médiatár nem található": "Library not found",
    "Médiatár törlése": "Delete library", "Médiatárak, lejátszás, metaadatok és NAS-kapcsolat kezelése": "Manage libraries, playback, metadata, and NAS connections",
    "Helyi médiamappák": "Local media folders", "Helyi médiamappa": "Local media folder",
    "Távoli NAS": "Remote NAS", "Távoli NAS – QuickConnect": "Remote NAS – QuickConnect",
    "Távoli mappa hozzárendelése": "Assign remote folder",
    "Távoli mappaböngészés és MPV-lejátszás QuickConnecten keresztül.": "Browse remote folders and play media with MPV through QuickConnect.",
    "QuickConnect teszt": "QuickConnect test", "Synology QuickConnect – kapcsolatpróba": "Synology QuickConnect – connection test",
    "NAS-kapcsolat": "NAS connection", "Kapcsolódás": "Connect", "Kapcsolódva": "Connected",
    "QuickConnect-azonosító": "QuickConnect ID", "QuickConnect ID:": "QuickConnect ID:",
    "NAS-felhasználó:": "NAS username:", "NAS-felhasználónév": "NAS username",
    "NAS-jelszó:": "NAS password:", "NAS-jelszó (csak helyben használjuk)": "NAS password (used locally only)",
    "Felhasználónév:": "Username:", "Jelszó:": "Password:",
    "QuickConnect-azonosító, a felhasználónevet és a jelszót.": "QuickConnect ID, username, and password.",
    "Nincs csatlakoztatva": "Not connected", "Szülőmappa": "Parent folder",
    "◀ Szülőmappa": "◀ Parent folder", "Kiválasztott videó lejátszása MPV-vel": "Play selected video with MPV",
    "Aktuális mappa kiválasztása…": "Use current folder…", "Melyik könyvtárként mentsem a jelenleg megnyitott mappát?": "Which library should use the currently open folder?",
    "Médiatárához adás": "Add to library", "Mégse": "Cancel", "Bezárás": "Close",
    "Nyelv": "Language", "Nyelv:": "Language:", "Magyar": "Hungarian", "Eredeti": "Original",
    "Lejátszás": "Playback", "Preferált audio nyelv:": "Preferred audio language:",
    "Preferált felirat nyelv:": "Preferred subtitle language:",
    "Az „Eredeti” a TMDB által megadott eredeti nyelvet részesíti előnyben; ha a nyelv nem ismert vagy nincs ilyen sáv, a lejátszó alapértelmezett választása érvényes. Ha egyik feliratjelölő sincs bepipálva, az MPV választ.": "“Original” prefers the original language reported by TMDB. If the language is unknown or no matching track is available, the player's default selection is used. If no subtitle option is checked, MPV chooses.",
    "Lejátszási beállítások mentése": "Save playback settings",
    "Karbantartás és mentés": "Maintenance and backup",
    "A plakátcache legfeljebb 512 MB; a régebben használt képek törlődnek először.": "The poster cache is limited to 512 MB; least recently used images are removed first.",
    "A sikeres médiatár-beolvasás takarítja az árva médiaadatokat és plakátokat. A plakátcache legfeljebb {cache_limit} MB; a régebben használt képek törlődnek először.": "A successful library scan removes orphaned media records and posters. The poster cache is limited to {cache_limit} MB; least recently used images are removed first.",
    "Plakátcache ürítése": "Clear poster cache", "TMDB-adatcache ürítése": "Clear TMDB data cache",
    "Beállítások és adatbázis mentése…": "Back up settings and database…", "Mentés visszaállítása…": "Restore backup…",
    "Névjegy": "About", "Verzió:": "Version:", "Kiadás: Nyilvános kiadás": "Release: Public release",
    "Licenc: GNU GPL-3.0-only": "License: GNU GPL-3.0-only",
    "A program a GNU GPL-3.0-only licenc alatt érhető el. A licenc ismerteti a használat, módosítás és továbbadás feltételeit, valamint a jótállás kizárását. A teljes szöveg a jogi tájékoztatóban olvasható.": "This program is available under the GNU GPL-3.0-only license. The license describes the terms for using, modifying, and redistributing the software, including the warranty disclaimer. Read the full text in the license and legal information dialog.",
    "Licenc és jogi tájékoztató megtekintése": "View license and legal information",
    "Médiatár-kezelő és lejátszó NAS-on tárolt műsorokhoz.": "A media library manager and player for media stored on a NAS.",
    "ABC": "Title (A–Z)", "Kiadási év": "Release year", "Hozzáadás": "Date added",
    "Korhatár": "Age rating", "Nincs korhatár-besorolás": "No age rating available",
    "Korhatár-besorolás nem tölthető be": "Age rating could not be loaded",
    "Növekvő": "Ascending", "Csökkenő": "Descending", "Rendezés szempontja": "Sort by",
    "A rendezés iránya": "Sort order", "Keresés": "Search",
    "Az éppen megnyitott médiatár frissítése": "Refresh the currently open library",
    "Indulás és megjelenés": "Startup and appearance",
    "Induláskori frissítés:": "Startup refresh:",
    "Utoljára használt médiatár": "Last used library",
    "Minden médiatár": "All libraries",
    "Ne frissítsen induláskor": "Do not refresh at startup",
    "Kártyaméret:": "Card size:",
    "Kompakt": "Compact", "Normál": "Normal", "Nagy": "Large",
    "A „Ne frissítsen induláskor” mód betölti a korábbi listákat, de nem ellenőrzi a NAS-t; a frissítés ikonnal indíthatod el az ellenőrzést.": "The “Do not refresh at startup” mode loads the previous lists without checking the NAS; click the refresh icon to check for changes.",
    "Az induláskori frissítés módja a program következő indításakor lép életbe.": "The startup refresh mode takes effect the next time the app starts.",
    "Az induláskori frissítés módja a program következő indításakor lép életbe. A „Ne frissítsen induláskor” mód betölti a korábbi listákat, de nem ellenőrzi a NAS-t; a frissítés ikonnal indíthatod el az ellenőrzést.": "The startup refresh mode takes effect the next time the app starts. The “Do not refresh at startup” mode loads the previous lists without checking the NAS; click the refresh icon to check for changes.",
    "Induláskor nem történik beolvasás. A frissítés ikonra kattintva indíthatod el.": "No library scan runs at startup. Click the refresh icon to start one.",
    "A korábbi lista betöltve; háttérben ellenőrzöm a változásokat...": "The previous library snapshot is loaded; checking for changes in the background…",
    "A korábbi lista betöltve; a frissítés ikon ellenőrzi a változásokat.": "The previous library snapshot is loaded; use the refresh icon to check for changes.",
    "Az utolsó beolvasott listák betöltve; a frissítés ikonnal ellenőrizheted a változásokat.": "The last scanned lists are loaded; use the refresh icon to check for changes.",
    "Lejátszás teljes képernyőn": "Start playback in fullscreen",
    "Következő epizód automatikus indítása": "Automatically play the next episode",
    "Kikapcsolva": "Off", "Beállítások mentése": "Save settings",
    "A felirat-beállítás az MPV által választott sávra is bízható.": "Subtitle selection can also be left to MPV.",
    "Visszavonás": "Undo", "Ismét": "Redo", "Kivágás": "Cut",
    "Másolás": "Copy", "Beillesztés": "Paste", "Törlés": "Delete",
    "Összes kijelölése": "Select All",
    "Médiatár frissítése": "Refresh library", "Beolvasás folyamatban...": "Scanning…",
    "A médiatár létrejött. Útvonalat a „Helyi médiamappák” ablakban adhatsz hozzá.": "The library was created. Add a folder path in Local media folders.",
    "A mappa üres vagy nem érhető el a megadott útvonalon.": "The folder is empty or the specified path is unavailable.",
    "Videoinformációk lekérése": "Fetch media information", "Videoinformációk lekérése – találatok": "Fetch media information – results",
    "Videoinformációk hozzáadása": "Add media information", "Milyen címet keressünk a TMDB-n?": "What title should we search for on TMDB?",
    "Itt rendelhetsz hozzá megfelelő TMDB-adatokat egy videóhoz vagy TV-műsor mappához. A NAS-on lévő eredeti fájl érintetlen marad!": "Use this window to match a video or TV show folder with the correct TMDB information. The original file on the NAS will not be changed.",
    "Pl. Oppenheimer vagy Breaking Bad": "For example: Oppenheimer or Breaking Bad",
    "Pl. \\\\NAS\\Filmek\\ppnhmr.fulcrum.mkv vagy \\\\NAS\\TV_sorozatok\\Breaking Bad": "For example: \\\\NAS\\Movies\\movie.mkv or \\\\NAS\\TV_Shows\\Breaking Bad",
    "Fájl / Mappa teljes útvonala:": "Full file or folder path:", "Média típusa:": "Media type:",
    "Helyes cím (TMDB):": "Correct title (TMDB):", "Film": "Movie", "TV műsor": "TV show",
    "Videoinformációk mentése és frissítés": "Save media information and refresh",
    "Kézi párosítás visszavonása": "Undo manual match", "Kézi párosítás visszavonása?": "Undo manual match?",
    "Eltávolítja a kézi TMDB-párosítást, majd újra megpróbálja az automatikus párosítást.": "Remove the manual TMDB match and try automatic matching again.",
    "Másik TV-műsor kártyával összevonás": "Merge with another TV show card",
    "Manuális összevonás feloldása": "Undo manual merge",
    "Megjelölés megnézettként": "Mark as watched", "✓ Megnézve": "✓ Watched", "Megnézve": "Watched",
    "A sorozat összes epizódját megjelöli megnézettként vagy nézetlenként.": "Mark all episodes in this show as watched or unwatched.",
    "Epizódok (a kiválasztott résztől folytatva):": "Episodes (play from the selected episode):",
    "Epizódok betöltése...": "Loading episodes…", "Epizódok betöltése…": "Loading episodes…",
    "Lejátszás innen": "Play from here", "A lejátszás a kijelölt résszel indul, majd MPV automatikusan elindítja a soron következőt.": "Playback starts from the selected episode, then MPV automatically plays the next one.",
    "Lejátszás elölről": "Play from beginning", "Folytatás": "Resume",
    "Lejátszó: MPV": "Player: MPV", "Média Részletek": "Media details", "Nincs borító": "No poster",
    "Nincs leírás.": "No description.", "További adatok betöltése…": "Loading more details…",
    "További adatok most nem tölthetők be.": "More details are currently unavailable.",
    "További adatokhoz előbb párosítsd a médiát a TMDB-vel.": "Match this media with TMDB to load more details.",
    "Nincs további TMDB-adat.": "No additional TMDB data.", "Epizódhossz": "Episode runtime", "Játékidő": "Runtime",
    "Szereplők: ": "Cast: ", "Műfaj: ": "Genres: ", "TMDB értékelés: ": "TMDB rating: ",
    "Műfaj:": "Genre:", "Megjelenés:": "Release date:", "Média típusa": "Media type",
    "Mappa kiválasztása": "Select folder", "Útvonal megadása": "Enter path", "Tallózás…": "Browse…", "Eltávolítás": "Remove",
    "Mappa hozzáadása": "Add folder", "Mappa elmentve": "Folder saved",
    "QuickConnect-napló mentése": "Save QuickConnect log",
    "SynoStream mentés helye": "Save SynoStream backup",
    "SynoStream mentés kiválasztása": "Select SynoStream backup",
    "Nem sikerült törölni az ideiglenes MPV-lejátszólistát.": "Could not delete the temporary MPV playlist.",
    "Milyen címen jelenjen meg az összevont kártya?": "What title should the merged card use?",
    "Médiatár neve:": "Library name:", "Add meg a QuickConnect-azonosítót, a felhasználónevet és a jelszót.": "Enter the QuickConnect ID, username, and password.",
    "Add meg a teljes helyi vagy hálózati mappaútvonalat:": "Enter the full local or network folder path:",
    "Adj meg egy címet az összevont műsornak.": "Enter a title for the merged show.",
    "Mappa már hozzáadva": "Folder already added", "TMDB beállítva": "TMDB configured",
    "Frissítési figyelmeztetés": "Update warning", "MPV telepítése": "Installing MPV",
    "Írási hiba": "Write error",
    "Nem sikerült beállítani az MPV lejátszókapcsolatát.": "Could not configure the MPV connection.",
    "Nem sikerült elküldeni a lejátszólistát az MPV-nek.": "Could not send the playlist to MPV.",
    "Az MPV nem tudta megnyitni a lejátszólistát.": "MPV could not open the playlist.",
    "Az MPV elindult, de a lejátszókapcsolat 45 másodpercen belül nem jött létre.": "MPV started, but the player connection was not established within 45 seconds.",
    "Az MPV nem tudta 90 másodpercen belül elindítani a videót.": "MPV could not start the video within 90 seconds.",
    "Az MPV lejátszó hiányzik. Letöltés és telepítés…": "MPV is missing. Downloading and installing…",
    "MPV Windows x64 csomag keresése a hivatalos GitHub kiadások között…": "Looking for an MPV Windows x64 package in the official GitHub releases…",
    "MPV kicsomagolása…": "Extracting MPV…",
    "MPV telepítése nem sikerült": "MPV installation failed", "Kézi újraindítás szükséges": "Manual restart required",
    "Könyvtáron kívüli útvonal": "Path outside library",
    "Ellenőrzi, hogy a NAS DSM API-ja elérhető-e közvetlenül QuickConnecten keresztül.": "Check whether the NAS DSM API is directly accessible through QuickConnect.",
    "Feloldod ezt az összevonást? A mappák külön kártyák lesznek, kivéve ha a nevük alapján automatikusan is összetartoznak.": "Undo this merge? The folders will become separate cards unless their names match automatically.",
    "Nem található a TMDB-n. Használd a Videoinformációk lekérését!": "Not found on TMDB. Use Fetch media information to match it.",
    "Nem található megbízható egyezés a TMDB-n. Használd a Videoinformációk lekérését!": "No reliable match was found on TMDB. Use Fetch media information to match it.",
    "Válaszd ki a médiatárat, majd adj hozzá helyi, hálózati vagy QuickConnecten megadott mappautat.": "Select a library, then add a local, network, or QuickConnect folder path.",
    "TMDB kulcs": "TMDB key", "TMDB API-kulcs": "TMDB API key",
    "Illeszd be a TMDB API Read Access Token / API-kulcs értékét.\nA kulcs a Windows-fiókodhoz kötött DPAPI-védelemmel kerül mentésre:": "Paste your TMDB API Read Access Token or API key.\nThe key is protected with DPAPI and tied to your Windows account:",
    "Távoli NAS": "Remote NAS", "TMDB API-kulcs megadása.": "Set the TMDB API key.",
    "Add meg egyszer a NAS eléréseit. A sorrend: helyi hálózat, DDNS, QuickConnect. Elég egy működő elérés; a többi tartalék. A forrásmappákat minden kapcsolaton ugyanazzal az útvonallal használjuk.": "Browse the NAS shared folders through the QuickConnect relay. The NAS password is protected and tied to your Windows account.",
    "Ez a próba először a QuickConnect közvetítői végpontján, majd közvetlenül próbálja elérni a DSM API-t. A jelszót a program nem menti el. Siker esetén megmutatja a megosztott mappákat.": "This test first tries the QuickConnect relay endpoint, then connects directly to the DSM API. The password is not saved. If the test succeeds, the shared folders are shown.",
    "A kapcsolatpróba eredménye itt jelenik meg.": "Connection test results will appear here.",
    "Kapcsolat tesztelése": "Test connection", "Eredmény másolása": "Copy results", "Napló mentése…": "Save log…",
    "Milyen címen jelenjen meg az összevont kártya?": "What title should the merged card use?",
    "Közös sorozatcím": "Shared show title", "Műsorok összevonása": "Merge TV shows",
    "Válaszd ki, melyik másik kártyát kapcsoljam ehhez:": "Choose another card to merge with this one:",
    "Keresés": "Search", "Nincs kép": "No image", "Betöltés...": "Loading…",
    "További adatokhoz előbb párosítsd a médiát a TMDB-vel.": "Match this media with TMDB to load more details.",
    "Minden mezőt ki kell tölteni!": "All fields are required.", "Hiba": "Error", "Figyelmeztetés": "Warning",
    "Adatbázis hiba": "Database error", "Adatbázishiba": "Database error",
    "Hiányzó adat": "Missing information", "Hiányzó cím": "Missing title", "Hiányzó kulcs": "Missing key",
    "Hiányzó név": "Missing name", "Hiányzó útvonal": "Missing path", "Már létezik": "Already exists",
    "Nem található": "Not found", "Siker": "Success", "Mentve": "Saved", "Folyamatban": "In progress",
    "Lejátszás folyamatban": "Playback in progress", "Cache ürítve": "Cache cleared",
    "Mentés elkészült": "Backup complete", "Mentés visszaállítása": "Restore backup",
    "Visszaállítás kész": "Restore complete", "Visszaállítási hiba": "Restore error",
    "Mentési hiba": "Save error", "Napló mentve": "Log saved", "QuickConnect hiba": "QuickConnect error",
    "Mappalista hiba": "Folder list error", "MPV hiba": "MPV error", "Lejátszási hiba": "Playback error",
    "Távoli lejátszási hiba": "Remote playback error", "TMDB Hiba": "TMDB error", "Konfigurációs figyelmeztetés": "Configuration warning",
    "Beolvasási figyelmeztetések": "Scan warnings", "Részleges ürítés": "Partial cleanup",
    "Médiatár törlése": "Delete library", "Mentés hitelesítő adatok nélkül": "Backup without credentials",
    "Plakátcache ürítése": "Clear poster cache", "TMDB-adatcache ürítése": "Clear TMDB data cache",
    "Visszavonod a kézi TMDB-párosítást? A program ezután újra megpróbálja az automatikus párosítást.": "Undo the manual TMDB match? The app will then try automatic matching again.",
    "Törlöd a letöltött plakátképeket? A képek szükség esetén újra letöltődnek.": "Delete downloaded poster images? They will be downloaded again when needed.",
    "Törlöd a TMDB-részletes adatok gyorsítótárát? A médiatárban tárolt címek, leírások és kézi párosítások megmaradnak.": "Delete cached TMDB details? Titles, descriptions, and manual matches stored in the library will remain.",
    "A mentés az adatbázist és a beállításokat tartalmazza, de a TMDB-kulcsot és a NAS-jelszót nem. Visszaállítás után ezeket újra meg kell adni. Folytatod?": "The backup includes the database and settings, but not the TMDB key or NAS password. You will need to enter them again after restoring. Continue?",
    "A visszaállítás lecseréli a jelenlegi beállításokat és adatbázist. A program előtte külön biztonsági másolatot készít a mostani állapotról. Folytatod?": "Restoring will replace the current settings and database. The app will first create a separate backup of the current state. Continue?",
    "Médiatár törlése": "Delete library", "Kézi párosítás visszavonása": "Undo manual match",
    "Már fut egy videoinformációs keresés.": "A media information search is already running.",
    "A NAS-böngészőből egyszerre egy videót lehet lejátszani.": "Only one video can be played at a time from the NAS browser.",
    "Az aktuális médiatárban legalább két külön TV-műsor-kártyának kell lennie az összevonáshoz.": "At least two separate TV show cards must be present in the current library to merge them.",
    "Nincs másik kártya": "No other card", "Nincs kézi párosítás": "No manual match",
    "Ehhez az elemhez nem tartozik visszavonható kézi párosítás.": "This item has no manual match to undo.",
    "Ez az útvonal már szerepel a listában.": "This path is already in the list.", "Mappa már hozzáadva": "Folder already added",
    "A visszaállítás most nem indítható el": "Restore cannot be started right now",
    "A biztonságos visszaállításhoz előbb várd meg a beolvasások végét, és zárd be a futó MPV-lejátszást. Ezután próbáld újra.": "For a safe restore, wait for all scans to finish and close any active MPV playback. Then try again.",
    "Válassz ki egy epizódot a listából!": "Select an episode from the list.",
    "Ehhez a kártyához nem tartozik elérési útvonal.": "This card has no associated path.",
    "Adj meg egy címet a kereséshez.": "Enter a title to search for.", "Adj meg egy nevet a médiatárnak.": "Enter a name for the library.",
    "Ezzel a névvel már van médiatár.": "A library with this name already exists.", "Nem adtál meg TMDB API-kulcsot.": "No TMDB API key was provided.",
    "A kiválasztott médiatár már nem létezik.": "The selected library no longer exists.",
    "Nem találom a megnyitott kártya médiatárát.": "The library for the open card could not be found.",
    "A TMDB nem talált ilyen címet a megadott kategóriában.": "TMDB found no title matching this category.",
    "A kulcs el lett mentve, a műsortár újra lekéri a címeket, leírásokat és plakátokat.\nA letöltés az internetkapcsolattól és a találatok számától függően eltarthat egy ideig.": "The key was saved. The library will fetch titles, descriptions, and posters again.\nThis may take some time depending on your internet connection and the number of results.",
    "A lejátszási beállítások elmentve.": "Playback settings saved.",
    "A távoli mappa hozzáadva ehhez: {library}\n{path}\n\nA beállítás megmarad a következő indításra is.": "The remote folder was added to: {library}\n{path}\n\nThis setting will be saved for the next launch.",
    "A visszaállítás elkészült. A SynoStream most újraindul, hogy a teljes felület és az adatbázis az új állapotot használja.\n\nA korábbi adatbázis másolata:\n{database_backup}\nA korábbi konfiguráció másolata:\n{config_backup}": "Restore is complete. SynoStream will now restart to load the restored interface and database.\n\nPrevious database backup:\n{database_backup}\nPrevious configuration backup:\n{config_backup}",
    "A licenc és jogi tájékoztató": "License and legal information",
    "Kiadás: Nyilvános kiadás": "Release: Public release", "Lejátszó: MPV": "Player: MPV",
    "SynoStream mentés (*.zip)": "SynoStream backup (*.zip)",
    "SynoStream – licenc és jogi tájékoztató": "SynoStream – License and legal information",
}

_UI_PREFIXES_EN = (
    ("Verzió: ", "Version: "),
    ("Megjelenés: ", "Release date: "),
    ("Epizódhossz: ", "Episode runtime: "),
    ("Játékidő: ", "Runtime: "),
    ("Korhatár (", "Age rating ("),
    ("Korhatár: ", "Age rating: "),
    ("Kész: ", "Ready: "),
    ("Nem sikerült elindítani az MPV-t: ", "Could not start MPV: "),
    ("Nem sikerült csatlakozni:\n", "Could not connect:\n"),
    ("Nem sikerült lekérni a mappát:\n", "Could not load folder:\n"),
    ("Nem sikerült elmenteni a naplót:\n", "Could not save the log:\n"),
    ("Nem sikerült elmenteni a távoli mappát:\n", "Could not save the remote folder:\n"),
    ("Nem sikerült törölni a médiatárat:\n", "Could not delete the library:\n"),
    ("Nem sikerült elmenteni a médiatárat:\n", "Could not save the library:\n"),
    ("Nem sikerült elmenteni a kulcsot:\n", "Could not save the key:\n"),
    ("MPV letöltése: ", "Downloading MPV: "),
    ("MPV letöltése… ", "Downloading MPV… "),
    ("A program mappájába nem lehet írni, ezért a SynoStream nem indítható el:", "SynoStream cannot start because the application folder is not writable:"),
    ("Nem sikerült elmenteni a mappabeállításokat:\n", "Could not save folder settings:\n"),
    ("Nem sikerült menteni a videoinformációkat: ", "Could not save media information: "),
    ("Nem sikerült visszaállítani a mentést:\n", "Could not restore the backup:\n"),
    ("Nem sikerült elkészíteni a mentést:\n", "Could not create the backup:\n"),
    ("Nem sikerült inicializálni az adatbázist:\n", "Could not initialize the database:\n"),
    ("Nem sikerült üríteni a cache-t:\n", "Could not clear the cache:\n"),
    ("Nem sikerült menteni a beállításokat:\n", "Could not save settings:\n"),
    ("Nem sikerült előkészíteni az epizódlistát: ", "Could not prepare the episode list: "),
    ("Nem sikerült feloldani az összevonást:\n", "Could not undo the merge:\n"),
    ("Nem sikerült elmenteni az összevonást:\n", "Could not save the merge:\n"),
    ("Nem sikerült visszavonni a párosítást:\n", "Could not undo the match:\n"),
    ("Nem sikerült kapcsolódni a TMDB-hez:\n", "Could not connect to TMDB:\n"),
    ("Nem találhatók videófájlok ebben a mappában.", "No video files were found in this folder."),
    ("Műfaj: ", "Genres: "), ("TMDB értékelés: ", "TMDB rating: "),
    ("Szereplők: ", "Cast: "), ("Megjelenés: ", "Release date: "),
    ("Műsorok összevonása", "Merge TV shows"),
)


def _compile_translation_templates():
    templates = []
    for source, target in _UI_TEXTS_EN.items():
        if "{" not in source:
            continue
        pattern = re.escape(source)
        pattern = re.sub(r"\\\{([A-Za-z_]\w*)\\\}", r"(?P<\1>.*?)", pattern)
        templates.append((re.compile(pattern, re.DOTALL), target))
    return tuple(templates)


_UI_TEMPLATE_PATTERNS_EN = _compile_translation_templates()


def set_ui_language(language):
    global UI_LANGUAGE
    UI_LANGUAGE = "en" if language == "en" else "hu"
    application = _QtApplication.instance()
    if application is not None and hasattr(application, 'update_qt_language'):
        application.update_qt_language()


def current_tmdb_language():
    return "en-US" if UI_LANGUAGE == "en" else "hu-HU"


_UI_TEXTS_EN.update({
    "Az ismeretlen fájlokat is töröljem": "Also delete unknown files",
    "Ismeretlen fájlok – alapértelmezés szerint megmaradnak": "Unknown files – kept by default",
    "A NAS nem adta meg a fizikai útvonalat; a törlés nem végezhető el biztonságosan.": "The NAS did not provide the physical path; deletion cannot be performed safely.",
})


_UI_TEXTS_EN.update({
    'Kétlépcsős azonosítás':'Two-step verification',
    'A NAS egyszer használatos kódja:':'One-time NAS verification code:',
    'Megbízható eszköz megjegyzése a kétlépcsős belépéshez':'Remember this device for two-step verification',
    'Érvénytelen QuickConnect-azonosító a beállításokban; add meg újra.':'Invalid QuickConnect ID in settings; enter it again.',
    'Érvénytelen QuickConnect-régió; a teszt megszakadt.':'Invalid QuickConnect region; the test was stopped.',
    'A NAS nem értelmezhető JSON-választ adott.':'The NAS returned an invalid JSON response.',
    'A NAS nem értelmezhető API-választ adott.':'The NAS returned an invalid API response.',
    'Mentési figyelmeztetés':'Settings could not be saved',
    'MPV telepítése nem sikerült':'MPV installation failed',
    'Kétlépcsős kód szükséges: Nyisd meg a Beállítások NAS-kapcsolatát, add meg az egyszer használatos kódot, és a háttérműveletekhez engedélyezd a megbízható eszköz megjegyzését.':'Two-step verification required: open NAS connection settings, enter a one-time code and enable trusted device storage for background operations.',
})

def translate_text(text):
    if not isinstance(text, str) or UI_LANGUAGE != "en":
        return text
    if text in _UI_TEXTS_EN:
        return _UI_TEXTS_EN[text]
    # Allow callers to interpolate dynamic values into the translated templates.
    # This keeps messages with paths, titles, and backup filenames localizable.
    for pattern, target in _UI_TEMPLATE_PATTERNS_EN:
        match = pattern.fullmatch(text)
        if match:
            return target.format(**match.groupdict())
    if text.startswith("SynoStream ") and "Copyright © 2026 Lőrincz László" in text:
        return re.sub(
            r"A SynoStream a GNU GPL 3\.0-only licenc alapján használható, módosítható és továbbadható\. "
            r"A licenc a szoftver jótállás nélküli terjesztéséről is rendelkezik\. "
            r"A teljes licencszöveg alább olvasható\.",
            "SynoStream may be used, modified, and redistributed under the GNU GPL 3.0-only license. "
            "The license also provides for distribution of the software without warranty. "
            "Read the full license text below.",
            text,
        )
    match = re.fullmatch(r"(\d+)\. évad", text)
    if match:
        return f"Season {match.group(1)}"
    match = re.fullmatch(r"(\d+)\. rész", text)
    if match:
        return f"Episode {match.group(1)}"
    match = re.fullmatch(r"(.+) Műsortár", text)
    if match:
        return f"{match.group(1)} Library"
    match = re.fullmatch(r"(.+) médiatár törlése", text)
    if match:
        return f"Delete {match.group(1)} library"
    match = re.fullmatch(r"(.+) médiatárához adás", text)
    if match:
        return f"Add to {match.group(1)} library"
    match = re.fullmatch(r"⚠ (\d+) figyelmeztetés", text)
    if match:
        return f"⚠ {match.group(1)} warning(s)"
    match = re.fullmatch(r"⚠ Részleges lista\. ?(.*)", text, re.DOTALL)
    if match:
        return f"⚠ Partial list. {match.group(1)}"
    match = re.fullmatch(r"Biztosan törlöd a\(z\) „(.+)” médiatárat\?\n\nA beállítás és a médiatár útvonalai törlődnek, a videófájlok nem\.", text, re.DOTALL)
    if match:
        return f"Delete the “{match.group(1)}” library?\n\nThe library settings and folder paths will be removed. Video files will not be deleted."
    match = re.fullmatch(r"(\d+) plakát törölve\.", text)
    if match:
        return f"{match.group(1)} poster(s) deleted."
    match = re.fullmatch(r"(\d+) TMDB-adat törölve a gyorsítótárból\.", text)
    if match:
        return f"{match.group(1)} TMDB record(s) removed from the cache."
    match = re.fullmatch(r"Videoinformációk hozzárendelve: (.+) \(ID: (\d+)\)", text)
    if match:
        return f"Media information matched: {match.group(1)} (ID: {match.group(2)})"
    match = re.fullmatch(r"A távoli mappa hozzáadva ehhez: (.+)\n(.*)\n\nA beállítás megmarad a következő indításra is\.", text, re.DOTALL)
    if match:
        return f"The remote folder was added to: {match.group(1)}\n{match.group(2)}\n\nThis setting will be saved for the next launch."
    match = re.fullmatch(r"Kész: (\d+) film, (\d+) TV műsor", text)
    if match:
        return f"Ready: {match.group(1)} movies, {match.group(2)} TV shows"
    match = re.fullmatch(r"Kész: (\d+) elem – (.+)", text)
    if match:
        return f"Ready: {match.group(1)} items – {match.group(2)}"
    if "\n" in text:
        return "\n".join(translate_text(line) for line in text.split("\n"))
    for source, target in _UI_PREFIXES_EN:
        if text.startswith(source):
            return target + text[len(source):]
    return text


def _show_localized_edit_context_menu_at(widget, global_position, multiline=False):
    """Show the standard editing commands using the app's selected language."""
    menu = QMenu(widget)
    read_only = widget.isReadOnly()

    if multiline:
        text = widget.toPlainText()
        cursor = widget.textCursor()
        has_selection = cursor.hasSelection()
        selection_is_all = (
            has_selection
            and cursor.selectionStart() == 0
            and cursor.selectionEnd() >= len(text)
        )
        document = widget.document()
        can_undo = document.isUndoAvailable() and not read_only
        can_redo = document.isRedoAvailable() and not read_only

        def delete_selection():
            cursor = widget.textCursor()
            cursor.removeSelectedText()
            widget.setTextCursor(cursor)
    else:
        text = widget.text()
        selected_text = widget.selectedText()
        has_selection = bool(selected_text)
        selection_is_all = has_selection and len(selected_text) == len(text)
        can_undo = widget.isUndoAvailable() and not read_only
        can_redo = widget.isRedoAvailable() and not read_only

        def delete_selection():
            widget.insert("")

    clipboard_data = QApplication.clipboard().mimeData()
    clipboard_has_text = bool(clipboard_data and clipboard_data.hasText())

    def add_action(label, callback, enabled=True, shortcut=None):
        action = menu.addAction(translate_text(label))
        action.setEnabled(enabled)
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(callback)
        return action

    add_action("Visszavonás", widget.undo, can_undo, QKeySequence.StandardKey.Undo)
    add_action("Ismét", widget.redo, can_redo, QKeySequence.StandardKey.Redo)
    menu.addSeparator()
    clipboard_allowed = True
    if not multiline:
        clipboard_allowed = widget.echoMode() not in (
            _QtLineEdit.EchoMode.Password,
            _QtLineEdit.EchoMode.NoEcho,
        )
    add_action(
        "Kivágás", widget.cut,
        has_selection and not read_only and clipboard_allowed,
        QKeySequence.StandardKey.Cut,
    )
    copy_allowed = has_selection and clipboard_allowed
    add_action("Másolás", widget.copy, copy_allowed, QKeySequence.StandardKey.Copy)
    add_action(
        "Beillesztés", widget.paste,
        clipboard_has_text and not read_only,
        QKeySequence.StandardKey.Paste,
    )
    add_action("Törlés", delete_selection, has_selection and not read_only)
    menu.addSeparator()
    add_action("Összes kijelölése", widget.selectAll, bool(text) and not selection_is_all,
               QKeySequence.StandardKey.SelectAll)
    metrics = menu.fontMetrics()
    menu.setMinimumWidth(max(
        metrics.horizontalAdvance(action.text())
        + metrics.horizontalAdvance(action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)) + 64
        for action in menu.actions() if not action.isSeparator()
    ))
    menu.exec(global_position)


def _show_localized_edit_context_menu(widget, event, multiline=False):
    _show_localized_edit_context_menu_at(widget, event.globalPos(), multiline)
    event.accept()


def _install_localized_edit_context_menu(widget, multiline=False):
    """Localize a native Qt editor's menu without replacing its editor widget."""
    if widget is None or widget.property("_synostream_localized_context_menu"):
        return
    widget.setProperty("_synostream_localized_context_menu", True)
    widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    widget.customContextMenuRequested.connect(
        lambda point, target=widget, is_multiline=multiline:
            _show_localized_edit_context_menu_at(target, target.mapToGlobal(point), is_multiline)
    )


_I18N_ROLE = int(Qt.ItemDataRole.UserRole) + 937


class _LocalizedTextMixin:
    def __init__(self, *args, **kwargs):
        source = args[0] if args and isinstance(args[0], str) else kwargs.get("text")
        if isinstance(source, str):
            args = (translate_text(source), *args[1:]) if args and isinstance(args[0], str) else args
            if "text" in kwargs:
                kwargs["text"] = translate_text(source)
        super().__init__(*args, **kwargs)
        if isinstance(source, str):
            self.setProperty("_synostream_source_text", source)

    def setText(self, text):
        if isinstance(text, str):
            self.setProperty("_synostream_source_text", text)
            text = translate_text(text)
        return super().setText(text)

    def setRawText(self, text):
        """Set dynamic media text without treating it as a translatable UI label."""
        self.setProperty("_synostream_source_text", None)
        return super().setText(text)

    def setToolTip(self, text):
        if isinstance(text, str):
            self.setProperty("_synostream_source_tooltip", text)
            text = translate_text(text)
        return super().setToolTip(text)

    def setRawToolTip(self, text):
        self.setProperty("_synostream_source_tooltip", None)
        return super().setToolTip(text)

    def setAccessibleName(self, text):
        if isinstance(text, str):
            self.setProperty("_synostream_source_accessible_name", text)
            text = translate_text(text)
        return super().setAccessibleName(text)

    def retranslate_texts(self):
        for prop, setter in (
            ("_synostream_source_text", self.setText),
            ("_synostream_source_tooltip", self.setToolTip),
            ("_synostream_source_accessible_name", self.setAccessibleName),
        ):
            source = self.property(prop)
            if isinstance(source, str):
                setter(source)


class QApplication(_QtApplication):
    def __init__(self, *args, **kwargs):
        _QtApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
        identity_set = configure_windows_identity()
        super().__init__(*args, **kwargs)
        self._synostream_app_id_set = identity_set
        self._synostream_application_icon = load_application_icon(APP_ICON_FILE)
        self.setWindowIcon(self._synostream_application_icon)
        from synostream_window_chrome import install_window_chrome
        install_window_chrome(self, self._synostream_application_icon, lambda: UI_LANGUAGE, APP_ICON_FILE)
        self._qt_hungarian = QTranslator(self)
        self._qt_hungarian.load(os.path.join(RESOURCE_DIR, 'assets', 'qt', 'qtbase_hu.qm'))
        self.update_qt_language()

    def update_qt_language(self):
        if not hasattr(self, '_qt_hungarian'):
            return
        self.removeTranslator(self._qt_hungarian)
        if UI_LANGUAGE == 'hu':
            self.installTranslator(self._qt_hungarian)

    def notify(self, widget, event):
        if event.type() == QEvent.Type.ContextMenu:
            if isinstance(widget, _QtLineEdit):
                _show_localized_edit_context_menu(widget, event)
                return True
            editor = widget if isinstance(widget, (_QtPlainTextEdit, _QtTextEdit)) else None
            parent = widget.parent()
            if isinstance(parent, (_QtPlainTextEdit, _QtTextEdit)) and widget is parent.viewport():
                editor = parent
            if editor is not None:
                _show_localized_edit_context_menu(editor, event, multiline=True)
                return True
        return super().notify(widget, event)

    @staticmethod
    def allWidgets():
        return _QtApplication.allWidgets()

    def retranslate_all_widgets(self):
        for widget in _QtApplication.allWidgets():
            retranslate = getattr(widget, "retranslate_texts", None)
            if callable(retranslate):
                retranslate()
            if isinstance(widget, QComboBox):
                widget.retranslate_items()
            if isinstance(widget, QTabWidget):
                widget.retranslate_tabs()
            if isinstance(widget, QTreeWidget):
                widget.retranslate_tree()
            if isinstance(widget, QDialogButtonBox):
                localize_standard_buttons(widget)


def localize_standard_buttons(button_box):
    labels = {
        _QtDialogButtonBox.StandardButton.Ok: ("OK", "Rendben"),
        _QtDialogButtonBox.StandardButton.Save: ("Save", "Mentés"),
        _QtDialogButtonBox.StandardButton.Cancel: ("Cancel", "Mégse"),
        _QtDialogButtonBox.StandardButton.Close: ("Close", "Bezárás"),
        _QtDialogButtonBox.StandardButton.Yes: ("Yes", "Igen"),
        _QtDialogButtonBox.StandardButton.No: ("No", "Nem"),
        _QtDialogButtonBox.StandardButton.Open: ("Open", "Megnyitás"),
        _QtDialogButtonBox.StandardButton.Apply: ("Apply", "Alkalmaz"),
        _QtDialogButtonBox.StandardButton.Reset: ("Reset", "Alaphelyzet"),
    }
    for standard, (english, hungarian) in labels.items():
        button = button_box.button(standard)
        if button is not None:
            button.setText(english if UI_LANGUAGE == "en" else hungarian)


class QDialogButtonBox(_QtDialogButtonBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        localize_standard_buttons(self)


class QLabel(_LocalizedTextMixin, _QtLabel):
    pass


class QPushButton(_LocalizedTextMixin, _QtPushButton):
    pass


class QCheckBox(_LocalizedTextMixin, _QtCheckBox):
    pass


class QGroupBox(_QtGroupBox):
    def __init__(self, *args, **kwargs):
        source = args[0] if args and isinstance(args[0], str) else kwargs.get("title")
        if isinstance(source, str):
            args = (translate_text(source), *args[1:]) if args and isinstance(args[0], str) else args
            if "title" in kwargs:
                kwargs["title"] = translate_text(source)
        super().__init__(*args, **kwargs)
        if isinstance(source, str):
            self.setProperty("_synostream_source_title", source)

    def setTitle(self, text):
        if isinstance(text, str):
            self.setProperty("_synostream_source_title", text)
            text = translate_text(text)
        return super().setTitle(text)

    def setToolTip(self, text):
        if isinstance(text, str):
            self.setProperty("_synostream_source_tooltip", text)
            text = translate_text(text)
        return super().setToolTip(text)

    def retranslate_texts(self):
        title = self.property("_synostream_source_title")
        if isinstance(title, str):
            self.setTitle(title)
        tooltip = self.property("_synostream_source_tooltip")
        if isinstance(tooltip, str):
            self.setToolTip(tooltip)


class QDialog(_LocalizedTextMixin, _QtDialog):
    def setWindowTitle(self, text):
        if isinstance(text, str):
            self.setProperty("_synostream_source_window_title", text)
            text = translate_text(text)
        return super().setWindowTitle(text)

    def retranslate_texts(self):
        super().retranslate_texts()
        source = self.property("_synostream_source_window_title")
        if isinstance(source, str):
            self.setWindowTitle(source)


class QMainWindow(_LocalizedTextMixin, _QtMainWindow):
    def setWindowTitle(self, text):
        if isinstance(text, str):
            self.setProperty("_synostream_source_window_title", text)
            text = translate_text(text)
        return super().setWindowTitle(text)

    def retranslate_texts(self):
        super().retranslate_texts()
        source = self.property("_synostream_source_window_title")
        if isinstance(source, str):
            self.setWindowTitle(source)


class QLineEdit(_QtLineEdit):
    def contextMenuEvent(self, event):
        _show_localized_edit_context_menu(self, event)

    def setToolTip(self, text):
        if isinstance(text, str):
            self.setProperty("_synostream_source_tooltip", text)
            text = translate_text(text)
        return super().setToolTip(text)

    def setPlaceholderText(self, text):
        if isinstance(text, str):
            self.setProperty("_synostream_source_placeholder", text)
            text = translate_text(text)
        return super().setPlaceholderText(text)

    def retranslate_texts(self):
        tooltip = self.property("_synostream_source_tooltip")
        if isinstance(tooltip, str):
            self.setToolTip(tooltip)
        source = self.property("_synostream_source_placeholder")
        if isinstance(source, str):
            self.setPlaceholderText(source)


class QPlainTextEdit(_QtPlainTextEdit):
    def contextMenuEvent(self, event):
        _show_localized_edit_context_menu(self, event, multiline=True)

    def setToolTip(self, text):
        if isinstance(text, str):
            self.setProperty("_synostream_source_tooltip", text)
            text = translate_text(text)
        return super().setToolTip(text)

    def setPlaceholderText(self, text):
        if isinstance(text, str):
            self.setProperty("_synostream_source_placeholder", text)
            text = translate_text(text)
        return super().setPlaceholderText(text)

    def retranslate_texts(self):
        tooltip = self.property("_synostream_source_tooltip")
        if isinstance(tooltip, str):
            self.setToolTip(tooltip)
        source = self.property("_synostream_source_placeholder")
        if isinstance(source, str):
            self.setPlaceholderText(source)


class QComboBox(_QtComboBox):
    def setEditable(self, editable):
        super().setEditable(editable)
        if editable:
            _install_localized_edit_context_menu(self.lineEdit())

    def setToolTip(self, text):
        if isinstance(text, str):
            self.setProperty("_synostream_source_tooltip", text)
            text = translate_text(text)
        return super().setToolTip(text)

    def setAccessibleName(self, text):
        if isinstance(text, str):
            self.setProperty("_synostream_source_accessible_name", text)
            text = translate_text(text)
        return super().setAccessibleName(text)

    def retranslate_texts(self):
        for prop, setter in (
            ("_synostream_source_tooltip", self.setToolTip),
            ("_synostream_source_accessible_name", self.setAccessibleName),
        ):
            source = self.property(prop)
            if isinstance(source, str):
                setter(source)

    def _display_text(self, args):
        if args and isinstance(args[0], str):
            return args[0], 0
        if len(args) > 1 and isinstance(args[1], str):
            return args[1], 1
        return None, -1

    def addItem(self, *args, **kwargs):
        source, text_index = self._display_text(args)
        if source is not None:
            args = args[:text_index] + (translate_text(source),) + args[text_index + 1:]
        super().addItem(*args, **kwargs)
        if source is not None:
            self.setItemData(self.count() - 1, source, _I18N_ROLE)

    def addItems(self, texts):
        for text in texts:
            self.addItem(text)

    def setItemText(self, index, text):
        if isinstance(text, str):
            self.setItemData(index, text, _I18N_ROLE)
            text = translate_text(text)
        return super().setItemText(index, text)

    def retranslate_items(self):
        for index in range(self.count()):
            source = self.itemData(index, _I18N_ROLE)
            if isinstance(source, str):
                _QtComboBox.setItemText(self, index, translate_text(source))


class QTabWidget(_QtTabWidget):
    def addTab(self, *args):
        text_index = 0 if args and isinstance(args[0], QWidget) else 1
        if len(args) > text_index and isinstance(args[text_index], str):
            source = args[text_index]
            args = args[:text_index] + (translate_text(source),) + args[text_index + 1:]
            index = super().addTab(*args)
            self.setTabData(index, source) if hasattr(self, "setTabData") else None
            self.setProperty(f"_synostream_tab_{index}", source)
            return index
        return super().addTab(*args)

    def setTabText(self, index, text):
        if isinstance(text, str):
            self.setProperty(f"_synostream_tab_{index}", text)
            text = translate_text(text)
        return super().setTabText(index, text)

    def retranslate_tabs(self):
        for index in range(self.count()):
            source = self.property(f"_synostream_tab_{index}")
            if isinstance(source, str):
                _QtTabWidget.setTabText(self, index, translate_text(source))


class QFormLayout(_QtFormLayout):
    def addRow(self, *args):
        if args and isinstance(args[0], str):
            label = QLabel(args[0])
            return super().addRow(label, *args[1:])
        return super().addRow(*args)


class QTreeWidgetItem(_QtTreeWidgetItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        strings = next((arg for arg in args if isinstance(arg, (list, tuple)) and all(isinstance(x, str) for x in arg)), None)
        if strings is None and args and isinstance(args[0], str):
            strings = [args[0]]
        if strings:
            for column, text in enumerate(strings):
                self.setData(column, _I18N_ROLE, text)
                _QtTreeWidgetItem.setText(self, column, translate_text(text))

    def setText(self, column, text):
        if isinstance(text, str):
            self.setData(column, _I18N_ROLE, text)
            text = translate_text(text)
        return super().setText(column, text)

    def setRawText(self, column, text):
        self.setData(column, _I18N_ROLE, None)
        return _QtTreeWidgetItem.setText(self, column, text)

    def setToolTip(self, column, text):
        if isinstance(text, str):
            self.setData(column, _I18N_ROLE + 1, text)
            text = translate_text(text)
        return super().setToolTip(column, text)


class QListWidgetItem(_QtListWidgetItem):
    def __init__(self, *args, **kwargs):
        source = args[0] if args and isinstance(args[0], str) else None
        if source is not None:
            args = (translate_text(source),) + args[1:]
        super().__init__(*args, **kwargs)
        if source is not None:
            self.setData(_I18N_ROLE, source)

    def setText(self, text):
        if isinstance(text, str):
            self.setData(_I18N_ROLE, text)
            text = translate_text(text)
        return super().setText(text)

    def setRawText(self, text):
        self.setData(_I18N_ROLE, None)
        return _QtListWidgetItem.setText(self, text)


class _LocalizedDialogMethods:
    @staticmethod
    def _translate_dialog_args(args, positions):
        args = list(args)
        for index in positions:
            if index < len(args) and isinstance(args[index], str):
                args[index] = translate_text(args[index])
        return args


class QMessageBox(_QtMessageBox):
    @staticmethod
    def _show_localized(icon, *args, **kwargs):
        args = list(args)
        parent = args[0] if args else kwargs.pop("parent", None)
        title = args[1] if len(args) > 1 else kwargs.pop("title", "")
        text = args[2] if len(args) > 2 else kwargs.pop("text", "")
        buttons = args[3] if len(args) > 3 else kwargs.pop("buttons", _QtMessageBox.StandardButton.Ok)
        default_button = args[4] if len(args) > 4 else kwargs.pop("defaultButton", _QtMessageBox.StandardButton.NoButton)
        box = _QtMessageBox(parent)
        box.setIcon(icon)
        box.setWindowTitle(translate_text(title))
        box.setText(translate_text(text))
        button_labels = {
            _QtMessageBox.StandardButton.Ok: ("OK", "Rendben"),
            _QtMessageBox.StandardButton.Save: ("Save", "Mentés"),
            _QtMessageBox.StandardButton.Cancel: ("Cancel", "Mégse"),
            _QtMessageBox.StandardButton.Close: ("Close", "Bezárás"),
            _QtMessageBox.StandardButton.Yes: ("Yes", "Igen"),
            _QtMessageBox.StandardButton.No: ("No", "Nem"),
            _QtMessageBox.StandardButton.Open: ("Open", "Megnyitás"),
            _QtMessageBox.StandardButton.Apply: ("Apply", "Alkalmaz"),
            _QtMessageBox.StandardButton.Reset: ("Reset", "Alaphelyzet"),
        }
        for standard, (english, hungarian) in button_labels.items():
            if buttons & standard:
                button = box.addButton(standard)
                button.setText(english if UI_LANGUAGE == "en" else hungarian)
        if default_button and default_button != _QtMessageBox.StandardButton.NoButton:
            box.setDefaultButton(default_button)
        box.exec()
        return box.standardButton(box.clickedButton())

    @staticmethod
    def critical(*args, **kwargs):
        return QMessageBox._show_localized(_QtMessageBox.Icon.Critical, *args, **kwargs)

    @staticmethod
    def warning(*args, **kwargs):
        return QMessageBox._show_localized(_QtMessageBox.Icon.Warning, *args, **kwargs)

    @staticmethod
    def information(*args, **kwargs):
        return QMessageBox._show_localized(_QtMessageBox.Icon.Information, *args, **kwargs)

    @staticmethod
    def question(*args, **kwargs):
        return QMessageBox._show_localized(_QtMessageBox.Icon.Question, *args, **kwargs)


class QFileDialog(_QtFileDialog):
    @staticmethod
    def getSaveFileName(*args, **kwargs):
        args = _LocalizedDialogMethods._translate_dialog_args(args, (1, 3))
        if isinstance(kwargs.get("caption"), str): kwargs["caption"] = translate_text(kwargs["caption"])
        if isinstance(kwargs.get("filter"), str): kwargs["filter"] = translate_text(kwargs["filter"])
        return _QtFileDialog.getSaveFileName(*args, **kwargs)

    @staticmethod
    def getOpenFileName(*args, **kwargs):
        args = _LocalizedDialogMethods._translate_dialog_args(args, (1, 3))
        if isinstance(kwargs.get("caption"), str): kwargs["caption"] = translate_text(kwargs["caption"])
        if isinstance(kwargs.get("filter"), str): kwargs["filter"] = translate_text(kwargs["filter"])
        return _QtFileDialog.getOpenFileName(*args, **kwargs)

    @staticmethod
    def getExistingDirectory(*args, **kwargs):
        args = _LocalizedDialogMethods._translate_dialog_args(args, (1,))
        if isinstance(kwargs.get("caption"), str): kwargs["caption"] = translate_text(kwargs["caption"])
        return _QtFileDialog.getExistingDirectory(*args, **kwargs)


class QInputDialog(_QtInputDialog):
    @staticmethod
    def getText(*args, **kwargs):
        args = list(args)
        parent = args[0] if args else kwargs.get("parent")
        title = args[1] if len(args) > 1 else kwargs.get("title", "")
        label = args[2] if len(args) > 2 else kwargs.get("label", "")
        echo = args[3] if len(args) > 3 else kwargs.get("echo", _QtLineEdit.EchoMode.Normal)
        initial = args[4] if len(args) > 4 else kwargs.get("text", "")
        flags = args[5] if len(args) > 5 else kwargs.get("flags")
        hints = args[6] if len(args) > 6 else kwargs.get("inputMethodHints")
        dialog = _QtInputDialog(parent)
        dialog.setInputMode(_QtInputDialog.InputMode.TextInput)
        dialog.setWindowTitle(translate_text(title))
        dialog.setLabelText(translate_text(label))
        dialog.setTextEchoMode(echo)
        dialog.setTextValue(initial)
        _install_localized_edit_context_menu(dialog.findChild(_QtLineEdit))
        if flags is not None:
            dialog.setWindowFlags(flags)
        if hints is not None:
            dialog.setInputMethodHints(hints)
        dialog.setOkButtonText("OK" if UI_LANGUAGE == "en" else "Rendben")
        dialog.setCancelButtonText("Cancel" if UI_LANGUAGE == "en" else "Mégse")
        accepted = dialog.exec() == _QtDialog.DialogCode.Accepted
        return dialog.textValue(), accepted

    @staticmethod
    def getItem(*args, **kwargs):
        args = list(args)
        parent = args[0] if args else kwargs.get("parent")
        title = args[1] if len(args) > 1 else kwargs.get("title", "")
        label = args[2] if len(args) > 2 else kwargs.get("label", "")
        items = args[3] if len(args) > 3 else kwargs.get("items", [])
        current = args[4] if len(args) > 4 else kwargs.get("current", 0)
        editable = args[5] if len(args) > 5 else kwargs.get("editable", False)
        return_index = kwargs.get("return_index", False)
        flags = args[6] if len(args) > 6 else kwargs.get("flags")
        hints = args[7] if len(args) > 7 else kwargs.get("inputMethodHints")
        dialog = QDialog(parent)
        dialog.setWindowTitle(translate_text(title))
        if flags is not None:
            dialog.setWindowFlags(flags)
        if hints is not None:
            dialog.setInputMethodHints(hints)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(translate_text(label), dialog))
        choices = QComboBox(dialog)
        # These labels can contain actual media titles and paths. Keep them raw.
        for item in items:
            _QtComboBox.addItem(choices, str(item))
        choices.setCurrentIndex(current)
        choices.setEditable(editable)
        layout.addWidget(choices)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        accepted = dialog.exec() == _QtDialog.DialogCode.Accepted
        selected = choices.currentIndex() if return_index else choices.currentText()
        return selected, accepted


class QTreeWidget(_QtTreeWidget):
    def retranslate_tree(self):
        def visit(item):
            for column in range(item.columnCount()):
                source = item.data(column, _I18N_ROLE)
                if isinstance(source, str):
                    _QtTreeWidgetItem.setText(item, column, translate_text(source))
                tooltip = item.data(column, _I18N_ROLE + 1)
                if isinstance(tooltip, str):
                    _QtTreeWidgetItem.setToolTip(item, column, translate_text(tooltip))
            for child_index in range(item.childCount()):
                visit(item.child(child_index))
        for index in range(self.topLevelItemCount()):
            visit(self.topLevelItem(index))


def retranslate_ui():
    app = _QtApplication.instance()
    if app is not None:
        app.retranslate_all_widgets()

# ==========================================
# ÁLLANDÓK
# ==========================================
# Az adatok forrásfuttatáskor a szkript, fagyasztott buildnél az EXE mellett jönnek létre.
BASE_DIR = os.path.dirname(os.path.abspath(
    sys.executable if getattr(sys, "frozen", False) else __file__
))
# A becsomagolt licencet a PyInstaller erőforrás-mappájából olvassuk.
APP_DIR = BASE_DIR
RESOURCE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
BASE_DIR = data_directory(APP_DIR)
try:
    _application_data_lock = acquire_application_lock(BASE_DIR, timeout=15 if "--wait-for-instance" in sys.argv else 0)
except DataDirectoryInUse:
    if "--smoke-test" not in sys.argv:
        ctypes.windll.user32.MessageBoxW(None, "A SynoStream már fut. Használd a már megnyitott ablakot.", "SynoStream", 0x40)
    raise SystemExit(2)
recover_settings_transaction(BASE_DIR)
if __name__ == '__main__' and '--smoke-test' not in sys.argv and '--updated-from' not in sys.argv:
    from synostream_updates import launch_pending_update
    if launch_pending_update('1.107', sys.executable, BASE_DIR):
        raise SystemExit(0)
backup_before_upgrade(BASE_DIR, "1.107")
if os.path.isfile(os.path.join(BASE_DIR, "media_library.db")):
    with contextlib.closing(sqlite3.connect(os.path.join(BASE_DIR, "media_library.db"))) as _preflight:
        if _preflight.execute("PRAGMA user_version").fetchone()[0] > 1:
            raise RuntimeError("Az adatbázis újabb SynoStream-verzióhoz tartozik.")
LICENSE_FILE = os.path.join(RESOURCE_DIR, "LICENSE")
APP_ICON_FILE = os.path.join(RESOURCE_DIR, "assets", "synostream.ico")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
SECRET_STORE_FILE = os.path.join(BASE_DIR, "credentials.dat")
DB_FILE = os.path.join(BASE_DIR, "media_library.db")
CACHE_DIR = os.path.join(BASE_DIR, "cache_posters")

FALLBACK_LANGUAGE = "en-US"
DEFAULT_API_KEY = "IDE_JON_A_TMDB_API_KULCS"
TMDB_BASE = "https://api.themoviedb.org/3"
IMG_BASE = "https://image.tmdb.org/t/p/w500"
VIDEO_EXTENSIONS = (".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts")
MAX_POSTER_BYTES = 15 * 1024 * 1024
NO_MATCH_TEXT = "Nem található a TMDB-n. Használd a Videoinformációk lekérését!"
LOW_CONFIDENCE_TEXT = "Nem található megbízható egyezés a TMDB-n. Használd a Videoinformációk lekérését!"

# Automatikus párosításnál a legjobb találatnak legalább ennyire kell hasonlítania a címre
# (0..1, szószintű Dice-együttható); egyező évszámnál enyhébb a követelmény.
MIN_SIMILARITY = 0.76
MIN_SIMILARITY_WITH_YEAR = 0.72

POSTER_CONNECT_TIMEOUT = 5   # mp: kapcsolódás
POSTER_READ_TIMEOUT = 5      # mp: egyetlen olvasás (ennyit blokkolhat leállításkor)
POSTER_TOTAL_TIMEOUT = 20    # mp: egy plakát teljes letöltése

CARD_W, CARD_H, CARD_SPACING = 180, 270, 12
CARD_SIZE_PRESETS = {
    "compact": (148, 278, 144, 216),
    "normal": (172, 314, 168, 252),
    "large": (220, 386, 216, 324),
}

# Minden további alkalmazásmódosításnál a verzió tizedes utáni száma növekszik.
APP_VERSION = "1.107"
MAX_POSTER_CACHE_BYTES = 512 * 1024 * 1024
BACKUP_FORMAT_VERSION = 1
POSTER_CACHE_LOCK = threading.RLock()
POSTER_CACHE_WRITERS = 0
POSTER_CACHE_GENERATION = 0
POSTER_PIXMAP_CACHE = PosterPixmapCache()
DISPLAY_STATE_CACHE = PlaybackDisplaySnapshot()
WATCHED_PATHS_CACHE = None
WATCHED_PATHS_LOCK = threading.RLock()

LOG_ROOT = os.environ.get("LOCALAPPDATA") or BASE_DIR
LOG_DIR = os.path.join(LOG_ROOT, "SynoStream", "logs")
SCAN_ERROR_LOG_FILE = os.path.join(LOG_DIR, "SynoStream_scan_errors.log")
LOGGER = logging.getLogger("SynoStream")
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False
if not LOGGER.handlers:
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        log_handler = RotatingFileHandler(
            os.path.join(LOG_DIR, "SynoStream.log"), maxBytes=2 * 1024 * 1024,
            backupCount=5, encoding="utf-8",
        )
        log_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(threadName)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        LOGGER.addHandler(log_handler)
    except OSError:
        LOGGER.addHandler(logging.NullHandler())


def log_uncaught_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    LOGGER.critical("Nem kezelt alkalmazáshiba", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = log_uncaught_exception


def redact_credentials(value):
    """Remove sensitive values from URLs before displaying or logging errors."""
    return re.sub(
        r"(?i)([_?&](?:_sid|sid|passwd|password|api_key)=)[^&\s\"']+",
        r"\1[redacted]", str(value),
    )


class CredentialRedactionFilter(logging.Filter):
    """Remove NAS session and API credentials from all application log records."""
    def filter(self, record):
        try:
            safe_message = redact_credentials(record.getMessage())
            record.args = ()
            if record.exc_info:
                traceback_text = "".join(traceback.format_exception(*record.exc_info))
                record.msg = safe_message + "\n" + redact_credentials(traceback_text)
                record.exc_info = None
                record.exc_text = None
            else:
                record.msg = safe_message
            if record.exc_text:
                record.exc_text = redact_credentials(record.exc_text)
            if record.stack_info:
                record.stack_info = redact_credentials(record.stack_info)
        except Exception:
            # Logging must continue even if an unusual record cannot be formatted.
            record.msg = "SynoStream naplóbejegyzés (érzékeny adat kiszűrve)"
            record.args = ()
            record.exc_info = None
            record.exc_text = None
        return True


LOGGER.addFilter(CredentialRedactionFilter())

SCAN_ERROR_LOGGER = logging.getLogger("SynoStream.ScanErrors")
SCAN_ERROR_LOGGER.setLevel(logging.ERROR)
SCAN_ERROR_LOGGER.propagate = False
if not SCAN_ERROR_LOGGER.handlers:
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        scan_error_handler = RotatingFileHandler(
            SCAN_ERROR_LOG_FILE,
            maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8",
        )
        scan_error_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        SCAN_ERROR_LOGGER.addHandler(scan_error_handler)
    except OSError:
        SCAN_ERROR_LOGGER.addHandler(logging.NullHandler())
SCAN_ERROR_LOGGER.addFilter(CredentialRedactionFilter())


def constant_time_equal_text(candidate, expected):
    """Compare arbitrary URL text safely without str compare_digest ASCII errors."""
    if not isinstance(candidate, str) or not isinstance(expected, str):
        return False
    return secrets.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


def local_media_browse_directory():
    """A helyi mappaválasztó a Videók mappából indul, ennek hiányában a C: gyökeréből."""
    videos_directory = os.path.join(os.path.expanduser("~"), "Videos")
    if os.path.isdir(videos_directory):
        return videos_directory
    if sys.platform == "win32":
        drive = (os.environ.get("SystemDrive") or "C:").rstrip("\\/")
        return drive + "\\"
    return os.path.abspath(os.sep)


CACHE_DIR_INIT_ERROR = None
try:
    os.makedirs(CACHE_DIR, exist_ok=True)
except OSError as exc:
    # Keep portable data beside the executable, but report an unwritable folder
    # through the GUI instead of failing before QApplication exists.
    CACHE_DIR_INIT_ERROR = exc


def set_windows_frame_colors(window):
    """Visszafogott, grafit és levendula tónusú Windows-ablakkeret beállítása."""
    if sys.platform != "win32":
        return
    try:
        dwm_set_attribute = ctypes.WinDLL("dwmapi").DwmSetWindowAttribute
        dwm_set_attribute.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
        ]
        dwm_set_attribute.restype = ctypes.c_long
        hwnd = ctypes.c_void_p(int(window.winId()))

        def colorref(value):
            red = int(value[1:3], 16)
            green = int(value[3:5], 16)
            blue = int(value[5:7], 16)
            return red | (green << 8) | (blue << 16)

        for attribute, value in (
            (34, colorref("#62596B")),  # DWMWA_BORDER_COLOR
            (35, colorref("#211F23")),  # DWMWA_CAPTION_COLOR
            (36, colorref("#F0EDF5")),  # DWMWA_TEXT_COLOR
        ):
            native_color = ctypes.c_uint(value)
            dwm_set_attribute(
                hwnd, attribute, ctypes.byref(native_color), ctypes.sizeof(native_color),
            )
    except (AttributeError, OSError, TypeError, ValueError, ctypes.ArgumentError):
        pass


# ==========================================
# KONFIGURÁCIÓ BETÖLTÉSE ÉS BIZTONSÁGI MÁSOLAT
# ==========================================
DEFAULT_CONFIG = {
    "recommendation_prefer_hungarian": True,
    "check_updates": True,
    "auto_update": False,
    "update_last_check": 0,
    "paired_sources": [],
    "torrent_sites": [{"name": "nCore", "url": "https://ncore.pro/"}],
    "download_station_destinations": {},
    "download_station_destination": "",
    "language": "hu",
    "tmdb_api_key": DEFAULT_API_KEY,
    "mpv_path": "mpv.exe",
    "preferred_audio_language": "original",
    "preferred_subtitle_language": "hu",
    "playback_fullscreen": False,
    "auto_play_next_episode": True,
    "startup_scan_mode": "all",
    "library_refresh_minutes": 5,
    "inventory_startup_v103": True,
    "card_size": "normal",
    "movies_path": "",
    "shows_path": "",
    "movies_paths": [],
    "shows_paths": [],
    "quickconnect_id": "",
    "nas_direct_url": "",
    "nas_local_url": "",
    "nas_username": "",
    "nas_password": "",
    "nas_device_tokens": "",
    "remote_movies_path": "",
    "remote_shows_path": "",
    "custom_libraries": [],
    "manual_show_groups": [],
    "excluded_media_paths": [],
    "window_geometry": "",
    "last_library": "movies",
    "media_view_settings": {},
    "library_scan_state": {},
}

SECRET_CONFIG_KEYS = {"tmdb_api_key", "nas_password", "nas_device_tokens"}
SECRET_STORE_UNREADABLE = False


def dpapi_transform(payload, protect):
    """Encrypt/decrypt bytes for the current Windows user using DPAPI."""
    if os.name != "nt":
        raise OSError("A hitelesítő adatok védelméhez Windows szükséges.")

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    source_buffer = ctypes.create_string_buffer(payload, len(payload))
    source = DATA_BLOB(
        len(payload), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    result = DATA_BLOB()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    if protect:
        transform = crypt32.CryptProtectData
        transform.argtypes = [
            ctypes.POINTER(DATA_BLOB), ctypes.c_wchar_p, ctypes.POINTER(DATA_BLOB),
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(DATA_BLOB),
        ]
        transform.restype = ctypes.c_int
        succeeded = transform(
            ctypes.byref(source), "SynoStream credentials", None, None, None,
            0x1, ctypes.byref(result),
        )
    else:
        transform = crypt32.CryptUnprotectData
        description = ctypes.c_wchar_p()
        transform.argtypes = [
            ctypes.POINTER(DATA_BLOB), ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_uint32, ctypes.POINTER(DATA_BLOB),
        ]
        transform.restype = ctypes.c_int
        succeeded = transform(
            ctypes.byref(source), ctypes.byref(description), None, None, None,
            0x1, ctypes.byref(result),
        )

    if not succeeded:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        if result.pbData:
            kernel32.LocalFree(ctypes.cast(result.pbData, ctypes.c_void_p))
        if not protect and description:
            kernel32.LocalFree(ctypes.cast(description, ctypes.c_void_p))


def load_protected_secrets():
    if not os.path.exists(SECRET_STORE_FILE):
        return {}
    with open(SECRET_STORE_FILE, "rb") as secret_file:
        decrypted = dpapi_transform(secret_file.read(), protect=False)
    secrets_data = json.loads(decrypted.decode("utf-8"))
    if not isinstance(secrets_data, dict):
        raise ValueError("A védett hitelesítőadat-fájl hibás formátumú.")
    return {
        key: value for key, value in secrets_data.items()
        if key in SECRET_CONFIG_KEYS and isinstance(value, str)
    }


def save_protected_secrets(values):
    global SECRET_STORE_UNREADABLE
    secrets_data = {
        key: value for key, value in values.items()
        if key in SECRET_CONFIG_KEYS and isinstance(value, str) and value.strip()
        and not (key == "tmdb_api_key" and value == DEFAULT_API_KEY)
    }
    if not secrets_data:
        # A failed DPAPI decrypt must never make an ordinary settings save erase
        # the only remaining copy of the encrypted credentials.
        if SECRET_STORE_UNREADABLE:
            return
        with contextlib.suppress(FileNotFoundError):
            os.remove(SECRET_STORE_FILE)
        return
    if SECRET_STORE_UNREADABLE and os.path.isfile(SECRET_STORE_FILE):
        stamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = f"{SECRET_STORE_FILE}.unreadable_{stamp}"
        if not os.path.exists(backup_path):
            shutil.copy2(SECRET_STORE_FILE, backup_path)
    protected = dpapi_transform(
        json.dumps(secrets_data, ensure_ascii=False).encode("utf-8"), protect=True,
    )
    temp_path = SECRET_STORE_FILE + ".tmp"
    try:
        with open(temp_path, "wb") as secret_file:
            secret_file.write(protected)
            secret_file.flush()
            os.fsync(secret_file.fileno())
        os.replace(temp_path, SECRET_STORE_FILE)
        SECRET_STORE_UNREADABLE = False
    finally:
        with contextlib.suppress(OSError):
            if os.path.exists(temp_path):
                os.remove(temp_path)


def config_for_disk(values):
    """Remove credentials before serializing settings or creating backups."""
    return {key: value for key, value in values.items() if key not in SECRET_CONFIG_KEYS}


def scrub_config_backups():
    """Remove legacy plaintext credentials from valid app-created config copies."""
    for name in os.listdir(BASE_DIR):
        if not name.startswith("config.json."):
            continue
        path = os.path.join(BASE_DIR, name)
        try:
            with open(path, "r", encoding="utf-8") as backup:
                old_data = json.load(backup)
            if not isinstance(old_data, dict):
                continue
            safe_data = config_for_disk(old_data)
            if safe_data == old_data:
                continue
            temporary = path + ".tmp"
            with open(temporary, "w", encoding="utf-8") as backup:
                json.dump(safe_data, backup, indent=4, ensure_ascii=False)
            os.replace(temporary, path)
        except (OSError, ValueError, TypeError):
            if name == "config.json.tmp":
                with contextlib.suppress(OSError):
                    os.remove(path)
                continue
            LOGGER.warning("Egy korábbi konfigurációs másolatot nem sikerült biztonságosan átalakítani: %s", name)


def backup_file(path, tag):
    backup = f"{path}.{tag}_{uuid.uuid4().hex[:6]}"
    try:
        shutil.copy2(path, backup)
    except OSError:
        return None
    return backup


def is_placeholder_configured_path(path):
    if not isinstance(path, str):
        return False
    normalized = path.strip().strip('"').replace("/", "\\").rstrip("\\").casefold()
    return normalized in {r"\\nas-ip\filmek", r"\\nas-ip\tv_sorozatok"}


def infer_custom_library_media_type(name):
    """Infer the type of legacy custom libraries that predate explicit types."""
    show_terms = {
        "tv", "show", "shows", "series", "sorozat", "sorozatok", "sori",
        "sorik", "musor", "musorok",
    }
    if set(normalize_title(name).split()) & show_terms:
        return "shows"
    return "movies"


def custom_library_is_movie(library):
    """Resolve a custom library's stored or legacy-inferred media type."""
    media_type = str(library.get("media_type", "")).casefold()
    if media_type not in {"movies", "shows"}:
        media_type = infer_custom_library_media_type(library.get("name", ""))
    return media_type == "movies"


def media_item_is_movie(item):
    """Resolve saved cards without treating a NAS URL as a local directory."""
    value = item.get("is_movie")
    if type(value) is bool or type(value) is int and value in (0, 1):
        return bool(value)
    if item.get("episode_roots"):
        return False
    library_id = str(item.get("library_id") or item.get("_scan_library_id") or "")
    if library_id == "shows":
        return False
    if library_id == "movies":
        return True
    if library_id.startswith("custom:"):
        library_id = library_id.split(":", 1)[1]
    library = next((lib for lib in config.get("custom_libraries", []) if lib.get("id") == library_id), None)
    if library:
        return custom_library_is_movie(library)
    path = item.get("file_path") or ""
    if is_remote_path(path):
        # Older cards may also lack their library id. Resolve the most
        # specific configured root, without issuing a NAS/network stat call.
        matches = []
        for movie, roots in ((True, configured_paths("movies")), (False, configured_paths("shows"))):
            matches.extend((len(normalize_media_path(root)), movie) for root in roots if media_path_is_within(path, root))
        for library in config.get("custom_libraries", []):
            matches.extend((len(normalize_media_path(root)), custom_library_is_movie(library))
                           for root in library.get("paths", []) if media_path_is_within(path, root))
        return max(matches, key=lambda value: value[0])[1] if matches else True
    return not os.path.isdir(path)


def write_config_atomic(values):
    """Keep the last complete settings file until its replacement is durable."""
    fd, temporary = tempfile.mkstemp(prefix=".config-", suffix=".tmp", dir=os.path.dirname(CONFIG_FILE))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(config_for_disk(values), output, indent=4, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, CONFIG_FILE)
    finally:
        with contextlib.suppress(OSError):
            os.remove(temporary)


def load_config():
    """(beállítások, figyelmeztetés vagy None)"""
    global SECRET_STORE_UNREADABLE
    # A shallow copy would let edits to nested defaults leak across config reloads.
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    warning = None
    may_write = True
    data = {}

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("a config.json nem JSON objektum")
            for key, default in DEFAULT_CONFIG.items():
                if key in SECRET_CONFIG_KEYS:
                    continue
                if key in data and isinstance(data[key], type(default)):
                    cfg[key] = data[key]
            if cfg.get("language") not in {"hu", "en"}:
                cfg["language"] = "hu"
            if "preferred_audio_language" not in data:
                old_audio_languages = str(data.get("audio_languages", "")).casefold().split(",")
                cfg["preferred_audio_language"] = (
                    "hu" if any(language.strip() in {"hu", "hun"} for language in old_audio_languages)
                    else "original"
                )
            if "preferred_subtitle_language" not in data:
                old_subtitle_languages = str(data.get("subtitle_languages", "hu,en")).casefold().split(",")
                cfg["preferred_subtitle_language"] = (
                    "hu" if any(language.strip() in {"hu", "hun"} for language in old_subtitle_languages)
                    else "original" if any(language.strip() for language in old_subtitle_languages)
                    else "hu"
                )
            if cfg.get("preferred_audio_language") not in {"hu", "original", "default"}:
                cfg["preferred_audio_language"] = "original"
            if cfg.get("preferred_subtitle_language") not in {"hu", "original", "default", "none"}:
                cfg["preferred_subtitle_language"] = "hu"
            if 'inventory_startup_v103' not in data:
                cfg['inventory_startup_v103'] = True
                if cfg.get('startup_scan_mode') == 'current': cfg['startup_scan_mode'] = 'all'
            if cfg.get("startup_scan_mode") not in {"current", "all", "none"}:
                cfg["startup_scan_mode"] = "current"
            if cfg.get("card_size") not in CARD_SIZE_PRESETS:
                cfg["card_size"] = "normal"
            # Régi konfigurációkban csak egy-egy útvonal szerepelt; ezeket automatikusan átvesszük.
            if isinstance(data.get("movies_paths"), list):
                cfg["movies_paths"] = [p for p in data["movies_paths"] if isinstance(p, str) and p.strip() and not is_placeholder_configured_path(p)]
            else:
                cfg["movies_paths"] = [cfg["movies_path"]] if cfg["movies_path"].strip() and not is_placeholder_configured_path(cfg["movies_path"]) else []
            if isinstance(data.get("shows_paths"), list):
                cfg["shows_paths"] = [p for p in data["shows_paths"] if isinstance(p, str) and p.strip() and not is_placeholder_configured_path(p)]
            else:
                cfg["shows_paths"] = [cfg["shows_path"]] if cfg["shows_path"].strip() and not is_placeholder_configured_path(cfg["shows_path"]) else []
            cfg["movies_path"] = cfg["movies_paths"][0] if cfg["movies_paths"] else ""
            cfg["shows_path"] = cfg["shows_paths"][0] if cfg["shows_paths"] else ""
            custom = data.get("custom_libraries", [])
            if isinstance(custom, list):
                cfg["custom_libraries"] = []
                for item in custom:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name", "")).strip()
                    if not name:
                        continue
                    media_type = str(item.get("media_type", "")).casefold()
                    if media_type not in {"movies", "shows"}:
                        media_type = infer_custom_library_media_type(name)
                    cfg["custom_libraries"].append({
                        "id": str(item.get("id") or uuid.uuid4().hex),
                        "name": name,
                        "media_type": media_type,
                        "paths": [p for p in item.get("paths", []) if isinstance(p, str) and p.strip() and not is_placeholder_configured_path(p)]
                        if isinstance(item.get("paths", []), list) else [],
                    })
        except (OSError, ValueError) as e:
            data = {}
            backup = backup_file(CONFIG_FILE, "err")
            if backup:
                warning = (f"A config.json nem olvasható ({e}).\n"
                           f"Biztonsági másolat: {backup}\n"
                           "Az alapértelmezett beállításokat használom, add meg újra a TMDB API kulcsot és az útvonalakat.")
            else:
                warning = (f"A config.json nem olvasható ({e}), és biztonsági másolat sem készíthető.\n"
                           "Az alapértelmezett beállításokat használom; az eredeti fájlt nem írtam felül.")
            LOGGER.warning("A konfiguráció nem olvasható; alapértelmezett beállítások használata: %s", warning)
            may_write = backup is not None

    legacy_secrets = {
        key: value for key in SECRET_CONFIG_KEYS
        if isinstance((value := data.get(key)), str) and value.strip()
        and not (key == "tmdb_api_key" and value == DEFAULT_API_KEY)
    }
    try:
        protected_secrets = load_protected_secrets()
        SECRET_STORE_UNREADABLE = False
    except Exception as exc:
        SECRET_STORE_UNREADABLE = True
        protected_secrets = {}
        message = (
            "A korábban védett hitelesítő adatokat nem sikerült visszafejteni. "
            "Ellenőrizd, hogy ugyanazzal a Windows-fiókkal fut-e a program; "
            "szükség esetén add meg újra a NAS-jelszót és a TMDB-kulcsot."
        )
        warning = f"{warning}\n\n{message}" if warning else message
        LOGGER.warning("A védett hitelesítő adatok nem olvashatók: %s", exc)

    for key in SECRET_CONFIG_KEYS:
        cfg[key] = protected_secrets.get(key, legacy_secrets.get(key, DEFAULT_CONFIG[key]))

    secrets_to_migrate = {
        key: cfg[key] for key in SECRET_CONFIG_KEYS
        if key in legacy_secrets and protected_secrets.get(key) != cfg[key]
    }
    if secrets_to_migrate:
        try:
            save_protected_secrets({
                key: cfg[key] for key in SECRET_CONFIG_KEYS
            })
        except Exception as exc:
            may_write = False
            message = (
                "A régi konfiguráció hitelesítő adatait nem sikerült Windows DPAPI-védelemmel "
                "elmenteni, ezért a config.json fájlt változatlanul hagytam. "
                "A probléma javításáig ne oszd meg ezt a mappát."
            )
            warning = f"{warning}\n\n{message}" if warning else message
            LOGGER.error("Nem sikerült a régi hitelesítő adatokat DPAPI-val védeni: %s", exc)

    if may_write:
        scrub_config_backups()

    if may_write and data != config_for_disk(cfg):
        try:
            write_config_atomic(cfg)
        except OSError as e:
            LOGGER.error("Nem sikerült írni a config.json-t: %s", e, exc_info=True)
    try:
        cfg['quickconnect_id'] = validate_quickconnect_id(cfg.get('quickconnect_id'))
    except ValueError:
        cfg['quickconnect_id'] = ''
        warning = 'Érvénytelen QuickConnect-azonosító a beállításokban; add meg újra.'
    return cfg, warning


config, CONFIG_WARNING = load_config()
set_ui_language(config.get("language", "hu"))


def save_config():
    """Save settings and DPAPI credentials as one recoverable transaction."""
    global SECRET_STORE_UNREADABLE
    previous_unreadable = SECRET_STORE_UNREADABLE
    try:
        with settings_transaction(os.path.dirname(CONFIG_FILE)):
            validate_quickconnect_id(config.get("quickconnect_id"))
            save_protected_secrets(config)
            write_config_atomic(config)
        return True, ""
    except Exception as e:
        SECRET_STORE_UNREADABLE = previous_unreadable
        LOGGER.error("Nem sikerült elmenteni az alkalmazás beállításait: %s", e, exc_info=True)
        return False, str(e)


def snapshot_database(source_path, destination):
    """Create a consistent SQLite snapshot without copying a live database file."""
    fd, temp_path = tempfile.mkstemp(prefix="synostream_db_snapshot_", suffix=".db", dir=BASE_DIR)
    os.close(fd)
    try:
        with contextlib.closing(sqlite3.connect(source_path, timeout=30)) as source:
            with contextlib.closing(sqlite3.connect(temp_path, timeout=30)) as target:
                source.backup(target)
        os.replace(temp_path, destination)
    finally:
        with contextlib.suppress(OSError):
            os.remove(temp_path)


def create_backup_archive(destination):
    """Create a consistent ZIP backup containing config.json and a SQLite snapshot."""
    ok, error = save_config()
    if not ok:
        raise OSError(f"A beállításokat nem sikerült menteni: {error}")

    fd, database_snapshot = tempfile.mkstemp(prefix="synostream_backup_", suffix=".db", dir=BASE_DIR)
    os.close(fd)
    archive_temp = destination + f".{uuid.uuid4().hex[:8]}.tmp"
    try:
        snapshot_database(DB_FILE, database_snapshot)

        manifest = {
            "format_version": BACKUP_FORMAT_VERSION,
            "app_version": APP_VERSION,
            "created_at": time.time(),
        }
        with zipfile.ZipFile(archive_temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.writestr(
                "config.json",
                json.dumps(config_for_disk(config), ensure_ascii=False, indent=4),
            )
            archive.write(database_snapshot, "media_library.db")
        os.replace(archive_temp, destination)
    except Exception:
        raise
    finally:
        for path in (database_snapshot, archive_temp):
            with contextlib.suppress(OSError):
                os.remove(path)


def restore_backup_archive(archive_path):
    """Recover config, encrypted credentials and database together after a crash."""
    global config, CONFIG_WARNING
    try:
        with settings_transaction(BASE_DIR, include_database=True):
            return _restore_backup_archive(archive_path)
    except Exception:
        # The durable journal has restored the files before in-memory reload.
        config, CONFIG_WARNING = load_config()
        raise


def _restore_backup_archive(archive_path):
    """Validate a backup and replace config/database, retaining rollback copies."""
    global config, CONFIG_WARNING, SECRET_STORE_UNREADABLE

    staged_db = None
    staged_config = None
    rollback_db = None
    rollback_config = None
    previous_secret_store = None
    previous_secret_store_unreadable = SECRET_STORE_UNREADABLE
    secret_store_changed = False
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            def read_member_limited(name, maximum):
                with archive.open(name, "r") as source:
                    payload = source.read(maximum + 1)
                if len(payload) > maximum:
                    raise ValueError(f"A mentés túl nagy vagy hibás: {name}.")
                return payload

            member_names = archive.namelist()
            if len(member_names) != len(set(member_names)):
                raise ValueError("A mentés duplikált fájlneveket tartalmaz.")
            required = {"manifest.json", "config.json", "media_library.db"}
            if not required.issubset(set(member_names)):
                raise ValueError("A mentésből hiányzik a konfiguráció, az adatbázis vagy a verziójegyzék.")
            for name, maximum in (("manifest.json", 64 * 1024), ("config.json", 4 * 1024 * 1024),
                                  ("media_library.db", 8 * 1024 * 1024 * 1024)):
                info = archive.getinfo(name)
                if info.file_size > maximum:
                    raise ValueError(f"A mentés túl nagy vagy hibás: {name}.")
            manifest = json.loads(read_member_limited("manifest.json", 64 * 1024).decode("utf-8"))
            if not isinstance(manifest, dict) or manifest.get("format_version") != BACKUP_FORMAT_VERSION:
                raise ValueError("A mentés formátuma nem támogatott.")
            imported_config = json.loads(read_member_limited("config.json", 4 * 1024 * 1024).decode("utf-8"))
            if not isinstance(imported_config, dict):
                raise ValueError("A mentés konfigurációja nem érvényes JSON objektum.")
            # An imported backup must not silently change which executable the
            # next playback launches. Keep the path explicitly configured here.
            imported_config["mpv_path"] = config.get("mpv_path") or DEFAULT_CONFIG["mpv_path"]
            imported_secrets = {
                key: value for key in SECRET_CONFIG_KEYS
                if isinstance((value := imported_config.get(key)), str) and value.strip()
                and not (key == "tmdb_api_key" and value == DEFAULT_API_KEY)
            }

            fd, staged_db = tempfile.mkstemp(prefix="synostream_restore_", suffix=".db", dir=BASE_DIR)
            os.close(fd)
            copied = 0
            with archive.open("media_library.db", "r") as source, open(staged_db, "wb") as target:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    copied += len(chunk)
                    if copied > 8 * 1024 * 1024 * 1024:
                        raise ValueError("A mentés adatbázisa túllépi a megengedett méretet.")
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())

        with contextlib.closing(sqlite3.connect(staged_db, timeout=30)) as check_conn:
            if check_conn.execute("PRAGMA user_version").fetchone()[0] > 1:
                raise ValueError("A mentés újabb SynoStream-verzióhoz tartozik.")
            integrity = check_conn.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ValueError("A mentés adatbázisa sérült.")
            tables = {row[0] for row in check_conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )}
            if not {"media_cache", "manual_overrides", "playback_state"}.issubset(tables):
                raise ValueError("A mentés nem SynoStream-adatbázist tartalmaz.")
            validate_backup_database(check_conn)

        validate_quickconnect_id(imported_config.get("quickconnect_id"))
        fd, staged_config = tempfile.mkstemp(prefix="synostream_restore_", suffix=".json", dir=BASE_DIR)
        with os.fdopen(fd, "w", encoding="utf-8") as config_file:
            json.dump(config_for_disk(imported_config), config_file, indent=4, ensure_ascii=False)
            config_file.flush()
            os.fsync(config_file.fileno())

        if os.path.exists(SECRET_STORE_FILE):
            with open(SECRET_STORE_FILE, "rb") as secret_file:
                previous_secret_store = secret_file.read()
        if imported_secrets:
            # A restore replaces credential state too. Do not merge credentials
            # from the current installation into the selected backup.
            SECRET_STORE_UNREADABLE = False
            save_protected_secrets(imported_secrets)
            secret_store_changed = True
        else:
            # Backups intentionally omit secrets. Remove any current credentials
            # so the restored settings match the archive and prompt for reentry.
            with contextlib.suppress(FileNotFoundError):
                os.remove(SECRET_STORE_FILE)
            SECRET_STORE_UNREADABLE = False
            secret_store_changed = True

        stamp = time.strftime("%Y%m%d_%H%M%S") + f"_{uuid.uuid4().hex[:6]}"
        rollback_db = f"{DB_FILE}.pre_restore_{stamp}"
        rollback_config = backup_file(CONFIG_FILE, f"pre_restore_{stamp}")
        if os.path.exists(DB_FILE):
            snapshot_database(DB_FILE, rollback_db)
        else:
            rollback_db = None
        if not rollback_db or not rollback_config:
            raise OSError("Nem sikerült biztonsági másolatot készíteni a jelenlegi adatokról.")

        os.replace(staged_db, DB_FILE)
        staged_db = None
        os.replace(staged_config, CONFIG_FILE)
        staged_config = None
        init_db()
        config, CONFIG_WARNING = load_config()
        set_ui_language(config.get("language", "hu"))
        return {"database_backup": rollback_db, "config_backup": rollback_config}
    except Exception:
        if secret_store_changed:
            if previous_secret_store is None:
                with contextlib.suppress(OSError):
                    os.remove(SECRET_STORE_FILE)
            else:
                rollback_secret = SECRET_STORE_FILE + ".rollback.tmp"
                try:
                    with open(rollback_secret, "wb") as secret_file:
                        secret_file.write(previous_secret_store)
                    os.replace(rollback_secret, SECRET_STORE_FILE)
                finally:
                    with contextlib.suppress(OSError):
                        if os.path.exists(rollback_secret):
                            os.remove(rollback_secret)
        SECRET_STORE_UNREADABLE = previous_secret_store_unreadable
        if rollback_db and os.path.exists(rollback_db):
            with contextlib.suppress(OSError):
                shutil.copy2(rollback_db, DB_FILE)
        if rollback_config and os.path.exists(rollback_config):
            with contextlib.suppress(OSError):
                shutil.copy2(rollback_config, CONFIG_FILE)
        if rollback_db or rollback_config:
            with contextlib.suppress(Exception):
                config, CONFIG_WARNING = load_config()
                set_ui_language(config.get("language", "hu"))
        raise
    finally:
        for path in (staged_db, staged_config):
            if path:
                with contextlib.suppress(OSError):
                    os.remove(path)


_source_router_key = None
_source_router_value = SourceRouter()
_source_router_lock = threading.RLock()


def source_router():
    global _source_router_key, _source_router_value
    settings = globals().get("config", {})
    values = {key:settings.get(key) for key in ('paired_sources', 'nas_local_url', 'movies_paths', 'shows_paths',
        'movies_path', 'shows_path', 'remote_movies_path', 'remote_shows_path', 'custom_libraries')}
    key = json.dumps(values, sort_keys=True, ensure_ascii=False)
    with _source_router_lock:
        if key != _source_router_key:
            try:
                _source_router_value = SourceRouter(automatic_pairs(settings))
            except ValueError:
                LOGGER.error("Érvénytelen forrás-összerendelés; a meglévő útvonalak változatlanul használhatók.")
                _source_router_value = SourceRouter()
            _source_router_key = key
        return _source_router_value


def configured_paths(kind):
    if isinstance(kind, str) and kind.startswith("custom:"):
        library_id = kind.split(":", 1)[1]
        library = next((lib for lib in config.get("custom_libraries", [])
                        if lib.get("id") == library_id), None)
        candidates = library.get("paths", []) if library else []
        result = []
        seen = set()
        for path in candidates:
            if isinstance(path, str) and path.strip():
                clean = source_router().canonical(path.strip().strip('"'))
                norm = clean if is_remote_path(clean) else normalize_path(clean)
                if norm not in seen:
                    seen.add(norm)
                    result.append(clean)
        return result

    key = "movies_paths" if kind == "movies" else "shows_paths"
    legacy_key = "movies_path" if kind == "movies" else "shows_path"
    paths = config.get(key)
    if not isinstance(paths, list):
        legacy = config.get(legacy_key, "")
        paths = [legacy] if legacy else []
    result = []
    seen = set()
    remote_key = "remote_movies_path" if kind == "movies" else "remote_shows_path"
    candidates = list(paths) if isinstance(paths, list) else []
    remote_path = (config.get(remote_key) or "").strip()
    if remote_path:
        candidates.append(REMOTE_PREFIX + remote_path)
    for path in candidates:
        if isinstance(path, str) and path.strip():
            clean = source_router().canonical(path.strip().strip('"'))
            norm = clean if is_remote_path(clean) else normalize_path(clean)
            if norm not in seen:
                seen.add(norm)
                result.append(clean)
    return result


# ==========================================
# ADATBÁZIS INICIALIZÁLÁS ÉS MIGRÁCIÓ
# ==========================================
def portable_roots(is_movie=None):
    roots=[]
    for kind, flag in (("movies", True), ("shows", False)):
        if is_movie is None or is_movie == flag:
            roots.extend(configured_paths(kind))
    for library in config.get("custom_libraries", []):
        if is_movie is None or is_movie == custom_library_is_movie(library):
            roots.extend(configured_paths("custom:" + library["id"]))
    return list(dict.fromkeys(portable_pairs.normalize_root(root) for root in roots))


def record_portable_edit(conn, path, is_movie, tmdb_id=None, title="", deleted=False, library_id=None):
    try:
        roots = (configured_paths(library_id if library_id in ("movies", "shows") else "custom:" + library_id)
                 if library_id else portable_roots())
        return portable_pairs.enqueue(conn, roots, source_router().canonical(path), is_movie, tmdb_id, title, deleted)
    except (ValueError, OSError):
        LOGGER.warning("A kézi párosítás hordozható formája nem készíthető el: %s", path)
        return None


def synchronize_portable_root(conn, root, backend, stop, all_roots, verify):
    table = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_route_pending'").fetchone()
    deferred = [path for path, in conn.execute("SELECT file_path FROM source_route_pending WHERE root=?", (root,))] if table else []
    if deferred:
        return portable_pairs.synchronize(conn, root, backend, stop, all_roots=all_roots, verify=verify, defer_paths=deferred)
    return portable_pairs.synchronize(conn, root, backend, stop, all_roots=all_roots, verify=verify)


def portable_summary(stats):
    if stats.get("warnings") or stats.get("pending") or stats.get("invalid", 0) > stats.get("repaired", 0):
        return translate_text("A párosítás helyben mentve. A médiatári közös mentés nem sikerült; frissítéskor újrapróbálom.")
    message = translate_text("Párosítások: {imported} átvett, {written} mentett, {pending} mentésre vár.").format(**stats)
    if stats.get("repaired"):
        message += " " + translate_text("Helyreállított közös fájlok: {count}.").format(count=stats["repaired"])
    return message


REQUIRED_COLUMNS = {
    "manual_overrides": {
        "tmdb_id": "INTEGER DEFAULT 0",
        "custom_title": "TEXT DEFAULT ''",
        "is_movie": "INTEGER DEFAULT 1",
    },
    "media_cache": {
        "tmdb_id": "INTEGER DEFAULT 0",
        "title": "TEXT DEFAULT ''",
        "overview": "TEXT DEFAULT ''",
        "poster_url": "TEXT DEFAULT ''",
        "release_date": "TEXT DEFAULT ''",
        "is_movie": "INTEGER DEFAULT 1",
        "file_mtime": "REAL DEFAULT 0.0",
        "status": "TEXT DEFAULT 'success'",
        "signature": "TEXT DEFAULT ''",
        "lookup_at": "REAL DEFAULT 0",
    },
}


def initialize_database_connection(conn):
    """Apply supported migrations to an explicitly selected database connection."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS manual_overrides (
            file_path TEXT PRIMARY KEY,
            tmdb_id INTEGER,
            custom_title TEXT,
            is_movie INTEGER
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS media_cache (
            file_path TEXT PRIMARY KEY,
            tmdb_id INTEGER,
            title TEXT,
            overview TEXT,
            poster_url TEXT,
            release_date TEXT,
            is_movie INTEGER,
            file_mtime REAL,
            status TEXT,
            signature TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS scan_directory_cache (
            library_id TEXT NOT NULL,
            is_movie INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            mtime REAL NOT NULL,
            has_subdirs INTEGER NOT NULL DEFAULT 0,
            video_count INTEGER NOT NULL DEFAULT 0,
            scan_token TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (library_id, is_movie, file_path)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS library_card_cache (
            library_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY (library_id, file_path)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS playback_state (
            file_path TEXT PRIMARY KEY,
            media_title TEXT NOT NULL DEFAULT '',
            episode_title TEXT NOT NULL DEFAULT '',
            poster TEXT NOT NULL DEFAULT '',
            is_movie INTEGER NOT NULL DEFAULT 1,
            position REAL NOT NULL DEFAULT 0,
            duration REAL NOT NULL DEFAULT 0,
            last_played REAL NOT NULL DEFAULT 0,
            watched INTEGER NOT NULL DEFAULT 0,
            playlist_paths TEXT NOT NULL DEFAULT '[]'
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tmdb_metadata_cache (
            cache_key TEXT NOT NULL,
            language TEXT NOT NULL,
            payload TEXT NOT NULL,
            fetched_at REAL NOT NULL,
            PRIMARY KEY (cache_key, language)
        )
    ''')
    for table, columns in REQUIRED_COLUMNS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for col_name, col_def in columns.items():
            if col_name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
    portable_pairs.init_tables(conn)
    recommendations.init_tables(conn)
    conn.execute("CREATE TABLE IF NOT EXISTS source_route_pending(file_path TEXT PRIMARY KEY, root TEXT NOT NULL)")
    migrate_schema(conn)
    conn.commit()


def validate_backup_database(conn):
    """Migrate staging, then verify all columns and keys before replacing live files."""
    try:
        initialize_database_connection(conn)
        with contextlib.closing(sqlite3.connect(":memory:")) as expected:
            initialize_database_connection(expected)
            tables = [row[0] for row in expected.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )]
            for table in tables:
                reference = expected.execute(f'PRAGMA table_info("{table}")').fetchall()
                actual = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
                if not {row[1] for row in reference}.issubset({row[1] for row in actual}):
                    raise ValueError(f"A mentés adatbázisának táblaszerkezete hiányos: {table}.")
                key = lambda rows: [row[1] for row in sorted(rows, key=lambda row: row[5]) if row[5]]
                if key(actual) != key(reference):
                    raise ValueError(f"A mentés adatbázisának elsődleges kulcsa hibás: {table}.")
                def affinity(declaration):
                    declaration = (declaration or "").upper()
                    if "INT" in declaration:
                        return "INTEGER"
                    if any(value in declaration for value in ("CHAR", "CLOB", "TEXT")):
                        return "TEXT"
                    if not declaration or "BLOB" in declaration:
                        return "BLOB"
                    if any(value in declaration for value in ("REAL", "FLOA", "DOUB")):
                        return "REAL"
                    return "NUMERIC"
                actual_types = {row[1]: affinity(row[2]) for row in actual}
                if any(row[5] and actual_types[row[1]] != affinity(row[2]) for row in reference):
                    raise ValueError(f"A mentés adatbázisának kulcstípusa hibás: {table}.")
    except (sqlite3.Error, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("A mentés adatbázisának szerkezete nem használható.") from exc


def init_db():
    with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
        initialize_database_connection(conn)
    commit_data_version(BASE_DIR, APP_VERSION)
    DISPLAY_STATE_CACHE.clear()


# ==========================================
# ÚTVONAL SEGÉDFÜGGVÉNYEK
# ==========================================
def normalize_path(path):
    if not path:
        return ""
    try:
        return os.path.normcase(os.path.normpath(os.path.abspath(path)))
    except (OSError, ValueError):
        return os.path.normcase(path)


def is_within(path, base):
    """Igaz, ha a path azonos a base mappával, vagy azon belül van (mindkettő normalizált).
    Mappahatáron vág, így a "Filmek2" nem esik a "Filmek" alá."""
    if not path or not base:
        return False
    seps = os.sep + (os.altsep or "")
    path = path.rstrip(seps)
    base = base.rstrip(seps)
    return path == base or path.startswith(base + os.sep)


# Csak a valóban rendszer- / NAS-szemét neveket zárjuk ki (kisbetűvel összehasonlítva),
# így pl. a "#Alive (2020).mkv" vagy az "@Home" látható marad.
IGNORED_NAMES = {".synostream",
    "@eadir", "#recycle", "#snapshot", "@recycle", "@tmp", "@recently-snapshot", "@sharesnap",
    "$recycle.bin", "system volume information", "lost+found", ".ds_store",
    ".synologyworkingdirectory", ".@__thumb",
}


def excluded_media_paths():
    values = config.get("excluded_media_paths", [])
    return tuple(normalize_media_path(path) for path in values if isinstance(path, str) and path) if isinstance(values, list) else ()


def media_is_excluded(path, excluded=None):
    normalized = normalize_media_path(path)
    return any(media_path_is_within(normalized, root) for root in (excluded_media_paths() if excluded is None else excluded))


def is_ignored(name):
    lowered = name.lower()
    # A "._" előtagú fájlok macOS metaadat-maradványok (AppleDouble), nem valódi videók.
    return lowered in IGNORED_NAMES or lowered.startswith("._")


def natural_sort_key(s):
    # A re.split a számokat mindig a páratlan indexeken adja vissza.
    return [int(part) if i % 2 else part.lower() for i, part in enumerate(re.split(r'(\d+)', s))]


def find_episodes(show_path, should_stop=None):
    """(epizódlista, hibaüzenet). A bejárási hibákat (NAS, jogosultság) nem nyeli le."""
    episodes = []
    errors = []
    try:
        for root, dirs, files in os.walk(show_path, onerror=errors.append):
            if should_stop is not None and should_stop():
                break
            dirs[:] = [d for d in dirs if not is_ignored(d) and not media_is_excluded(os.path.join(root, d))]
            for f in files:
                if f.lower().endswith(VIDEO_EXTENSIONS) and not is_ignored(f):
                    full = os.path.join(root, f)
                    if media_is_excluded(full):
                        continue
                    episodes.append((os.path.relpath(full, show_path), full))
    except OSError as e:
        errors.append(e)
    episodes.sort(key=lambda x: natural_sort_key(x[0]))

    error = ""
    if errors:
        error = f"A mappa vagy egy almappája nem olvasható: {errors[0]}"
        if len(errors) > 1:
            error += f" (és még {len(errors) - 1} hiba)"
    return episodes, error


# ==========================================
# TMDB
# ==========================================
class TmdbError(Exception):
    pass


_TMDB_THREAD_LOCAL = threading.local()


def _tmdb_session():
    """Reuse HTTP connections without sharing a requests.Session across threads."""
    session = getattr(_TMDB_THREAD_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": f"SynoStream/{APP_VERSION}"})
        _TMDB_THREAD_LOCAL.session = session
    return session


def get_api_key():
    key = (config.get("tmdb_api_key") or "").strip()
    if not key or key == DEFAULT_API_KEY:
        return None
    return key


def tmdb_request(path, params):
    """JSON-t ad vissza, 404 esetén None-t; hiba esetén TmdbError."""
    key = get_api_key()
    if not key:
        raise TmdbError("Hiányzó vagy érvénytelen TMDB API kulcs.")
    # A TMDB kétféle hitelesítést ad: v3 API key query paraméterben,
    # v4 Read Access Token Bearer fejlécben. Mindkettőt elfogadjuk.
    if key.startswith("eyJ") or key.count(".") >= 2:
        request_params = params
        headers = {"Authorization": f"Bearer {key}"}
    else:
        request_params = {**params, "api_key": key}
        headers = None

    for attempt in range(3):
        retry_delay = None
        try:
            with _tmdb_session().get(
                f"{TMDB_BASE}/{path}", params=request_params,
                headers=headers, timeout=(5, 8),
            ) as response:
                if response.status_code == 404:
                    return None
                if response.status_code == 401:
                    raise TmdbError("Érvénytelen TMDB API-kulcs / Read Access Token (401 Unauthorized).")
                if response.status_code == 429:
                    if attempt == 2:
                        raise TmdbError("A TMDB ideiglenes kéréskorlátja miatt a lekérés most nem sikerült.")
                    try:
                        retry_delay = float(response.headers.get("Retry-After", ""))
                    except (TypeError, ValueError):
                        retry_delay = 2 ** attempt
                    retry_delay = min(max(retry_delay, 0.5), 5.0)
                else:
                    response.raise_for_status()
                    return response.json()
            if retry_delay is not None:
                LOGGER.info("TMDB 429 válasz; újrapróbálás %.1f másodperc múlva.", retry_delay)
                time.sleep(retry_delay)
        except TmdbError:
            raise
        except requests.RequestException as exc:
            # The exception may include the API key in its URL.
            raise TmdbError(f"Hálózati / TMDB hiba: {str(exc).replace(key, '***')}") from None
        except ValueError as exc:
            raise TmdbError(f"Hibás TMDB válasz: {exc}") from None
    raise TmdbError("A TMDB nem válaszolt a korlátozás utáni újrapróbálásokra.")


TMDB_METADATA_CACHE_TTL = 30 * 24 * 60 * 60


def read_tmdb_metadata_cache(cache_key):
    try:
        with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
            row = conn.execute(
                "SELECT payload, fetched_at FROM tmdb_metadata_cache WHERE cache_key = ? AND language = ?",
                (cache_key, current_tmdb_language()),
            ).fetchone()
        if not row:
            return None, False
        payload = json.loads(row[0])
        is_fresh = time.time() - float(row[1] or 0) < TMDB_METADATA_CACHE_TTL
        return (payload if isinstance(payload, dict) else None), is_fresh
    except (OSError, sqlite3.Error, TypeError, ValueError):
        return None, False


def write_tmdb_metadata_cache(cache_key, payload):
    try:
        with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO tmdb_metadata_cache (cache_key, language, payload, fetched_at)
                VALUES (?, ?, ?, ?)
            ''', (cache_key, current_tmdb_language(), json.dumps(payload, ensure_ascii=False), time.time()))
            conn.commit()
    except (OSError, sqlite3.Error, TypeError, ValueError) as diagnostic_error:
        LOGGER.warning('Nem sikerült egy művelet: write_tmdb_metadata_cache. A korábbi adatokat vagy állapotot ellenőrizni kell. [%s] [%s]', type(diagnostic_error).__name__, type(diagnostic_error).__name__)


def merge_tmdb_metadata_cache(cache_key, payload):
    """Merge concurrent detail/rating updates without replacing other cached fields."""
    try:
        with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT payload FROM tmdb_metadata_cache WHERE cache_key = ? AND language = ?",
                (cache_key, current_tmdb_language()),
            ).fetchone()
            existing = {}
            if row:
                try:
                    decoded = json.loads(row[0])
                    if isinstance(decoded, dict):
                        existing = decoded
                except (TypeError, ValueError) as diagnostic_error:
                    LOGGER.warning('Nem sikerült egy művelet: merge_tmdb_metadata_cache. A korábbi adatokat vagy állapotot ellenőrizni kell. [%s] [%s]', type(diagnostic_error).__name__, type(diagnostic_error).__name__)
            existing.update(payload)
            conn.execute('''
                INSERT OR REPLACE INTO tmdb_metadata_cache (cache_key, language, payload, fetched_at)
                VALUES (?, ?, ?, ?)
            ''', (cache_key, current_tmdb_language(), json.dumps(existing, ensure_ascii=False), time.time()))
            conn.commit()
    except (OSError, sqlite3.Error, TypeError, ValueError) as diagnostic_error:
        LOGGER.warning('Nem sikerült egy művelet: merge_tmdb_metadata_cache. A korábbi adatokat vagy állapotot ellenőrizni kell. [%s] [%s]', type(diagnostic_error).__name__, type(diagnostic_error).__name__)


def fetch_tmdb_certification_order(country, certification, is_movie):
    media_type = "movie" if is_movie else "tv"
    cache_key = f"certifications:{media_type}"
    cached, fresh = read_tmdb_metadata_cache(cache_key)
    if not fresh or not isinstance(cached, dict):
        data = tmdb_request(f"certification/{media_type}/list", {})
        if not isinstance(data, dict):
            return None
        cached = data
        write_tmdb_metadata_cache(cache_key, cached)

    country_ratings = (cached.get("certifications") or {}).get(country, [])
    wanted = str(certification or "").strip().casefold()
    for entry in country_ratings:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("certification") or "").strip().casefold() != wanted:
            continue
        order = entry.get("order")
        if isinstance(order, (int, float)):
            return int(order)
    return None


def fallback_certification_order(certification, country, is_movie):
    value = re.sub(r"\s+", "", str(certification or "")).upper()
    if value in {"KN", "UNRATED", "NOTRATED", "NR", "G", "TV-Y", "TV-G", "U"}:
        return 0
    age_match = re.search(r"\d{1,2}", value)
    if age_match:
        return int(age_match.group())
    if country == "US":
        if is_movie:
            return {"PG": 8, "PG-13": 13, "R": 17, "NC-17": 18}.get(value)
        return {"TV-Y7": 7, "TV-PG": 10, "TV-14": 14, "TV-MA": 17}.get(value)
    if country == "GB":
        return {"PG": 8, "12A": 12, "15": 15, "18": 18}.get(value)
    return None


def fetch_tmdb_certification(tmdb_id, is_movie):
    """Return the Hungarian TMDB certification when available, with a labeled fallback."""
    media_type = "movie" if is_movie else "tv"
    subresource = "release_dates" if is_movie else "content_ratings"
    data = tmdb_request(f"{media_type}/{int(tmdb_id)}/{subresource}", {})
    results = data.get("results", []) if isinstance(data, dict) else []
    by_country = {
        str(entry.get("iso_3166_1") or "").upper(): entry
        for entry in results if isinstance(entry, dict)
    }

    selected_country = ""
    selected_certification = ""
    selected_order = None
    country_order = ["HU", "US", "GB"]
    country_order.extend(sorted(country for country in by_country if country not in country_order))
    for country in country_order:
        country_data = by_country.get(country)
        if not country_data:
            continue
        if is_movie:
            candidate_rows = country_data.get("release_dates", [])
            certifications = [
                str(row.get("certification") or "").strip()
                for row in candidate_rows if isinstance(row, dict)
            ]
        else:
            certification = str(country_data.get("rating") or "").strip()
            certifications = [certification] if certification else []
        certifications = [value for value in certifications if value]
        if not certifications:
            continue

        # If a country has several releases, use its most restrictive published value.
        ranked = []
        for certification in dict.fromkeys(certifications):
            try:
                order = fetch_tmdb_certification_order(country, certification, is_movie)
            except TmdbError as exc:
                LOGGER.info("TMDB-besorolási sorrend nem tölthető be (%s, %s): %s",
                            media_type, country, exc)
                order = None
            if order is None:
                order = fallback_certification_order(certification, country, is_movie)
            ranked.append((order, certification))
        ranked.sort(key=lambda pair: (pair[0] is not None, pair[0] or -1), reverse=True)
        selected_order, selected_certification = ranked[0]
        selected_country = country
        break

    return {
        "certification": selected_certification,
        "certification_country": selected_country,
        "certification_order": selected_order,
        "certification_checked": True,
    }


def fetch_tmdb_media_metadata(tmdb_id, is_movie, cached_metadata=None):
    endpoint = "movie" if is_movie else "tv"
    data = tmdb_request(
        f"{endpoint}/{int(tmdb_id)}",
        {"language": current_tmdb_language(), "append_to_response": "credits"},
    )
    if not isinstance(data, dict):
        return None

    genres = [genre.get("name", "").strip() for genre in data.get("genres", [])
              if isinstance(genre, dict) and genre.get("name")]
    credits = data.get("credits") if isinstance(data.get("credits"), dict) else {}
    cast = []
    seen_cast = set()
    for member in credits.get("cast", []):
        if not isinstance(member, dict):
            continue
        name = str(member.get("name") or "").strip()
        normalized = name.casefold()
        if name and normalized not in seen_cast:
            cast.append(name)
            seen_cast.add(normalized)
        if len(cast) >= 5:
            break

    runtime = data.get("runtime") if is_movie else next(
        (value for value in data.get("episode_run_time", []) if isinstance(value, int) and value > 0),
        None,
    )
    rating = data.get("vote_average")
    metadata = {
        "genres": genres,
        "rating": rating if isinstance(rating, (int, float)) else None,
        "runtime": runtime if isinstance(runtime, int) and runtime > 0 else None,
        "cast": cast,
        "original_language": str(data.get("original_language") or "").strip().lower(),
    }
    if isinstance(cached_metadata, dict) and cached_metadata.get("certification_checked") is True:
        metadata.update({
            key: cached_metadata[key]
            for key in ("certification", "certification_country", "certification_order", "certification_checked")
            if key in cached_metadata
        })
    else:
        try:
            metadata.update(fetch_tmdb_certification(tmdb_id, is_movie))
        except TmdbError as exc:
            LOGGER.warning("TMDB-korhatár-besorolás nem tölthető be (%s, film=%s): %s",
                           tmdb_id, is_movie, exc)
            metadata["certification_checked"] = False
    return metadata


def fetch_tmdb_season_metadata(tmdb_id, season_number):
    data = tmdb_request(
        f"tv/{int(tmdb_id)}/season/{int(season_number)}", {"language": current_tmdb_language()}
    )
    if not isinstance(data, dict):
        return None
    episodes = {}
    for episode in data.get("episodes", []):
        if not isinstance(episode, dict):
            continue
        number = episode.get("episode_number")
        if not isinstance(number, int):
            continue
        episodes[number] = {
            "name": str(episode.get("name") or "").strip(),
            "overview": str(episode.get("overview") or "").strip(),
            "air_date": str(episode.get("air_date") or "").strip(),
        }
    return {"episodes": episodes}


def hit_to_info(hit, is_movie, fallback_title=""):
    poster_path = hit.get("poster_path")
    return {
        "id": hit.get("id"),
        "title": (hit.get("title") if is_movie else hit.get("name")) or fallback_title,
        "overview": hit.get("overview") or "",
        "poster_url": f"{IMG_BASE}{poster_path}" if poster_path else "",
        "date": (hit.get("release_date") if is_movie else hit.get("first_air_date")) or "",
    }


def fill_overview_fallback(info, is_movie):
    """Ha nincs magyar leírás, az angolt használjuk. Visszaad: (info, teljes-e)."""
    if info["overview"] or not info["id"]:
        return info, True
    if current_tmdb_language() == FALLBACK_LANGUAGE:
        return info, True
    endpoint = "movie" if is_movie else "tv"
    try:
        data = tmdb_request(f"{endpoint}/{info['id']}", {"language": FALLBACK_LANGUAGE})
    except TmdbError:
        # Átmeneti hiba: az eredmény nem teljes, ezért nem szabad véglegesen cache-elni.
        return info, False
    if isinstance(data, dict) and data.get("overview"):
        info["overview"] = data["overview"]
    return info, True


def title_search_variants(title):
    values = [title]
    if re.search(r"(?i)\b(?:és|es)\b", title):
        values.extend(re.sub(r"(?i)\b(?:és|es)\b", connector, title) for connector in ("and", "et", "&", ""))
    return list(dict.fromkeys(re.sub(r"\s+", " ", value).strip() for value in values if value.strip()))


def search_tmdb(title, year, is_movie, language=None):
    """Egyetlen keresés; évszám megadásakor az adott évre szűrve."""
    endpoint = "movie" if is_movie else "tv"
    year_key = "primary_release_year" if is_movie else "first_air_date_year"
    params = {"query": title, "language": language or current_tmdb_language()}
    if year:
        params[year_key] = year
    data = tmdb_request(f"search/{endpoint}", params)
    return data.get("results", []) if isinstance(data, dict) else []


def movie_year_matches(date, year):
    if not year:
        return True
    value = str(date or "")[:4]
    return value.isdigit() and abs(int(value) - int(year)) <= 1


def evaluate_hit(hit, query, year, is_movie):
    """(megbízható-e, pontszám) egy TMDB-találatra; a query már normalizált."""
    title = normalize_title(hit.get("title") if is_movie else hit.get("name"))
    original = normalize_title(hit.get("original_title") if is_movie else hit.get("original_name"))
    query_variants = [normalize_title(value) for value in title_search_variants(query)]
    names = {title, original, *(normalize_title(alias) for alias in hit.get("_matching_aliases", []))}
    similarity = max(matching_title_similarity(value, candidate) for value in query_variants for candidate in names)

    date = (hit.get("release_date") if is_movie else hit.get("first_air_date")) or ""
    hit_year = date[:4]
    year_exact = year_near = False
    if year and hit_year.isdigit():
        diff = abs(int(hit_year) - int(year))
        year_exact = diff == 0
        year_near = diff == 1

    # A one-year release-date discrepancy is common. A date match must not
    # outweigh the title, nor let an unrated namesake beat a well-established
    # exact-title candidate from the adjacent year.
    votes = max(0, float(hit.get("vote_count") or 0))
    prominence = min(5.0, math.log10(1 + votes) * 2)
    exact_title = bool(set(query_variants) & names)
    score = similarity * 30 + (3 if exact_title else 0) + (2 if year_exact else 0) + prominence
    reliable = similarity >= MIN_SIMILARITY or (year_exact and similarity >= MIN_SIMILARITY_WITH_YEAR)
    if is_movie:
        if not movie_year_matches(date, year):
            reliable = False
        words = query.split()
        if len(words) == 1 and len(words[0]) <= 4 and query not in {title, original}:
            reliable = False
    return reliable, score


def matching_title_similarity(query, candidate):
    if not query or not candidate:
        return 0.0
    token_score = title_similarity(query, candidate)
    characters = SequenceMatcher(None, query, candidate).ratio()
    # Shared words in a different, much longer title are weak evidence.
    score = token_score if characters >= 0.70 or token_score == 1 else 0.0
    # Joined words and long title suffixes (e.g. Hungarian compounds) are
    # common. Restrict character matching so short abbreviations stay unsafe.
    if min(len(query), len(candidate)) >= 7:
        if characters >= 0.90:
            score = max(score, characters)
        elif characters >= 0.72 and " " not in query and " " not in candidate and (query.startswith(candidate) or candidate.startswith(query)):
            score = max(score, 0.80)
    return score


def pick_reliable_hit(results, query, year, is_movie):
    candidates = []
    for r in results:
        reliable, score = evaluate_hit(r, query, year, is_movie)
        if reliable:
            candidates.append((score, r))
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    if len(candidates) > 1 and candidates[0][1].get("id") != candidates[1][1].get("id") and candidates[0][0] - candidates[1][0] < 1.0:
        return None  # Equally plausible namesakes need stronger evidence.
    return candidates[0][1] if candidates else None


def ambiguous_match_ids(results, query, year, is_movie):
    reliable = []
    for candidate in results:
        accepted, score = evaluate_hit(candidate, query, year, is_movie)
        if accepted:
            reliable.append((score, candidate.get("id")))
    if not reliable:
        return []
    best = max(score for score, identifier in reliable)
    identifiers = list(dict.fromkeys(identifier for score, identifier in reliable if best - score < 1.0))
    return identifiers if len(identifiers) > 1 else []


def movie_lookup_signatures(context):
    if context.get("from_folder"):
        fingerprint = hashlib.sha256(json.dumps([context["title"], context["year"]], ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
        suffix = f"movie_folder_v3:{fingerprint}:{current_tmdb_language()}"
        return "language:" + suffix, "no_result:" + suffix + ":alternatives_v2"
    return (f"language:match_v185:{current_tmdb_language()}",
            f"no_result:language_fallback_v8:{current_tmdb_language()}")


def fetch_tmdb_by_imdb(imdb_id, is_movie):
    try:
        result = tmdb_request(f"find/{imdb_id}", {"external_source": "imdb_id", "language": current_tmdb_language()})
        rows = (result or {}).get("movie_results" if is_movie else "tv_results", [])
        identifiers = {row.get("id") for row in rows if isinstance(row, dict) and type(row.get("id")) is int and row["id"] > 0}
        if len(identifiers) != 1:
            return {"status": "no_result"}
        return fetch_tmdb_data(None, is_movie=is_movie, tmdb_id=next(iter(identifiers)))
    except TmdbError as exc:
        return {"status": "error", "message": str(exc)}


def display_info_cache_key(tmdb_id, is_movie):
    return f"display_info_v1:{'movie' if is_movie else 'tv'}:{int(tmdb_id)}"


def cache_localized_display_info(hit, is_movie):
    if isinstance(hit, dict) and type(hit.get("id")) is int and hit["id"] > 0:
        fallback = hit.get("original_title" if is_movie else "original_name") or ""
        info = hit_to_info(hit, is_movie, fallback)
        if info["title"]:
            write_tmdb_metadata_cache(display_info_cache_key(hit["id"], is_movie), info)
            return info
    return None


def fetch_tmdb_data(title, year=None, is_movie=True, tmdb_id=None):
    endpoint = "movie" if is_movie else "tv"
    try:
        if tmdb_id:
            hit = tmdb_request(f"{endpoint}/{tmdb_id}", {"language": current_tmdb_language()})
            if not isinstance(hit, dict) or "id" not in hit:
                return {"status": "no_result"}
        else:
            query = normalize_title(title)
            hit = None
            had_results = False
            candidates = {}
            search_titles = [title]
            punctuation_variant = re.sub(r"[-–]+", " ", title).strip()
            if punctuation_variant and punctuation_variant.casefold() != title.casefold():
                search_titles.append(punctuation_variant)
            search_titles = list(dict.fromkeys(variant for value in search_titles for variant in title_search_variants(value)))
            search_languages = list(dict.fromkeys((current_tmdb_language(), "en-US")))

            def collect(search_title, search_year, language):
                nonlocal had_results
                results = search_tmdb(search_title, search_year, is_movie, language=language)
                had_results = had_results or bool(results)
                for candidate in results:
                    if not isinstance(candidate, dict) or type(candidate.get("id")) is not int:
                        continue
                    date = candidate.get("release_date") if is_movie else candidate.get("first_air_date")
                    if is_movie and not movie_year_matches(date, year):
                        continue
                    identifier = candidate["id"]
                    existing = candidates.get(identifier)
                    if existing is None:
                        candidates[identifier] = dict(candidate)
                    else:
                        # Retain every localized/original title returned by search.
                        aliases = existing.setdefault("_matching_aliases", [])
                        aliases.extend(str(candidate.get(key) or "") for key in ("title", "original_title", "name", "original_name"))

            for language in search_languages:
                for search_title in search_titles:
                    for search_year in ([year, None] if year else [None]):
                        collect(search_title, search_year, language)
                hit = pick_reliable_hit(candidates.values(), query, year, is_movie)
                if hit is not None:
                    names = [hit.get("title"), hit.get("original_title"), hit.get("name"), hit.get("original_name"), *hit.get("_matching_aliases", [])]
                    if query in {normalize_title(value) for value in names}:
                        break

            # If the full query fails, remove grammatical connecting words. The
            # resulting candidates still have to match the FULL original title.
            if not candidates:
                words = str(title).split()
                content = [word for word in words if normalize_title(word) not in {"the", "a", "an", "of", "and", "to", "in", "on", "at", "for", "with", "from", "by"}]
                compact = " ".join(content)
                if len(content) >= 2 and compact != title:
                    collect(compact, None, "en-US")
                if not candidates and len(content) >= 3:
                    # Bounded recovery for one mistyped word; never accepts a
                    # match merely because these two search words overlap.
                    collect(" ".join((content[0], content[-1])), None, "en-US")

            # TMDB searches romanized/alternative titles but omits them from the
            # localized result. Verify aliases before accepting a loose hit.
            if hit is None or max(matching_title_similarity(query, normalize_title(hit.get(key))) for key in ("title", "original_title", "name", "original_name")) < 0.95:
                ranked = sorted(candidates.values(), key=lambda c: float(c.get("vote_count") or 0), reverse=True)
                for candidate in ranked[:5]:
                    aliases = tmdb_request(f"{endpoint}/{candidate['id']}/alternative_titles", {})
                    rows = (aliases.get("titles") or aliases.get("results") or []) if isinstance(aliases, dict) else []
                    candidate.setdefault("_matching_aliases", []).extend(row.get("title", "") for row in rows if isinstance(row, dict))
            hit = pick_reliable_hit(candidates.values(), query, year, is_movie)
            if hit is None:
                if had_results:
                    # Volt találat, de egyik sem elég hasonló: inkább kézi párosítás, mint rossz egyezés.
                    return {"status": "no_result", "message": LOW_CONFIDENCE_TEXT,
                            "ambiguous_ids": ambiguous_match_ids(candidates.values(), query, year, is_movie)}
                return {"status": "no_result"}
        if not tmdb_id:
            matched_id = hit.get("id")
            localized = tmdb_request(f"{endpoint}/{matched_id}", {"language": current_tmdb_language()})
            if not isinstance(localized, dict) or localized.get("id") != matched_id:
                return {"status": "no_result"}
            hit = localized
        cache_localized_display_info(hit, is_movie)
        fallback_title = hit.get("original_title" if is_movie else "original_name") or title or ""
        info, complete = fill_overview_fallback(hit_to_info(hit, is_movie, fallback_title), is_movie)
    except TmdbError as e:
        return {"status": "error", "message": str(e)}

    info["overview"] = info["overview"] or "Nincs leírás."
    return {"status": "success", "complete": complete, **info}


def search_tmdb_multiple(title, is_movie=True):
    try:
        cleaned, year = clean_name(title, is_file=False)
        variants = list(dict.fromkeys(v for v in (title.strip(), cleaned,
            re.sub(r"[-–]+", " ", cleaned).strip()) if v))
        variants = list(dict.fromkeys(variant for value in variants for variant in title_search_variants(value)))
        hits = {}
        failures = []
        successful_requests = 0
        for query in variants:
            for language in dict.fromkeys((current_tmdb_language(), "en-US")):
                try:
                    batch = search_tmdb(query, None, is_movie, language=language)
                    successful_requests += 1
                except TmdbError as error:
                    failures.append(str(error))
                    continue
                for hit in batch:
                    if hit.get("id"):
                        hits.setdefault(hit["id"], hit)
        if failures and not successful_requests:
            return {"status": "error", "message": failures[0], "results": []}
        if failures and not hits:
            return {"status": "error", "message": failures[0], "results": []}
        values = list(hits.values())
        if year:
            date_key = "release_date" if is_movie else "first_air_date"
            values.sort(key=lambda h: 0 if str(h.get(date_key, "")).startswith(year) else 1)
        return {"status": "success", "results": [hit_to_info(h, is_movie, title) for h in values], "partial": bool(failures)}
    except TmdbError as e:
        return {"status": "error", "message": str(e), "results": []}


# ==========================================
# PLAKÁT LETÖLTÉS (ATOMI)
# ==========================================
def is_cached_file(path):
    try:
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            # A hozzáférési időt a fájlok nem minden Windows-beállítás mellett frissítik,
            # ezért az írási időt használjuk a cache LRU-sorrendjéhez.
            with contextlib.suppress(OSError):
                os.utime(path, None)
            return True
        return False
    except OSError:
        return False


def prune_poster_cache(max_bytes=MAX_POSTER_CACHE_BYTES):
    """Keep the newest poster files up to the configured cache-size limit."""
    if not isinstance(max_bytes, int) or max_bytes < 0:
        raise ValueError("A plakátcache méretkorlátja nem lehet negatív.")
    removed_count = 0
    removed_bytes = 0
    failures = []
    try:
        with POSTER_CACHE_LOCK:
            candidates = []
            total_bytes = 0
            with os.scandir(CACHE_DIR) as entries:
                for entry in entries:
                    if not re.fullmatch(r"(?:movie|tv)_\d+\.jpg", entry.name, re.IGNORECASE):
                        continue
                    try:
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        info = entry.stat(follow_symlinks=False)
                        candidates.append((info.st_mtime, info.st_size, entry.path))
                        total_bytes += info.st_size
                    except OSError as exc:
                        failures.append(f"{entry.name}: {exc}")

            for _modified, size, path in sorted(candidates):
                if total_bytes <= max_bytes:
                    break
                try:
                    os.remove(path)
                    total_bytes -= size
                    removed_count += 1
                    removed_bytes += size
                except OSError as exc:
                    failures.append(f"{os.path.basename(path)}: {exc}")
    except OSError as exc:
        failures.append(str(exc))
    if failures:
        LOGGER.warning("A plakátcache méretkorlátjának alkalmazása hiányos: %s", "; ".join(failures))
    return removed_count, removed_bytes, failures


def clear_poster_cache_files():
    """Remove SynoStream-managed poster images, leaving other files untouched."""
    global POSTER_CACHE_GENERATION
    POSTER_PIXMAP_CACHE.clear()
    removed = 0
    errors = []
    with POSTER_CACHE_LOCK:
        # Invalidate downloads already in flight so they cannot repopulate a cleared cache.
        POSTER_CACHE_GENERATION += 1
        try:
            with os.scandir(CACHE_DIR) as entries:
                for entry in entries:
                    if not re.fullmatch(r"(?:movie|tv)_\d+\.jpg", entry.name, re.IGNORECASE):
                        continue
                    try:
                        if entry.is_file(follow_symlinks=False):
                            os.remove(entry.path)
                            removed += 1
                    except OSError as exc:
                        errors.append(f"{entry.name}: {exc}")
        except OSError as exc:
            errors.append(str(exc))
    return removed, errors


@contextlib.contextmanager
def poster_cache_activity():
    """Protect the interval between downloading a poster and committing its owner."""
    global POSTER_CACHE_WRITERS
    with POSTER_CACHE_LOCK:
        POSTER_CACHE_WRITERS += 1
    try:
        yield
    finally:
        with POSTER_CACHE_LOCK:
            POSTER_CACHE_WRITERS -= 1


def cleanup_orphaned_poster_files(conn):
    with POSTER_CACHE_LOCK:
        if POSTER_CACHE_WRITERS:
            return []  # A later completed scan will collect genuine orphans.
        return _cleanup_orphaned_poster_files(conn)


def _cleanup_orphaned_poster_files(conn):
    """Eltávolítja a saját plakát-cache azon képeit, amelyeket már nem használ médiabejegyzés."""
    try:
        rows = conn.execute(
            "SELECT DISTINCT tmdb_id, is_movie FROM media_cache "
            "WHERE status = 'success' AND tmdb_id > 0 AND poster_url <> ''"
        ).fetchall()
        referenced = recommendations.poster_names(conn)
        for tmdb_id, is_movie in rows:
            try:
                media_id = int(tmdb_id)
            except (TypeError, ValueError):
                continue
            media_type = "movie" if bool(is_movie) else "tv"
            referenced.add(f"{media_type}_{media_id}.jpg".casefold())

        # Playback records can outlive a library-cache row (for example after a
        # temporary NAS outage); keep any managed poster they still point to.
        for (poster_path,) in conn.execute(
            "SELECT poster FROM playback_state WHERE poster <> ''"
        ):
            name = os.path.basename(str(poster_path).replace("/", os.sep)).casefold()
            if re.fullmatch(r"(?:movie|tv)_\d+\.jpg", name):
                referenced.add(name)

        for entry in os.scandir(CACHE_DIR):
            name = entry.name.casefold()
            if not re.fullmatch(r"(?:movie|tv)_\d+\.jpg", name):
                continue
            if name not in referenced and entry.is_file():
                os.remove(entry.path)
    except (OSError, sqlite3.Error) as exc:
        return [f"A fölösleges borítóképek takarítása nem sikerült: {exc}"]
    _removed, _freed, errors = prune_poster_cache()
    return [f"A plakátcache méretkorlátja nem volt teljesen alkalmazható: {error}"
            for error in errors]


def download_and_cache_poster(poster_url, media_id, is_movie=True, should_stop=None):
    """Plakát letöltése atomi cache-eléssel.

    should_stop: opcionális hívható; igaz értéknél a letöltés megszakad. Egy blokkoló socket-olvasást
    a requests nem tud félbeszakítani, ezért a leállás legrosszabb esetben egy olvasási időkorlátnyit
    (POSTER_READ_TIMEOUT) késik; a teljes letöltés pedig legfeljebb POSTER_TOTAL_TIMEOUT + egy olvasás.
    (A DNS-feloldást az időkorlát nem fedi.)
    """
    if not poster_url or not media_id or media_id <= 0:
        return None

    media_type = "movie" if is_movie else "tv"
    cache_filename = f"{media_type}_{media_id}.jpg"
    cache_path = os.path.join(CACHE_DIR, cache_filename)

    with POSTER_CACHE_LOCK:
        generation = POSTER_CACHE_GENERATION
        if is_cached_file(cache_path):
            return cache_path
    if should_stop is not None and should_stop():
        return None

    temp_path = os.path.join(CACHE_DIR, f"temp_{uuid.uuid4().hex}_{cache_filename}")
    deadline = time.monotonic() + POSTER_TOTAL_TIMEOUT
    try:
        with requests.get(poster_url, timeout=(POSTER_CONNECT_TIMEOUT, POSTER_READ_TIMEOUT),
                          stream=True) as response:
            response.raise_for_status()
            declared = response.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > MAX_POSTER_BYTES:
                return None
            chunks = []
            size = 0
            # Kis adagok: lassan csorgó válasznál is gyakran van lehetőség a megszakítás / határidő ellenőrzésére.
            for chunk in response.iter_content(chunk_size=2048):
                if (should_stop is not None and should_stop()) or time.monotonic() > deadline:
                    return None
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_POSTER_BYTES:
                    return None
                chunks.append(chunk)
        content = b"".join(chunks)

        if not QImage().loadFromData(content):
            return None

        with open(temp_path, "wb") as f:
            f.write(content)
        with POSTER_CACHE_LOCK:
            if generation != POSTER_CACHE_GENERATION:
                return None
            os.replace(temp_path, cache_path)
        return cache_path
    except (requests.RequestException, OSError) as e:
        LOGGER.warning("Borítóletöltési hiba (%s): %s", media_id, e, exc_info=True)
        # Párhuzamos letöltésnél vagy zárolt célfájlnál lehet, hogy közben már elkészült.
        return cache_path if is_cached_file(cache_path) else None
    finally:
        if os.path.exists(temp_path):
            with contextlib.suppress(OSError):
                os.remove(temp_path)


def load_pixmap(path, width, height):
    POSTER_PIXMAP_CACHE.managed_directory = CACHE_DIR
    return POSTER_PIXMAP_CACHE.load(path, width, height)


def get_display_playback_state(path):
    try:
        return DISPLAY_STATE_CACHE.get(DB_FILE, normalize_media_path(path))
    except sqlite3.Error:
        LOGGER.exception("Nem sikerült betölteni a kártyák lejátszási állapotát.")
        return {}


# ==========================================
# HÁTTÉRSZÁLAK
# ==========================================
_background_workers = []


def run_worker(worker):
    """Elindítja a szálat, és életben tartja, amíg be nem fejeződik."""
    _background_workers.append(worker)

    def on_finished():
        worker.wait()
        if worker in _background_workers:
            _background_workers.remove(worker)

    worker.finished.connect(on_finished)
    worker.start()


class NasTask(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, operation, dispose=None):
        super().__init__()
        self.operation = operation
        self.dispose = dispose

    def run(self):
        try:
            result = self.operation(self.isInterruptionRequested)
            if self.isInterruptionRequested():
                if self.dispose:
                    self.dispose(result)
            else:
                self.succeeded.emit(result)
        except InterruptedError:
            pass
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(redact_credentials(exc))
        finally:
            self.operation = None


class PosterLoaderWorker(QThread):
    poster_loaded = pyqtSignal(str, int)  # (helyi útvonal vagy "", kérés azonosító)

    def __init__(self, url, media_id, is_movie, req_id):
        super().__init__()
        self.url = url
        self.media_id = media_id
        self.is_movie = is_movie
        self.req_id = req_id

    def run(self):
        if self.isInterruptionRequested():
            return
        path = download_and_cache_poster(self.url, self.media_id, self.is_movie, self.isInterruptionRequested)
        if not self.isInterruptionRequested():
            self.poster_loaded.emit(path or "", self.req_id)


class TmdbSearchWorker(QThread):
    search_done = pyqtSignal(dict)

    def __init__(self, title, is_movie):
        super().__init__()
        self.title = title
        self.is_movie = is_movie

    def run(self):
        try:
            res = search_tmdb_multiple(self.title, self.is_movie)
        except Exception as e:  # a felület ne maradjon "keresés" állapotban
            res = {"status": "error", "message": f"Váratlan hiba: {e}", "results": []}
        if not self.isInterruptionRequested():
            self.search_done.emit(res)


class TmdbMediaMetadataWorker(QThread):
    metadata_ready = pyqtSignal(dict)

    def __init__(self, tmdb_id, is_movie):
        super().__init__()
        self.tmdb_id = int(tmdb_id)
        self.is_movie = bool(is_movie)

    def run(self):
        cache_key = f"media:{'movie' if self.is_movie else 'tv'}:{self.tmdb_id}"
        cached, fresh = read_tmdb_metadata_cache(cache_key)
        if (fresh and cached is not None and "original_language" in cached
                and cached.get("certification_checked") is True):
            self.metadata_ready.emit({"status": "success", **cached})
            return
        try:
            result = fetch_tmdb_media_metadata(self.tmdb_id, self.is_movie, cached)
            if result is None:
                if cached is not None:
                    self.metadata_ready.emit({"status": "success", **cached})
                else:
                    self.metadata_ready.emit({"status": "error", "message": "Nincs további TMDB-adat."})
                return
            merged = dict(cached or {})
            merged.update(result)
            if result.get("certification_checked") is True:
                merge_tmdb_metadata_cache(cache_key, merged)
            if not self.isInterruptionRequested():
                self.metadata_ready.emit({"status": "success", **merged})
        except TmdbError as exc:
            LOGGER.warning("TMDB-adatlap betöltési hiba (%s, film=%s): %s",
                           self.tmdb_id, self.is_movie, exc)
            if not self.isInterruptionRequested():
                if cached is not None:
                    self.metadata_ready.emit({"status": "success", **cached})
                else:
                    self.metadata_ready.emit({"status": "error", "message": str(exc)})


class TmdbCertificationSortWorker(QThread):
    certification_ready = pyqtSignal(int, bool, dict)

    def __init__(self, media_items):
        super().__init__()
        self.media_items = list(media_items)

    def run(self):
        seen = set()
        for tmdb_id, is_movie in self.media_items:
            if self.isInterruptionRequested():
                return
            key = (int(tmdb_id), bool(is_movie))
            if key in seen:
                continue
            seen.add(key)
            cache_key = f"media:{'movie' if is_movie else 'tv'}:{tmdb_id}"
            cached, fresh = read_tmdb_metadata_cache(cache_key)
            if isinstance(cached, dict) and cached.get("certification_checked") is True:
                self.certification_ready.emit(tmdb_id, is_movie, cached)
                if fresh:
                    continue
            try:
                result = fetch_tmdb_certification(tmdb_id, is_movie)
            except TmdbError as exc:
                LOGGER.warning("Korhatár rendezési adat betöltése sikertelen (%s, film=%s): %s",
                               tmdb_id, is_movie, exc)
                if not self.isInterruptionRequested():
                    fallback = dict(cached or {})
                    fallback["certification_checked"] = True
                    fallback["certification_error"] = True
                    self.certification_ready.emit(tmdb_id, is_movie, fallback)
                continue

            merged = dict(cached or {})
            merged.update(result)
            merge_tmdb_metadata_cache(cache_key, merged)
            if not self.isInterruptionRequested():
                self.certification_ready.emit(tmdb_id, is_movie, merged)


class TmdbSeasonMetadataWorker(QThread):
    metadata_ready = pyqtSignal(dict, str)

    def __init__(self, tmdb_id, season_numbers):
        super().__init__()
        self.tmdb_id = int(tmdb_id)
        self.season_numbers = sorted({int(number) for number in season_numbers})

    def run(self):
        combined = {}
        errors = []
        for season_number in self.season_numbers:
            if self.isInterruptionRequested():
                return
            cache_key = f"season:tv:{self.tmdb_id}:{season_number}"
            cached, fresh = read_tmdb_metadata_cache(cache_key)
            cached_episodes = cached.get("episodes", {}) if isinstance(cached, dict) else {}
            if not isinstance(cached_episodes, dict):
                cached_episodes = {}
            normalized_cached_episodes = {
                int(number): episode_data
                for number, episode_data in cached_episodes.items()
                if str(number).isdigit() and isinstance(episode_data, dict)
            }
            if fresh and cached is not None:
                combined[season_number] = normalized_cached_episodes
                continue
            try:
                result = fetch_tmdb_season_metadata(self.tmdb_id, season_number)
                if result is not None:
                    write_tmdb_metadata_cache(cache_key, result)
                    combined[season_number] = result.get("episodes", {})
                else:
                    if normalized_cached_episodes:
                        combined[season_number] = normalized_cached_episodes
                    errors.append(f"{season_number}. évad: nincs adat")
            except TmdbError as exc:
                LOGGER.warning("TMDB-epizódadat betöltési hiba (%s, %s. évad): %s",
                               self.tmdb_id, season_number, exc)
                if normalized_cached_episodes:
                    combined[season_number] = normalized_cached_episodes
                errors.append(f"{season_number}. évad: {exc}")
        if not self.isInterruptionRequested():
            self.metadata_ready.emit(combined, "; ".join(errors))


PAIRING_TOKEN_UNSET = object()


def read_pairing_token(conn, path):
    row = conn.execute(
        "SELECT tmdb_id,custom_title,is_movie FROM manual_overrides WHERE file_path=?",
        (normalize_media_path(path),),
    ).fetchone()
    return (row[0], row[1] or "", int(bool(row[2]))) if row is not None else None


def pairing_item_is_current(conn, item):
    if "_pairing_token" not in item:
        return True
    token = item["_pairing_token"]
    return read_pairing_token(conn, item.get("file_path", "")) == (tuple(token) if token is not None else None)


class ManualOverrideRefreshWorker(QThread):
    """A kézi TMDB-párosítás után csak az érintett média metaadatait frissíti."""
    refresh_done = pyqtSignal(dict, bool, str)  # (médiaelem, film-e, hibaüzenet)

    def __init__(self, file_path, is_movie, tmdb_id):
        super().__init__()
        self.file_path = file_path
        self.is_movie = is_movie
        self.tmdb_id = tmdb_id

    @poster_cache_activity()
    def run(self):
        try:
            norm_path = normalize_media_path(self.file_path)
            flag = 1 if self.is_movie else 0
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
                pairing_token = read_pairing_token(conn, norm_path)
                if not pairing_token or pairing_token[0] != self.tmdb_id or bool(pairing_token[2]) != bool(self.is_movie):
                    return  # This request was superseded before its worker started.
                row = conn.execute(
                    "SELECT file_mtime FROM media_cache WHERE file_path = ? AND is_movie = ?",
                    (norm_path, flag),
                ).fetchone()
                mtime = float(row[0] or 0.0) if row else 0.0
                if self.is_movie and not is_remote_path(self.file_path):
                    mtime = os.stat(self.file_path).st_mtime

                result = fetch_tmdb_data(None, is_movie=self.is_movie, tmdb_id=self.tmdb_id)
                if result.get("status") != "success":
                    self.refresh_done.emit({}, self.is_movie,
                                           result.get("message") or "A TMDB-adatok nem tölthetők be.")
                    return

                poster = download_and_cache_poster(
                    result.get("poster_url"), result["id"], self.is_movie,
                    self.isInterruptionRequested,
                )
                signature = f"override:{self.tmdb_id}:{current_tmdb_language()}"
                if result.get("complete", True):
                    if not LibraryScannerThread.save_cache(
                        conn, norm_path, flag, result["id"], result["title"], result["overview"],
                        result["poster_url"], result["date"], mtime, "success", signature,
                        pairing_token=pairing_token,
                    ):
                        return
                if read_pairing_token(conn, norm_path) != pairing_token:
                    return


                item = {
                    "file_path": self.file_path,
                    "_pairing_token": pairing_token,
                    "title": result["title"],
                    "overview": result["overview"],
                    "poster": poster,
                    "date": result["date"],
                    "id": result["id"],
                }
                self.refresh_done.emit(item, self.is_movie, "")
        except Exception as exc:
            LOGGER.exception("Nem sikerült a kézi párosítás utáni metaadat-frissítés (%s).",
                             self.file_path)
            self.refresh_done.emit({}, self.is_movie, f"Nem sikerült frissíteni a videoinformációkat: {exc}")


class PathCheckWorker(QThread):
    # "" = rendben; "missing" / "not_file" / "not_dir" / "error"
    check_done = pyqtSignal(str)

    def __init__(self, path, is_movie):
        super().__init__()
        self.path = path
        self.is_movie = is_movie

    def run(self):
        # A lassú / elérhetetlen UNC útvonalnál ezek a hívások sokáig blokkolhatnak, ezért nem a GUI-szálban futnak.
        try:
            if is_remote_path(self.path):
                remote_path = "/" + remote_real_path(self.path).replace("\\", "/").lstrip("/")
                remote_path = posixpath.normpath(remote_path)
                parent_path = posixpath.dirname(remote_path)
                parent_to_list = "" if parent_path in ("", "/") else parent_path
                with contextlib.closing(RemoteNASClient(should_stop=self.isInterruptionRequested)) as client:
                    entries = client.list_folder(parent_to_list)
                expected_name = posixpath.basename(remote_path).casefold()
                found = next((entry for entry in entries
                              if str(entry.get("name") or "").casefold() == expected_name), None)
                if not found:
                    result = "missing"
                elif self.is_movie and bool(found.get("isdir")):
                    result = "not_file"
                elif not self.is_movie and not bool(found.get("isdir")):
                    result = "not_dir"
                else:
                    result = ""
            elif not os.path.exists(self.path):
                result = "missing"
            elif self.is_movie and not os.path.isfile(self.path):
                result = "not_file"
            elif not self.is_movie and not os.path.isdir(self.path):
                result = "not_dir"
            else:
                result = ""
        except Exception:
            result = "error"
        if not self.isInterruptionRequested():
            self.check_done.emit(result)


class QuickConnectProbeWorker(QThread):
    """A QuickConnect közvetítői végpontján is megpróbál DSM API-kapcsolatot létesíteni."""
    finished_with_result = pyqtSignal(str)

    def __init__(self, quickconnect_id, username, password):
        super().__init__()
        self.quickconnect_id = quickconnect_id.strip()
        self.username = username
        self.password = password

    def _finish(self, message):
        self.password = ""
        self.finished_with_result.emit(message)

    @staticmethod
    def _api_info(session, base_url):
        details = []
        params = {
            "api": "SYNO.API.Info", "version": "1", "method": "query",
            "query": "SYNO.API.Auth,SYNO.FileStation.List",
        }
        for endpoint in ("webapi/query.cgi", "webapi/entry.cgi"):
            url = f"{base_url.rstrip('/')}/{endpoint}"
            try:
                response = session.get(url, params=params, timeout=(4, 6))
                details.append(f"  {endpoint}: HTTP {response.status_code}")
                if response.status_code != 200:
                    continue
                try:
                    payload = response.json()
                except ValueError:
                    details.append("    A válasz nem JSON.")
                    continue
                if payload.get("success") and isinstance(payload.get("data"), dict):
                    return payload["data"], details
                details.append(f"    API-válasz: {str(payload)[:220]}")
            except requests.exceptions.ConnectTimeout:
                details.append(f"  {endpoint}: kapcsolódási időtúllépés")
            except requests.exceptions.ReadTimeout:
                details.append(f"  {endpoint}: válaszra várás időtúllépése")
            except requests.exceptions.SSLError as exc:
                details.append(f"  {endpoint}: TLS/tanúsítványhiba ({str(exc)[:150]})")
            except requests.exceptions.ConnectionError as exc:
                details.append(f"  {endpoint}: kapcsolódási hiba ({str(exc)[:150]})")
            except requests.RequestException as exc:
                details.append(f"  {endpoint}: {type(exc).__name__}: {str(exc)[:150]}")
        return None, details

    def run(self):
        try:
            validate_quickconnect_id(self.quickconnect_id)
        except ValueError as error:
            self._finish(str(error))
            return
        if not self.quickconnect_id or not self.username or not self.password:
            self._finish("Add meg a QuickConnect-azonosítót, a NAS-felhasználónevet és a jelszót.")
            return

        lines = ["1. QUICKCONNECT-FELOLDÁS"]
        request_items = [
            {"version": 1, "command": "get_server_info", "stop_when_error": False,
             "stop_when_success": False, "id": "dsm_portal_https",
             "serverID": self.quickconnect_id, "is_gofile": False},
            {"version": 1, "command": "get_server_info", "stop_when_error": False,
             "stop_when_success": False, "id": "dsm_portal",
             "serverID": self.quickconnect_id, "is_gofile": False},
        ]
        try:
            response = requests.post(
                "https://global.quickconnect.to/Serv.php",
                json=request_items, timeout=(5, 10),
            )
            lines.append(f"Feloldó HTTP-státusz: {response.status_code}")
            response.raise_for_status()
            resolved = response.json()
        except requests.exceptions.ConnectTimeout as exc:
            self._finish("A QuickConnect feloldóhoz való kapcsolódás időtúllépés miatt meghiúsult.\n\n" + str(exc))
            return
        except requests.exceptions.ReadTimeout as exc:
            self._finish("A QuickConnect feloldó nem válaszolt időben.\n\n" + str(exc))
            return
        except requests.exceptions.SSLError as exc:
            self._finish("TLS/tanúsítványhiba a QuickConnect feloldónál:\n" + str(exc))
            return
        except requests.RequestException as exc:
            self._finish("Nem sikerült elérni a QuickConnect feloldót.\n\n" + f"{type(exc).__name__}: {exc}")
            return
        except ValueError as exc:
            self._finish("A QuickConnect feloldója nem érvényes JSON-választ adott.\n\n" + str(exc))
            return

        candidates = []
        relay_candidates = []
        invalid_regions = 0
        if not isinstance(resolved, list):
            lines.append(f"Váratlan válaszformátum: {str(resolved)[:500]}")
        else:
            lines.append(f"Feloldó válaszainak száma: {len(resolved)}")
            for item in resolved:
                if not isinstance(item, dict):
                    lines.append(f"  Nem várt válaszelem: {str(item)[:180]}")
                    continue
                service = item.get("service") or {}
                server = item.get("server") or {}
                external = server.get("external") or {}
                env = item.get("env") or {}
                relay_region = env.get("relay_region")
                if item.get("errno") == 0 and isinstance(relay_region, str) and relay_region.strip():
                    try:
                        relay_candidates.append(quickconnect_url(self.quickconnect_id, relay_region))
                    except ValueError:
                        invalid_regions += 1
                        LOGGER.warning("Érvénytelen QuickConnect-régió kihagyva: ValueError")
                lines.append(
                    "  Szolgáltatás {sid}: errno={errno}, pingpong={ping}, ext_port={port}, hostok={hosts}".format(
                        sid=item.get("id", "?"), errno=item.get("errno", "?"),
                        ping=service.get("pingpong", "nincs adat"),
                        port=service.get("ext_port", "nincs adat"),
                        hosts=str(service.get("pingpong_desc") or ([external.get("ip")] if external.get("ip") else []))[:220],
                    )
                )
                if item.get("errno") != 0 or service.get("pingpong") != "CONNECTED":
                    continue
                ext_port = service.get("ext_port")
                internal_port = service.get("port")
                hosts = list(service.get("pingpong_desc") or [])
                if external.get("ip"):
                    hosts.append(external["ip"])
                for host in hosts:
                    if not isinstance(host, str) or not host.strip():
                        continue
                    host = host.strip().rstrip("/")
                    if host.startswith(("https://", "http://")):
                        candidates.append(host)
                        continue
                    has_port = host.count(":") == 1 and host.rsplit(":", 1)[-1].isdigit()
                    if has_port:
                        candidates.append(f"https://{host}")
                    else:
                        for port in (ext_port, internal_port):
                            if isinstance(port, int) and 1 <= port <= 65535:
                                candidates.append(f"https://{host}:{port}")
                        candidates.append(f"https://{host}")

        if invalid_regions and not relay_candidates and not candidates:
            self._finish("Érvénytelen QuickConnect-régió; a teszt megszakadt.")
            return
        candidates.extend([
            quickconnect_url(self.quickconnect_id, "direct"),
        ])
        relay_candidates = list(dict.fromkeys(relay_candidates))
        direct_candidates = list(dict.fromkeys(candidates))
        # Először a QuickConnect régióhoz tartozó közvetítői hostot próbáljuk;
        # a korábbi teszt ezt a lépést teljesen kihagyta.
        candidates = relay_candidates + [u for u in direct_candidates if u not in relay_candidates]
        lines.append("\n2. QUICKCONNECT KÖZVETÍTŐ ÉS DSM API PRÓBÁJA")
        lines.append(f"Közvetítői címek: {len(relay_candidates)}; közvetlen címek: {len(direct_candidates)}")
        if relay_candidates:
            lines.extend(f"  Közvetítői cím: {u}" for u in relay_candidates)
        if not candidates:
            lines.append("A feloldás nem adott vizsgálható címet.")

        tested_count = 0
        for base_url in candidates:
            if self.isInterruptionRequested():
                self._finish("A teszt megszakadt.\n\n" + "\n".join(lines))
                return
            tested_count += 1
            lines.append(f"\n[{tested_count}] {base_url}")
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 SynoStream/1.0",
                "Referer": f"https://{self.quickconnect_id}.quickconnect.to/",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            })
            # A relay hoston először megnyitjuk a portált, hogy a QuickConnect
            # munkamenet és a szükséges sütik létrejöhessenek.
            try:
                portal = session.get(base_url, timeout=(4, 8))
                lines.append(f"  Portál: HTTP {portal.status_code}; sütik: {len(session.cookies)}")
            except requests.RequestException as exc:
                lines.append(f"  Portálmegnyitás: {type(exc).__name__}: {str(exc)[:150]}")
            api_data, api_details = self._api_info(session, base_url)
            lines.extend(api_details)
            if not api_data:
                continue

            lines.append("  DSM API felismerve; bejelentkezés próbája…")
            auth_info = api_data.get("SYNO.API.Auth") or {}
            auth_path = auth_info.get("path") or "auth.cgi"
            auth_version = auth_info.get("maxVersion") or 6
            auth_url = f"{base_url.rstrip('/')}/webapi/{auth_path.lstrip('/')}"
            try:
                login = session.post(auth_url, data={
                    "api": "SYNO.API.Auth", "version": auth_version, "method": "login",
                    "account": self.username, "passwd": self.password,
                    "session": "FileStation", "format": "sid",
                }, timeout=(4, 8))
                lines.append(f"  Bejelentkezés HTTP-státusz: {login.status_code}")
                login.raise_for_status()
                login_data = login.json()
            except requests.exceptions.ConnectTimeout:
                lines.append("  Bejelentkezés: kapcsolódási időtúllépés.")
                continue
            except requests.exceptions.ReadTimeout:
                lines.append("  Bejelentkezés: válaszra várás időtúllépése.")
                continue
            except requests.RequestException as exc:
                lines.append(f"  Bejelentkezés hálózati hibája: {type(exc).__name__}: {str(exc)[:160]}")
                continue
            except ValueError:
                lines.append("  Bejelentkezés: a NAS nem JSON-választ adott.")
                continue

            if not login_data.get("success"):
                code = (login_data.get("error") or {}).get("code", "ismeretlen")
                lines.append(f"  Bejelentkezés sikertelen, DSM-hibakód: {code}")
                self._finish("A DSM API elérhető, de a bejelentkezés sikertelen.\n\n" + "\n".join(lines))
                return

            sid = (login_data.get("data") or {}).get("sid")
            if not sid:
                self._finish("A NAS nem adott érvényes munkamenet-azonosítót.")
                return
            list_info = api_data.get("SYNO.FileStation.List") or {}
            list_path = list_info.get("path") or "entry.cgi"
            list_version = list_info.get("maxVersion") or 2
            list_url = f"{base_url.rstrip('/')}/webapi/{list_path.lstrip('/')}"
            try:
                listing = session.get(list_url, params={
                    "api": "SYNO.FileStation.List", "version": list_version,
                    "method": "list_share", "_sid": sid,
                }, timeout=(4, 8))
                listing.raise_for_status()
                listing_data = listing.json()
            except (requests.RequestException, ValueError) as exc:
                listing_data = {}
                lines.append(f"  Mappalista lekérése sikertelen: {type(exc).__name__}: {str(exc)[:160]}")
            finally:
                try:
                    session.get(auth_url, params={
                        "api": "SYNO.API.Auth", "version": auth_version,
                        "method": "logout", "session": "FileStation", "_sid": sid,
                    }, timeout=(2, 3))
                except requests.RequestException:
                    pass

            if listing_data.get("success"):
                shares = (listing_data.get("data") or {}).get("shares") or []
                lines.append(f"\nEREDMÉNY: SIKERES. Megosztott mappák: {len(shares)}.")
                lines.append("A NAS-kapcsolat működik; a médiatárhoz NAS-forrásmappát választhatsz.")
                self._finish("\n".join(lines))
                return
            code = (listing_data.get("error") or {}).get("code", "ismeretlen")
            lines.append(f"  Bejelentkezés sikerült, mappalista hibakódja: {code}")
            self._finish("A DSM API és a bejelentkezés működik, de a mappalista nem kérhető le.\n\n" + "\n".join(lines))
            return

        lines.append("\nÖSSZEGZÉS")
        if relay_candidates:
            lines.append("A QuickConnect közvetítői hostot is kipróbáltuk, de ezen és a közvetlen címeken sem sikerült használható DSM API-választ kapni.")
            lines.append("A részletes portál- és API-hibák fent láthatók; ezek alapján tovább lehet javítani a protokollkezelést.")
        else:
            lines.append("A feloldó nem adott relay_region mezőt, így közvetítői végpontot nem lehetett összeállítani; csak a közvetlen címeket próbáltuk.")
        lines.append("A teszt nem módosított semmit a NAS-on.")
        self._finish("\n".join(lines))


class RemoteQuickConnectDialog(QDialog):
    """Távoli File Station böngésző QuickConnect közvetítőn keresztül.

    A hitelesítő adatokat és a DSM SID-et csak memóriában tartja. A helyi MPV-proxy
    kizárólag loopback címen figyel, és a NAS-ról streameli a kiválasztott fájlt.
    """
    def __init__(self, parent=None, target_library=None, folder_picker=False, connection_only=False):
        super().__init__(parent)
        self.setWindowTitle("NAS-kapcsolat")
        self.resize(760, 600)
        # Új médiatár létrehozásakor a NAS-mappát közvetlenül ehhez rendeljük.
        # A konfigurációba csak akkor kerül be, amikor a felhasználó ténylegesen
        # kiválasztott egy NAS-mappát.
        self.target_library = target_library
        self.connection_only = connection_only
        self.folder_picker = folder_picker
        self.selected_folder = None
        self.folder_assigned = False
        self._nas_task = None
        self._nas_client = None
        self.session = requests.Session()
        self.qc_id = config.get("quickconnect_id", "") or ""
        self.base_url = ""
        self.sid = ""
        self.auth_url = ""
        self.auth_version = 6
        self.list_url = ""
        self.list_version = 2
        self.download_url = ""
        self.download_version = 2
        self.current_path = ""
        self._proxy_server = None
        self._proxy_thread = None
        self._proxy_token = secrets.token_urlsafe(32)
        self._proxy_allowed_paths = set()
        self._active_player_process = None
        self._pending_dialog_result = None
        self._cleanup_done = False
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._cleanup_connection)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        if self.target_library:
            intro_text = (
                "Kapcsolódj a NAS-hoz, tallózd be a kívánt megosztott mappát, "
                "majd válaszd a „Mappa hozzáadása az új médiatárhoz” gombot. "
                "A NAS-jelszót Windows-fiókodhoz kötött védelem tárolja."
            )
        else:
            intro_text = "Add meg egyszer a NAS eléréseit. A sorrend: helyi hálózat, DDNS, QuickConnect. Elég egy működő elérés; a többi tartalék. A forrásmappákat minden kapcsolaton ugyanazzal az útvonallal használjuk."
        intro = QLabel(translate_text(intro_text))
        intro.setWordWrap(True)
        root.addWidget(intro)
        form = QFormLayout()
        self.id_edit = QLineEdit(config.get("quickconnect_id", "") or "")
        self.id_edit.setPlaceholderText("QuickConnect-azonosító")
        self.user_edit = QLineEdit(config.get("nas_username", ""))
        saved_password_exists = bool(config.get("nas_password", ""))
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_edit.setPlaceholderText(translate_text(
            "Mentett jelszó használata (üresen hagyva)"
            if saved_password_exists else "Jelszó megadása"
        ))
        self.pass_show_check = QCheckBox(translate_text("Mutat"))
        self.pass_show_check.toggled.connect(
            lambda visible: self.pass_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
            )
        )
        password_row = QWidget()
        password_layout = QHBoxLayout(password_row)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.addWidget(self.pass_edit, 1)
        password_layout.addWidget(self.pass_show_check)
        self.local_edit = QLineEdit(config.get("nas_local_url", "") or "")
        self.local_edit.setPlaceholderText("192.168.1.2 (opcionális)")
        self.local_edit.setToolTip("A NAS helyi File Station-címe. A NAS-mappákhoz az SMB-elérést is automatikusan megpróbáljuk.")
        form.addRow("Helyi NAS-cím:", self.local_edit)
        self.direct_edit = QLineEdit(config.get("nas_direct_url", "") or "")
        self.direct_edit.setPlaceholderText("https://nas.pelda.hu:5001 vagy http://nas.pelda.hu:5000")
        self.direct_edit.setToolTip("Közvetlen HTTP-/HTTPS-/DDNS-cím. Ha nem érhető el, a QuickConnect a tartalék.")
        form.addRow("DDNS / közvetlen cím:", self.direct_edit)
        form.addRow("QuickConnect ID:", self.id_edit)
        form.addRow("NAS-felhasználó:", self.user_edit)
        form.addRow("NAS-jelszó:", password_row)
        self.remember_device = QCheckBox(translate_text("Megbízható eszköz megjegyzése a kétlépcsős belépéshez"))
        self.remember_device.setChecked(bool(trusted_device_id(config)))
        form.addRow(self.remember_device)
        root.addLayout(form)
        row = QHBoxLayout()
        self.connect_btn = QPushButton("Kapcsolódás")
        self.up_btn = QPushButton("◀ Szülőmappa")
        self.up_btn.setEnabled(False)
        self.path_lbl = QLabel("Nincs csatlakoztatva")
        self.path_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self.connect_btn)
        row.addWidget(self.up_btn)
        row.addWidget(self.path_lbl, 1)
        root.addLayout(row)
        self.items = QListWidget()
        self.items.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        root.addWidget(self.items, 1)
        bottom = QHBoxLayout()
        self.play_btn = QPushButton("Kiválasztott videó lejátszása MPV-vel")
        self.play_btn.setEnabled(False)
        self.select_folder_btn = QPushButton(
            translate_text("Mappa hozzáadása az új médiatárhoz")
            if self.target_library else "Aktuális mappa kiválasztása…"
        )
        self.select_folder_btn.setEnabled(False)
        if self.folder_picker:
            self.select_folder_btn.setText(translate_text("Mappa kiválasztása"))
            self.play_btn.hide()
        elif not self.target_library:
            self.select_folder_btn.hide()
        self.close_btn = QPushButton("Bezárás")
        bottom.addWidget(self.play_btn)
        bottom.addWidget(self.select_folder_btn)
        bottom.addStretch(1)
        bottom.addWidget(self.close_btn)
        root.addLayout(bottom)
        self.connect_btn.clicked.connect(self.connect_nas)
        self.up_btn.clicked.connect(self.go_parent)
        self.items.itemDoubleClicked.connect(self.activate_item)
        self.items.itemSelectionChanged.connect(self.update_play_button)
        self.play_btn.clicked.connect(self.play_selected)
        self.select_folder_btn.clicked.connect(self.choose_remote_folder)
        self.close_btn.clicked.connect(self.close)
        if self.connection_only:
            self.resize(760, 370)
            self.up_btn.hide(); self.items.hide(); self.play_btn.hide(); self.select_folder_btn.hide()
            self.connect_btn.setText("Kapcsolat ellenőrzése és mentése")

    def _start_task(self, operation, success, dispose=None):
        if self._nas_task is not None:
            return
        task = NasTask(operation, dispose)
        self._nas_task = task
        self.connect_btn.setEnabled(False)
        self.up_btn.setEnabled(False)
        self.items.setEnabled(False)
        self.select_folder_btn.setEnabled(False)
        self.play_btn.setEnabled(False)
        self.path_lbl.setText("Kapcsolódás / mappalista betöltése…")
        self.close_btn.setText("Megszakítás")
        task.succeeded.connect(success)
        task.failed.connect(self._nas_failure)
        task.finished.connect(self._task_finished)
        run_worker(task)

    def _nas_failure(self, message):
        if message.startswith('Kétlépcsős kód szükséges:'):
            self._otp_requested = True
        else:
            QMessageBox.warning(self, 'NAS-kapcsolat', message)

    def _request_otp(self):
        code, accepted = QInputDialog.getText(self, 'Kétlépcsős azonosítás', 'A NAS egyszer használatos kódja:')
        if accepted and code.strip():
            self._otp_once = code.strip()
            self.connect_nas()

    def _task_finished(self):
        self._nas_task = None
        if getattr(self, "_otp_requested", False):
            self._otp_requested = False
            QTimer.singleShot(0, self._request_otp)
        self.close_btn.setText("Bezárás")
        self.connect_btn.setEnabled(not bool(self.sid))
        self.items.setEnabled(True)
        self.up_btn.setEnabled(bool(self.current_path))
        self.select_folder_btn.setEnabled(bool(self.sid))
        self.update_play_button()
        self.path_lbl.setText(self.current_path or ("/ (megosztott mappák)" if self.sid else "Nincs csatlakoztatva"))
        if self.connection_only and self.sid:
            self.path_lbl.setText(self.connect_btn.text())
        if self._pending_dialog_result is not None and self._active_player_process is None:
            result = self._pending_dialog_result
            self._pending_dialog_result = None
            self.done(result)
        elif self.sid and self.items.count() == 0:
            # The initial folder listing starts after connection task cleanup.
            if getattr(self, "_initial_listing", False):
                self._initial_listing = False
                self.load_folder("")

    def connect_nas(self):
        credentials = dict(nas_local_url=self.local_edit.text().strip(), nas_direct_url=self.direct_edit.text().strip(), quickconnect_id=self.id_edit.text().strip(),
                           nas_username=self.user_edit.text().strip(),
                           nas_password=self.pass_edit.text() or config.get("nas_password", ""))
        from synostream_nas import normalize_direct_url
        from synostream_connections import normalize_local_url
        try:
            credentials['nas_direct_url'] = normalize_direct_url(credentials['nas_direct_url'])
            credentials['nas_local_url'] = normalize_local_url(credentials['nas_local_url'])
        except ValueError as exc:
            QMessageBox.warning(self, "Hibás NAS-cím", str(exc))
            return
        if not (credentials['quickconnect_id'] or credentials['nas_direct_url'] or credentials['nas_local_url']) or not credentials['nas_username'] or not credentials['nas_password']:
            QMessageBox.warning(self, "Hiányzó adat", "Adj meg legalább egy NAS-elérést, valamint a felhasználónevet és a jelszót.")
            return
        otp = getattr(self, "_otp_once", "")
        self._otp_once = ""
        client_credentials = dict(credentials, nas_device_tokens=config.get("nas_device_tokens", ""),
                                  use_device_token=self.remember_device.isChecked(), remember_device=self.remember_device.isChecked(),
                                  **({"otp_code":otp} if otp else {}))
        def connected(client):
            self.session.close()
            self._nas_client = client
            for name in ("session", "base_url", "sid", "auth_url", "auth_version", "list_url",
                         "list_version", "download_url", "download_version"):
                setattr(self, name, getattr(client, name))
            config.update(credentials)
            try: devices = json.loads(config.get('nas_device_tokens') or '{}')
            except (TypeError,ValueError): devices = {}
            if not isinstance(devices,dict):devices={}
            key=nas_device_key(credentials)
            if not self.remember_device.isChecked():devices.pop(key,None)
            elif getattr(client,'device_id',''):devices[key]=client.device_id
            config['nas_device_tokens']=json.dumps(devices)
            ok, error = save_config()
            if not ok:
                QMessageBox.warning(self, "Mentési figyelmeztetés", redact_credentials(error))
            self.pass_edit.clear()
            self.pass_show_check.setChecked(False)
            self.id_edit.setEnabled(False)
            self.direct_edit.setEnabled(False)
            self.local_edit.setEnabled(False)
            self.user_edit.setEnabled(False)
            self.connect_btn.setText("Kapcsolódva – " + ({"local":"helyi hálózat", "direct":"DDNS / közvetlen NAS"}.get(getattr(client, "transport", ""), "QuickConnect")))
            self._initial_listing = not self.connection_only
            owner = self.parentWidget()
            while owner is not None and not hasattr(owner, 'migrate_unified_sources'):
                owner = owner.parentWidget()
            if owner is not None:
                QTimer.singleShot(0, owner.migrate_unified_sources)
        self._start_task(lambda stop: RemoteNASClient(client_credentials, stop), connected, lambda client: client.close())

    def load_folder(self, path):
        if self._nas_client is None:
            return
        def listing(stop):
            self._nas_client.should_stop = stop
            return self._nas_client.list_folder(path)
        def loaded(entries):
            self.current_path = path
            self.items.clear()
            entries.sort(key=lambda x: (not bool(x.get("isdir")), x.get("name", "").casefold()))
            for entry in entries:
                if self.folder_picker and not entry.get("isdir"): continue
                name = entry.get("name", "(névtelen)")
                is_dir = bool(entry.get("isdir"))
                full = entry.get("path") or (path.rstrip("/") + "/" + name)
                item = QListWidgetItem()
                item.setRawText(("📁  " if is_dir else "🎬  ") + name)
                item.setData(Qt.ItemDataRole.UserRole, {"path": full, "isdir": is_dir, "name": name})
                self.items.addItem(item)
        self._start_task(listing, loaded)

    def choose_remote_folder(self):
        """Az aktuális NAS-mappa mentése egy médiatár útvonalaként."""
        if not self.sid:
            return
        if self.folder_picker:
            if not self.current_path:
                QMessageBox.warning(self, "Mappa kiválasztása", "Válassz előbb egy megosztott mappát.")
                return
            self.selected_folder = REMOTE_PREFIX + self.current_path
            self.accept()
            return
        options = [("movies", "Filmek") , ("shows", "TV műsorok")]
        options.extend((f"custom:{lib['id']}", lib["name"])
                       for lib in config.get("custom_libraries", []))
        if self.target_library and not any(
            kind == f"custom:{self.target_library['id']}" for kind, _name in options
        ):
            options.append((f"custom:{self.target_library['id']}", self.target_library["name"]))
        if self.target_library:
            kind = f"custom:{self.target_library['id']}"
            if not self.current_path:
                QMessageBox.warning(self, "Mappa kiválasztása", "Válassz előbb egy megosztott mappát.")
                return
        else:
            choices = QDialog(self)
            choices.setWindowTitle("Távoli mappa hozzárendelése")
            layout = QVBoxLayout(choices)
            layout.addWidget(QLabel("Melyik könyvtárként mentsem a jelenleg megnyitott mappát?"))
            result = {"kind": None}
            for option_kind, name in options:
                button = QPushButton(f"{name} médiatárához adás")
                button.clicked.connect(lambda _checked=False, k=option_kind: (result.update(kind=k), choices.accept()))
                layout.addWidget(button)
            cancel_btn = QPushButton("Mégse")
            layout.addWidget(cancel_btn)
            cancel_btn.clicked.connect(choices.reject)
            if choices.exec() != QDialog.DialogCode.Accepted or not result["kind"]:
                return
            kind = result["kind"]

        old_path = None
        new_library_added = False
        if kind == "movies":
            key = "remote_movies_path"
            old_path = config.get(key, "")
            config[key] = self.current_path
        elif kind == "shows":
            key = "remote_shows_path"
            old_path = config.get(key, "")
            config[key] = self.current_path
        else:
            library_id = kind.split(":", 1)[1]
            library = next((lib for lib in config.get("custom_libraries", [])
                            if lib.get("id") == library_id), None)
            if library is None and self.target_library and self.target_library.get("id") == library_id:
                library = self.target_library
                config.setdefault("custom_libraries", []).append(library)
                new_library_added = True
            if library is None:
                QMessageBox.warning(self, "Médiatár nem található", "A kiválasztott médiatár már nem létezik.")
                return
            remote_path = REMOTE_PREFIX + self.current_path
            library.setdefault("paths", [])
            old_path = list(library["paths"])
            if normalize_media_path(remote_path) not in {
                normalize_media_path(path) for path in library["paths"]
            }:
                library["paths"].append(remote_path)
        ok, error = save_config()
        if not ok:
            if kind.startswith("custom:"):
                library["paths"] = old_path
                if new_library_added:
                    config["custom_libraries"].remove(library)
            elif old_path is not None:
                config[key] = old_path
            QMessageBox.critical(self, "Mentési hiba", f"Nem sikerült elmenteni a távoli mappát:\n{error}")
            return
        label = next((name for option, name in options if option == kind), "média")
        QMessageBox.information(self, "Mappa elmentve", f"A távoli mappa hozzáadva ehhez: {label}\n{self.current_path or '/'}\n\nA beállítás megmarad a következő indításra is.")
        if self.target_library:
            self.folder_assigned = True
            self.accept()
            return
        parent = self.parent()
        if parent is not None and hasattr(parent, "start_library_scan"):
            parent.start_library_scan()

    def activate_item(self, item):
        info = item.data(Qt.ItemDataRole.UserRole) or {}
        if info.get("isdir"):
            self.load_folder(info.get("path", ""))
        elif info.get("name", "").lower().endswith(VIDEO_EXTENSIONS):
            self.play_selected()

    def go_parent(self):
        if not self.current_path:
            return
        parent = self.current_path.rsplit("/", 1)[0]
        if not parent:
            parent = ""
        self.load_folder(parent)

    def update_play_button(self):
        item = self.items.currentItem()
        info = item.data(Qt.ItemDataRole.UserRole) if item else {}
        self.play_btn.setEnabled(bool(info and not info.get("isdir") and info.get("name", "").lower().endswith(VIDEO_EXTENSIONS)))

    def play_selected(self):
        item = self.items.currentItem()
        info = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not info or info.get("isdir") or not info.get("name", "").lower().endswith(VIDEO_EXTENSIONS):
            return
        if self._active_player_process is not None and self._active_player_process.poll() is None:
            QMessageBox.information(self, "Lejátszás folyamatban", "A NAS-böngészőből egyszerre egy videót lehet lejátszani.")
            return
        mpv_raw = config.get("mpv_path") or "mpv.exe"
        mpv_path = resolve_mpv_path(mpv_raw)
        if not mpv_path:
            mpv_path = ensure_mpv(self)
            if not mpv_path:
                return
        self.start_proxy()
        remote_path = info.get("path") or ""
        self._proxy_allowed_paths.add(remote_path)
        saved_path = REMOTE_PREFIX + remote_path
        state = get_playback_state(saved_path)
        resume_position = (
            state["position"] if state and not state["watched"] and state["position"] >= 15 else 0
        )
        pipe_name = rf"\\.\pipe\SynoStream-{uuid.uuid4().hex}"
        stream_url = (
            f"http://127.0.0.1:{self._proxy_server.server_address[1]}/stream"
            f"?token={self._proxy_token}&path={quote(remote_path, safe='')}"
        )
        entry = {
            "path": saved_path,
            "media_title": info.get("name", ""),
            "episode_title": "",
            "poster": "",
            "is_movie": True,
        }
        cmd = [
            mpv_path, "--hwdec=auto", "--no-resume-playback", "--no-save-position-on-quit",
            f"--input-ipc-server={pipe_name}",
        ]
        if config.get("playback_fullscreen", False):
            cmd.append("--fullscreen=yes")
        cmd.extend(mpv_localized_context_menu_args(mpv_path))
        cmd.append("--{")
        if resume_position > 0:
            cmd.append(f"--start={resume_position:.3f}")
        if info.get("name"):
            cmd.append(f"--force-media-title={info['name']}")
        cmd.extend((stream_url, "--}"))
        try:
            process = subprocess.Popen(cmd, env=mpv_child_environment())
        except OSError as exc:
            QMessageBox.critical(self, "MPV hiba", str(exc))
            return
        self._active_player_process = process
        save_playback_progress(entry, resume_position, state["duration"] if state else 0, [entry])
        monitor = MpvPlaybackMonitor(process, pipe_name, [entry], resume_position, source_paths=[stream_url])
        monitor.finished.connect(self._on_player_finished)
        run_worker(monitor)

    def start_proxy(self):
        if self._proxy_server:
            return
        dialog = self
        class Handler(BaseHTTPRequestHandler):
            def do_HEAD(self):
                self.do_GET(head_only=True)
            def do_GET(self, head_only=False):
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(self.path)
                if parsed.path != "/stream":
                    self.send_error(404); return
                query = parse_qs(parsed.query)
                token = (query.get("token") or [""])[0]
                remote_path = (query.get("path") or [""])[0]
                if not constant_time_equal_text(token, dialog._proxy_token):
                    self.send_error(403); return
                if not remote_path or remote_path not in dialog._proxy_allowed_paths:
                    self.send_error(403); return
                try:
                    params = {"api": "SYNO.FileStation.Download", "version": dialog.download_version,
                              "method": "download", "path": remote_path, "mode": "open", "_sid": dialog.sid}
                    headers = {}
                    if self.headers.get("Range"):
                        headers["Range"] = self.headers["Range"]
                    upstream = dialog._nas_client.open_stream(remote_path, headers)
                    if upstream.status_code not in (200, 206):
                        self.send_error(upstream.status_code, "NAS stream hiba"); upstream.close(); return
                    if "json" in upstream.headers.get("Content-Type", "").lower():
                        upstream.close()
                        self.send_error(502, "A NAS nem videófájlt adott vissza.")
                        return
                    self.send_response(upstream.status_code)
                    for key in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "Last-Modified", "ETag"):
                        if upstream.headers.get(key): self.send_header(key, upstream.headers[key])
                    self.send_header("Connection", "close")
                    self.end_headers()
                    if not head_only:
                        for chunk in upstream.iter_content(1024 * 1024):
                            if not chunk: continue
                            try: self.wfile.write(chunk)
                            except (BrokenPipeError, ConnectionResetError): break
                    upstream.close()
                except Exception as exc:
                    safe_error = redact_credentials(exc)
                    LOGGER.warning("Távoli NAS-stream hiba: %s", safe_error)
                    try: self.send_error(502, safe_error[:180])
                    except Exception: pass
            def log_message(self, fmt, *args):
                pass
        self._proxy_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._proxy_server.daemon_threads = True
        self._proxy_thread = threading.Thread(target=self._proxy_server.serve_forever, daemon=True)
        self._proxy_thread.start()

    def _cleanup_connection(self):
        if self._cleanup_done:
            return
        self._cleanup_done = True
        server, client, session = self._proxy_server, self._nas_client, self.session
        self._proxy_server = None
        self._nas_client = None
        self.sid = ""
        def cleanup(_stop):
            if server:
                server.shutdown()
                server.server_close()
            if client:
                client.close()
            else:
                session.close()
        run_worker(NasTask(cleanup))

    def done(self, result):
        if self._nas_task is not None:
            self._pending_dialog_result = result
            self._nas_task.requestInterruption()
            self.hide()
            return
        # Az Esc gomb a QDialog.reject()/done() útvonalát használja, nem a closeEventet.
        if self._active_player_process is not None and self._active_player_process.poll() is None:
            self._pending_dialog_result = result
            self.hide()
            return
        self._cleanup_connection()
        super().done(result)

    def _on_player_finished(self):
        self._active_player_process = None
        if self._pending_dialog_result is not None:
            result = self._pending_dialog_result
            self._pending_dialog_result = None
            self._cleanup_connection()
            super().done(result)

    def closeEvent(self, event):
        if self._nas_task is not None:
            self.done(QDialog.DialogCode.Rejected)
            event.ignore()
            return
        if self._active_player_process is not None and self._active_player_process.poll() is None:
            self._pending_dialog_result = QDialog.DialogCode.Rejected
            self.hide()
            event.ignore()
            return
        self._cleanup_connection()
        event.accept()



class QuickConnectTestDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.setWindowTitle("Synology QuickConnect – kapcsolatpróba")
        self.resize(820, 680)
        self.setMinimumSize(620, 480)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Ez a próba először a QuickConnect közvetítői végpontján, majd közvetlenül próbálja elérni a DSM API-t. "
            "A jelszót a program nem menti el. Siker esetén megmutatja a megosztott mappákat."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.id_edit = QLineEdit(config.get("quickconnect_id", "") or "")
        self.id_edit.setPlaceholderText("QuickConnect-azonosító")
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("NAS-felhasználónév")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("NAS-jelszó (csak helyben használjuk)")
        self.password_show_check = QCheckBox(translate_text("Mutat"))
        self.password_show_check.toggled.connect(
            lambda visible: self.password_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
            )
        )
        password_row = QWidget()
        password_layout = QHBoxLayout(password_row)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.addWidget(self.password_edit, 1)
        password_layout.addWidget(self.password_show_check)
        form.addRow("QuickConnect ID:", self.id_edit)
        form.addRow("Felhasználónév:", self.user_edit)
        form.addRow("Jelszó:", password_row)
        layout.addLayout(form)
        # A részletes napló külön szövegmezőben jelenik meg: görgethető és kijelölhető.
        self.status = QPlainTextEdit()
        self.status.setReadOnly(True)
        self.status.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.status.setPlaceholderText("A kapcsolatpróba eredménye itt jelenik meg.")
        self.status.setMinimumHeight(220)
        self.status.setStyleSheet("QPlainTextEdit { font-family: Consolas, monospace; }")
        layout.addWidget(self.status, 1)
        buttons = QHBoxLayout()
        self.test_btn = QPushButton("Kapcsolat tesztelése")
        self.copy_btn = QPushButton("Eredmény másolása")
        self.save_btn = QPushButton("Napló mentése…")
        self.close_btn = QPushButton("Bezárás")
        self.copy_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.test_btn.clicked.connect(self.start_test)
        self.copy_btn.clicked.connect(self.copy_result)
        self.save_btn.clicked.connect(self.save_result)
        self.close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.test_btn)
        buttons.addWidget(self.copy_btn)
        buttons.addWidget(self.save_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

    def start_test(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self.test_btn.setEnabled(False)
        self.status.setPlainText("Kapcsolat ellenőrzése… ez akár 20–30 másodpercig is tarthat.")
        self.copy_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.worker = QuickConnectProbeWorker(
            self.id_edit.text(), self.user_edit.text(), self.password_edit.text()
        )
        self.worker.finished_with_result.connect(self.show_result)
        run_worker(self.worker)

    def show_result(self, message):
        self.test_btn.setEnabled(True)
        self.status.setPlainText(message)
        self.status.verticalScrollBar().setValue(0)
        self.copy_btn.setEnabled(bool(message))
        self.save_btn.setEnabled(bool(message))
        self.password_edit.clear()

    def copy_result(self):
        text = self.status.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    def save_result(self):
        text = self.status.toPlainText()
        if not text:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "QuickConnect-napló mentése", "quickconnect_diagnosztika.txt",
            "Szövegfájl (*.txt);;Minden fájl (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            QMessageBox.information(self, "Napló mentve", f"A diagnosztika mentve ide:\n{path}")
        except OSError as exc:
            QMessageBox.critical(self, "Mentési hiba", f"Nem sikerült elmenteni a naplót:\n{exc}")


class EpisodeScanWorker(QThread):
    episodes_found = pyqtSignal(list, str)  # (epizódok, hibaüzenet vagy "")

    def __init__(self, show_path):
        super().__init__()
        # A szokásos sorozatmappa mellett támogatjuk az egyes epizódmappákból
        # összeállított csoportokat is.
        self.show_paths = show_path if isinstance(show_path, list) else [show_path]

    def run(self):
        episodes = []
        errors = []
        client = None
        try:
            for root_index, show_path in enumerate(self.show_paths):
                if self.isInterruptionRequested():
                    return
                prefix = os.path.basename(remote_real_path(show_path).rstrip("/")) if is_remote_path(show_path) else os.path.basename(os.path.normpath(show_path))
                if is_remote_path(show_path):
                    if client is None:
                        client = RemoteNASClient(should_stop=self.isInterruptionRequested)
                    root = remote_real_path(show_path)
                    def walk(path, rel=""):
                        if self.isInterruptionRequested(): return
                        try: entries = client.list_folder(path)
                        except Exception as exc:
                            errors.append(str(exc)); return
                        for e in sorted(entries, key=lambda x: natural_sort_key(x.get("name", ""))):
                            name=e.get("name", "")
                            if is_ignored(name): continue
                            full=e.get("path") or path.rstrip("/")+"/"+name
                            if media_is_excluded(REMOTE_PREFIX+full): continue
                            subrel=os.path.join(rel,name) if rel else name
                            if e.get("isdir"):
                                walk(full,subrel)
                            elif name.lower().endswith(VIDEO_EXTENSIONS):
                                label = os.path.join(prefix, subrel) if len(self.show_paths)>1 else subrel
                                episodes.append((label, REMOTE_PREFIX+full))
                    walk(root)
                else:
                    found, error = find_episodes(show_path, self.isInterruptionRequested)
                    if error: errors.append(error)
                    for rel, full in found:
                        label = os.path.join(prefix, rel) if len(self.show_paths)>1 else rel
                        episodes.append((label, full))
            episodes.sort(key=lambda x: natural_sort_key(x[0]))
            unique_episodes = {}
            for label, path in episodes:
                unique_episodes.setdefault(normalize_media_path(path), (label, path))
            episodes = list(unique_episodes.values())
            error = f"NAS-/mappahiba: {errors[0]}" if errors else ""
        except Exception as e:
            LOGGER.exception("Nem sikerült beolvasni a sorozat epizódjait.")
            episodes, error = [], f"Váratlan hiba: {e}"
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    LOGGER.exception("Nem sikerült lezárni az epizódbeolvasás NAS-kapcsolatát.")
        if not self.isInterruptionRequested():
            self.episodes_found.emit(episodes, error)




REMOTE_PREFIX = "syno://"
def is_remote_path(path):
    return isinstance(path, str) and path.startswith(REMOTE_PREFIX)
def remote_real_path(path):
    return path[len(REMOTE_PREFIX):] if is_remote_path(path) else path


def normalize_media_path(path):
    """Stabilizálja a médiatár kulcsát, a syno:// útvonalat nem alakítja Windows-helyi úttá."""
    path = source_router().canonical(path)
    if is_remote_path(path):
        remote = remote_real_path(path).replace("\\", "/")
        normalized = posixpath.normpath(remote)
        if not normalized.startswith("/"):
            normalized = "/" + normalized
        return REMOTE_PREFIX + normalized
    return normalize_path(path)


def media_path_is_within(path, base):
    path, base = source_router().canonical(path), source_router().canonical(base)
    if is_remote_path(path) or is_remote_path(base):
        if not (is_remote_path(path) and is_remote_path(base)):
            return False
        remote_path = remote_real_path(path).replace("\\", "/").rstrip("/")
        remote_base = remote_real_path(base).replace("\\", "/").rstrip("/")
        return remote_path == remote_base or remote_path.startswith(remote_base + "/")
    return is_within(path, base)


def get_playback_state(file_path):
    norm_path = normalize_media_path(file_path)
    if not norm_path:
        return None
    try:
        with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
            row = conn.execute(
                "SELECT media_title, episode_title, poster, is_movie, position, duration, "
                "last_played, watched, playlist_paths FROM playback_state WHERE file_path = ?",
                (norm_path,),
            ).fetchone()
    except sqlite3.Error:
        LOGGER.exception("Nem sikerült lejátszási állapotot olvasni: %s", norm_path)
        return None
    if not row:
        return None
    try:
        playlist_paths = json.loads(row[8] or "[]")
    except (TypeError, json.JSONDecodeError):
        playlist_paths = []
    return {
        "file_path": norm_path,
        "media_title": row[0] or "",
        "episode_title": row[1] or "",
        "poster": row[2] or "",
        "is_movie": bool(row[3]),
        "position": float(row[4] or 0),
        "duration": float(row[5] or 0),
        "last_played": float(row[6] or 0),
        "watched": bool(row[7]),
        "playlist_paths": playlist_paths if isinstance(playlist_paths, list) else [],
    }


def watched_path_prefixes(file_path):
    """Return the file path and all its parents for O(1) descendant lookups."""
    normalized = normalize_media_path(file_path)
    if not normalized:
        return set()
    prefixes = set()
    if is_remote_path(normalized):
        current = remote_real_path(normalized).replace("\\", "/").rstrip("/") or "/"
        while True:
            prefixes.add(REMOTE_PREFIX + current)
            parent = posixpath.dirname(current.rstrip("/")) or "/"
            if parent == current:
                break
            current = parent
    else:
        current = normalized
        while current:
            prefixes.add(current)
            parent = os.path.dirname(current)
            if not parent or parent == current:
                break
            current = parent
    return prefixes


def get_watched_path_prefixes():
    global WATCHED_PATHS_CACHE
    with WATCHED_PATHS_LOCK:
        if WATCHED_PATHS_CACHE is None:
            try:
                with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
                    rows = conn.execute(
                        "SELECT file_path FROM playback_state WHERE watched = 1"
                    ).fetchall()
                prefixes = set()
                for row in rows:
                    prefixes.update(watched_path_prefixes(row[0]))
                WATCHED_PATHS_CACHE = prefixes
            except sqlite3.Error:
                WATCHED_PATHS_CACHE = set()
                LOGGER.exception("Nem sikerült lekérdezni a megtekintett videókat.")
        return WATCHED_PATHS_CACHE


def invalidate_watched_paths_cache():
    global WATCHED_PATHS_CACHE
    with WATCHED_PATHS_LOCK:
        WATCHED_PATHS_CACHE = None


def invalidate_watched_paths_cache_for_unseen(path):
    """Invalidate only when progress newly marks a path watched."""
    global WATCHED_PATHS_CACHE
    with WATCHED_PATHS_LOCK:
        if WATCHED_PATHS_CACHE is not None and path not in WATCHED_PATHS_CACHE:
            WATCHED_PATHS_CACHE = None


def item_has_watched_playback(item):
    """True if the item itself or any episode under its roots is marked watched."""
    roots = item.get("episode_roots") or [item.get("file_path", "")]
    normalized_roots = {
        normalize_media_path(path) for path in roots
        if isinstance(path, str) and path
    }
    if not normalized_roots:
        return False
    watched_prefixes = get_watched_path_prefixes()
    return any(root in watched_prefixes for root in normalized_roots)


def save_playback_progress(entry, position, duration, remaining_paths):
    file_path = entry.get("path") or ""
    norm_path = normalize_media_path(file_path)
    if not norm_path:
        return
    position = max(0.0, float(position or 0))
    duration = max(0.0, float(duration or 0))
    auto_watched = int(duration > 0 and position >= duration * 0.9)
    try:
        with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
            conn.execute('''
                INSERT INTO playback_state
                    (file_path, media_title, episode_title, poster, is_movie,
                     position, duration, last_played, watched, playlist_paths)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    media_title=excluded.media_title,
                    episode_title=excluded.episode_title,
                    poster=excluded.poster,
                    is_movie=excluded.is_movie,
                    position=excluded.position,
                    duration=CASE WHEN excluded.duration > 0
                                  THEN excluded.duration ELSE playback_state.duration END,
                    last_played=excluded.last_played,
                    watched=MAX(playback_state.watched, excluded.watched),
                    playlist_paths=excluded.playlist_paths
            ''', (
                norm_path,
                entry.get("media_title", ""),
                entry.get("episode_title", ""),
                entry.get("poster", ""),
                1 if entry.get("is_movie", True) else 0,
                position,
                duration,
                time.time(),
                auto_watched,
                json.dumps(remaining_paths or [file_path], ensure_ascii=False),
            ))
            conn.commit()
            DISPLAY_STATE_CACHE.update(DB_FILE, norm_path, conn)
            if auto_watched:
                invalidate_watched_paths_cache_for_unseen(norm_path)
    except sqlite3.Error:
        LOGGER.exception("Nem sikerült menteni a lejátszási pozíciót: %s", norm_path)


def set_playback_watched(file_path, media_title, episode_title, poster, is_movie, watched):
    norm_path = normalize_media_path(file_path)
    if not norm_path:
        return
    try:
        with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
            conn.execute('''
                INSERT INTO playback_state
                    (file_path, media_title, episode_title, poster, is_movie,
                     last_played, watched, playlist_paths)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    media_title=excluded.media_title,
                    episode_title=excluded.episode_title,
                    poster=excluded.poster,
                    is_movie=excluded.is_movie,
                    watched=excluded.watched,
                    position=CASE WHEN excluded.watched = 0 THEN 0 ELSE playback_state.position END
            ''', (
                norm_path, media_title or "", episode_title or "", poster or "",
                1 if is_movie else 0, time.time(), 1 if watched else 0,
                json.dumps([file_path], ensure_ascii=False),
            ))
            conn.commit()
            DISPLAY_STATE_CACHE.update(DB_FILE, norm_path, conn)
            invalidate_watched_paths_cache()
    except sqlite3.Error:
        LOGGER.exception("Nem sikerült menteni a megtekintési állapotot: %s", norm_path)


def set_playback_watched_many(entries, watched):
    """Sets the watched state for a series' episodes in one database transaction."""
    rows = []
    for entry in entries:
        file_path = entry.get("path") or ""
        normalized_path = normalize_media_path(file_path)
        if not normalized_path:
            continue
        rows.append((
            normalized_path, entry.get("media_title", ""), entry.get("episode_title", ""),
            entry.get("poster", ""), 0, 0, 1 if watched else 0,
            json.dumps([file_path], ensure_ascii=False),
        ))
    if not rows:
        return
    try:
        with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
            conn.executemany('''
                INSERT INTO playback_state
                    (file_path, media_title, episode_title, poster, is_movie,
                     last_played, watched, playlist_paths)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    media_title=excluded.media_title,
                    episode_title=excluded.episode_title,
                    poster=excluded.poster,
                    is_movie=excluded.is_movie,
                    watched=excluded.watched,
                    position=CASE WHEN excluded.watched = 0 THEN 0 ELSE playback_state.position END
            ''', rows)
            conn.commit()
        DISPLAY_STATE_CACHE.clear()
        invalidate_watched_paths_cache()
    except sqlite3.Error:
        LOGGER.exception("Nem sikerült menteni a sorozat epizódjainak megtekintési állapotát.")


class LibraryScannerThread(QThread):
    preview_ready = pyqtSignal(dict, bool)
    inventory_ready = pyqtSignal(object)
    pairings_notice = pyqtSignal(str)
    item_ready = pyqtSignal(dict, bool)   # (elem, film-e)
    scan_completed = pyqtSignal(list)     # hibák listája

    def __init__(self, movies_paths, shows_paths, custom_libraries=None, library_key=None,
                 manual_show_groups=None, force_remote_refresh=False):
        super().__init__()
        self.movies_paths = movies_paths if isinstance(movies_paths, list) else ([movies_paths] if movies_paths else [])
        self.shows_paths = shows_paths if isinstance(shows_paths, list) else ([shows_paths] if shows_paths else [])
        self.movies_paths = list(dict.fromkeys(source_router().canonical(path) for path in self.movies_paths))
        self.shows_paths = list(dict.fromkeys(source_router().canonical(path) for path in self.shows_paths))
        self.custom_libraries = list(custom_libraries or [])
        self.library_key = library_key
        self.force_remote_refresh = bool(force_remote_refresh)
        self._discovering = False
        self._inventory_pending = {}
        self._inventory_seen = set()
        self._inventory_previews = {}
        self._nfo_listings = {}
        self._nfo_hints = {}
        self._localized_display_info = {}
        self._display_title_failures = 0
        self._pair_root_listings = {}
        self.manual_show_groups = []
        self.manual_show_path_groups = {}
        self.manual_show_group_parts = {}
        for index, group in enumerate(manual_show_groups or []):
            if not isinstance(group, dict):
                continue
            group_id = str(group.get("id") or f"manual-{index}")
            title = str(group.get("title") or "").strip()
            group_library_id = str(group.get("library_id") or "")
            if self.library_key is not None and group_library_id and group_library_id != self.library_key:
                continue
            paths = [path for path in group.get("paths", [])
                     if isinstance(path, str) and path.strip()]
            if not title or not paths:
                continue
            snapshot = {
                "id": group_id, "title": title, "paths": list(paths),
                "library_id": group_library_id or None,
            }
            self.manual_show_groups.append(snapshot)
            self.manual_show_group_parts[group_id] = {
                "title": title, "paths": [], "entries": [], "manual_group_id": group_id,
                "added_at": 0.0,
            }
            for path in paths:
                self.manual_show_path_groups[normalize_media_path(path)] = group_id
        self.current_library_id = None
        self.current_scan_library_id = None
        self.failed_libraries = set()
        self.unattributed_scan_error = False
        self.metadata_failed_libraries = set()
        self.errors = []
        self.error_library_ids = {}
        self.excluded_paths = excluded_media_paths()
        self.tmdb_failures = 0
        self._tmdb_probe_at = 0.0
        self._deferred_metadata = {}
        self._retrying_metadata = False
        self._incomplete_metadata_libraries = set()
        self.last_error = ""
        self.poster_failures = 0
        self.remote_client = None
        self.seen_media_keys = set()
        # Map detected TV roots to the library whose scan discovered them so
        # cleanup warnings can be isolated to that library.
        self.detected_numbered_show_roots = set()
        self.parent_scanner = None
        self.directory_scan_token = ""
        self.directory_snapshot_library = None
        self.directory_snapshot_type = None
        self.directory_snapshot_rows = {}
        self.directory_snapshot_updates = {}
        self.cached_media_rows = {}
        self.cached_movie_rows_by_parent = {}
        self.manual_override_index = {}
        self.emitted_card_items = {}

    def isInterruptionRequested(self):
        """Also honor cancellation requested on the coordinating full scan."""
        parent = self.parent_scanner
        if parent is not None and parent.isInterruptionRequested():
            return True
        return super().isInterruptionRequested()

    def add_error(self, msg, library_id=None):
        safe_message = redact_credentials(msg)
        affected_library_id = library_id or self.current_scan_library_id
        if affected_library_id:
            self.failed_libraries.add(affected_library_id)
        else:
            self.unattributed_scan_error = True
        self.error_library_ids.setdefault(safe_message, set()).add(affected_library_id)
        if safe_message not in self.errors:
            self.errors.append(safe_message)

    def cleanup_stale_media_cache(self, conn, scanned_roots, full_scan):
        """A teljesen bejárt médiatárból eltűnt videók metaadatait és borítóit takarítja."""
        # Attributed failures are handled per library below. If the failing scope
        # is unknown, no root can be proven complete enough for stale-row cleanup.
        if self.unattributed_scan_error or self.isInterruptionRequested():
            return

        normalized_roots = [
            (normalize_media_path(path), 1 if is_movie else 0, library_id)
            for library_id, path, is_movie in scanned_roots if path
        ]
        normalized_roots = list(dict.fromkeys(
            (root, media_type, library_id)
            for root, media_type, library_id in normalized_roots if root
        ))
        # An empty root list can mean that configuration was temporarily unavailable;
        # it must never be interpreted as "everything in the cache is stale".
        if not normalized_roots:
            return
        try:
            rows = conn.execute("SELECT file_path, is_movie FROM media_cache").fetchall()
            safe_roots = []
            for root, root_type, library_id in normalized_roots:
                if library_id in self.failed_libraries:
                    continue
                cached_count = sum(
                    1 for path, media_type in rows
                    if (1 if bool(media_type) else 0) == root_type
                    and media_path_is_within(normalize_media_path(path), root)
                )
                seen_count = sum(
                    1 for path, media_type in self.seen_media_keys
                    if media_type == root_type and media_path_is_within(path, root)
                )
                suspiciously_small = (
                    cached_count > 0 and seen_count == 0
                ) or (
                    cached_count >= 5 and seen_count < cached_count * 0.2
                )
                if suspiciously_small and is_remote_path(root):
                    # NAS APIs can occasionally return a partial or empty directory listing
                    # without reporting an error. Preserve this root rather than mass-deleting
                    # its cache based on a suspiciously small result set.
                    message = (
                        f"A(z) {root} médiatár cache-e megmaradt, mert a beolvasás "
                        f"szokatlanul kevés elemet talált ({seen_count}/{cached_count})."
                    )
                    LOGGER.warning(message)
                    self.add_error(message, library_id=library_id)
                    continue
                safe_roots.append((root, root_type))

            failed_roots = [
                root for root, _root_type, library_id in normalized_roots
                if library_id in self.failed_libraries
            ]
            stale_paths = []
            for file_path, is_movie in rows:
                norm_path = normalize_media_path(file_path)
                media_type = 1 if bool(is_movie) else 0
                in_failed_scope = any(
                    media_path_is_within(norm_path, root) for root in failed_roots
                )
                in_configured_scope = any(
                    root_type == media_type and media_path_is_within(norm_path, root)
                    for root, root_type, _library_id in normalized_roots
                )
                in_scanned_scope = any(
                    root_type == media_type and media_path_is_within(norm_path, root)
                    for root, root_type in safe_roots
                )
                in_wrong_type_scanned_scope = any(
                    root_type != media_type and media_path_is_within(norm_path, root)
                    for root, root_type in safe_roots
                )
                if in_failed_scope:
                    continue
                if in_scanned_scope and (norm_path, media_type) not in self.seen_media_keys:
                    stale_paths.append((file_path,))
                elif in_wrong_type_scanned_scope and not in_scanned_scope:
                    # A library may have been reclassified (for example, an old
                    # custom show library was previously scanned as movies).
                    stale_paths.append((file_path,))
                elif full_scan and not in_configured_scope and not in_failed_scope:
                    stale_paths.append((file_path,))

            if stale_paths:
                conn.executemany("DELETE FROM media_cache WHERE file_path = ?", stale_paths)
                conn.commit()
            for warning in cleanup_orphaned_poster_files(conn):
                self.add_error(warning)
        except sqlite3.Error as exc:
            self.add_error(f"A fölösleges médiatár-cache takarítása nem sikerült: {exc}")

    def prepare_remote_incremental_scan(self, conn, library_id, roots):
        """Load the last remote directory snapshot and cached cards for this library."""
        self.directory_scan_token = uuid.uuid4().hex
        self.directory_snapshot_library = str(library_id or "")
        self.directory_snapshot_type = 1
        self.directory_snapshot_rows = {}
        self.directory_snapshot_updates = {}
        self.cached_media_rows = {}
        self.cached_movie_rows_by_parent = {}
        self.manual_override_index = {}
        normalized_roots = [normalize_media_path(root) for root in roots if root]
        try:
            for path, mtime, has_subdirs, video_count in conn.execute(
                "SELECT file_path, mtime, has_subdirs, video_count "
                "FROM scan_directory_cache WHERE library_id = ? AND is_movie = 1",
                (self.directory_snapshot_library,),
            ):
                normalized = normalize_media_path(path)
                if any(media_path_is_within(normalized, root) for root in normalized_roots):
                    self.directory_snapshot_rows[normalized] = (
                        float(mtime or 0), bool(has_subdirs), int(video_count or 0)
                    )

            for row in conn.execute(
                "SELECT file_path, tmdb_id, title, overview, poster_url, release_date, "
                "is_movie, file_mtime, status, signature FROM media_cache"
            ):
                path = normalize_media_path(row[0])
                if not any(media_path_is_within(path, root) for root in normalized_roots):
                    continue
                media_type = 1 if bool(row[6]) else 0
                cached = {
                    "file_path": path, "tmdb_id": int(row[1] or 0), "title": row[2] or "",
                    "overview": row[3] or "", "poster_url": row[4] or "",
                    "release_date": row[5] or "", "is_movie": media_type,
                    "file_mtime": float(row[7] or 0), "status": row[8] or "",
                    "signature": row[9] or "",
                }
                self.cached_media_rows[(path, media_type)] = cached
                if media_type:
                    parent = normalize_media_path(
                        REMOTE_PREFIX + posixpath.dirname(remote_real_path(path))
                    )
                    self.cached_movie_rows_by_parent.setdefault(parent, []).append(cached)

            for path, tmdb_id, custom_title, is_movie in conn.execute(
                "SELECT file_path, tmdb_id, custom_title, is_movie FROM manual_overrides"
            ):
                self.manual_override_index[(normalize_media_path(path), 1 if is_movie else 0)] = (
                    int(tmdb_id or 0), custom_title or ""
                )
        except sqlite3.Error as exc:
            self.add_error(f"Nem sikerült betölteni a NAS korábbi beolvasási állapotát: {exc}")

    def _cached_row_is_current(self, path, name, is_movie, row, file_mtime=None):
        if media_is_excluded(path, self.excluded_paths) or row is None or row["status"] != "success":
            return False
        flag = 1 if is_movie else 0
        override = self.manual_override_index.get((normalize_media_path(path), flag))
        if override and override[0] > 0:
            expected_signatures = {f"override:{override[0]}:{current_tmdb_language()}"}
        else:
            has_alias = not is_movie and bool(re.search(r"\([^()]+\)", name or ""))
            expected_signatures = {
                f"language:match_v185:{current_tmdb_language()}" + (":show_alias_v2" if has_alias else ""),
                (f"no_result:show_alias_v2:{current_tmdb_language()}" if has_alias
                 else f"no_result:language_fallback_v8:{current_tmdb_language()}"),
            }
        if is_movie and not override:
            directory = REMOTE_PREFIX + posixpath.dirname(remote_real_path(path))
            snapshot = self._snapshot_for_directory(directory)
            potential = movie_search_context(name, posixpath.basename(remote_real_path(directory)), True)
            if potential["from_folder"] and row["signature"] == f"language:match_v185:{current_tmdb_language()}":
                return False
            context = movie_search_context(name, posixpath.basename(remote_real_path(directory)), bool(snapshot and snapshot[2] == 1))
            expected_signatures = set(movie_lookup_signatures(context))
            if not movie_year_matches(row.get("release_date"), context["year"]):
                return False
        if row["signature"] not in expected_signatures:
            return False
        if is_movie and file_mtime is not None:
            try:
                if abs(row["file_mtime"] - float(file_mtime)) > 0.001:
                    return False
            except (TypeError, ValueError):
                return False
        return True

    def localized_cached_info(self, conn, path, media_id, is_movie, title, overview, poster_url, date):
        original = dict(id=media_id, title=title, overview=overview, poster_url=poster_url, date=date)
        if media_id <= 0:
            return original
        identity = (media_id, bool(is_movie), current_tmdb_language())
        if identity not in self._localized_display_info:
            payload, fresh = read_tmdb_metadata_cache(display_info_cache_key(media_id, is_movie))
            if not self.force_remote_refresh and isinstance(payload, dict):
                fresh = True  # Refresh existing metadata only when explicitly requested.
            if not fresh and self._display_title_failures >= 3:
                payload = None
            elif not fresh:
                try:
                    endpoint = "movie" if is_movie else "tv"
                    data = tmdb_request(f"{endpoint}/{media_id}", {"language": current_tmdb_language()})
                    payload = cache_localized_display_info(data, is_movie) if isinstance(data, dict) and data.get("id") == media_id else None
                    if payload is not None:
                        self._display_title_failures = 0
                except TmdbError:
                    self._display_title_failures += 1
                    # Keep usable cached data while offline; retry on the next scan.
                    payload = None
            self._localized_display_info[identity] = payload
        payload = self._localized_display_info[identity]
        if not isinstance(payload, dict):
            return original
        updated = dict(original)
        for field in ("title", "overview", "poster_url", "date"):
            if payload.get(field):
                updated[field] = payload[field]
        if updated != original:
            conn.execute("UPDATE media_cache SET title=?,overview=?,poster_url=?,release_date=? WHERE file_path=? AND tmdb_id=? AND is_movie=?",
                (updated["title"], updated["overview"], updated["poster_url"], updated["date"], normalize_media_path(path), media_id, int(bool(is_movie))))
            conn.commit()
        return updated

    def emit_cached_media_row(self, row, is_movie, added_at=None, episode_roots=None):
        if not row:
            return
        path = row["file_path"]
        title = row["title"]
        overview = row["overview"]
        tmdb_id = row["tmdb_id"]
        with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
            info = self.localized_cached_info(conn, path, tmdb_id, is_movie, title, overview, row["poster_url"], row["release_date"])
        poster = self.get_poster(info["poster_url"], tmdb_id, is_movie) if tmdb_id > 0 else None
        item = self.make_item(path, info["title"], info["overview"], poster, info["date"], tmdb_id)
        override = self.manual_override_index.get((normalize_media_path(path), int(bool(is_movie))))
        item["_pairing_token"] = (override[0], override[1], int(bool(is_movie))) if override else None
        item["added_at"] = float(added_at if added_at is not None else row["file_mtime"])
        if episode_roots:
            item["episode_roots"] = list(episode_roots)
        self.emit_item(item, is_movie)

    def _cached_rows_for_movie_directory(self, directory):
        remote_directory = directory if is_remote_path(directory) else REMOTE_PREFIX + directory
        key = normalize_media_path(remote_directory)
        rows = self.cached_movie_rows_by_parent.get(key, [])
        return [row for row in rows if self._cached_row_is_current(
            row["file_path"], posixpath.basename(remote_real_path(row["file_path"])), True, row
        )]

    def _snapshot_for_directory(self, directory):
        remote_path = directory if is_remote_path(directory) else REMOTE_PREFIX + directory
        return self.directory_snapshot_rows.get(normalize_media_path(remote_path))

    def _record_directory_snapshot(self, directory, mtime, has_subdirs, video_count):
        remote_path = directory if is_remote_path(directory) else REMOTE_PREFIX + directory
        path = normalize_media_path(remote_path)
        if not path or not self.directory_scan_token:
            return
        snapshot = (float(mtime or 0), bool(has_subdirs), int(video_count or 0))
        self.directory_snapshot_rows[path] = snapshot
        self.directory_snapshot_updates[path] = (
            self.directory_snapshot_library, 1, path, snapshot[0],
            1 if snapshot[1] else 0, snapshot[2], self.directory_scan_token,
        )

    def finish_remote_incremental_scan(self, conn, roots, error_count_at_start):
        """Persist/prune snapshots only after the entire library listing succeeded."""
        if (not self.directory_scan_token or self.isInterruptionRequested()
                or len(self.errors) > error_count_at_start):
            return
        try:
            if self.directory_snapshot_updates:
                conn.executemany("""
                    INSERT INTO scan_directory_cache
                        (library_id, is_movie, file_path, mtime, has_subdirs, video_count, scan_token)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(library_id, is_movie, file_path) DO UPDATE SET
                        mtime=excluded.mtime, has_subdirs=excluded.has_subdirs,
                        video_count=excluded.video_count, scan_token=excluded.scan_token
                """, list(self.directory_snapshot_updates.values()))
            conn.execute(
                "DELETE FROM scan_directory_cache WHERE library_id = ? AND is_movie = 1 AND scan_token <> ?",
                (self.directory_snapshot_library, self.directory_scan_token),
            )
            conn.commit()
        except sqlite3.Error as exc:
            with contextlib.suppress(sqlite3.Error):
                conn.rollback()
            self.add_error(f"A NAS-mappák beolvasási állapotát nem sikerült menteni: {exc}")

    def _try_skip_unchanged_remote_leaf(self, directory, directory_mtime):
        if self.force_remote_refresh or not directory_mtime or not self.directory_scan_token:
            return False
        snapshot = self._snapshot_for_directory(directory)
        if not snapshot:
            return False
        old_mtime, has_subdirs, video_count = snapshot
        if has_subdirs or old_mtime <= 0 or abs(old_mtime - float(directory_mtime)) > 0.001:
            return False
        remote_directory = directory if is_remote_path(directory) else REMOTE_PREFIX + directory
        normalized_directory = normalize_media_path(remote_directory)
        numbered_show = self.cached_media_rows.get((normalized_directory, 0))
        if numbered_show and self._cached_row_is_current(
            normalized_directory, posixpath.basename(remote_real_path(directory)), False, numbered_show
        ):
            self._record_directory_snapshot(directory, directory_mtime, False, video_count)
            self.emit_cached_media_row(
                numbered_show, False, directory_mtime, episode_roots=[REMOTE_PREFIX + remote_real_path(directory)]
            )
            self.detected_numbered_show_roots.add(
                (self.current_scan_library_id, normalized_directory)
            )
            return True
        if video_count == 0:
            has_cached_descendants = any(
                path != normalized_directory and media_path_is_within(path, normalized_directory)
                for path, _media_type in self.cached_media_rows
            ) or any(
                path != normalized_directory and media_path_is_within(path, normalized_directory)
                for path in self.directory_snapshot_rows
            )
            if has_cached_descendants:
                # Do not trust a successful but unexpectedly empty NAS response if
                # the previous snapshot still contains media beneath this folder.
                return False
            self._record_directory_snapshot(directory, directory_mtime, False, 0)
            return True
        cached_rows = self._cached_rows_for_movie_directory(directory)
        if len(cached_rows) != video_count:
            return False
        self._record_directory_snapshot(directory, directory_mtime, False, video_count)
        for row in cached_rows:
            if self.isInterruptionRequested():
                return True
            self.emit_cached_media_row(row, True, row["file_mtime"])
        return True

    def get_poster(self, url, media_id, is_movie):
        """Plakát letöltése; ha egymás után 3 sikertelen, a beolvasás hátralévő részében nem várunk többet
        (pl. kimaradt internetkapcsolatnál ne kelljen elemenként időkorlátot kivárni)."""
        if not media_id or media_id <= 0:
            return None
        media_type = "movie" if is_movie else "tv"
        cache_path = os.path.join(CACHE_DIR, f"{media_type}_{media_id}.jpg")
        if is_cached_file(cache_path):
            return cache_path
        if not url or self.poster_failures >= 3:
            return None
        poster = download_and_cache_poster(url, media_id, is_movie, self.isInterruptionRequested)
        if poster:
            self.poster_failures = 0
        elif not self.isInterruptionRequested():
            self.poster_failures += 1
        return poster

    def _configured_scan_groups(self):
        groups = []
        if self.library_key in (None, "movies"):
            groups.append(("movies", self.movies_paths, True))
        if self.library_key in (None, "shows"):
            groups.append(("shows", self.shows_paths, False))
        for library in self.custom_libraries:
            library_id = library.get("id")
            if self.library_key is None or self.library_key == library_id:
                groups.append((
                    library_id, configured_paths(f"custom:{library_id}"),
                    custom_library_is_movie(library),
                ))
        return groups

    def sync_portable_roots(self, conn, bases):
        for root in dict.fromkeys(bases):
            if self.isInterruptionRequested():
                return
            try:
                if is_remote_path(root):
                    if self.remote_client is None:
                        self.remote_client = RemoteNASClient(should_stop=self.isInterruptionRequested)
                    resolve_pending_cases(conn, root, self.remote_client, source_router())
                    listing = self.remote_client.list_folder(remote_real_path(root))
                    self._pair_root_listings[normalize_media_path(root)] = listing
                    backend = portable_pairs.NASBackend(root, self.remote_client, listing)
                else:
                    backend = portable_pairs.LocalBackend(root)
                stats = synchronize_portable_root(conn, root, backend, self.isInterruptionRequested,
                    all_roots=portable_roots(), verify=self.force_remote_refresh)
                if any(stats.get(key) for key in ("imported", "written", "pending", "invalid")):
                    self.pairings_notice.emit(portable_summary(stats))
            except InterruptedError:
                return
            except Exception:
                LOGGER.warning("A médiatári párosítások most nem szinkronizálhatók: %s", root)
                self.pairings_notice.emit(translate_text("A párosítás helyben mentve. A médiatári közös mentés nem sikerült; frissítéskor újrapróbálom."))

    def portable_remote_listing(self, path):
        key = normalize_media_path(REMOTE_PREFIX + path)
        if key in self._pair_root_listings:
            return self._pair_root_listings.pop(key)
        return self.remote_client.list_folder(path)

    def _scan_groups_serially(self, groups):
        scanned_roots = [
            (library_id, base, is_movie)
            for library_id, bases, is_movie in groups
            for base in bases
        ]
        with contextlib.closing(sqlite3.connect(DB_FILE, timeout=30)) as conn:
            for library_id, bases, is_movie in groups:
                self.current_scan_library_id = library_id
                self.current_library_id = library_id if library_id not in ("movies", "shows") else None
                group_error_count = len(self.errors)
                self.sync_portable_roots(conn, bases)
                self._begin_inventory(conn)
                remote_movie_roots = [base for base in bases if is_movie and is_remote_path(base)]
                if remote_movie_roots:
                    self.prepare_remote_incremental_scan(conn, library_id, remote_movie_roots)
                seen = set()
                for base in bases:
                    if self.isInterruptionRequested():
                        return
                    norm_base = normalize_media_path(base)
                    if norm_base in seen:
                        continue
                    seen.add(norm_base)
                    self.scan_folder(conn, base, is_movie)
                if remote_movie_roots and not self.isInterruptionRequested():
                    self.finish_remote_incremental_scan(conn, remote_movie_roots, group_error_count)
                self.emit_manual_show_groups(conn)
                self._finish_inventory(conn, group_error_count)
                self.retry_deferred_metadata(conn)
            self.current_library_id = None
            self.current_scan_library_id = None
            scanned_roots.extend(
                (library_id, path, False)
                for library_id, path in self.detected_numbered_show_roots
            )
            self.cleanup_stale_media_cache(conn, scanned_roots, self.library_key is None)

    def _scan_one_library_group(self, library_id, bases, is_movie):
        """Scan one library with an independent DB connection and network session."""
        self.current_scan_library_id = library_id
        self.current_library_id = library_id if library_id not in ("movies", "shows") else None
        seen = set()
        group_error_count = len(self.errors)
        try:
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=30)) as conn:
                self.sync_portable_roots(conn, bases)
                self._begin_inventory(conn)
                remote_movie_roots = [base for base in bases if is_movie and is_remote_path(base)]
                if remote_movie_roots:
                    self.prepare_remote_incremental_scan(conn, library_id, remote_movie_roots)
                for base in bases:
                    if self.isInterruptionRequested():
                        break
                    norm_base = normalize_media_path(base)
                    if norm_base in seen:
                        continue
                    seen.add(norm_base)
                    self.scan_folder(conn, base, is_movie)
                if not self.isInterruptionRequested():
                    self.emit_manual_show_groups(conn)
                    self._finish_inventory(conn, group_error_count)
                    self.retry_deferred_metadata(conn)
                if remote_movie_roots and not self.isInterruptionRequested():
                    self.finish_remote_incremental_scan(conn, remote_movie_roots, group_error_count)
        except sqlite3.Error as exc:
            LOGGER.exception("Adatbázishiba a(z) %s médiatár párhuzamos beolvasásakor.", library_id)
            self.add_error(f"Adatbázis hiba beolvasás közben: {exc}")
        except Exception as exc:
            LOGGER.exception("Váratlan hiba a(z) %s médiatár párhuzamos beolvasásakor.", library_id)
            self.add_error(f"Váratlan hiba beolvasás közben: {exc}")
        finally:
            if self.remote_client is not None:
                try:
                    self.remote_client.close()
                except Exception as exc:
                    LOGGER.exception("Nem sikerült lezárni a NAS-kapcsolatot a beolvasás után.")
                    self.add_error(f"Nem sikerült lezárni a NAS-kapcsolatot: {exc}")
                self.remote_client = None

    def _scan_all_libraries_in_parallel(self, groups):
        workers = []
        worker_limit = min(4, len(groups))
        with ThreadPoolExecutor(max_workers=worker_limit, thread_name_prefix="SynoLibrary") as pool:
            futures = {}
            for library_id, bases, is_movie in groups:
                worker = LibraryScannerThread(
                    [], [], library_key=library_id,
                    manual_show_groups=self.manual_show_groups,
                    force_remote_refresh=self.force_remote_refresh,
                )
                worker.parent_scanner = self
                worker.preview_ready.connect(self.preview_ready)
                worker.inventory_ready.connect(self.inventory_ready)
                worker.item_ready.connect(self.item_ready)
                worker.pairings_notice.connect(self.pairings_notice)
                workers.append(worker)
                futures[pool.submit(worker._scan_one_library_group, library_id, bases, is_movie)] = worker

            for future in as_completed(futures):
                worker = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    LOGGER.exception("Nem sikerült beolvasni az egyik párhuzamos médiatárat.")
                    worker.add_error(f"Váratlan hiba beolvasás közben: {exc}")
                for error in worker.errors:
                    safe_message = redact_credentials(error)
                    if safe_message not in self.errors:
                        self.errors.append(safe_message)
                    self.error_library_ids.setdefault(safe_message, set()).update(
                        worker.error_library_ids.get(error, {None})
                    )
                self.failed_libraries.update(worker.failed_libraries)
                self.unattributed_scan_error = (
                    self.unattributed_scan_error or worker.unattributed_scan_error
                )
                self.metadata_failed_libraries.update(worker.metadata_failed_libraries)
                self.seen_media_keys.update(worker.seen_media_keys)
                self.detected_numbered_show_roots.update(worker.detected_numbered_show_roots)
                for library_id, items in worker.emitted_card_items.items():
                    self.emitted_card_items.setdefault(library_id, []).extend(items)

        if self.isInterruptionRequested():
            return
        scanned_roots = [
            (library_id, base, is_movie)
            for library_id, bases, is_movie in groups
            for base in bases
        ]
        scanned_roots.extend(
            (library_id, path, False)
            for library_id, path in self.detected_numbered_show_roots
        )
        try:
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=30)) as conn:
                self.cleanup_stale_media_cache(conn, scanned_roots, full_scan=True)
        except sqlite3.Error as exc:
            LOGGER.exception("Nem sikerült a párhuzamos beolvasás utáni cache-karbantartás.")
            self.add_error(f"A fölösleges médiatár-cache takarítása nem sikerült: {exc}")

    def run(self):
        try:
            groups = self._configured_scan_groups()
            if self.library_key is None and len(groups) > 1:
                self._scan_all_libraries_in_parallel(groups)
            else:
                self._scan_groups_serially(groups)
            if not self.isInterruptionRequested():
                self.persist_card_cache(groups)
        except sqlite3.Error as exc:
            LOGGER.exception("Adatbázishiba a médiatár beolvasásakor.")
            self.add_error(f"Adatbázis hiba beolvasás közben: {exc}")
        except Exception as exc:
            LOGGER.exception("Váratlan hiba a médiatár beolvasásakor.")
            self.add_error(f"Váratlan hiba beolvasás közben: {exc}")
        finally:
            if self.remote_client is not None:
                try:
                    self.remote_client.close()
                except Exception as exc:
                    LOGGER.exception("Nem sikerült lezárni a NAS-kapcsolatot a beolvasás után.")
                    self.add_error(f"Nem sikerült lezárni a NAS-kapcsolatot: {exc}")
                self.remote_client = None
            if not self.isInterruptionRequested():
                self.scan_completed.emit(self.errors)

    def retry_deferred_metadata(self, conn):
        if not self._deferred_metadata or self.isInterruptionRequested():
            return
        saved = (self.current_scan_library_id, self.current_library_id)
        pending = list(self._deferred_metadata.items())
        if self.tmdb_failures >= 3:
            while time.monotonic() < self._tmdb_probe_at:
                if self.isInterruptionRequested():
                    return
                self.msleep(50)
        original_counts = {library: len(values) for library, values in self.emitted_card_items.items()}
        previous_items = {}
        for values in self.emitted_card_items.values():
            for old in values:
                previous_items.setdefault(normalize_media_path(old.get("file_path", "")), old)
        replaced_paths = set()
        self._retrying_metadata = True
        try:
            for key, (entry, movie, library, custom) in pending:
                if self.isInterruptionRequested():
                    break
                self.current_scan_library_id, self.current_library_id = library, custom
                if media_is_excluded(entry.path, self.excluded_paths):
                    self._deferred_metadata.pop(key, None)
                    continue
                self.tmdb_failures = 0
                item = self.process_media_item(entry, movie, conn)
                if key in self._deferred_metadata:
                    break  # Still offline: one probe, never replay the entire queue.
                previous = previous_items.get(key[0])
                if previous:
                    for field in ("episode_roots", "manual_group_id", "added_at"):
                        if field in previous:
                            item[field] = previous[field]
                replaced_paths.add(key[0])
                self.emit_item(item, movie)
            for library in {value[2] for _key, value in pending}:
                if (library not in self._incomplete_metadata_libraries
                        and not any(value[2] == library for value in self._deferred_metadata.values())):
                    self.metadata_failed_libraries.discard(library)
        finally:
            # Keep only the replacements for processed paths; unprocessed originals survive.
            for library, values in self.emitted_card_items.items():
                original_count = original_counts.get(library, 0)
                values[:] = [old for index, old in enumerate(values)
                             if index >= original_count or normalize_media_path(old.get("file_path", "")) not in replaced_paths]
            self._retrying_metadata = False
            self.current_scan_library_id, self.current_library_id = saved

    def persist_card_cache(self, groups):
        """Save complete card snapshots so another library can show its last scan immediately."""
        library_ids = list(dict.fromkeys(str(library_id) for library_id, _bases, _is_movie in groups))
        if self.unattributed_scan_error or (self.errors and not self.failed_libraries and not self.error_library_ids):
            # Global cleanup warnings are not attributable to one library;
            # preserve snapshots rather than replacing them from an uncertain scan.
            return
        try:
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=30)) as conn:
                conn.execute("BEGIN IMMEDIATE")
                for library_id in library_ids:
                    if library_id in self.failed_libraries or library_id in self.metadata_failed_libraries:
                        continue
                    items = self.emitted_card_items.get(library_id, [])
                    rows = []
                    seen_paths = set()
                    for item in items:
                        if not pairing_item_is_current(conn, item):
                            current = conn.execute(
                                "SELECT payload FROM library_card_cache WHERE library_id=? AND file_path=?",
                                (library_id, normalize_media_path(item.get("file_path", ""))),
                            ).fetchone()
                            if not current:
                                continue
                            item = json.loads(current[0])
                            if not pairing_item_is_current(conn, item):
                                continue
                        path = normalize_media_path(item.get("file_path", ""))
                        if not path or path in seen_paths:
                            continue
                        seen_paths.add(path)
                        rows.append((library_id, path, json.dumps(item, ensure_ascii=False)))
                    conn.execute("DELETE FROM library_card_cache WHERE library_id = ?", (library_id,))
                    if rows:
                        conn.executemany(
                            "INSERT INTO library_card_cache (library_id, file_path, payload) VALUES (?, ?, ?)",
                            rows,
                        )
                conn.commit()
        except (OSError, sqlite3.Error, TypeError, ValueError):
            LOGGER.exception("Nem sikerült elmenteni a műsortárak kártya-gyorsítótárát.")

    def emit_manual_show_groups(self, conn):
        for group in self.manual_show_group_parts.values():
            if self.isInterruptionRequested():
                return
            paths = group["paths"]
            if not paths:
                continue
            configured = next((g["paths"] for g in self.manual_show_groups if g["id"] == group["manual_group_id"]), [])
            order = {normalize_media_path(path): index for index, path in enumerate(configured)}
            paths = sorted(paths, key=lambda path: order.get(normalize_media_path(path), len(order)))
            representative = SimpleNamespace(
                path=paths[0], name=group["title"], stat=lambda: SimpleNamespace(st_mtime=0)
            )
            try:
                item = self.process_media_item(representative, False, conn)
            except sqlite3.Error as exc:
                with contextlib.suppress(sqlite3.Error):
                    conn.rollback()
                self.add_error(f"Adatbázis hiba ({group['title']}): {exc}")
                item = self.make_item(paths[0], group["title"], "")
            item["episode_roots"] = paths
            item["manual_group_id"] = group["manual_group_id"]
            item["added_at"] = group.get("added_at", 0.0)
            self.emit_item(item, False)
            group["paths"] = []

    def scan_folder(self, conn, base, is_movie):
        if media_is_excluded(base, self.excluded_paths):
            return
        label = "Film" if is_movie else "TV műsorok"
        if not base:
            return
        if is_remote_path(base):
            self.scan_remote_folder(conn, base, is_movie, label)
            return
        # Filmeknél rekurzívan bejárjuk az almappákat is; TV műsoroknál a kiválasztott
        # gyökér közvetlen almappái a műsorok, azok epizódjait a részletező keresi.
        if is_movie:
            def on_walk_error(error):
                failed_path = getattr(error, "filename", None) or base
                self.add_error(f"A(z) {label} mappa nem érhető el: {failed_path} ({error})")

            try:
                for root, dirs, files in os.walk(base, onerror=on_walk_error):
                    if self.isInterruptionRequested():
                        return
                    dirs[:] = sorted((d for d in dirs if not is_ignored(d) and not media_is_excluded(os.path.join(root, d), self.excluded_paths)), key=natural_sort_key)
                    files = [name for name in files if not media_is_excluded(os.path.join(root, name), self.excluded_paths)]
                    self._nfo_listings[normalize_media_path(root)] = [
                        {"name": filename, "isdir": False} for filename in files]
                    if self._is_numbered_show_folder(root, files):
                        self.emit_numbered_show_folder(conn, root)
                        self.detected_numbered_show_roots.add(
                            (self.current_scan_library_id, normalize_media_path(root))
                        )
                        # The show card owns the whole folder; its episode files
                        # must not also appear as separate movie cards.
                        dirs[:] = []
                        continue
                    for filename in sorted(files, key=natural_sort_key):
                        if self.isInterruptionRequested():
                            return
                        if is_ignored(filename) or not filename.lower().endswith(VIDEO_EXTENSIONS):
                            continue
                        full_path = os.path.join(root, filename)
                        entry = SimpleNamespace(path=full_path, name=filename, stat=lambda fp=full_path: os.stat(fp))
                        try:
                            item = self.process_media_item(entry, True, conn)
                        except (sqlite3.Error, OSError) as exc:
                            if isinstance(exc, sqlite3.Error):
                                with contextlib.suppress(sqlite3.Error):
                                    conn.rollback()
                            self.add_error(f"Beolvasási hiba ({filename}): {exc}")
                            item = self.make_item(full_path, filename, "")
                        self.emit_item(item, True)
            except OSError as e:
                self.add_error(f"A(z) {label} mappa nem érhető el: {base} ({e})")
            return

        try:
            with os.scandir(base) as it:
                entries = [e for e in it if not is_ignored(e.name)]
        except OSError as e:
            self.add_error(f"A(z) {label} mappa nem érhető el: {base} ({e})")
            return
        entries.sort(key=lambda e: natural_sort_key(e.name))
        self._emit_show_entries(entries, conn, remote=False)

    @staticmethod
    def _is_numbered_show_folder(folder, filenames):
        """Recognize a series folder with several directly numbered videos."""
        folder_name = os.path.basename(os.path.normpath(folder))
        normalized_folder = normalize_title(folder_name)
        if not folder_name or normalized_folder in {
            "movie", "movies", "film", "films", "filmek", "video", "videos",
            "media", "movies library", "tv", "tv shows", "shows", "sorozatok",
            "műsorok", "musorok",
        }:
            return False
        if re.search(r"(?i)(?:^|[\W_])(?:season|évad|evad|saison|temporada|сезон)[\W_]*\d+", folder_name):
            return False

        videos = [
            name for name in filenames
            if not is_ignored(name) and name.lower().endswith(VIDEO_EXTENSIONS)
        ]
        if len(videos) < 2:
            return False

        episode_prefix = re.compile(
            r"(?i)^(?:S\s*\d{1,2}\s*E\s*\d{1,4}|E\s*\d{2,5}|"
            r"EP(?:ISODE)?\s*\d{1,4}|\d{1,4})(?=$|[ ._-])"
        )
        positions = []
        for name in videos:
            stem = os.path.splitext(name)[0]
            if not episode_prefix.match(stem):
                continue
            _season, episode, explicit = parse_episode_position(name)
            if explicit and episode is not None:
                positions.append((_season, episode))

        return (
            len(positions) >= 2
            and len(set(positions)) == len(positions)
            and len(positions) * 4 >= len(videos) * 3
        )

    def emit_numbered_show_folder(self, conn, folder, remote=False):
        """Emit one TV-series item for a folder of numbered episode files."""
        if remote:
            folder_name = posixpath.basename(remote_real_path(folder).rstrip("/"))
            folder_mtime = 0.0
        else:
            folder_name = os.path.basename(os.path.normpath(folder))
            try:
                folder_mtime = os.stat(folder).st_mtime
            except OSError:
                folder_mtime = 0.0
        group_id = self.manual_show_path_groups.get(normalize_media_path(folder))
        if group_id:
            group = self.manual_show_group_parts[group_id]
            if folder not in group["paths"]:
                group["paths"].append(folder)
            group["added_at"] = max(group.get("added_at", 0), folder_mtime)
            return
        entry = SimpleNamespace(
            path=folder,
            name=folder_name,
            stat=lambda mt=folder_mtime: SimpleNamespace(st_mtime=mt),
        )
        try:
            item = self.process_media_item(entry, False, conn)
        except sqlite3.Error as exc:
            with contextlib.suppress(sqlite3.Error):
                conn.rollback()
            self.add_error(f"Adatbázis hiba ({folder_name}): {exc}")
            item = self.make_item(folder, folder_name, "")
        item["episode_roots"] = [folder]
        item["added_at"] = folder_mtime
        self.emit_item(item, False)

    @staticmethod
    def _episode_group_marker(name):
        # A gyakori angol, magyar, francia, spanyol és orosz évadjelölések,
        # zárójelek között is (pl. „Sorozat [S01]”, „Sorozat (Season 1)”).
        patterns = (
            r"(?i)(?:^|[\W_])S\d{1,2}(?:[\W_]*E\d{1,3})?(?=$|[\W_])",
            r"(?i)(?:^|[\W_])E0*\d{3,5}(?:[\W_]*[-–][\W_]*E?0*\d{3,5})?(?=$|[\W_])",
            r"(?i)(?:^|[\W_])\d{1,2}x\d{1,3}(?=$|[\W_])",
            r"(?i)(?:^|[\W_])(?:season|évad|evad|saison|temporada|сезон)[\W_]*\d{1,3}(?=$|[\W_])",
            r"(?i)(?:^|[\W_])\d{1,3}\.?[\W_]*(?:season|évad|evad|saison|temporada|сезон)(?=$|[\W_])",
            r"(?i)(?:^|[\W_])\d{1,4}\.?[\W_]*(?:rész|resz|epizód|epizod)(?=$|[\W_])",
            r"(?i)(?:^|[\W_])[-–]\s*\d{1,3}(?=$|[\W_])",
            r"(?i)(?:19|20)\d{2}[-._ ](?:0?[1-9]|1[0-2])[-._ ](?:0?[1-9]|[12]\d|3[01])(?=$|[\W_])",
            r"(?i)(?:19|20)\d{6}(?=$|[\W_])",
            r"(?i)(?:0?[1-9]|1[0-2])[-._ ](?:0?[1-9]|[12]\d|3[01])[-._ ](?:19|20)\d{2}(?=$|[\W_])",
        )
        matches = [re.search(pattern, name) for pattern in patterns]
        return min((match for match in matches if match), key=lambda match: match.start(), default=None)

    @staticmethod
    def _episode_group_title(name):
        """Sorozatcím becslése többféle évadjelölésből, a jelölés előtt vagy után álló cím támogatásával."""
        stem = name  # Mappanév: a pont utáni S01 jelölés nem fájlkiterjesztés.
        marker = LibraryScannerThread._episode_group_marker(stem)
        if marker:
            # Kezeli a „Sorozat Season 1” és a „Season 1 - Sorozat” formát is.
            before = stem[:marker.start()].strip(" ._-[](){}")
            after = stem[marker.end():].strip(" ._-[](){}")
            stem = before or after
        title, _year = clean_name(stem, is_file=False)
        return title.strip(" ._-[](){}")

    def _emit_show_entries(self, entries, conn, remote=False, real_base=None):
        """Normál sorozatmappákat megtart, az epizódonként elnevezett mappákat csoportosítja."""
        groups = {}
        ordinary = []
        for entry in entries:
            if self.isInterruptionRequested(): return
            name = entry.get("name", "") if remote else entry.name
            is_dir = bool(entry.get("isdir")) if remote else entry.is_dir()
            if not is_dir: continue
            path = (REMOTE_PREFIX + (entry.get("path") or real_base.rstrip("/") + "/" + name)) if remote else entry.path
            if media_is_excluded(path, self.excluded_paths):
                continue
            if remote:
                add_info = entry.get("additional") or {}
                time_info = add_info.get("time") or {}
                entry_mtime = float(time_info.get("mtime", 0) or 0)
            else:
                try:
                    entry_mtime = entry.stat().st_mtime
                except OSError:
                    entry_mtime = 0.0
            manual_group_id = self.manual_show_path_groups.get(normalize_media_path(path))
            if manual_group_id:
                group = self.manual_show_group_parts[manual_group_id]
                path_key = normalize_media_path(path)
                if path_key not in {normalize_media_path(existing) for existing in group["paths"]}:
                    group["paths"].append(path)
                    group["entries"].append(entry)
                    group["added_at"] = max(group.get("added_at", 0.0), entry_mtime)
                continue
            title = self._episode_group_title(name)
            # Csak egyértelmű epizód-/évadjelölés esetén vonjuk össze a mappákat.
            marked = bool(self._episode_group_marker(name))
            if marked and title:
                group = groups.setdefault(title.casefold(), {
                    "title": title, "paths": [], "entries": [], "added_at": 0.0
                })
                group["paths"].append(path)
                group["entries"].append(entry)
                group["added_at"] = max(group["added_at"], entry_mtime)
            else:
                ordinary.append((entry, path, entry_mtime))
        for entry, path, entry_mtime in ordinary:
            name = entry.get("name", "") if remote else entry.name
            if remote:
                add_info = entry.get("additional") or {}
                time_info = add_info.get("time") or {}
                mtime = float(time_info.get("mtime", 0) or 0)
                media_entry = SimpleNamespace(path=path, name=name, stat=lambda mt=mtime: SimpleNamespace(st_mtime=mt))
            else:
                media_entry = SimpleNamespace(
                    path=path, name=name,
                    stat=lambda mt=entry_mtime: SimpleNamespace(st_mtime=mt),
                )
            try:
                item = self.process_media_item(media_entry, False, conn)
            except sqlite3.Error as exc:
                with contextlib.suppress(sqlite3.Error): conn.rollback()
                self.add_error(f"Adatbázis hiba ({name}): {exc}")
                item = self.make_item(path, name, "")
            item["added_at"] = entry_mtime
            self.emit_item(item, False)
        for group in groups.values():
            if self.isInterruptionRequested(): return
            paths = group["paths"]
            # A TMDB-kereséshez tisztított csoportcímet használjuk; a részletező minden mappát bejár.
            representative = group["entries"][0]
            if remote:
                representative = SimpleNamespace(path=paths[0], name=group["title"], stat=lambda: SimpleNamespace(st_mtime=0))
            else:
                representative = SimpleNamespace(path=paths[0], name=group["title"], stat=lambda: SimpleNamespace(st_mtime=0))
            try:
                item = self.process_media_item(representative, False, conn)
            except sqlite3.Error as exc:
                with contextlib.suppress(sqlite3.Error): conn.rollback()
                self.add_error(f"Adatbázis hiba ({group['title']}): {exc}")
                item = self.make_item(paths[0], group["title"], "")
            item["episode_roots"] = paths
            item["added_at"] = group["added_at"]
            self.emit_item(item, False)

    def scan_remote_folder(self, conn, base, is_movie, label):
        try:
            if self.remote_client is None:
                self.remote_client = RemoteNASClient(should_stop=self.isInterruptionRequested)
            real_base = remote_real_path(base)
        except Exception as exc:
            self.add_error(f"A távoli {label} mappa nem olvasható: {base} ({exc})")
            return

        # Filmeknél a NAS-mappa teljes fáját bejárjuk, nem csak a gyökérben lévő fájlokat.
        # TV műsoroknál továbbra is a gyökér közvetlen könyvtárai jelennek meg.
        if not is_movie:
            try:
                entries = self.portable_remote_listing(real_base)
                self._nfo_listings[normalize_media_path(base)] = entries
                entries = [e for e in entries if not is_ignored(e.get("name", ""))]
                entries.sort(key=lambda e: natural_sort_key(e.get("name", "")))
                self._emit_show_entries(entries, conn, remote=True, real_base=real_base)
            except Exception as exc:
                self.add_error(f"A távoli TV műsorok mappa nem olvasható: {real_base} ({exc})")
            return

        pending = deque([(real_base, 0.0)])
        visited_directories = set()
        while pending:
            if self.isInterruptionRequested():
                return
            current, current_mtime = pending.popleft()
            normalized_current = normalize_media_path(REMOTE_PREFIX + current)
            if normalized_current in visited_directories:
                continue
            visited_directories.add(normalized_current)
            if current != real_base and self._try_skip_unchanged_remote_leaf(current, current_mtime):
                continue
            try:
                entries = self.portable_remote_listing(current)
            except Exception as exc:
                self.add_error(f"A távoli mappa nem olvasható: {current} ({exc})")
                continue
            self._nfo_listings[normalize_media_path(REMOTE_PREFIX + current)] = entries
            entries = [e for e in entries if not is_ignored(e.get("name", "")) and not media_is_excluded(REMOTE_PREFIX + (e.get("path") or current.rstrip("/") + "/" + e.get("name", "")), self.excluded_paths)]
            entries.sort(key=lambda e: (-float(((e.get("additional") or {}).get("time") or {}).get("mtime",0) or 0), natural_sort_key(e.get("name", ""))))
            directories = [entry for entry in entries if entry.get("isdir")]
            direct_videos = [
                entry for entry in entries
                if not entry.get("isdir")
                and entry.get("name", "").lower().endswith(VIDEO_EXTENSIONS)
            ]
            self._record_directory_snapshot(current, current_mtime, bool(directories), len(direct_videos))
            if self._is_numbered_show_folder(
                current,
                [entry.get("name", "") for entry in direct_videos],
            ):
                show_path = REMOTE_PREFIX + current
                self.emit_numbered_show_folder(conn, show_path, remote=True)
                self.detected_numbered_show_roots.add(
                    (self.current_scan_library_id, normalize_media_path(show_path))
                )
                continue
            for remote_entry in entries:
                if self.isInterruptionRequested():
                    return
                name = remote_entry.get("name", "")
                if not name:
                    continue
                is_dir = bool(remote_entry.get("isdir"))
                remote_path = remote_entry.get("path") or (current.rstrip("/") + "/" + name)
                add_info = remote_entry.get("additional") or {}
                time_info = add_info.get("time") or {}
                mtime = float(time_info.get("mtime", 0) or 0)
                if is_movie and is_dir:
                    pending.append((remote_path, mtime))
                    continue
                if is_movie:
                    if is_dir or not name.lower().endswith(VIDEO_EXTENSIONS):
                        continue
                    wanted_movie = True
                else:
                    # A TV műsorok gyökérmappájának közvetlen almappái jelenjenek meg a listában.
                    if current != real_base or not is_dir:
                        continue
                    wanted_movie = False
                path = REMOTE_PREFIX + remote_path
                cached = self.cached_media_rows.get((normalize_media_path(path), 1))
                if (wanted_movie and self._cached_row_is_current(
                        path, name, True, cached, file_mtime=mtime)):
                    self.emit_cached_media_row(cached, True, mtime)
                    continue
                entry = SimpleNamespace(path=path, name=name, stat=lambda mt=mtime: SimpleNamespace(st_mtime=mt))
                try:
                    item = self.process_media_item(entry, wanted_movie, conn)
                except sqlite3.Error as exc:
                    with contextlib.suppress(sqlite3.Error):
                        conn.rollback()
                    self.add_error(f"Adatbázis hiba ({name}): {exc}")
                    item = self.make_item(path, name, "")
                item["added_at"] = mtime
                self.emit_item(item, wanted_movie)

    def emit_item(self, item, is_movie):
        if self._discovering:
            for path in item.get('episode_roots') or [item.get('file_path', '')]:
                if path: self._inventory_seen.add(normalize_media_path(path))
        if item.pop('_inventory_preview', False):
            if media_is_excluded(item.get('file_path',''), self.excluded_paths): return
            item['is_movie'] = bool(is_movie)
            item['library_id'] = self.current_scan_library_id
            item['_scan_library_id'] = self.current_scan_library_id
            self._inventory_previews[(normalize_media_path(item['file_path']), bool(is_movie))] = dict(item)
            self.preview_ready.emit(item, is_movie)
            return
        if media_is_excluded(item.get("file_path", ""), self.excluded_paths):
            return
        norm_path = normalize_media_path(item.get("file_path", ""))
        if norm_path:
            self.seen_media_keys.add((norm_path, 1 if is_movie else 0))
        # Persist the type BEFORE copying the snapshot. The GUI later adding
        # this field cannot update the scanner's already copied card records.
        item["is_movie"] = bool(is_movie)
        if self.current_scan_library_id:
            item["_scan_library_id"] = self.current_scan_library_id
            item["library_id"] = self.current_scan_library_id
            self.emitted_card_items.setdefault(self.current_scan_library_id, []).append(dict(item))
        else:
            scan_library_id = "movies" if is_movie else "shows"
            item["_scan_library_id"] = scan_library_id
            self.emitted_card_items.setdefault(scan_library_id, []).append(dict(item))
        self.item_ready.emit(item, is_movie)

    @staticmethod
    def make_item(path, title, overview, poster=None, date="", media_id=-1):
        return {
            "file_path": path, "title": title, "overview": overview,
            "poster": poster, "date": date, "id": media_id,
        }

    def negative_cache_is_fresh(self, conn, path):
        if self.force_remote_refresh:
            return False
        row = conn.execute("SELECT lookup_at FROM media_cache WHERE file_path=?", (normalize_media_path(path),)).fetchone()
        age = time.time() - float(row[0] or 0) if row else -1
        return 0 <= age < 24 * 60 * 60

    @staticmethod
    def save_cache(conn, norm_path, flag, tmdb_id, title, overview, poster_url,
                   date, mtime, status, signature, *, pairing_token=PAIRING_TOKEN_UNSET):
        with conn:
            if pairing_token is not PAIRING_TOKEN_UNSET:
                if not conn.in_transaction:
                    conn.execute("BEGIN IMMEDIATE")
                if read_pairing_token(conn, norm_path) != pairing_token:
                    return False
            conn.execute('''
                INSERT OR REPLACE INTO media_cache
                (file_path, tmdb_id, title, overview, poster_url, release_date,
                 is_movie, file_mtime, status, signature, lookup_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (norm_path, tmdb_id, title, overview, poster_url, date, flag, mtime, status, signature, time.time()))
        return True

    def movie_name_context(self, full_path, filename):
        if is_sample_video(filename):
            return movie_search_context(filename)
        remote = is_remote_path(full_path)
        folder = REMOTE_PREFIX + posixpath.dirname(remote_real_path(full_path)) if remote else os.path.dirname(full_path)
        folder_name = posixpath.basename(remote_real_path(folder)) if remote else os.path.basename(folder)
        # Only list when a folder name can improve the search.
        candidate = movie_search_context(filename, folder_name, True)
        if not candidate["from_folder"]:
            return candidate
        try:
            key = normalize_media_path(folder)
            if key not in self._nfo_listings:
                if remote:
                    if self.remote_client is None:
                        return movie_search_context(filename)
                    self._nfo_listings[key] = self.remote_client.list_folder(remote_real_path(folder))
                else:
                    with os.scandir(folder) as entries:
                        self._nfo_listings[key] = [{"name": entry.name, "isdir": entry.is_dir()} for entry in entries]
            def allowed(item):
                path = folder.rstrip("/") + "/" + item.get("name", "") if remote else os.path.join(folder, item.get("name", ""))
                return not media_is_excluded(path, self.excluded_paths)
            count = sum(allowed(item) and not item.get("isdir") and not is_ignored(item.get("name", "")) and not is_sample_video(item.get("name", ""))
                        and item.get("name", "").lower().endswith(VIDEO_EXTENSIONS)
                        for item in self._nfo_listings[key])
            return movie_search_context(filename, folder_name, count == 1)
        except Exception:
            LOGGER.debug("A film mappanév-környezete nem olvasható: %s", full_path, exc_info=True)
            return movie_search_context(filename)

    def read_nfo_hint(self, full_path, name, is_movie):
        """Read only a confidently associated sidecar, with bounded NAS/local IO."""
        if is_movie and is_sample_video(name):
            return {}
        folder = (REMOTE_PREFIX + posixpath.dirname(remote_real_path(full_path))
                  if is_remote_path(full_path) and is_movie else
                  full_path if not is_movie else os.path.dirname(full_path))
        key = (normalize_media_path(full_path), bool(is_movie))
        if key in self._nfo_hints:
            return self._nfo_hints[key]
        hint = {}
        try:
            if self.isInterruptionRequested():
                return {}
            folder_key = normalize_media_path(folder)
            if folder_key not in self._nfo_listings:
                if is_remote_path(folder):
                    if self.remote_client is None:
                        return {}
                    entries = self.remote_client.list_folder(remote_real_path(folder))
                    self._nfo_listings[folder_key] = entries
                else:
                    with os.scandir(folder) as items:
                        self._nfo_listings[folder_key] = [
                            {"name": item.name, "isdir": item.is_dir()} for item in items]
            entries = self._nfo_listings[folder_key]
            files = [item for item in entries if not item.get("isdir") and not media_is_excluded(folder.rstrip("/") + "/" + item.get("name", "") if is_remote_path(folder) else os.path.join(folder, item.get("name", "")), self.excluded_paths)]
            video_count = sum(item.get("name", "").lower().endswith(VIDEO_EXTENSIONS) and not is_ignored(item.get("name", "")) and not is_sample_video(item.get("name", "")) for item in files)
            selected = select_nfo_names([item.get("name", "") for item in files], name, is_movie, video_count)
            if selected:
                filename = selected[0]
                cache_key = None
                if not self.force_remote_refresh:
                    if is_remote_path(folder):
                        info = next(item for item in files if item.get("name") == filename)
                        additional = info.get("additional") or {}
                        stamp = (additional.get("time") or {}).get("mtime", 0)
                        size = additional.get("size", info.get("size", 0))
                    else:
                        info = os.stat(os.path.join(folder, filename))
                        stamp, size = info.st_mtime_ns, info.st_size
                    if isinstance(stamp, (int, float)) and stamp > 0:
                        identity = (folder_key, filename, stamp, size, bool(is_movie))
                        cache_key = "nfo-v1:" + hashlib.sha256(repr(identity).encode("utf-8")).hexdigest()
                        cached_hint, fresh = read_tmdb_metadata_cache(cache_key)
                        if fresh and cached_hint is not None:
                            self._nfo_hints[key] = cached_hint
                            return cached_hint
                if is_remote_path(folder):
                    remote_path = remote_real_path(folder).rstrip("/") + "/" + filename
                    response = self.remote_client.open_stream(remote_path)
                    try:
                        response.raise_for_status()
                        payload = bytearray()
                        for chunk in response.iter_content(16384):
                            if self.isInterruptionRequested() or len(payload) + len(chunk) > MAX_NFO_BYTES:
                                payload = bytearray()
                                break
                            payload.extend(chunk)
                        hint = parse_nfo(bytes(payload), is_movie)
                    finally:
                        response.close()
                else:
                    with open(os.path.join(folder, filename), "rb") as source:
                        hint = parse_nfo(source.read(MAX_NFO_BYTES + 1), is_movie)
                if cache_key:
                    write_tmdb_metadata_cache(cache_key, hint)
        except Exception:
            # Preserve an existing NFO match on transient NAS/IO failures.
            hint = None
            LOGGER.debug("Az NFO nem olvasható: %s", full_path, exc_info=True)
        self._nfo_hints[key] = hint
        return hint

    @poster_cache_activity()
    def _begin_inventory(self, conn):
        self._discovering = True
        self._inventory_pending = {}
        self._inventory_seen = set()
        self._inventory_previews = {}
        self._inventory_cached = {}
        for path, payload in conn.execute('SELECT file_path,payload FROM library_card_cache WHERE library_id=?', (self.current_scan_library_id,)):
            try:
                value = json.loads(payload)
                if isinstance(value, dict): self._inventory_cached[normalize_media_path(path)] = value
            except (ValueError, TypeError): pass

    def _finish_inventory(self, conn, error_count):
        self._discovering = False
        if (len(self.errors) == error_count and not self.isInterruptionRequested()
                and not (not self._inventory_seen and any(is_remote_path(path) for path in self._inventory_cached))):
            self.inventory_ready.emit({'library':self.current_scan_library_id, 'paths':list(self._inventory_seen)})
        pending = list(self._inventory_pending.items())
        # New cards obtain metadata first; known content never blocks discovery.
        pending.sort(key=lambda value:(value[0][0] in self._inventory_cached, -value[1][2]))
        for key, (entry, movie, _mtime) in pending:
            if self.isInterruptionRequested(): return
            try: item = self.process_media_item(entry, movie, conn)
            except (OSError, sqlite3.Error) as error:
                self.add_error('Médiainformáció feldolgozási hiba: ' + str(error)); continue
            preview = self._inventory_previews.get(key, {})
            for field in ('episode_roots', 'manual_group_id', 'added_at'):
                if field in preview: item[field] = preview[field]
            self.emit_item(item, movie)
        self._inventory_pending.clear()
        self._inventory_previews.clear()
        self._inventory_cached.clear()

    def process_media_item(self, entry, is_movie, conn):
        if self._discovering:
            path = normalize_media_path(entry.path)
            try: mtime = float(entry.stat().st_mtime)
            except OSError: mtime = 0
            self._inventory_pending[(path, bool(is_movie))] = (entry, is_movie, mtime)
            cached = self._inventory_cached.get(path)
            item = dict(cached) if cached else self.make_item(entry.path, clean_name(entry.name)[0], '')
            item['file_path'] = entry.path
            item['_inventory_preview'] = True
            return item
        for _attempt in range(3):
            token = read_pairing_token(conn, entry.path)
            item = self._process_media_item(entry, is_movie, conn, token)
            item["_pairing_token"] = token
            key = (normalize_media_path(entry.path), bool(is_movie))
            if item.pop("_metadata_deferred", False):
                self._deferred_metadata[key] = (entry, is_movie, self.current_scan_library_id, self.current_library_id)
            else:
                self._deferred_metadata.pop(key, None)
            if read_pairing_token(conn, entry.path) == token or self.isInterruptionRequested():
                return item
        return item  # GUI and snapshot guards reject an already superseded result.

    def _process_media_item(self, entry, is_movie, conn, pairing_token):
        full_path = entry.path
        name = entry.name
        norm_path = normalize_media_path(full_path)
        flag = 1 if is_movie else 0

        added_at = 0.0
        try:
            added_at = float(entry.stat().st_mtime)
        except OSError as e:
            if is_movie:
                self.add_error(f"Nem olvasható a fájl módosítási ideje: {full_path} ({e})")
                return self.make_item(full_path, name, "")
        mtime = added_at if is_movie else 0.0

        def make_processed_item(*args):
            item = self.make_item(*args)
            item["added_at"] = added_at
            return item

        # fetchall(): a lekérdezés lezárul, így a hosszú hálózati hívások alatt nem tartja
        # zárolva az adatbázist (különben a kézi párosítás mentése várakozna).
        rows = conn.execute(
            "SELECT tmdb_id, custom_title FROM manual_overrides WHERE file_path = ? AND is_movie = ?",
            (norm_path, flag),
        ).fetchall()
        override = rows[0] if rows else None
        if override and not (isinstance(override[0], int) and override[0] > 0):
            override = None  # érvénytelen azonosítójú kézi bejegyzés nem használható

        movie_context = self.movie_name_context(full_path, name) if is_movie and not override else None
        query = ("SELECT tmdb_id, title, overview, poster_url, release_date, status, signature "
                 "FROM media_cache WHERE file_path = ? AND is_movie = ?")
        args = [norm_path, flag]
        no_result_signature = None
        if override:
            signature = f"override:{override[0]}:{current_tmdb_language()}"
            query += " AND signature = ?"
            args.append(signature)
        else:
            has_alternate_show_title = (
                not is_movie and bool(re.search(r"\([^()]+\)", name))
            )
            signature = (
                f"language:match_v185:{current_tmdb_language()}:show_alias_v2"
                if has_alternate_show_title else f"language:match_v185:{current_tmdb_language()}"
            )
            no_result_signature = (
                f"no_result:show_alias_v2:{current_tmdb_language()}"
                if has_alternate_show_title
                else f"no_result:language_fallback_v8:{current_tmdb_language()}"
            )
            if is_movie:
                signature, no_result_signature = movie_lookup_signatures(movie_context)
            # Keep successful lookups cached. Retry failures once after a
            # parser improvement so old no-result rows do not hide new matches.
            query += " AND signature IN (?, ?)"
            args.extend((signature, no_result_signature))
            if is_movie:
                query += " AND file_mtime = ?"
                args.append(mtime)
        rows = conn.execute(query, args).fetchall()
        cached = rows[0] if rows else None
        if cached and movie_context and not movie_year_matches(cached[4], movie_context["year"]):
            cached = None

        if cached:
            tmdb_id, title, overview, poster_url, release_date, status, cached_signature = cached
            if status == "success":
                info = self.localized_cached_info(conn, full_path, tmdb_id, is_movie, title, overview, poster_url, release_date)
                poster = self.get_poster(info["poster_url"], tmdb_id, is_movie)
                return make_processed_item(full_path, info["title"], info["overview"], poster, info["date"], tmdb_id)
        nfo = self.read_nfo_hint(full_path, name, is_movie) if not override else {}
        if nfo is None:
            previous = conn.execute(
                "SELECT tmdb_id,title,overview,poster_url,release_date FROM media_cache WHERE file_path=? AND is_movie=? AND status='success' AND signature LIKE 'nfo:%'",
                (norm_path, flag)).fetchone()
            if previous:
                media_id, previous_title, description, poster_url, date = previous
                info = self.localized_cached_info(conn, full_path, media_id, is_movie, previous_title, description, poster_url, date)
                return make_processed_item(full_path, info["title"], info["overview"], self.get_poster(info["poster_url"], media_id, is_movie), info["date"], media_id)
        if nfo:
            signature = "nfo:" + hashlib.sha256(json.dumps(nfo, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest() + ":" + current_tmdb_language()
            signature += ":match_v185"
            no_result_signature = signature + ":no_result_v4"
            row = conn.execute(
                "SELECT tmdb_id,title,overview,poster_url,release_date,status,signature FROM media_cache WHERE file_path=? AND is_movie=? AND signature IN (?,?)",
                (norm_path, flag, signature, no_result_signature)).fetchone()
            if row and (not is_movie or conn.execute("SELECT file_mtime FROM media_cache WHERE file_path=?", (norm_path,)).fetchone()[0] == mtime):
                media_id, cached_title, description, poster_url, date, status, _signature = row
                if status == "success":
                    info = self.localized_cached_info(conn, full_path, media_id, is_movie, cached_title, description, poster_url, date)
                    return make_processed_item(full_path, info["title"], info["overview"], self.get_poster(info["poster_url"], media_id, is_movie), info["date"], media_id)
                if status == "no_result" and self.negative_cache_is_fresh(conn, full_path):
                    return make_processed_item(full_path, name, description or NO_MATCH_TEXT)
        elif cached and cached[5] == "no_result" and cached[6] == no_result_signature and self.negative_cache_is_fresh(conn, full_path):
            return make_processed_item(full_path, name, cached[2] or NO_MATCH_TEXT)

        fallback_title = (override[1] if override and override[1] else name)
        if self.tmdb_failures >= 3:
            if time.monotonic() < self._tmdb_probe_at and not self._retrying_metadata:
                if self.current_scan_library_id:
                    self.metadata_failed_libraries.add(self.current_scan_library_id)
                item = make_processed_item(full_path, fallback_title, "")
                item["_metadata_deferred"] = True
                return item
            self.tmdb_failures = 0  # Half-open probe after a bounded cooldown.

        if override:
            res = fetch_tmdb_data(None, is_movie=is_movie, tmdb_id=override[0])
        elif nfo:
            res = {"status": "no_result"}
            if nfo.get("tmdb_id"):
                res = fetch_tmdb_data(None, is_movie=is_movie, tmdb_id=nfo["tmdb_id"])
            if res.get("status") == "no_result" and nfo.get("imdb_id"):
                res = fetch_tmdb_by_imdb(nfo["imdb_id"], is_movie)
            for nfo_title in nfo.get("titles", []):
                if res.get("status") != "no_result":
                    break
                res = fetch_tmdb_data(nfo_title, nfo.get("year"), is_movie)
        else:
            res = {"status": "no_result"}

        if res["status"] == "no_result" and not override:
            cleaned, year = (movie_context["title"], movie_context["year"]) if is_movie else clean_name(name, is_file=False)
            search_titles = [cleaned]
            title_source = name
            if is_movie:
                title_source = (posixpath.basename(posixpath.dirname(remote_real_path(full_path)))
                                if is_remote_path(full_path) else os.path.basename(os.path.dirname(full_path))) if movie_context["from_folder"] else os.path.splitext(name)[0]
            if not is_movie or "(" in title_source:
                # A folder such as "Locsi-Fecsi Márta (Martha Speaks)" often
                # stores the Hungarian and original titles together. Search
                # each independently so their words do not dilute the match.
                base_title = re.sub(r"\s*\([^()]*\)", " ", title_source).strip()
                candidates = [base_title, *re.findall(r"\(([^()]+)\)", title_source)]
                search_titles = []
                for candidate in candidates:
                    candidate = candidate.strip()
                    if (not candidate
                            or re.fullmatch(r"(?:19|20)\d{2}", candidate)
                            or re.fullmatch(r"(?i)(?:season|évad|evad|saison|temporada)\s*\d+", candidate)):
                        continue
                    title_variant, _variant_year = clean_name(candidate, is_file=False)
                    if title_variant and title_variant.casefold() not in {
                        title.casefold() for title in search_titles
                    }:
                        search_titles.append(title_variant)
            res = {"status": "no_result"}
            for search_title in search_titles or [cleaned]:
                candidate_result = fetch_tmdb_data(search_title, year, is_movie)
                if candidate_result.get("status") == "success" or candidate_result.get("status") == "error":
                    res = candidate_result
                    break
                if candidate_result.get("message"):
                    res = candidate_result
                elif res.get("message") is None:
                    res = candidate_result

        if res["status"] == "no_result" and is_movie and not override:
            folder_name = posixpath.basename(posixpath.dirname(remote_real_path(full_path))) if is_remote_path(full_path) else os.path.basename(os.path.dirname(full_path))
            candidate = release_filename_candidate(name, folder_name)
            if candidate and candidate != (movie_context["title"], movie_context["year"]):
                res = fetch_tmdb_data(candidate[0], candidate[1], True)

        if res["status"] == "no_result" and not override and res.get("ambiguous_ids"):
            previous = conn.execute(
                "SELECT tmdb_id,file_mtime FROM media_cache WHERE file_path=? AND is_movie=? AND status='success'",
                (norm_path, flag)).fetchone()
            # New evidence can overturn an old match; a tie alone cannot. Only
            # preserve a candidate that passed the NEW full-title/year checks.
            if previous and previous[0] in res["ambiguous_ids"] and (not is_movie or previous[1] == mtime):
                res = fetch_tmdb_data(None, is_movie=is_movie, tmdb_id=previous[0])

        if res["status"] == "error":
            # Hálózati / API hiba: nem cache-eljük, a következő beolvasáskor újrapróbáljuk.
            if self.current_scan_library_id:
                self.metadata_failed_libraries.add(self.current_scan_library_id)
            self.tmdb_failures += 1
            self.last_error = res["message"]
            if self.tmdb_failures >= 3:
                self._tmdb_probe_at = time.monotonic() + 5.0
            if res["message"] not in self.errors:
                self.errors.append(res["message"])
            self.error_library_ids.setdefault(res["message"], set()).add(self.current_scan_library_id)
            item = make_processed_item(full_path, fallback_title, "")
            item["_metadata_deferred"] = True
            return item
        self.tmdb_failures = 0

        if res["status"] == "no_result":
            if override:
                if self.current_scan_library_id:
                    self.metadata_failed_libraries.add(self.current_scan_library_id)
                self.add_error(f"A kézi párosítás TMDB azonosítója nem található ({override[0]}): {full_path}")
                return make_processed_item(
                    full_path, fallback_title,
                    "A megadott TMDB ID nem található. Kérem, párosítsa újra!",
                )
            message = res.get("message") or NO_MATCH_TEXT
            self.save_cache(
                conn, norm_path, flag, -1, name, message, "", "", mtime,
                "no_result", no_result_signature or signature, pairing_token=pairing_token,
            )
            return make_processed_item(full_path, name, message)

        poster = self.get_poster(res["poster_url"], res["id"], is_movie)
        if not res.get("complete", True) and self.current_scan_library_id:
            self.metadata_failed_libraries.add(self.current_scan_library_id)
            self._incomplete_metadata_libraries.add(self.current_scan_library_id)
        if res.get("complete", True):
            self.save_cache(conn, norm_path, flag, res["id"], res["title"], res["overview"],
                            res["poster_url"], res["date"], mtime, "success", signature, pairing_token=pairing_token)
        return make_processed_item(full_path, res["title"], res["overview"], poster, res["date"], res["id"])


# ==========================================
# MPV LEJÁTSZÓ
# ==========================================
class MpvPlaybackMonitor(_MpvPlaybackMonitor):
    def __init__(self, process, pipe_name, entries, resume_position=0, playlist_file=None, source_paths=None):
        super().__init__(process, pipe_name, entries, resume_position, playlist_file,
                         save_progress=save_playback_progress, set_watched=set_playback_watched,
                         normalize_path=normalize_media_path, logger=LOGGER, source_paths=source_paths)


def resolve_mpv_path(configured_path):
    configured_path = (configured_path or "").strip().strip('"') or "mpv.exe"
    if os.path.isabs(configured_path):
        return configured_path if os.path.exists(configured_path) else None
    local_path = os.path.join(APP_DIR, configured_path)
    if os.path.exists(local_path):
        return local_path
    return shutil.which(configured_path)


_remote_playback_client = None
_remote_playback_server = None
_remote_playback_thread = None
_remote_playback_lock = threading.Lock()
_remote_playback_token = None
_remote_playback_allowed_paths = set()
_remote_playback_profiles = {}

def _remote_stream_url(remote_path):
    global _remote_playback_client, _remote_playback_server, _remote_playback_thread
    global _remote_playback_token
    remote_path = remote_real_path(remote_path)
    with _remote_playback_lock:
        if _remote_playback_server is None:
            _remote_playback_profiles.clear()
            _remote_playback_token = secrets.token_urlsafe(32)
            proxy_token = _remote_playback_token
            class Handler(BaseHTTPRequestHandler):
                def do_HEAD(self): self.do_GET(head_only=True)
                def do_GET(self, head_only=False):
                    from urllib.parse import urlparse, parse_qs
                    parsed=urlparse(self.path)
                    if parsed.path != "/stream": self.send_error(404); return
                    query=parse_qs(parsed.query)
                    token=(query.get("token") or [""])[0]
                    path=(query.get("path") or [""])[0]
                    if not constant_time_equal_text(token, proxy_token):
                        self.send_error(403); return
                    profile_id = (query.get("session") or [""])[0]
                    with _remote_playback_lock:
                        profile = _remote_playback_profiles.get(profile_id)
                        allowed = profile is not None and path in profile["paths"]
                    if not path or not allowed:
                        self.send_error(403); return
                    try:
                        global _remote_playback_client
                        with _remote_playback_lock:
                            if _remote_playback_profiles.get(profile_id) is not profile or path not in profile["paths"]:
                                self.send_error(403)
                                return
                            if profile["client"] is None or not profile["client"].sid:
                                profile["client"] = RemoteNASClient(profile["credentials"])
                            client = profile["client"]
                            _remote_playback_client = client
                        headers={}
                        if self.headers.get("Range"): headers["Range"]=self.headers["Range"]
                        upstream=client.open_stream(path, headers)
                        if upstream.status_code not in (200,206):
                            self.send_error(upstream.status_code,"NAS stream hiba"); upstream.close(); return
                        if "json" in upstream.headers.get("Content-Type", "").lower():
                            upstream.close()
                            self.send_error(502, "A NAS nem videófájlt adott vissza.")
                            return
                        self.send_response(upstream.status_code)
                        for key in ("Content-Type","Content-Length","Content-Range","Accept-Ranges","Last-Modified","ETag"):
                            if upstream.headers.get(key): self.send_header(key,upstream.headers[key])
                        self.send_header("Connection","close"); self.end_headers()
                        if not head_only:
                            for chunk in upstream.iter_content(1024*1024):
                                if chunk:
                                    try: self.wfile.write(chunk)
                                    except (BrokenPipeError,ConnectionResetError): break
                        upstream.close()
                    except Exception as exc:
                        safe_error = redact_credentials(exc)
                        LOGGER.warning("Távoli NAS-lejátszási proxy hiba: %s", safe_error)
                        try: self.send_error(502,safe_error[:180])
                        except Exception: pass
                def log_message(self,fmt,*args): pass
            _remote_playback_server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
            _remote_playback_server.daemon_threads=True
            _remote_playback_thread=threading.Thread(target=_remote_playback_server.serve_forever,daemon=True)
            _remote_playback_thread.start()
        credentials = {key: config.get(key, "") for key in ("quickconnect_id", "nas_username", "nas_password", "nas_direct_url", "nas_local_url", "nas_device_tokens")}
        profile_id = next((key for key, value in _remote_playback_profiles.items()
                           if value["credentials"] == credentials), None)
        if profile_id is None:
            profile_id = secrets.token_urlsafe(24)
            _remote_playback_profiles[profile_id] = {"credentials": credentials, "client": None, "paths": {}}
        paths = _remote_playback_profiles[profile_id]["paths"]
        paths[remote_path] = paths.get(remote_path, 0) + 1
        _remote_playback_allowed_paths.add(remote_path)
        return (
            f"http://127.0.0.1:{_remote_playback_server.server_address[1]}/stream"
            f"?token={_remote_playback_token}&session={profile_id}&path={quote(remote_path,safe='')}"
        )


def release_remote_sources(sources):
    """Release only the ended player's routes; other MPV sessions keep working."""
    from urllib.parse import parse_qs
    global _remote_playback_client
    clients = []
    with _remote_playback_lock:
        for source in sources:
            parsed = urlsplit(source)
            if parsed.hostname != "127.0.0.1" or parsed.path != "/stream":
                continue
            query = parse_qs(parsed.query)
            profile_id = (query.get("session") or [""])[0]
            path = (query.get("path") or [""])[0]
            profile = _remote_playback_profiles.get(profile_id)
            if profile is None or path not in profile["paths"]:
                continue
            profile["paths"][path] -= 1
            if profile["paths"][path] == 0:
                del profile["paths"][path]
            if not profile["paths"]:
                _remote_playback_profiles.pop(profile_id)
                if profile["client"] is not None:
                    clients.append(profile["client"])
                    if _remote_playback_client is profile["client"]:
                        _remote_playback_client = None
        _remote_playback_allowed_paths.intersection_update(
            {path for profile in _remote_playback_profiles.values() for path in profile["paths"]})
    for client in clients:
        run_worker(NasTask(lambda _stop, client=client: client.close()))


def release_remote_sources_after_exit(process, sources):
    # IPC monitoring can stop before MPV itself (for example after a pipe error).
    # The player's still-running stream must stay valid until the process exits.
    if process.poll() is not None:
        release_remote_sources(sources)
        return
    waiter = NasTask(lambda _stop: process.wait())
    waiter.succeeded.connect(lambda _result: release_remote_sources(sources))
    run_worker(waiter)


class SourceResolutionWorker(QThread):
    resolved = pyqtSignal(object)
    failed = pyqtSignal(str)
    def __init__(self, router, paths):
        super().__init__()
        self.router, self.paths = router, list(paths)
    def run(self):
        try:
            values = []
            checked = set()
            for path in self.paths:
                if self.isInterruptionRequested(): return
                pair = self.router.pair_for(path)
                values.append(self.router.playback_path(path, recheck=bool(pair and pair.id not in checked)))
                if pair: checked.add(pair.id)
            self.resolved.emit(values)
        except Exception as error:
            self.failed.emit(str(error))


def playback_source_text(paths):
    kinds = {'remote' if is_remote_path(path) else 'network' if expand_mapped_path(path).startswith(('\\\\', '//')) else 'local' for path in paths}
    if 'remote' in kinds and len(kinds) > 1: return 'Lejátszás: helyi és NAS elérés'
    if 'remote' in kinds:
        if config.get('nas_local_url'): return 'Lejátszás: NAS (automatikus kapcsolat)'
        return 'Lejátszás: NAS (DDNS / QuickConnect)' if config.get('nas_direct_url') else 'Lejátszás: NAS / QuickConnect'
    if 'network' in kinds: return 'Lejátszás: helyi hálózat'
    return 'Lejátszás: helyi fájl'


def play_with_mpv(parent_window, file_path, title=None, media_info=None,
                  playlist_entries=None, resume_position=None, _routed_sources=None):
    mpv_raw = config.get("mpv_path") or "mpv.exe"
    if not resolve_mpv_path(mpv_raw):
        mpv_raw = ensure_mpv(parent_window)
        if not mpv_raw:
            return
    mpv_path = resolve_mpv_path(mpv_raw)
    if not mpv_path:
        QMessageBox.critical(
            parent_window, "Lejátszási hiba",
            f"Az MPV lejátszó nem található itt: '{mpv_raw}'. Ellenőrizd a beállításokat!",
        )
        return

    media_info = dict(media_info or {})
    entries = playlist_entries or [{"path": file_path}]
    normalized_entries = []
    for entry in entries:
        if isinstance(entry, str):
            entry = {"path": entry}
        path = source_router().canonical(entry.get("path") or "")
        if not path:
            continue
        prepared = dict(entry)
        prepared.update({
            "path": path,
            "media_title": prepared.get("media_title") or media_info.get("media_title") or title or "",
            "episode_title": prepared.get("episode_title") or media_info.get("episode_title") or "",
            "poster": prepared.get("poster") or media_info.get("poster") or "",
            "is_movie": prepared.get("is_movie", media_info.get("is_movie", True)),
            "original_language": prepared.get("original_language") or media_info.get("original_language") or "",
        })
        normalized_entries.append(prepared)
    if not normalized_entries:
        return
    if (len(normalized_entries) > 1
            and not config.get("auto_play_next_episode", True)
            and not normalized_entries[0].get("is_movie", True)):
        normalized_entries = normalized_entries[:1]

    router = source_router()
    if _routed_sources is None and any(router.pair_for(entry["path"]) for entry in normalized_entries):
        if parent_window is not None and getattr(parent_window, "_synostream_source_pending", False): return
        if parent_window is not None: parent_window._synostream_source_pending = True
        worker = SourceResolutionWorker(router, [entry["path"] for entry in normalized_entries])
        def owner_available():
            if parent_window is None: return True
            from PyQt6 import sip
            return not sip.isdeleted(parent_window) and parent_window.isVisible() and not getattr(parent_window, "is_closing", False)
        def finished_resolution(values):
            if parent_window is not None: parent_window._synostream_source_pending = False
            if owner_available():
                play_with_mpv(parent_window, normalized_entries[0]["path"], title, media_info,
                              normalized_entries, resume_position, _routed_sources=values)
        def failed_resolution(message):
            if parent_window is not None: parent_window._synostream_source_pending = False
            if owner_available(): QMessageBox.critical(parent_window, "Lejátszási hiba", message)
        worker.resolved.connect(finished_resolution)
        worker.failed.connect(failed_resolution)
        worker.finished.connect(lambda: setattr(parent_window, "_synostream_source_pending", False) if parent_window is not None else None)
        run_worker(worker)
        return

    first_path = normalized_entries[0]["path"]
    if not is_remote_path(first_path) and not os.path.isfile(first_path):
        is_unc = first_path.startswith(("\\\\", "//"))
        QMessageBox.critical(
            parent_window,
            "Hálózati hiba" if is_unc else "Lejátszási hiba",
            f"A lejátszandó fájl jelenleg nem érhető el:\n{first_path}",
        )
        return
    state = get_playback_state(first_path)
    if resume_position is None:
        resume_position = (
            state["position"] if state and not state["watched"] and state["position"] >= 15 else 0
        )
    resume_position = max(0.0, float(resume_position or 0))

    pipe_name = rf"\\.\pipe\SynoStream-{uuid.uuid4().hex}"
    sources = []
    try:
        for index, entry in enumerate(normalized_entries):
            path = _routed_sources[index] if _routed_sources is not None else entry["path"]
            sources.append(_remote_stream_url(path) if is_remote_path(path) else path)
    except Exception as exc:
        release_remote_sources(sources)
        QMessageBox.critical(parent_window, "Távoli lejátszási hiba", str(exc))
        return

    playlist_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", suffix=".m3u8",
            prefix="synostream_playlist_", delete=False,
        ) as playlist:
            playlist_file = playlist.name
            playlist.write("#EXTM3U\n")
            for entry, source in zip(normalized_entries, sources):
                media_title = entry.get("media_title") or title or ""
                episode_title = entry.get("episode_title") or ""
                display_title = (
                    f"{media_title} — {episode_title}" if episode_title and media_title
                    else (episode_title or media_title)
                )
                display_title = " ".join(display_title.replace("\r", " ").replace("\n", " ").split())
                playlist.write(f"#EXTINF:0,{display_title}\n{source}\n")
    except OSError as exc:
        if playlist_file:
            try:
                os.remove(playlist_file)
            except OSError:
                pass
        release_remote_sources(sources)
        QMessageBox.critical(
            parent_window, "Lejátszási hiba",
            f"Nem sikerült előkészíteni az epizódlistát: {exc}",
        )
        return

    # SynoStream owns resume state in SQLite; disable MPV's separate watch-later
    # files so old per-URL positions cannot override it or accumulate indefinitely.
    cmd = [
        mpv_path, "--hwdec=auto", "--no-resume-playback",
        "--no-save-position-on-quit", "--idle=once", "--pause=yes", "--force-window=yes",
        f"--input-ipc-server={pipe_name}",
    ]
    network_playback = any(
        is_remote_path(entry["path"])
        or entry["path"].startswith(("\\\\", "//"))
        for entry in normalized_entries
    )
    network_movie_playback = (
        network_playback
        and all(bool(entry.get("is_movie", True)) for entry in normalized_entries)
    )
    if network_movie_playback:
        # Movies often have substantially higher bitrates than TV episodes.
        # Increase their bounded memory buffer and initial refill window while
        # keeping the TV playback settings lighter.
        cmd.extend((
            "--cache=yes",
            "--cache-secs=180",
            "--demuxer-max-bytes=768MiB",
            "--demuxer-max-back-bytes=128MiB",
            "--cache-pause=yes",
            "--cache-pause-wait=10",
            "--cache-pause-initial=yes",
        ))
    elif network_playback:
        # QuickConnect streams are exposed through a local HTTP proxy, so MPV
        # cannot infer that the upstream is a slow network. Give it a useful
        # forward buffer and let it rebuffer before playback starts/continues.
        cmd.extend((
            "--cache=yes",
            "--cache-secs=120",
            "--demuxer-max-bytes=512MiB",
            "--demuxer-max-back-bytes=128MiB",
            "--cache-pause=yes",
            "--cache-pause-wait=5",
            "--cache-pause-initial=yes",
        ))
    if config.get("playback_fullscreen", False):
        cmd.append("--fullscreen=yes")
    cmd.extend(mpv_localized_context_menu_args(mpv_path))
    audio_preference = config.get("preferred_audio_language", "original")
    subtitle_preference = config.get("preferred_subtitle_language", "hu")
    if audio_preference == "hu":
        cmd.append("--alang=hu")
    elif audio_preference == "original":
        original_languages = {
            str(entry.get("original_language") or "").strip().lower()
            for entry in normalized_entries
        }
        original_languages.discard("")
        if len(original_languages) == 1:
            language = next(iter(original_languages))
            if re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*", language):
                cmd.append(f"--alang={language}")
    if subtitle_preference == "hu":
        cmd.append("--slang=hu")
    elif subtitle_preference == "original":
        original_languages = {
            str(entry.get("original_language") or "").strip().lower()
            for entry in normalized_entries
        }
        original_languages.discard("")
        if len(original_languages) == 1:
            language = next(iter(original_languages))
            if re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*", language):
                cmd.append(f"--slang={language}")
    elif subtitle_preference == "none":
        cmd.append("--sid=no")
    try:
        process = subprocess.Popen(cmd, env=mpv_child_environment())
    except OSError as e:
        try:
            os.remove(playlist_file)
        except OSError:
            pass
        release_remote_sources(sources)
        QMessageBox.critical(parent_window, "Lejátszási hiba", f"Nem sikerült elindítani az MPV-t: {e}")
        return

    first = normalized_entries[0]
    save_playback_progress(
        first, resume_position, state["duration"] if state else 0, normalized_entries,
    )
    monitor = MpvPlaybackMonitor(
        process, pipe_name, normalized_entries, resume_position, playlist_file, source_paths=sources,
    )
    main_window = parent_window
    watched_slot = None
    while main_window is not None:
        watched_slot = getattr(main_window, "on_playback_watched", None)
        if callable(watched_slot):
            break
        main_window = main_window.parentWidget() if hasattr(main_window, "parentWidget") else None
    if main_window is None:
        main_window = parent_window.window()
    if not callable(watched_slot):
        watched_slot = getattr(main_window, "on_playback_watched", None)
    if callable(watched_slot):
        monitor.watched_changed.connect(watched_slot)
        monitor.progress_saved.connect(watched_slot)
    if hasattr(main_window, 'statusBar'):
        from PyQt6 import sip
        label = getattr(main_window, '_playback_source_label', None)
        if label is None:
            label = QLabel(); main_window.statusBar().addPermanentWidget(label)
            main_window._playback_source_label = label
        selected_paths = _routed_sources if _routed_sources is not None else [entry['path'] for entry in normalized_entries]
        source_text = playback_source_text(selected_paths)
        label.setText(source_text); label.show()
        main_window._playback_source_token = pipe_name
        LOGGER.info('%s', source_text)
        def clear_source_label():
            if not sip.isdeleted(main_window) and getattr(main_window, '_playback_source_token', None) == pipe_name:
                label.hide()
        monitor.finished.connect(clear_source_label)
    monitor.finished.connect(lambda sources=tuple(sources), process=process: release_remote_sources_after_exit(process, sources))
    monitor.startup_failed.connect(
        lambda message, owner=main_window: QMessageBox.critical(
            owner, "Lejátszási hiba", message
        )
    )
    run_worker(monitor)


def play_media(parent_window, file_path, title=None, media_info=None,
               playlist_entries=None, resume_position=None):
    play_with_mpv(parent_window, file_path, title, media_info, playlist_entries, resume_position)


# ==========================================
# MPV AUTOMATIKUS ELLENŐRZÉSE / TELEPÍTÉSE
# ==========================================
MPV_INSTALL_DIR = os.path.join(BASE_DIR, "tools", "mpv")
MPV_EXE_PATH = os.path.join(MPV_INSTALL_DIR, "mpv.exe")
MPV_RELEASE_API = "https://api.github.com/repos/mpv-player/mpv/releases/tags/git-release"
MAX_MPV_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_MPV_EXTRACTED_BYTES = 2 * 1024 * 1024 * 1024
MPV_CONTEXT_SCRIPT_SOURCE_PATH = os.path.join(
    RESOURCE_DIR, "assets", "mpv", "synostream_context.lua",
)
MPV_CONTEXT_SCRIPT_PATH = os.path.join(MPV_INSTALL_DIR, "synostream_context.lua")
_MPV_CONTEXT_MENU_SUPPORT = {}


def mpv_child_environment():
    child_env = os.environ.copy()
    child_env["SYNOSTREAM_MPV_LANGUAGE"] = "en" if UI_LANGUAGE == "en" else "hu"
    return child_env


def ensure_mpv_context_script():
    """Copy the app-bundled menu script beside its managed MPV installation."""
    source = MPV_CONTEXT_SCRIPT_SOURCE_PATH
    target = MPV_CONTEXT_SCRIPT_PATH
    if not os.path.isfile(source):
        return target if os.path.isfile(target) else None
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if (not os.path.isfile(target)
                or os.path.getsize(source) != os.path.getsize(target)
                or os.path.getmtime(source) > os.path.getmtime(target)):
            shutil.copy2(source, target)
        return target
    except OSError as exc:
        LOGGER.warning("Nem sikerült előkészíteni az MPV magyar menüjét: %s", exc)
        return source if os.path.isfile(source) else None


def mpv_localized_context_menu_args(mpv_path):
    """Enable SynoStream's translated right-click menu only on supporting MPV builds."""
    script_path = ensure_mpv_context_script()
    if not script_path:
        return []

    cache_key = os.path.normcase(os.path.abspath(mpv_path))
    if cache_key not in _MPV_CONTEXT_MENU_SUPPORT:
        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            properties = subprocess.run(
                [mpv_path, "--no-config", "--list-properties"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", timeout=8,
                creationflags=creationflags, check=False,
            )
            options = subprocess.run(
                [mpv_path, "--no-config", "--list-options"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", timeout=8,
                creationflags=creationflags, check=False,
            )
            has_menu_data = properties.returncode == 0 and re.search(
                r"(?m)^\s*menu-data(?:\s|$)", properties.stdout,
            )
            has_menu_loader = options.returncode == 0 and re.search(
                r"(?m)^\s*--load-context-menu(?:\s|=|$)", options.stdout,
            )
            _MPV_CONTEXT_MENU_SUPPORT[cache_key] = bool(has_menu_data and has_menu_loader)
        except (OSError, subprocess.SubprocessError):
            _MPV_CONTEXT_MENU_SUPPORT[cache_key] = False

    if not _MPV_CONTEXT_MENU_SUPPORT[cache_key]:
        return []
    return [
        "--load-context-menu=yes",
        f"--script={script_path}",
    ]


class MpvInstallWorker(QThread):
    progress_value = pyqtSignal(int)
    progress_label = pyqtSignal(str)
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def setValue(self, value): self.progress_value.emit(value)
    def setLabelText(self, text): self.progress_label.emit(text)

    def run(self):
        from synostream_mpv_install import bootstrap
        try:
            result = bootstrap(MPV_INSTALL_DIR, MPV_RELEASE_API, MAX_MPV_ARCHIVE_BYTES,
                               self.isInterruptionRequested, self)
            self.completed.emit(result)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(str(error))


def ensure_mpv(parent=None):
    """Keep the startup return contract while all bootstrap I/O runs off the GUI thread."""
    if not getattr(ensure_mpv, '_cleanup_started', False):
        from synostream_mpv_install import cleanup_stale
        ensure_mpv._cleanup_started = True
        threading.Thread(target=cleanup_stale, args=(MPV_INSTALL_DIR,), daemon=True).start()
    configured = (config.get('mpv_path') or 'mpv.exe').strip().strip('"')
    existing = resolve_mpv_path(configured)
    if existing: return existing
    if os.path.isfile(MPV_EXE_PATH):
        config['mpv_path'] = MPV_EXE_PATH
        ok, error = save_config()
        if not ok: QMessageBox.warning(parent, 'Mentési figyelmeztetés', redact_credentials(error))
        return MPV_EXE_PATH
    if sys.platform != 'win32': return None
    from PyQt6.QtCore import QEventLoop
    from PyQt6.QtWidgets import QProgressDialog
    progress = QProgressDialog(translate_text('Az MPV lejátszó hiányzik. Letöltés és telepítés…'), translate_text('Mégse'), 0, 100, parent)
    progress.setWindowTitle(translate_text('MPV telepítése'))
    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    worker = MpvInstallWorker()
    result = {'path':None, 'error':None, 'cancelled':False}
    worker.progress_value.connect(progress.setValue)
    worker.progress_label.connect(lambda text: progress.setLabelText(translate_text(text)))
    worker.completed.connect(lambda value:result.update(path=value))
    worker.failed.connect(lambda value:result.update(error=value))
    worker.cancelled.connect(lambda:result.update(cancelled=True))
    progress.canceled.connect(worker.requestInterruption)
    loop = QEventLoop()
    worker.finished.connect(loop.quit)
    progress.show()
    worker.start()
    loop.exec()
    worker.wait()
    progress.close()
    if result['cancelled']: return None
    if result['error']:
        QMessageBox.warning(parent, 'MPV telepítése nem sikerült', 'Az alkalmazás MPV nélkül indul tovább.\n\n'+result['error'])
        return None
    config['mpv_path'] = result['path']
    ok, error = save_config()
    if not ok: QMessageBox.warning(parent, 'Mentési figyelmeztetés', redact_credentials(error))
    return result['path']


# ==========================================
# QSS STÍLUS
# ==========================================
DS_VIDEO_PURPLE_FIXED_QSS = """
QMainWindow, QDialog {
    background-color: #121212;
}
QMainWindow {
    border: 1px solid #39363D;
}
QDialog {
    border: 1px solid #39363D;
}
QWidget {
    background-color: #121212;
    color: #e0e0e0;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}
QLabel {
    background: transparent;
}
QFrame#Sidebar {
    background-color: #181818;
    border-right: 1px solid #302E33;
}
QLabel#Logo {
    color: #eeeeee;
    font-family: 'Segoe UI Variable';
    font-size: 22px;
    font-weight: 500;
    padding-left: 20px;
    margin-bottom: 20px;
}
QLabel#StatusLabel {
    color: #888888;
    font-size: 12px;
    padding: 6px 20px;
}
QLabel#PageTitle {
    font-size: 22px;
    font-weight: bold;
    color: white;
}
QLabel#InfoLabel {
    color: #888888;
    font-size: 14px;
    margin-top: 10px;
}
QLabel#DetailTitle {
    font-size: 18px;
    font-weight: bold;
    color: #B7A9C8;
}
QLabel#Poster {
    background-color: #252525;
    border: 1px solid #39363D;
    border-radius: 4px;
}
QFrame#Card {
    background-color: #1a1a1a;
    border: 1px solid #343238;
    border-radius: 8px;
}
QFrame#Card:hover {
    background-color: #242424;
    border-color: #665A71;
}
QLabel#CardTitle {
    color: white;
    font-weight: bold;
    font-size: 12px;
}
QPushButton {
    background-color: #2a2a2a;
    border: 1px solid #39363D;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: #333333;
}
QPushButton[class="SidebarBtn"] {
    background-color: transparent;
    color: #b3b3b3;
    border: none;
    text-align: left;
    padding: 12px 20px;
    font-size: 14px;
    border-radius: 6px;
    margin: 2px 10px;
}
QPushButton[class="SidebarBtn"]:hover {
    background-color: #282828;
    color: #ffffff;
}
QPushButton[class="SidebarBtn"]:checked {
    background-color: #51485B;
    color: #ffffff;
    font-weight: bold;
}
QLineEdit, QComboBox, QListWidget {
    background-color: #222222;
    border: 1px solid #39363D;
    border-radius: 6px;
    padding: 8px 12px;
    color: #ffffff;
    font-size: 14px;
}
QLineEdit:focus, QComboBox:focus, QListWidget:focus {
    border: 1px solid #897A99;
}
QListWidget::item:selected {
    background-color: #5B5065;
    color: #ffffff;
}
QComboBox::drop-down {
    border: 0px;
}
QGroupBox {
    color: #d8d1e5;
    border: 1px solid #403B45;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px 6px 6px 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #B7A9C8;
}
QPushButton[class="ActionBtn"] {
    background-color: #5B5065;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 14px;
}
QPushButton[class="ActionBtn"]:hover {
    background-color: #70627B;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: #1A191C;
    width: 12px;
    margin: 2px;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background: #554B5F;
    min-height: 26px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #82738F;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: #1A191C;
    height: 12px;
    margin: 2px;
    border-radius: 6px;
}
QScrollBar::handle:horizontal {
    background: #554B5F;
    min-width: 26px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover {
    background: #82738F;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    border: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
"""

DS_VIDEO_PURPLE_FIXED_QSS += """
QMainWindow, QWidget {background-color:#141317; color:#EEEAF3;}
QLabel {background:transparent;}
QFrame#Sidebar {background-color:#1B191F; border-right:1px solid #302B36;}
QLabel#PageTitle {font-size:24px; font-weight:600; color:#EEEAF3;}
QLabel#LibraryCount {color:#A49CAE; font-size:12px;}
QFrame#Card {background:transparent; border:0; border-radius:6px;}
QFrame#Card:hover {background:#201C25; border:0;}
QLabel#Poster {background:#211D26; border:0; border-radius:6px; color:#A49CAE;}
QLabel#CardTitle {font-size:14px; font-weight:600; color:#EEEAF3;}
QLabel#CardMetadata {font-size:12px; font-weight:400; color:#A49CAE;}
QLabel#WatchedBadge {background:#30263C; color:#DDD0EB; border:0; border-radius:11px; font-size:13px;}
QPushButton[class="SidebarBtn"] {padding:11px 14px; margin:2px 8px; color:#B4ACBE;}
QPushButton[class="SidebarBtn"]:checked {background:#30263C; color:#EEEAF3; font-weight:600;}
QLineEdit, QComboBox {background:#1B191F; border:1px solid #302B36; border-radius:7px;}
QLineEdit:focus, QComboBox:focus {border:1px solid #A48BC2;}
QScrollArea {border:0; background:transparent;}
"""


# ==========================================
# KÁRTYA ÉS OLDAL
# ==========================================
def make_refresh_icon():
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#AA9BB9"), 2.2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawArc(4, 4, 16, 16, 45 * 16, 280 * 16)
    painter.drawLine(17, 4, 21, 5)
    painter.drawLine(21, 5, 20, 9)
    painter.end()
    return QIcon(pixmap)


def make_search_icon():
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#A49CAE"), 1.8))
    painter.drawEllipse(4, 4, 11, 11)
    painter.drawLine(14, 14, 20, 20)
    painter.end()
    return QIcon(pixmap)


class MediaCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, item, parent=None, card_size="normal"):
        super().__init__(parent)
        self.item = {}
        self.card_size = None
        self.setObjectName("Card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(7)
        self.poster_label = QLabel()
        self.poster_label.setObjectName("Poster")
        self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.poster_label)
        self.watched_badge = QLabel(self.poster_label)
        check = QPixmap(18, 18)
        check.fill(Qt.GlobalColor.transparent)
        check_painter = QPainter(check)
        check_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        check_painter.setPen(QPen(QColor("#DDD0EB"), 2))
        check_painter.drawLine(4, 9, 8, 13)
        check_painter.drawLine(8, 13, 15, 5)
        check_painter.end()
        self.watched_badge.setPixmap(check)
        self.watched_badge.setObjectName("WatchedBadge")
        self.watched_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.watched_badge.setFixedSize(22, 22)
        self.progress = QProgressBar(self.poster_label)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("QProgressBar {border:0; background:#38313F;} QProgressBar::chunk {background:#A48BC2;}")
        self.title_label = QLabel()
        self.title_label.setObjectName("CardTitle")
        self.title_label.setWordWrap(False)
        self.title_label.setFixedHeight(21)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.title_label)
        self.metadata_label = QLabel()
        self.metadata_label.setObjectName("CardMetadata")
        self.metadata_label.setFixedHeight(18)
        layout.addWidget(self.metadata_label)
        layout.addStretch(1)
        self.bind_item(item, card_size)

    def bind_item(self, item, card_size=None):
        self.item = item
        self.set_card_size(card_size or self.card_size or "normal", reload=False)
        title = str(item.get("title") or "")
        self.title_label.setRawToolTip(title)
        self.title_label.setRawText(self.title_label.fontMetrics().elidedText(
            title, Qt.TextElideMode.ElideRight, self.width() - 4))
        _, _, width, height = CARD_SIZE_PRESETS[self.card_size]
        pixmap = load_pixmap(item.get("poster"), width, height)
        self.poster_label.clear()
        if pixmap is not None:
            self.poster_label.setPixmap(pixmap)
        else:
            self.poster_label.setPixmap(placeholder_pixmap(item.get("file_path") or title, width, height))
        self.refresh_watched_badge()

    def set_card_size(self, card_size, reload=True):
        if card_size not in CARD_SIZE_PRESETS:
            return
        self.card_size = card_size
        width, height, poster_width, poster_height = CARD_SIZE_PRESETS[card_size]
        self.setFixedSize(width, height)
        self.poster_label.setFixedSize(poster_width, poster_height)
        self.watched_badge.move(poster_width - 30, 8)
        self.progress.setGeometry(0, poster_height - 3, poster_width, 3)
        if reload and self.item:
            self.bind_item(self.item, card_size)

    def refresh_watched_badge(self):
        state = get_display_playback_state(self.item.get("file_path", ""))
        watched = item_has_watched_playback(self.item)
        self.watched_badge.setVisible(watched)
        self.watched_badge.setToolTip("A sorozatban van megnézett epizód."
                                     if self.item.get("is_movie") is False else "Megnézve")
        position, duration = state.get("position", 0), state.get("duration", 0)
        percentage = min(100, max(0, int(100 * position / duration))) if duration else 0
        self.progress.setValue(percentage)
        self.progress.setVisible(bool(position and duration and not state.get("watched")))
        year = re.search(r"\b((?:18|19|20|21)\d{2})\b", str(self.item.get("date") or ""))
        parts = [year.group(1)] if year else []
        if state.get("watched"):
            parts.append(translate_text("Megnézve"))
        elif percentage:
            parts.append(translate_text("Folytatható") + f" · {percentage}%")
        self.metadata_label.setRawText(" · ".join(parts))

    def retranslate_texts(self):
        self.refresh_watched_badge()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            super().mousePressEvent(event)


class MediaPage(QWidget):
    card_clicked = pyqtSignal(dict)
    refresh_requested = pyqtSignal()
    recommendations_requested = pyqtSignal()

    def __init__(self, title_text):
        super().__init__()
        self._data_revision = 0
        self._sorted_key = None
        self._filter_key = None
        self._sorted_records = []
        self._widget_pool = []
        self.widget_creations = 0
        self.sort_passes = 0
        self._ordered_records = []
        self._visible_records = set()
        self._columns = 1
        self.cards = []  # (kisbetűs cím, kártya)
        self.card_by_path = {}
        self.card_positions = {}
        self.card_size = "normal"
        self.certification_worker = None
        self.bulk_update_depth = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)

        top_bar = QHBoxLayout()
        title = QLabel(title_text)
        self.page_title = title
        title.setObjectName("PageTitle")
        top_bar.addWidget(title)
        top_bar.addStretch()
        self.recommendations_button = QPushButton("Ajánló")
        self.recommendations_button.setToolTip("Ajánlások ennek a médiatárnak a műsorai alapján")
        self.recommendations_button.clicked.connect(self.recommendations_requested.emit)
        top_bar.addWidget(self.recommendations_button)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Keresés")
        self.search_box.addAction(make_search_icon(), QLineEdit.ActionPosition.LeadingPosition)
        self.search_box.setFixedWidth(250)
        self.search_box.textChanged.connect(self.schedule_reflow)
        top_bar.addWidget(self.search_box)
        layout.addLayout(top_bar)

        sort_row = QHBoxLayout()
        self.count_label = QLabel("")
        self.count_label.setObjectName("LibraryCount")
        sort_row.addWidget(self.count_label)
        sort_row.addStretch()
        self.sort_criterion = QComboBox()
        self.sort_criterion.addItem("ABC", "title")
        self.sort_criterion.addItem("Kiadási év", "year")
        self.sort_criterion.addItem("Hozzáadás", "added")
        self.sort_criterion.addItem("Korhatár", "certification")
        self.sort_criterion.setFixedWidth(155)
        self.sort_criterion.setToolTip("Rendezés szempontja")
        self.sort_criterion.currentIndexChanged.connect(self.on_sort_criterion_changed)
        sort_row.addWidget(self.sort_criterion)
        self.sort_direction = QComboBox()
        self.sort_direction.addItem("Növekvő", False)
        self.sort_direction.addItem("Csökkenő", True)
        self.sort_direction.setFixedWidth(135)
        self.sort_direction.setToolTip("A rendezés iránya")
        self.sort_direction.currentIndexChanged.connect(self.schedule_reflow)
        sort_row.addWidget(self.sort_direction)
        self.refresh_button = QPushButton(self)
        self.refresh_button.setObjectName("RefreshButton")
        self.refresh_button.setIcon(make_refresh_icon())
        self.refresh_button.setIconSize(QSize(18, 18))
        self.refresh_button.setFixedSize(38, 38)
        self.refresh_button.setToolTip("Az éppen megnyitott médiatár frissítése")
        self.refresh_button.setAccessibleName("Médiatár frissítése")
        self.refresh_button.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #49434F; "
            "border-radius: 6px; padding: 0px; }"
            "QPushButton:hover { background: #302D33; border-color: #82738F; }"
            "QPushButton:pressed { background: #51485B; }"
        )
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        sort_row.addWidget(self.refresh_button)
        layout.addLayout(sort_row)

        self.msg_lbl = QLabel("")
        self.msg_lbl.setObjectName("InfoLabel")
        self.msg_lbl.hide()
        layout.addWidget(self.msg_lbl)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(CARD_SPACING)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.grid_widget)
        self.scroll.verticalScrollBar().valueChanged.connect(self.render_visible)
        layout.addWidget(self.scroll)

        self.reflow_timer = QTimer(self)
        self.reflow_timer.setSingleShot(True)
        self.reflow_timer.setInterval(30)
        self.reflow_timer.timeout.connect(self.reflow)
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(3000)
        self.progress_timer.timeout.connect(self.refresh_visible_states)
        self.certification_request_timer = QTimer(self)
        self.certification_request_timer.setSingleShot(True)
        self.certification_request_timer.setInterval(250)
        self.certification_request_timer.timeout.connect(self.request_certification_data)

    def count(self):
        return len(self.cards)

    def set_message(self, text):
        self.msg_lbl.setText(text)
        self.msg_lbl.setVisible(bool(text))

    def clear(self):
        self.certification_request_timer.stop()
        if self.certification_worker is not None and self.certification_worker.isRunning():
            self.certification_worker.requestInterruption()
        for _, card in self.cards:
            card.deleteLater()
        self.cards = []
        self._ordered_records = []
        self._sorted_records = []
        self._sorted_key = None
        self._filter_key = None
        self._visible_records.clear()
        self.card_by_path.clear()
        self.card_positions.clear()
        self._data_revision += 1
        if self.bulk_update_depth == 0:
            self.schedule_reflow()

    def begin_bulk_update(self):
        self.bulk_update_depth += 1

    def end_bulk_update(self):
        self.bulk_update_depth = max(0, self.bulk_update_depth - 1)
        if self.bulk_update_depth == 0:
            self.schedule_reflow()
            if self.sort_criterion.currentData() == "certification":
                self.certification_request_timer.start()

    @staticmethod
    def _item_paths(item):
        return {
            normalize_media_path(path)
            for path in (item.get("episode_roots") or [item.get("file_path", "")])
            if isinstance(path, str) and path
        }

    def _make_card(self, item):
        return CardRecord(item, self)

    def _index_card(self, index, card):
        self._data_revision += 1
        self.card_positions[id(card)] = index
        for path in self._item_paths(card.item):
            self.card_by_path[path] = card

    def _unindex_card(self, card):
        self._data_revision += 1
        self.card_positions.pop(id(card), None)
        for path in self._item_paths(card.item):
            if self.card_by_path.get(path) is card:
                self.card_by_path.pop(path, None)

    def add_item(self, item):
        new_paths = self._item_paths(item)
        matched_cards = []
        for path in new_paths:
            card = self.card_by_path.get(path)
            if card is not None and card not in matched_cards:
                matched_cards.append(card)
        if matched_cards:
            old_card = matched_cards[0]
            index = self.card_positions.get(id(old_card))
            if index is None:
                return item
            old_item = old_card.item

            compared_keys = (
                "file_path", "title", "overview", "date", "id", "poster",
                "added_at", "episode_roots", "manual_group_id", "is_movie",
                "library_id", "_scan_library_id",
            )
            if all(old_item.get(key) == item.get(key) for key in compared_keys):
                return old_item

            updated = dict(old_item)
            updated.update(item)
            if "episode_roots" not in item:
                updated.pop("episode_roots", None)
            if "manual_group_id" not in item:
                updated.pop("manual_group_id", None)
            # Scanner rows do not contain detail metadata; keep it when a card
            # is refreshed so sorting and the opened card remain populated.
            same_media = (old_item.get("id") == item.get("id")
                          and bool(old_item.get("is_movie", True)) == bool(item.get("is_movie", True)))
            for key in (
                "original_language", "genres", "rating", "runtime", "cast",
                "certification", "certification_country", "certification_order",
                "certification_checked", "certification_error",
            ):
                if not same_media and key not in item:
                    updated.pop(key, None)
                elif key not in item and key in old_item:
                    updated[key] = old_item[key]
            replacement = self._make_card(updated)
            old_card.deleteLater()
            self._unindex_card(old_card)
            self.cards[index] = (str(updated.get("title") or "").lower(), replacement)
            self._index_card(index, replacement)
            for duplicate in matched_cards[1:]:
                duplicate_index = self.card_positions.get(id(duplicate))
                if duplicate_index is None:
                    continue
                duplicate.deleteLater()
                self._unindex_card(duplicate)
                self.cards[duplicate_index] = None
            if len(matched_cards) > 1:
                self.cards = [entry for entry in self.cards if entry is not None]
                self.card_positions = {
                    id(card): position for position, (_title, card) in enumerate(self.cards)
                }
            self.set_message("")
            if self.bulk_update_depth == 0:
                self.schedule_reflow()
            if (self.bulk_update_depth == 0
                    and self.sort_criterion.currentData() == "certification"):
                self.certification_request_timer.start()
            return updated

        card = self._make_card(item)
        self.cards.append((str(item.get("title") or "").lower(), card))
        self._index_card(len(self.cards) - 1, card)
        self.set_message("")
        if self.bulk_update_depth == 0:
            self.schedule_reflow()
        if (self.bulk_update_depth == 0
                and self.sort_criterion.currentData() == "certification"):
            self.certification_request_timer.start()
        return item

    def replace_items(self, items):
        self.begin_bulk_update()
        try:
            self.clear()
            for item in items:
                self.add_item(item)
        finally:
            self.end_bulk_update()

    def prune_scan_source(self, scan_library_id, seen_paths):
        """Remove stale cached cards from one library after a complete scan."""
        normalized_seen = {normalize_media_path(path) for path in seen_paths if path}
        retained = []
        removed = False
        for title, card in self.cards:
            item = card.item
            if (item.get("_scan_library_id") == scan_library_id
                    and normalize_media_path(item.get("file_path", "")) not in normalized_seen):
                card.deleteLater()
                removed = True
                continue
            retained.append((title, card))
        if removed:
            self.cards = retained
            self.card_by_path = {}
            self.card_positions = {}
            for index, (_title, card) in enumerate(self.cards):
                self._index_card(index, card)
            if self.bulk_update_depth == 0:
                self.schedule_reflow()

    def on_sort_criterion_changed(self, *_args):
        self.schedule_reflow()
        if self.sort_criterion.currentData() == "certification":
            self.request_certification_data()

    def request_certification_data(self):
        if self.sort_criterion.currentData() != "certification":
            return
        if self.certification_worker is not None and self.certification_worker.isRunning():
            return
        media_items = []
        for _title, card in self.cards:
            item = card.item
            if item.get("certification_checked") is True:
                continue
            try:
                tmdb_id = int(item.get("id") or 0)
            except (TypeError, ValueError):
                continue
            if tmdb_id > 0:
                media_items.append((tmdb_id, bool(item.get("is_movie", True))))
        if not media_items:
            return
        worker = TmdbCertificationSortWorker(media_items)
        worker.certification_ready.connect(self.apply_certification_data)
        worker.finished.connect(self.on_certification_worker_finished)
        self.certification_worker = worker
        run_worker(worker)

    def apply_certification_data(self, tmdb_id, is_movie, metadata):
        changed = False
        for _title, card in self.cards:
            item = card.item
            try:
                item_id = int(item.get("id") or 0)
            except (TypeError, ValueError):
                continue
            if item_id != tmdb_id or bool(item.get("is_movie", True)) != bool(is_movie):
                continue
            for key in (
                "certification", "certification_country", "certification_order",
                "certification_checked", "certification_error",
            ):
                if key in metadata:
                    item[key] = metadata[key]
            changed = True
        if changed:
            self._data_revision += 1
            self.schedule_reflow()

    def on_certification_worker_finished(self):
        self.certification_worker = None
        if self.sort_criterion.currentData() == "certification":
            self.certification_request_timer.start()

    def update_item(self, item):
        """A megadott útvonalhoz tartozó egyetlen kártyát cseréli le."""
        target = normalize_media_path(item.get("file_path", ""))
        for index, (_title, old_card) in enumerate(self.cards):
            old_item = old_card.item
            paths = old_item.get("episode_roots") or [old_item.get("file_path", "")]
            if target not in {normalize_media_path(path) for path in paths if path}:
                continue

            updated = dict(item)
            updated["is_movie"] = old_item.get("is_movie", item.get("is_movie"))
            updated.setdefault("added_at", old_item.get("added_at", 0.0))
            if old_item.get("episode_roots"):
                updated["episode_roots"] = old_item["episode_roots"]
            if old_item.get("manual_group_id"):
                updated["manual_group_id"] = old_item["manual_group_id"]
            new_card = self._make_card(updated)
            old_card.deleteLater()
            self._unindex_card(old_card)
            self.cards[index] = (updated["title"].lower(), new_card)
            self._index_card(index, new_card)
            self.set_message("")
            self.schedule_reflow()
            return updated
        return None

    def schedule_reflow(self, *_):
        self.reflow_timer.start()

    def set_card_size(self, card_size):
        if card_size not in CARD_SIZE_PRESETS or card_size == self.card_size:
            return
        self.card_size = card_size
        for _title, card in self.cards:
            card.set_card_size(card_size)
        self.grid_widget.updateGeometry()
        self.grid.invalidate()
        self.schedule_reflow()

    def reflow(self):
        query = self.search_box.text().strip().lower()
        viewport_w = self.scroll.viewport().width()
        card_w = CARD_SIZE_PRESETS[self.card_size][0]
        cols = max(1, (viewport_w + CARD_SPACING) // (card_w + CARD_SPACING))

        sort_mode = self.sort_criterion.currentData()
        reverse = bool(self.sort_direction.currentData())
        sort_key = (self._data_revision, sort_mode, reverse)
        if self._sorted_key != sort_key:
            ordered_cards = list(self.cards)
            if sort_mode == "title":
                ordered_cards.sort(key=lambda entry: str(entry[1].item.get("title", "")).casefold(), reverse=reverse)
            elif sort_mode == "certification":
                ranked = []
                unranked = []
                for entry in ordered_cards:
                    title, card = entry
                    value = card.item.get("certification_order")
                    if isinstance(value, (int, float)):
                        ranked.append((float(value), entry))
                    else:
                        unranked.append(entry)
                ranked.sort(
                    key=lambda pair: (pair[0], str(pair[1][1].item.get("title", "")).casefold()),
                    reverse=reverse,
                )
                unranked.sort(key=lambda entry: str(entry[1].item.get("title", "")).casefold())
                ordered_cards = [entry for _value, entry in ranked] + unranked
            else:
                dated = []
                undated = []
                for entry in ordered_cards:
                    title, card = entry
                    item = card.item
                    if sort_mode == "year":
                        value = card.year
                    else:
                        try:
                            value = float(item.get("added_at") or 0)
                        except (TypeError, ValueError):
                            value = 0.0
                        if value <= 0:
                            value = None
                    if value is None:
                        undated.append(entry)
                    else:
                        dated.append((value, entry))
                dated.sort(
                    key=lambda pair: (pair[0], str(pair[1][1].item.get("title", "")).casefold()),
                    reverse=reverse,
                )
                undated.sort(key=lambda entry: str(entry[1].item.get("title", "")).casefold())
                ordered_cards = [entry for _value, entry in dated] + undated

            self._sorted_records = ordered_cards
            self._sorted_key = sort_key
            self.sort_passes += 1
        filter_key = (sort_key, query)
        if self._filter_key != filter_key:
            self._ordered_records = [card for title, card in self._sorted_records if query in title]
            self._filter_key = filter_key
        self.count_label.setRawText(f"{len(self._ordered_records)} / {len(self.cards)} " + translate_text("elem"))
        self._columns = cols
        card_h = CARD_SIZE_PRESETS[self.card_size][1]
        rows = (len(self._ordered_records) + cols - 1) // cols
        self.grid_widget.setMinimumHeight(max(0, rows * (card_h + CARD_SPACING) - CARD_SPACING))
        self.render_visible()

    def render_visible(self, *_args):
        if not self.isVisible():
            return
        card_w, card_h, _, _ = CARD_SIZE_PRESETS[self.card_size]
        indices = visible_range(len(self._ordered_records), self._columns, card_h + CARD_SPACING,
                                self.scroll.verticalScrollBar().value(), self.scroll.viewport().height())
        visible = {self._ordered_records[i] for i in indices}
        for record in self._visible_records - visible:
            record.release()
        for index in indices:
            record = self._ordered_records[index]
            if record.widget is None:
                if self._widget_pool:
                    record.widget = self._widget_pool.pop()
                    record.widget.bind_item(record.item, self.card_size)
                else:
                    record.widget = MediaCard(record.item, self.grid_widget, self.card_size)
                    widget = record.widget
                    widget.clicked.connect(lambda w=widget: self.card_clicked.emit(w.item))
                    self.widget_creations += 1
            record.widget.move((index % self._columns) * (card_w + CARD_SPACING),
                               (index // self._columns) * (card_h + CARD_SPACING))
            record.widget.show()
        self._visible_records = visible

    def recycle_widget(self, widget):
        widget.hide()
        widget.item = {}
        widget.poster_label.clear()
        if len(self._widget_pool) < 64:
            self._widget_pool.append(widget)
        else:
            widget.deleteLater()

    def refresh_visible_states(self):
        for record in self._visible_records:
            if record.widget is not None:
                record.widget.refresh_watched_badge()

    def hideEvent(self, event):
        self.progress_timer.stop()
        for record in self._visible_records:
            record.release()
        self._visible_records.clear()
        super().hideEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.schedule_reflow()

    def showEvent(self, event):
        self.progress_timer.start()
        super().showEvent(event)
        self.schedule_reflow()


# ==========================================
# TMDB TALÁLAT VÁLASZTÓ PÁRBESZÉDABLAK
# ==========================================
class TmdbChoiceDialog(QDialog):
    def __init__(self, parent, results, is_movie):
        super().__init__(parent)
        self.is_movie = is_movie
        self.request_id = 0
        self.current_worker = None
        self.closed = False

        self.setWindowTitle("Videoinformációk lekérése – találatok")
        self.resize(650, 450)

        layout = QVBoxLayout(self)
        if len(results) == 1:
            intro = "A TMDB egyetlen találatot adott. Erősítsd meg, hogy ez a megfelelő:"
        else:
            intro = f"{len(results)} találat érkezett. Válaszd ki a megfelelőt:"
        layout.addWidget(QLabel(intro))

        content = QHBoxLayout()
        self.list_widget = QListWidget()
        for r in results:
            year = (r.get("date") or "")[:4]
            year_str = f" ({year})" if year else ""
            overview = r.get("overview") or ""
            snippet = overview[:100] + ("..." if len(overview) > 100 else "")
            lw_item = QListWidgetItem()
            lw_item.setRawText(f"{r['title']}{year_str} [ID: {r['id']}]\n{snippet}")
            lw_item.setData(Qt.ItemDataRole.UserRole, r)
            self.list_widget.addItem(lw_item)
        content.addWidget(self.list_widget, 2)

        self.preview = QLabel("Nincs kép")
        self.preview.setObjectName("Poster")
        self.preview.setFixedSize(150, 220)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content.addWidget(self.preview, 1, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(content)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.list_widget.itemActivated.connect(lambda _item: self.accept())
        self.list_widget.currentItemChanged.connect(self.update_preview)
        # Csak a bekötés UTÁN állítjuk be, így az első találat előnézete is betöltődik.
        self.list_widget.setCurrentRow(0)

    def selected_result(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def update_preview(self, current, _previous=None):
        self.request_id += 1  # a korábbi, még futó kérések eredményét eldobjuk
        if current is None:
            self.preview.setText("Nincs borító")
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        poster_url = data.get("poster_url")
        if not poster_url:
            self.preview.setText("Nincs borító")
            return

        media_type = "movie" if self.is_movie else "tv"
        cache_path = os.path.join(CACHE_DIR, f"{media_type}_{data['id']}.jpg")
        pixmap = load_pixmap(cache_path, 150, 220)
        if pixmap:
            self.preview.setPixmap(pixmap)
            return

        self.preview.setText("Betöltés...")
        if self.current_worker is not None:
            self.current_worker.requestInterruption()
        worker = PosterLoaderWorker(poster_url, data["id"], self.is_movie, self.request_id)
        worker.poster_loaded.connect(self.on_poster_loaded)
        self.current_worker = worker
        run_worker(worker)

    def on_poster_loaded(self, path, req_id):
        if self.closed or req_id != self.request_id:
            return
        pixmap = load_pixmap(path, 150, 220)
        if pixmap:
            self.preview.setPixmap(pixmap)
        else:
            self.preview.setText("Nincs borító")

    def done(self, result):
        self.closed = True
        if self.current_worker is not None:
            self.current_worker.requestInterruption()
        super().done(result)


# ==========================================
# FŐ ABLAK
# ==========================================
def create_sidebar_action_icon(icon_name):
    """Crisp, consistent vector-like icons for the sidebar action buttons."""
    icon = QIcon()
    colors = {
        QIcon.Mode.Normal: QColor("#B6A9C4" if icon_name == "settings" else "#AAA6B0"),
        QIcon.Mode.Active: QColor("#F08B98" if icon_name == "trash" else "#E4D8F0"),
    }
    for mode, color in colors.items():
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(color, 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.translate(12, 12)

        if icon_name == "settings":
            for angle in range(0, 360, 45):
                painter.save()
                painter.rotate(angle)
                painter.drawLine(0, -7, 0, -10)
                painter.restore()
            painter.drawEllipse(-7, -7, 14, 14)
            painter.drawEllipse(-2, -2, 4, 4)
        elif icon_name == "film":
            painter.drawRoundedRect(-8, -7, 16, 14, 2, 2)
            painter.drawLine(-4, -7, -4, 7)
            painter.drawLine(4, -7, 4, 7)
            for y in (-3, 3):
                painter.drawLine(-8, y, -4, y)
                painter.drawLine(4, y, 8, y)
        elif icon_name == "tv":
            painter.drawRoundedRect(-9, -6, 18, 12, 2, 2)
            painter.drawLine(-4, 9, 4, 9)
            painter.drawLine(0, 6, 0, 9)
        elif icon_name == "downloads":
            painter.drawLine(0, -9, 0, 3)
            painter.drawLine(-4, -1, 0, 3)
            painter.drawLine(0, 3, 4, -1)
            painter.drawLine(-7, 3, -7, 8)
            painter.drawLine(-7, 8, 7, 8)
            painter.drawLine(7, 8, 7, 3)
        elif icon_name == "trash":
            painter.drawLine(-7, -6, 7, -6)
            painter.drawLine(-3, -9, 3, -9)
            painter.drawRoundedRect(-5, -4, 10, 13, 1.5, 1.5)
            painter.drawLine(-2, -1, -2, 6)
            painter.drawLine(2, -1, 2, 6)

        painter.end()
        icon.addPixmap(pixmap, mode, QIcon.State.Off)
    return icon


class DSVideoWindow(QMainWindow):
    playback_state_changed = pyqtSignal(str)
    SAVE_TEXT = "Videoinformációk mentése és frissítés"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"SynoStream {APP_VERSION}")
        if os.path.isfile(APP_ICON_FILE):
            self.setWindowIcon(QApplication.instance().windowIcon())
        # Establish frameless chrome before any native geometry/state restoration.
        application = QApplication.instance()
        if application is not None:
            application._synostream_chrome.apply(self)
        self.resize(1100, 700)
        saved_geometry = config.get("window_geometry", "")
        if saved_geometry:
            try:
                from synostream_window_chrome import restore_desktop_geometry
                if not restore_desktop_geometry(self, QByteArray.fromHex(saved_geometry.encode("ascii"))):
                    LOGGER.warning("Az elmentett ablakméretet nem sikerült visszaállítani.")
            except (AttributeError, TypeError, ValueError):
                LOGGER.warning("Az elmentett ablakgeometria hibás; alapértelmezett méret használata.")

        # Older saved Qt geometries can contain both maximized and fullscreen.
        # The library is a desktop window: restore size/maximization, never an
        # immersive or minimized state that hides its title bar/taskbar.
        restored_state = self.windowState()
        desktop_state = restored_state & ~(Qt.WindowState.WindowFullScreen | Qt.WindowState.WindowMinimized)
        if restored_state != desktop_state:
            self.setWindowState(desktop_state)
            LOGGER.info("Az elmentett teljes képernyős/kis méretű állapot helyett asztali ablak nyílik.")

        self.scan_item_queue = deque()
        self._pending_scan_errors = None
        self._scanner_finished_waiting = False
        self._scan_next_repaint = 0
        self.scan_item_timer = QTimer(self)
        self.scan_item_timer.setSingleShot(True)
        self.scan_item_timer.timeout.connect(self.drain_scan_items)
        self.download_notice_timer = QTimer(self)
        self.download_notice_timer.setSingleShot(True)
        self.download_notice_timer.timeout.connect(lambda: self.statusBar().hide())
        self.download_refresh_targets = deque()
        self.scanner_thread = None
        self.pending_scan = False
        self.pending_scan_library = None
        self.pending_scan_force_remote_refresh = False
        self.scanner_scope = None
        self.scanner_tmdb_language = current_tmdb_language()
        self.scan_seen_paths = {}
        self.scan_page_keys = []
        self.current_library_key = "movies"
        self.is_closing = False
        self.scan_errors = []
        self.close_timer = None
        self.pending_override = None
        self.library_metadata_language = {}

        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- oldalsáv ---
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(190)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)

        logo_label = QLabel()
        logo_label.setObjectName("Logo")
        logo_label.setTextFormat(Qt.TextFormat.RichText)
        logo_label.setText(
            '<span style="color:#f0edf5; font-weight:600;">Syno</span>'
            '<span style="color:#AA9BB9; font-weight:400;">Stream</span>'
        )
        sidebar_layout.addWidget(logo_label)

        self.library_buttons = {}
        self.library_pages = {}
        self.library_nav_rows = {}
        self.library_nav_widget = QWidget()
        self.library_nav_layout = QVBoxLayout(self.library_nav_widget)
        self.library_nav_layout.setContentsMargins(0, 0, 0, 0)
        self.library_nav_layout.setSpacing(4)
        self.btn_movies = self.create_sidebar_btn("Filmek", True)
        self.btn_shows = self.create_sidebar_btn("TV Műsorok", False)
        self.btn_movies.setIcon(create_sidebar_action_icon("film"))
        self.btn_shows.setIcon(create_sidebar_action_icon("tv"))
        self.library_buttons["movies"] = self.btn_movies
        self.library_buttons["shows"] = self.btn_shows
        self.library_nav_layout.addWidget(self.btn_movies)
        self.library_nav_layout.addWidget(self.btn_shows)
        self.btn_add_library = QPushButton("+ Új médiatár")
        self.btn_add_library.setProperty("class", "SidebarBtn")
        self.btn_add_library.setToolTip("Új médiatár hozzáadása")
        self.btn_add_library.setFixedHeight(38)
        self.btn_add_library.clicked.connect(self.create_custom_library)
        self.library_nav_layout.addWidget(self.btn_add_library)
        sidebar_layout.addWidget(self.library_nav_widget)
        self.btn_paths = self.create_sidebar_btn("Forrásmappák", False, checkable=False)
        self.btn_paths.clicked.connect(self.manage_paths)
        sidebar_layout.addStretch(1)
        sidebar_layout.addSpacing(20)
        self.btn_downloads = self.create_sidebar_btn("Letöltések", False)
        self.btn_downloads.setIcon(create_sidebar_action_icon("downloads"))
        self.btn_downloads.clicked.connect(self.show_downloads)
        sidebar_layout.addWidget(self.btn_downloads)
        sidebar_layout.addSpacing(20)

        self.btn_library_status = self.create_sidebar_btn("Médiatár állapota", False, checkable=False)
        self.btn_library_status.clicked.connect(self.show_library_status)
        self.btn_scan_errors = self.create_sidebar_btn("Beolvasási hibanapló", False, checkable=False)
        self.btn_scan_errors.clicked.connect(self.open_scan_error_log)
        self.btn_tmdb = self.create_sidebar_btn("TMDB kulcs", False, checkable=False)
        self.btn_tmdb.clicked.connect(self.configure_tmdb)
        self.btn_tmdb.setToolTip("TMDB API-kulcs megadása.")
        self.btn_qc_remote = self.create_sidebar_btn("NAS-kapcsolat beállítása", False, checkable=False)
        self.btn_qc_remote.clicked.connect(self.open_remote_quickconnect)
        self.btn_qc_remote.setToolTip("Egy NAS, automatikus kapcsolódás: helyi hálózat → DDNS → QuickConnect.")
        self.btn_qc_test = self.create_sidebar_btn("QuickConnect teszt", False, checkable=False)
        self.btn_qc_test.clicked.connect(self.open_quickconnect_test)
        self.btn_qc_test.setToolTip("Ellenőrzi, hogy a NAS DSM API-ja elérhető-e közvetlenül QuickConnecten keresztül.")
        self.status_lbl = QLabel("")
        self.status_lbl.setObjectName("StatusLabel")
        self.status_lbl.setWordWrap(True)
        self.settings_dialog = QDialog(self)
        self.settings_dialog.setWindowTitle("Beállítások")
        self.settings_dialog.setMinimumWidth(440)
        self.settings_dialog.resize(520, 680)
        self.settings_dialog.setStyleSheet("""
            QDialog { background-color: #181818; color: #eeeeee; border: 1px solid #39363D; }
            QGroupBox {
                color: #d8d1e5;
                font-weight: 600;
                border: 1px solid #403B45;
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px 6px 6px 6px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #B7A9C8; }
        """)
        settings_outer_layout = QVBoxLayout(self.settings_dialog)
        settings_outer_layout.setContentsMargins(12, 12, 12, 12)
        settings_scroll = QScrollArea(self.settings_dialog)
        settings_scroll.setWidgetResizable(True)
        settings_content = QWidget()
        settings_scroll.setWidget(settings_content)
        settings_outer_layout.addWidget(settings_scroll, 1)
        settings_layout = QVBoxLayout(settings_content)
        settings_layout.setContentsMargins(10, 8, 10, 8)
        settings_layout.setSpacing(12)
        settings_title = QLabel("Beállítások")
        settings_title.setObjectName("PageTitle")
        settings_layout.addWidget(settings_title)
        settings_description = QLabel("Médiatárak, lejátszás, metaadatok és NAS-kapcsolat kezelése")
        settings_description.setObjectName("InfoLabel")
        settings_layout.addWidget(settings_description)

        language_settings = QGroupBox("Nyelv")
        language_form = QFormLayout(language_settings)
        self.language_combo = QComboBox()
        self.language_combo.addItem("Magyar", "hu")
        self.language_combo.addItem("English", "en")
        language_index = self.language_combo.findData(config.get("language", "hu"))
        self.language_combo.setCurrentIndex(language_index if language_index >= 0 else 0)
        language_form.addRow("Nyelv:", self.language_combo)
        self.language_combo.currentIndexChanged.connect(self.change_ui_language)
        settings_layout.addWidget(language_settings)

        startup_settings = QGroupBox("Indulás és megjelenés")
        startup_form = QFormLayout(startup_settings)
        self.startup_scan_combo = QComboBox()
        self.startup_scan_combo.addItem("Utoljára használt médiatár", "current")
        self.startup_scan_combo.addItem("Minden médiatár", "all")
        self.startup_scan_combo.addItem("Ne frissítsen induláskor", "none")
        startup_index = self.startup_scan_combo.findData(config.get("startup_scan_mode", "current"))
        self.startup_scan_combo.setCurrentIndex(startup_index if startup_index >= 0 else 0)
        startup_form.addRow("Induláskori frissítés:", self.startup_scan_combo)
        self.library_refresh_combo = QComboBox()
        for label, value in (("Kikapcsolva",0),("1 perc",1),("5 perc",5),("15 perc",15),("30 perc",30)):
            self.library_refresh_combo.addItem(label,value)
        self.library_refresh_combo.setCurrentIndex(max(0,self.library_refresh_combo.findData(config.get('library_refresh_minutes',5))))
        startup_form.addRow("Háttérbeli tartalomellenőrzés:",self.library_refresh_combo)
        self.card_size_combo = QComboBox()
        self.card_size_combo.addItem("Kompakt", "compact")
        self.card_size_combo.addItem("Normál", "normal")
        self.card_size_combo.addItem("Nagy", "large")
        card_size_index = self.card_size_combo.findData(config.get("card_size", "normal"))
        self.card_size_combo.setCurrentIndex(card_size_index if card_size_index >= 0 else 1)
        self.card_size_combo.currentIndexChanged.connect(self.apply_card_size_setting)
        startup_form.addRow("Kártyaméret:", self.card_size_combo)
        startup_note = QLabel(
            "Az induláskori frissítés módja a program következő indításakor lép életbe. "
            "A „Ne frissítsen induláskor” mód betölti a korábbi listákat, de nem ellenőrzi a NAS-t; "
            "a frissítés ikonnal indíthatod el az ellenőrzést."
        )
        startup_note.setWordWrap(True)
        startup_note.setStyleSheet("color: #999999;")
        startup_form.addRow(startup_note)
        settings_layout.addWidget(startup_settings)

        library_settings = QGroupBox("Médiatár és adatok")
        library_settings_layout = QVBoxLayout(library_settings)
        library_settings_layout.setContentsMargins(4, 8, 4, 4)
        library_settings_layout.addWidget(self.btn_library_status)
        library_settings_layout.addWidget(self.btn_scan_errors)
        library_settings_layout.addWidget(self.btn_tmdb)
        library_settings_layout.addWidget(self.btn_paths)
        excluded_button = QPushButton("Kihagyott fájlok és műsorok")
        excluded_button.clicked.connect(self.manage_excluded_media)
        library_settings_layout.addWidget(excluded_button)
        settings_layout.addWidget(library_settings)

        recommendation_settings = QGroupBox("Ajánló")
        recommendation_layout = QVBoxLayout(recommendation_settings)
        self.recommendation_hungarian_check = QCheckBox("Magyar adatlapok előnyben")
        self.recommendation_hungarian_check.setChecked(config.get("recommendation_prefer_hungarian", True))
        recommendation_layout.addWidget(self.recommendation_hungarian_check)
        recommendation_note = QLabel("A TMDB-n magyar leírással rendelkező ajánlások nagyobb eséllyel kerülnek a válogatás elejére. Más címek is megjelenhetnek. Ez nem igazolja a magyar szinkront.")
        recommendation_note.setWordWrap(True)
        recommendation_layout.addWidget(recommendation_note)
        settings_layout.addWidget(recommendation_settings)

        nas_settings = QGroupBox("NAS-kapcsolat")
        nas_settings_layout = QVBoxLayout(nas_settings)
        nas_settings_layout.setContentsMargins(4, 8, 4, 4)
        nas_settings_layout.addWidget(self.btn_qc_remote)
        self.btn_qc_test.hide()
        nas_settings_layout.addWidget(self.status_lbl)
        settings_layout.addWidget(nas_settings)

        pairing_settings = QGroupBox("Hordozható médiapárosítások")
        pairing_layout = QVBoxLayout(pairing_settings)
        pairing_info = QLabel("A kézi párosításokat a médiatár gyökerének .synostream mappája tárolja. Másik gépen ugyanazt a médiatárgyökeret válaszd ki, majd frissítsd a médiatárat.")
        pairing_info.setWordWrap(True)
        pairing_layout.addWidget(pairing_info)
        self.portable_notice = QLabel("A párosítások szinkronizálása a következő frissítéskor indul.")
        self.portable_notice.setWordWrap(True)
        self.portable_notice.setTextFormat(Qt.TextFormat.PlainText)
        pairing_layout.addWidget(self.portable_notice)
        self.portable_sync_button = QPushButton("Párosítások szinkronizálása")
        self.portable_sync_button.clicked.connect(lambda: self.sync_shared_pairings(True))
        pairing_layout.addWidget(self.portable_sync_button)
        settings_layout.addWidget(pairing_settings)
        self._pairing_sync_running = False
        self._pairing_sync_again = False
        self._pairing_rescan_requested = False

        playback_settings = QGroupBox("Lejátszás")
        playback_settings_layout = QVBoxLayout(playback_settings)
        playback_settings_layout.setContentsMargins(12, 10, 12, 10)
        playback_form = QFormLayout()
        audio_options = QWidget()
        audio_options_layout = QHBoxLayout(audio_options)
        audio_options_layout.setContentsMargins(0, 0, 0, 0)
        self.audio_hungarian_check = QCheckBox("Magyar")
        self.audio_original_check = QCheckBox("Eredeti")
        audio_preference = config.get("preferred_audio_language", "original")
        self.audio_hungarian_check.setChecked(audio_preference == "hu")
        self.audio_original_check.setChecked(audio_preference == "original")
        self.audio_hungarian_check.toggled.connect(
            lambda checked: self.audio_original_check.setChecked(False) if checked else None
        )
        self.audio_original_check.toggled.connect(
            lambda checked: self.audio_hungarian_check.setChecked(False) if checked else None
        )
        audio_options_layout.addWidget(self.audio_hungarian_check)
        audio_options_layout.addWidget(self.audio_original_check)
        audio_options_layout.addStretch(1)
        playback_form.addRow("Preferált audio nyelv:", audio_options)

        subtitle_options = QWidget()
        subtitle_options_layout = QHBoxLayout(subtitle_options)
        subtitle_options_layout.setContentsMargins(0, 0, 0, 0)
        self.subtitle_hungarian_check = QCheckBox("Magyar")
        self.subtitle_original_check = QCheckBox("Eredeti")
        self.subtitle_off_check = QCheckBox("Kikapcsolva")
        subtitle_preference = config.get("preferred_subtitle_language", "hu")
        self.subtitle_hungarian_check.setChecked(subtitle_preference == "hu")
        self.subtitle_original_check.setChecked(subtitle_preference == "original")
        self.subtitle_off_check.setChecked(subtitle_preference == "none")
        subtitle_choices = (
            self.subtitle_hungarian_check, self.subtitle_original_check, self.subtitle_off_check,
        )
        for checkbox in subtitle_choices:
            checkbox.toggled.connect(
                lambda checked, selected=checkbox, choices=subtitle_choices:
                    [choice.setChecked(False) for choice in choices if checked and choice is not selected]
            )
        subtitle_options_layout.addWidget(self.subtitle_hungarian_check)
        subtitle_options_layout.addWidget(self.subtitle_original_check)
        subtitle_options_layout.addWidget(self.subtitle_off_check)
        subtitle_options_layout.addStretch(1)
        playback_form.addRow("Preferált felirat nyelv:", subtitle_options)
        self.playback_fullscreen_check = QCheckBox("Lejátszás teljes képernyőn")
        self.playback_fullscreen_check.setChecked(bool(config.get("playback_fullscreen", False)))
        playback_form.addRow(self.playback_fullscreen_check)
        self.auto_play_next_check = QCheckBox("Következő epizód automatikus indítása")
        self.auto_play_next_check.setChecked(bool(config.get("auto_play_next_episode", True)))
        playback_form.addRow(self.auto_play_next_check)
        playback_settings_layout.addLayout(playback_form)
        playback_note = QLabel(
            "Az „Eredeti” a TMDB által megadott eredeti nyelvet részesíti előnyben; "
            "ha a nyelv nem ismert vagy nincs ilyen sáv, a lejátszó alapértelmezett választása érvényes. "
            "Ha egyik feliratjelölő sincs bepipálva, az MPV választ."
        )
        playback_note.setWordWrap(True)
        playback_note.setStyleSheet("color: #999999;")
        playback_settings_layout.addWidget(playback_note)
        settings_layout.addWidget(playback_settings)

        maintenance_settings = QGroupBox("Karbantartás és mentés")
        maintenance_settings_layout = QVBoxLayout(maintenance_settings)
        maintenance_settings_layout.setContentsMargins(12, 10, 12, 10)
        maintenance_note = QLabel(
            "A sikeres médiatár-beolvasás takarítja az árva médiaadatokat és plakátokat. "
            f"A plakátcache legfeljebb {MAX_POSTER_CACHE_BYTES // (1024 * 1024)} MB; "
            "a régebben használt képek törlődnek először."
        )
        maintenance_note.setWordWrap(True)
        maintenance_note.setStyleSheet("color: #999999;")
        maintenance_settings_layout.addWidget(maintenance_note)
        clear_poster_cache_btn = QPushButton("Plakátcache ürítése")
        clear_poster_cache_btn.clicked.connect(self.clear_poster_cache)
        maintenance_settings_layout.addWidget(clear_poster_cache_btn)
        clear_tmdb_cache_btn = QPushButton("TMDB-adatcache ürítése")
        clear_tmdb_cache_btn.clicked.connect(self.clear_tmdb_metadata_cache)
        maintenance_settings_layout.addWidget(clear_tmdb_cache_btn)
        export_backup_btn = QPushButton("Beállítások és adatbázis mentése…")
        export_backup_btn.clicked.connect(self.export_backup)
        maintenance_settings_layout.addWidget(export_backup_btn)
        import_backup_btn = QPushButton("Mentés visszaállítása…")
        import_backup_btn.clicked.connect(self.import_backup)
        maintenance_settings_layout.addWidget(import_backup_btn)
        settings_layout.addWidget(maintenance_settings)

        save_settings_button = QPushButton("Beállítások mentése")
        save_settings_button.clicked.connect(self.save_playback_preferences)
        settings_layout.addWidget(save_settings_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.updater = UpdateController(self, APP_VERSION, lambda: config, save_config, run_worker, BASE_DIR, lambda: UI_LANGUAGE)
        settings_layout.addWidget(self.updater.settings_group())
        about_settings = QGroupBox("Névjegy")
        about_settings_layout = QVBoxLayout(about_settings)
        about_settings_layout.setContentsMargins(12, 10, 12, 10)
        about_app_name = QLabel("SynoStream")
        about_app_name.setStyleSheet("font-size: 18px; font-weight: 600; color: #f0edf5;")
        about_settings_layout.addWidget(about_app_name)
        about_settings_layout.addWidget(QLabel(f"Verzió: {APP_VERSION}"))
        about_settings_layout.addWidget(QLabel("Kiadás: Nyilvános kiadás"))
        about_settings_layout.addWidget(QLabel("Copyright © 2026 Lőrincz László"))
        about_settings_layout.addWidget(QLabel("Licenc: GNU GPL-3.0-only"))
        legal_notice = QLabel(
            "A program a GNU GPL-3.0-only licenc alatt érhető el. A licenc ismerteti a használat, "
            "módosítás és továbbadás feltételeit, valamint a jótállás kizárását. "
            "A teljes szöveg a jogi tájékoztatóban olvasható."
        )
        legal_notice.setWordWrap(True)
        about_settings_layout.addWidget(legal_notice)
        license_button = QPushButton("Licenc és jogi tájékoztató megtekintése")
        license_button.clicked.connect(self.show_license_info)
        about_settings_layout.addWidget(license_button)
        about_description = QLabel("Médiatár-kezelő és lejátszó NAS-on tárolt műsorokhoz.")
        about_description.setWordWrap(True)
        about_description.setStyleSheet("color: #999999;")
        about_settings_layout.addWidget(about_description)
        settings_layout.addWidget(about_settings)
        settings_layout.addStretch()
        close_settings = QPushButton("Bezárás")
        close_settings.clicked.connect(self.settings_dialog.accept)
        settings_outer_layout.addWidget(close_settings, alignment=Qt.AlignmentFlag.AlignRight)

        self.btn_settings = QPushButton("Beállítások")
        self.btn_settings.setObjectName("SettingsButton")
        self.btn_settings.setIcon(create_sidebar_action_icon("settings"))
        self.btn_settings.setIconSize(QSize(22, 22))
        self.btn_settings.setAccessibleName("Beállítások")
        self.btn_settings.setToolTip("Beállítások")
        self.btn_settings.setFixedHeight(46)
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setStyleSheet("""
            QPushButton#SettingsButton {
                background-color: #24212A;
                color: #D8D2E0;
                border: 1px solid #45404B;
                border-radius: 10px;
                padding: 0 14px;
                text-align: left;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton#SettingsButton:hover {
                background-color: #332D3A;
                color: #F0EAF5;
                border-color: #71627F;
            }
            QPushButton#SettingsButton:pressed {
                background-color: #1D1A22;
                border-color: #8A779A;
            }
        """)
        self.btn_settings.clicked.connect(self.open_settings)
        settings_button_row = QHBoxLayout()
        settings_button_row.setContentsMargins(12, 0, 12, 0)
        settings_button_row.addWidget(self.btn_settings, 1)
        sidebar_layout.addLayout(settings_button_row)

        main_layout.addWidget(self.sidebar)

        # --- oldalak ---
        self.stack = QStackedWidget()
        self.movies_page = MediaPage("Filmek")
        self.shows_page = MediaPage("TV Műsorok")
        self.movies_page.set_card_size(config.get("card_size", "normal"))
        self.shows_page.set_card_size(config.get("card_size", "normal"))
        self.restore_media_page_state(self.movies_page, "movies")
        self.restore_media_page_state(self.shows_page, "shows")
        self.library_pages["movies"] = self.movies_page
        self.library_pages["shows"] = self.shows_page
        self.override_widget = self.create_override_page()
        self.movies_page.card_clicked.connect(self.open_media_detail)
        self.shows_page.card_clicked.connect(self.open_media_detail)
        self.movies_page.refresh_requested.connect(self.refresh_library)
        self.shows_page.refresh_requested.connect(self.refresh_library)
        self.movies_page.recommendations_requested.connect(lambda:self.show_recommendations("movies"))
        self.shows_page.recommendations_requested.connect(lambda:self.show_recommendations("shows"))
        self.stack.addWidget(self.movies_page)
        self.stack.addWidget(self.shows_page)
        self.downloads_page = DownloadPage(SimpleNamespace(
            config=lambda: config, save_config=save_config, task_factory=NasTask,
            run_worker=run_worker, redact=redact_credentials,
            configure_nas=self.open_remote_quickconnect,
            library_destinations=self.download_library_destinations,
        ), self)
        self.downloads_page.completed.connect(self.on_downloads_completed)
        self.stack.addWidget(self.downloads_page)
        for library in config.get("custom_libraries", []):
            self.add_custom_library_ui(library)
        self.library_metadata_language = {
            library_id: None for library_id in self.library_pages
        }
        main_layout.addWidget(self.stack)
        self.setCentralWidget(main_widget)

        self.btn_movies.clicked.connect(lambda: self.switch_library("movies"))
        self.btn_shows.clicked.connect(lambda: self.switch_library("shows"))

        last_library = str(config.get("last_library") or "movies")
        if last_library not in self.library_pages:
            last_library = "movies"
        self.switch_page(
            self.stack.indexOf(self.library_pages[last_library]),
            self.library_buttons[last_library],
        )
        self.migrate_unified_sources()
        self.library_refresh_timer = QTimer(self)
        self.library_refresh_timer.setInterval(60000)
        self._last_inventory_check = time.monotonic()
        self.library_refresh_timer.timeout.connect(self.check_library_changes)
        self.library_refresh_timer.start()
        startup_scan_mode = config.get("startup_scan_mode", "all")
        if startup_scan_mode == "all":
            self.start_library_scan()
        elif startup_scan_mode == "none":
            for library_id, page in self.library_pages.items():
                cached_items = self._cached_page_items(library_id)
                if cached_items:
                    page.replace_items(cached_items)
                    page.set_message("A korábbi lista betöltve; a frissítés ikon ellenőrzi a változásokat.")
                else:
                    page.set_message("Induláskor nem történik beolvasás. A frissítés ikonra kattintva indíthatod el.")
                self.library_metadata_language[library_id] = current_tmdb_language()
            message = "Az utolsó beolvasott listák betöltve; a frissítés ikonnal ellenőrizheted a változásokat."
            self.status_lbl.setText(message)
        else:
            self.start_library_scan(last_library)

    def show_downloads(self):
        for button in self.library_buttons.values():
            button.setChecked(False)
        self.btn_downloads.setChecked(True)
        self.stack.setCurrentWidget(self.downloads_page)

    def download_library_destinations(self, kind=None):
        destinations = []
        for key, button in self.library_buttons.items():
            custom = next((entry for entry in config.get("custom_libraries", []) if entry.get("id") == key), None)
            is_movie = key == "movies" or bool(custom and custom_library_is_movie(custom))
            if kind == "other" or kind == "movies" and not is_movie or kind == "shows" and is_movie:
                continue
            for root in self._library_cache_paths(key):
                if is_remote_path(root):
                    destination = normalize_destination(root)
                    if destination and (button.text(), destination) not in destinations:
                        destinations.append((button.text(), destination))
        return destinations

    def on_downloads_completed(self, tasks):
        if tasks:
            titles = ", ".join(str(task.get("title") or "") for task in tasks[:3])
            bar = self.statusBar()
            bar.setStyleSheet("QStatusBar {background:#1B191F; color:#DDD0EB; padding:5px 12px;} QStatusBar::item {border:0;}")
            bar.showMessage(translate_text("Elkészült letöltés: {titles}").format(titles=titles))
            bar.show()
            self.download_notice_timer.start(12000)
        for task in tasks:
            destination = ((task.get("additional") or {}).get("detail") or {}).get("destination")
            try:
                destination = normalize_destination(destination)
            except (ValueError, AttributeError):
                continue
            if not destination:
                continue
            target = REMOTE_PREFIX + "/" + destination
            for key in self.library_pages:
                if any(is_remote_path(root) and (
                    media_path_is_within(target, root) or media_path_is_within(root, target)
                ) for root in self._library_cache_paths(key)):
                    if key not in self.download_refresh_targets:
                        self.download_refresh_targets.append(key)
        self.start_download_refresh()

    def start_download_refresh(self):
        if self.is_closing or self.scanner_thread is not None:
            return
        while self.download_refresh_targets:
            key = self.download_refresh_targets.popleft()
            if key in self.library_pages:
                self.start_library_scan(key, force_remote_refresh=True)
                return

    def restore_media_page_state(self, page, library_key):
        all_states = config.get("media_view_settings", {})
        state = all_states.get(library_key, {}) if isinstance(all_states, dict) else {}
        if not isinstance(state, dict):
            state = {}
        sort_index = page.sort_criterion.findData(state.get("sort_by", "title"))
        if sort_index >= 0:
            page.sort_criterion.setCurrentIndex(sort_index)
        descending = state.get("descending", False)
        if not isinstance(descending, bool):
            descending = False
        direction_index = page.sort_direction.findData(descending)
        if direction_index >= 0:
            page.sort_direction.setCurrentIndex(direction_index)
        page.sort_criterion.currentIndexChanged.connect(
            lambda _index, key=library_key, target=page: self.save_media_page_state(key, target)
        )
        page.sort_direction.currentIndexChanged.connect(
            lambda _index, key=library_key, target=page: self.save_media_page_state(key, target)
        )

    def save_media_page_state(self, library_key, page):
        states = config.get("media_view_settings", {})
        if not isinstance(states, dict):
            states = {}
        states[library_key] = {
            "sort_by": page.sort_criterion.currentData() or "title",
            "descending": bool(page.sort_direction.currentData()),
        }
        config["media_view_settings"] = states
        ok, error = save_config()
        if not ok:
            LOGGER.error("Nem sikerült menteni a(z) %s médiatár rendezését: %s", library_key, error)

    def create_sidebar_btn(self, text, checked, checkable=True):
        btn = QPushButton(text)
        btn.setProperty("class", "SidebarBtn")
        btn.setCheckable(checkable)
        if checkable:
            btn.setChecked(checked)
        return btn

    @pyqtSlot(str)
    def show_pairing_notice(self, message):
        if self.is_closing:
            return
        self.portable_notice.setText(message)
        self.statusBar().setStyleSheet("QStatusBar {background:#17151C;color:#B7A9C8;border:0;}")
        self.statusBar().showMessage(message, 15000)

    def edit_source_pairs(self):
        libraries = [("movies", "Filmek"), ("shows", "TV Műsorok")]
        libraries.extend((library["id"], library["name"]) for library in config.get("custom_libraries", []))
        dialog = SourcePairsDialog(self, config, libraries, self.save_source_pairs, translate_text)
        dialog.exec()

    def save_source_pairs(self, values, _settings=None, _router=None):
        global config, SECRET_STORE_UNREADABLE
        if (self.scanner_thread is not None or self.pending_override is not None
                or self._pairing_sync_running
                or any(isinstance(worker, SourceResolutionWorker) and worker.isRunning() for worker in _background_workers)
                or any(isinstance(worker, MpvPlaybackMonitor) and worker.isRunning() for worker in _background_workers)):
            raise SourcesBusy("Várd meg a beolvasás, párosításszinkron vagy lejátszás végét az elérések módosítása előtt.")
        pairs = parse_pairs(values)
        old_settings = copy.deepcopy(config)
        old_secret_unreadable = SECRET_STORE_UNREADABLE
        old_router = source_router()
        router = _router or SourceRouter(pairs)
        if _settings is None and [pair.to_dict() for pair in pairs] == config.get("paired_sources", []): return
        updated = _settings if _settings is not None else canonicalize_config(config, router, old_router)
        try:
            with settings_transaction(BASE_DIR, include_database=True):
                with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
                    with conn:
                        migrate_source_database(conn, old_router, router)
                        save_protected_secrets(updated)
                        write_config_atomic(updated)
            config = updated
        except Exception:
            config = old_settings
            SECRET_STORE_UNREADABLE = old_secret_unreadable
            raise
        DISPLAY_STATE_CACHE.clear()
        invalidate_watched_paths_cache()
        for library_id, page in self.library_pages.items():
            page.replace_items(self._cached_page_items(library_id))
        self.statusBar().showMessage(translate_text("A forrásmappák mentve. Frissítsd a médiatárat a kapcsolat ellenőrzéséhez."), 15000)

    def sync_shared_pairings(self, rescan=False):
        if self.is_closing:
            return
        self._pairing_rescan_requested = self._pairing_rescan_requested or rescan
        if getattr(self, '_source_editing', False):
            self._source_sync_deferred = True
            return
        if self._pairing_sync_running:
            self._pairing_sync_again = True
            return
        roots = portable_roots()
        credentials = {key: config.get(key, "") for key in ("quickconnect_id", "nas_username", "nas_password", "nas_direct_url", "nas_local_url", "nas_device_tokens")}
        self._pairing_sync_running = True
        self.portable_sync_button.setEnabled(False)
        self.portable_notice.setText("Szinkronizálás folyamatban…")
        def execute(stop):
            total = dict(imported=0, written=0, pending=0, invalid=0, repaired=0, warnings=[])
            client = None
            try:
                with contextlib.closing(sqlite3.connect(DB_FILE, timeout=30)) as conn:
                    for root in roots:
                        if stop():
                            raise InterruptedError()
                        try:
                            if is_remote_path(root):
                                if client is None:
                                    client = RemoteNASClient(credentials, stop, extra_apis=("SYNO.FileStation.Upload",))
                                resolve_pending_cases(conn, root, client, source_router())
                                backend = portable_pairs.NASBackend(root, client)
                            else:
                                backend = portable_pairs.LocalBackend(root)
                            result = synchronize_portable_root(conn, root, backend, stop, all_roots=roots, verify=bool(rescan or self._pairing_rescan_requested))
                            for key in ("imported", "written", "pending", "invalid", "repaired"):
                                total[key] += result[key]
                            total["warnings"].extend(result["warnings"])
                        except InterruptedError:
                            raise
                        except Exception:
                            total["warnings"].append("unavailable")
            finally:
                if client is not None:
                    client.close()
            return total
        worker = NasTask(execute)
        worker.succeeded.connect(lambda stats: self.show_pairing_notice(portable_summary(stats)))
        worker.failed.connect(lambda _message: self.show_pairing_notice(translate_text("A párosítás helyben mentve. A médiatári közös mentés nem sikerült; frissítéskor újrapróbálom.")))
        def finished():
            self._pairing_sync_running = False
            if self.is_closing:
                return
            self.portable_sync_button.setEnabled(True)
            if self._pairing_sync_again:
                self._pairing_sync_again = False
                QTimer.singleShot(0, self.sync_shared_pairings)
            elif self._pairing_rescan_requested:
                self._pairing_rescan_requested = False
                self.start_library_scan()
        worker.finished.connect(finished)
        run_worker(worker)

    def open_settings(self):
        QTimer.singleShot(0, lambda: set_windows_frame_colors(self.settings_dialog))
        self.settings_dialog.exec()

    def show_license_info(self):
        dialog = QDialog(self.settings_dialog)
        dialog.setWindowTitle("SynoStream – licenc és jogi tájékoztató")
        dialog.resize(760, 680)
        layout = QVBoxLayout(dialog)
        notice = QLabel(
            f"SynoStream {APP_VERSION}\n"
            "Copyright © 2026 Lőrincz László\n\n"
            "A SynoStream a GNU GPL 3.0-only licenc alapján használható, módosítható és továbbadható. "
            "A licenc a szoftver jótállás nélküli terjesztéséről is rendelkezik. "
            "A teljes licencszöveg alább olvasható."
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)

        license_text = QPlainTextEdit(dialog)
        license_text.setReadOnly(True)
        license_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        try:
            with open(LICENSE_FILE, "r", encoding="utf-8") as license_file:
                license_text.setPlainText(license_file.read())
        except OSError:
            license_text.setPlainText(
                "A LICENSE fájl nem található az alkalmazás mappájában. "
                "A hivatalos licenc elérhető itt: https://www.gnu.org/licenses/gpl-3.0.html"
            )
        layout.addWidget(license_text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=dialog)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def clear_poster_cache(self):
        answer = QMessageBox.question(
            self.settings_dialog,
            "Plakátcache ürítése",
            "Törlöd a letöltött plakátképeket? A képek szükség esetén újra letöltődnek.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        removed, errors = clear_poster_cache_files()
        if errors:
            QMessageBox.warning(
                self.settings_dialog,
                "Részleges ürítés",
                f"{removed} plakát törölve, de néhány fájlt nem sikerült törölni:\n" + "\n".join(errors[:8]),
            )
        else:
            QMessageBox.information(self.settings_dialog, "Cache ürítve", f"{removed} plakát törölve.")

    def clear_tmdb_metadata_cache(self):
        answer = QMessageBox.question(
            self.settings_dialog,
            "TMDB-adatcache ürítése",
            "Törlöd a TMDB-részletes adatok gyorsítótárát? A médiatárban tárolt címek, leírások "
            "és kézi párosítások megmaradnak.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
                cursor = conn.execute("DELETE FROM tmdb_metadata_cache")
                removed = max(0, cursor.rowcount)
                conn.commit()
            QMessageBox.information(
                self.settings_dialog, "Cache ürítve", f"{removed} TMDB-adat törölve a gyorsítótárból."
            )
        except sqlite3.Error as exc:
            LOGGER.exception("Nem sikerült üríteni a TMDB-adatcache-t.")
            QMessageBox.critical(self.settings_dialog, "Adatbázishiba", f"Nem sikerült üríteni a cache-t:\n{exc}")

    def export_backup(self):
        default_name = f"SynoStream_backup_{time.strftime('%Y%m%d')}.zip"
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self.settings_dialog,
            "SynoStream mentés helye",
            default_name,
            "SynoStream mentés (*.zip)",
        )
        if not destination:
            return
        if not destination.lower().endswith(".zip"):
            destination += ".zip"
        answer = QMessageBox.question(
            self.settings_dialog,
            "Mentés hitelesítő adatok nélkül",
            "A mentés az adatbázist és a beállításokat tartalmazza, de a TMDB-kulcsot és a NAS-jelszót nem. "
            "Visszaállítás után ezeket újra meg kell adni. Folytatod?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            create_backup_archive(destination)
            QMessageBox.information(self.settings_dialog, "Mentés elkészült", f"A mentés elkészült:\n{destination}")
        except Exception as exc:
            LOGGER.exception("Nem sikerült létrehozni az alkalmazás mentését.")
            QMessageBox.critical(self.settings_dialog, "Mentési hiba", f"Nem sikerült elkészíteni a mentést:\n{exc}")

    def import_backup(self):
        archive_path, _selected_filter = QFileDialog.getOpenFileName(
            self.settings_dialog,
            "SynoStream mentés kiválasztása",
            "",
            "SynoStream mentés (*.zip)",
        )
        if not archive_path:
            return
        answer = QMessageBox.question(
            self.settings_dialog,
            "Mentés visszaállítása",
            "A visszaállítás lecseréli a jelenlegi beállításokat és adatbázist. "
            "A program előtte külön biztonsági másolatot készít a mostani állapotról. Folytatod?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self.running_threads():
            QMessageBox.warning(
                self.settings_dialog,
                "A visszaállítás most nem indítható el",
                "A biztonságos visszaállításhoz előbb várd meg a beolvasások végét, "
                "és zárd be a futó MPV-lejátszást. Ezután próbáld újra.",
            )
            return
        try:
            backups = restore_backup_archive(archive_path)
        except Exception as exc:
            LOGGER.exception("Nem sikerült visszaállítani az alkalmazás mentését.")
            QMessageBox.critical(self.settings_dialog, "Visszaállítási hiba", f"Nem sikerült visszaállítani a mentést:\n{exc}")
            return

        QMessageBox.information(
            self.settings_dialog,
            "Visszaállítás kész",
            "A visszaállítás elkészült. A SynoStream most újraindul, hogy a teljes "
            "felület és az adatbázis az új állapotot használja.\n\n"
            f"A korábbi adatbázis másolata:\n{backups['database_backup']}\n"
            f"A korábbi konfiguráció másolata:\n{backups['config_backup']}",
        )
        try:
            if getattr(sys, "frozen", False):
                command = [sys.executable, *sys.argv[1:]]
            else:
                command = [sys.executable, os.path.abspath(sys.argv[0]), *sys.argv[1:]]
            if "--wait-for-instance" not in command:
                command.append("--wait-for-instance")
            subprocess.Popen(command, cwd=BASE_DIR, close_fds=True)
        except OSError as exc:
            LOGGER.exception("A visszaállítás sikerült, de az alkalmazás automatikus újraindítása nem.")
            QMessageBox.warning(
                self.settings_dialog, "Kézi újraindítás szükséges",
                f"A visszaállítás sikerült, de a SynoStream nem indult újra automatikusan. "
                f"Indítsd el kézzel.\n\nRészlet: {exc}",
            )
            return
        QApplication.quit()

    def save_playback_preferences(self):
        setting_keys = (
            "preferred_audio_language", "preferred_subtitle_language",
            "playback_fullscreen", "auto_play_next_episode",
            "startup_scan_mode", "library_refresh_minutes", "card_size", "recommendation_prefer_hungarian",
        )
        old_settings = {key: config.get(key, DEFAULT_CONFIG[key]) for key in setting_keys}
        config["preferred_audio_language"] = (
            "hu" if self.audio_hungarian_check.isChecked()
            else "original" if self.audio_original_check.isChecked() else "default"
        )
        config["preferred_subtitle_language"] = (
            "hu" if self.subtitle_hungarian_check.isChecked()
            else "original" if self.subtitle_original_check.isChecked()
            else "none" if self.subtitle_off_check.isChecked() else "default"
        )
        config["playback_fullscreen"] = self.playback_fullscreen_check.isChecked()
        config["auto_play_next_episode"] = self.auto_play_next_check.isChecked()
        config["recommendation_prefer_hungarian"] = self.recommendation_hungarian_check.isChecked()
        config["startup_scan_mode"] = self.startup_scan_combo.currentData() or "all"
        config["library_refresh_minutes"] = self.library_refresh_combo.currentData()
        config["card_size"] = self.card_size_combo.currentData() or "normal"
        ok, error = save_config()
        if not ok:
            config.update(old_settings)
            QMessageBox.critical(self.settings_dialog, "Mentési hiba", f"Nem sikerült menteni a beállításokat:\n{error}")
            return
        for page in self.library_pages.values():
            page.set_card_size(config["card_size"])
        QMessageBox.information(self.settings_dialog, "Mentve", "Beállítások mentve.")

    def apply_card_size_setting(self, _index=None):
        card_size = self.card_size_combo.currentData()
        if card_size not in CARD_SIZE_PRESETS:
            return
        previous_size = config.get("card_size", "normal")
        if card_size == previous_size:
            return
        config["card_size"] = card_size
        ok, error = save_config()
        if not ok:
            config["card_size"] = previous_size
            previous_index = self.card_size_combo.findData(previous_size)
            self.card_size_combo.blockSignals(True)
            if previous_index >= 0:
                self.card_size_combo.setCurrentIndex(previous_index)
            self.card_size_combo.blockSignals(False)
            for page in self.library_pages.values():
                page.set_card_size(previous_size)
            QMessageBox.critical(
                self.settings_dialog, "Mentési hiba",
                f"Nem sikerült menteni a kártyaméretet:\n{error}",
            )
            return
        for page in self.library_pages.values():
            page.set_card_size(card_size)

    def change_ui_language(self, _index=None):
        selected_language = self.language_combo.currentData()
        selected_language = "en" if selected_language == "en" else "hu"
        previous_language = config.get("language", "hu")
        if selected_language == previous_language:
            return
        config["language"] = selected_language
        ok, error = save_config()
        if not ok:
            config["language"] = previous_language
            set_ui_language(previous_language)
            retranslate_ui()
            old_index = self.language_combo.findData(previous_language)
            if old_index >= 0:
                blocked = self.language_combo.blockSignals(True)
                self.language_combo.setCurrentIndex(old_index)
                self.language_combo.blockSignals(blocked)
            QMessageBox.warning(
                self.settings_dialog,
                "Mentési hiba",
                f"Nem sikerült menteni a beállításokat:\n{error}",
            )
            return
        set_ui_language(selected_language)
        retranslate_ui()
        # Refresh only the open library now. Other libraries are refreshed when
        # selected, avoiding a language switch that scans every library at once.
        self.start_library_scan(self.current_library_key)

    def switch_page(self, index, active_btn):
        self.btn_downloads.setChecked(False)
        for btn in self.library_buttons.values():
            btn.setChecked(btn is active_btn)
        self.current_library_key = next(
            (key for key, button in self.library_buttons.items() if button is active_btn),
            "movies",
        )
        self.stack.setCurrentIndex(index)
        if config.get("last_library") != self.current_library_key:
            config["last_library"] = self.current_library_key
            ok, error = save_config()
            if not ok:
                LOGGER.error("Nem sikerült menteni az utoljára megnyitott médiatárat: %s", error)

    def persist_watched_state(self, file_path, media_title, episode_title, poster, is_movie, watched):
        set_playback_watched(file_path, media_title, episode_title, poster, is_movie, watched)
        self.refresh_watched_badges_for_paths([file_path])

    @pyqtSlot(str)
    def on_playback_watched(self, file_path):
        self.refresh_watched_badges_for_paths([file_path])

    def persist_watched_states(self, entries, watched):
        set_playback_watched_many(entries, watched)
        self.refresh_watched_badges_for_paths(entry.get("path", "") for entry in entries)

    def refresh_watched_badges_for_paths(self, file_paths):
        file_paths = list(file_paths)
        changed_prefixes = set()
        for path in file_paths:
            if path:
                changed_prefixes.update(watched_path_prefixes(path))
        for page in self.library_pages.values():
            for _title, card in page.cards:
                roots = card.item.get("episode_roots") or [card.item.get("file_path", "")]
                if any(
                    root and normalize_media_path(root) in changed_prefixes
                    for root in roots
                ):
                    card.refresh_watched_badge()
        for path in file_paths:
            if path:
                self.playback_state_changed.emit(path)

    def add_custom_library_ui(self, library):
        library_id = library["id"]
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        button = self.create_sidebar_btn(library["name"], False)
        delete_button = QPushButton()
        delete_button.setObjectName("DeleteLibraryButton")
        delete_button.setIcon(create_sidebar_action_icon("trash"))
        delete_button.setIconSize(QSize(18, 18))
        delete_button.setAccessibleName(f"{library['name']} médiatár törlése")
        delete_button.setToolTip(f"{library['name']} médiatár törlése")
        delete_button.setFixedSize(36, 36)
        delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_button.setStyleSheet(
            "QPushButton#DeleteLibraryButton { background: #29272D; border: 1px solid #403C44; border-radius: 9px; padding: 0; }"
            "QPushButton#DeleteLibraryButton:hover { background: #3A2B30; border-color: #79535B; }"
            "QPushButton#DeleteLibraryButton:pressed { background: #241C20; border-color: #A16570; }"
        )
        row_layout.addWidget(button, 1)
        row_layout.addWidget(delete_button)
        self.library_buttons[library_id] = button
        self.library_nav_rows[library_id] = row
        self.library_nav_layout.insertWidget(self.library_nav_layout.count() - 1, row)
        delete_button.clicked.connect(lambda _checked=False, lid=library_id: self.delete_custom_library(lid))
        page = MediaPage(f"{library['name']} Műsortár")
        page.set_card_size(config.get("card_size", "normal"))
        self.restore_media_page_state(page, library_id)
        page.card_clicked.connect(self.open_media_detail)
        page.refresh_requested.connect(self.refresh_library)
        page.recommendations_requested.connect(lambda lid=library_id:self.show_recommendations(lid))
        self.library_pages[library_id] = page
        self.stack.addWidget(page)
        button.clicked.connect(lambda _checked=False, lid=library_id: self.switch_library(lid))
        return page

    def switch_library(self, library_id):
        page = self.library_pages.get(library_id)
        button = self.library_buttons.get(library_id)
        if page is not None and button is not None:
            self.switch_page(self.stack.indexOf(page), button)
            if self.library_metadata_language.get(library_id) != current_tmdb_language():
                self.start_library_scan(library_id)

    def delete_custom_library(self, library_id):
        if self.scanner_thread is not None:
            QMessageBox.information(
                self, translate_text("A beolvasás még folyamatban van"),
                translate_text("Várd meg a médiatárak beolvasásának végét, majd próbáld újra a törlést."),
            )
            return

        libraries = config.get("custom_libraries", [])
        index = next((i for i, lib in enumerate(libraries) if lib.get("id") == library_id), None)
        if index is None:
            return
        library = libraries[index]
        answer = QMessageBox.question(
            self, "Médiatár törlése",
            f"Biztosan törlöd a(z) „{library['name']}” médiatárat?\n\n"
            "A beállítás és a médiatár útvonalai törlődnek, a videófájlok nem.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        old_config = copy.deepcopy(config)
        configured_library_paths = library.get("paths", [])
        if not isinstance(configured_library_paths, list):
            configured_library_paths = []
        library_roots = [
            normalize_media_path(path)
            for path in configured_library_paths
            if isinstance(path, str) and path.strip()
        ]
        libraries.pop(index)
        config["paired_sources"] = [
            pair for pair in config.get("paired_sources", [])
            if pair.get("library_id", "movies") != library_id
        ]
        manual_groups = config.get("manual_show_groups", [])
        if isinstance(manual_groups, list):
            retained_groups = []
            for group in manual_groups:
                if not isinstance(group, dict):
                    retained_groups.append(group)
                    continue
                group_library_id = str(group.get("library_id") or "")
                if group_library_id == library_id:
                    continue
                if group_library_id:
                    retained_groups.append(group)
                    continue

                paths = group.get("paths", [])
                if not isinstance(paths, list):
                    retained_groups.append(group)
                    continue
                remaining_paths = [
                    path for path in paths
                    if not isinstance(path, str) or not any(
                        media_path_is_within(normalize_media_path(path), root)
                        for root in library_roots if root
                    )
                ]
                if not remaining_paths:
                    continue
                if len(remaining_paths) != len(paths):
                    retained_group = dict(group)
                    retained_group["paths"] = remaining_paths
                    retained_groups.append(retained_group)
                else:
                    retained_groups.append(group)
            config["manual_show_groups"] = retained_groups

        for state_key in ("media_view_settings", "library_scan_state"):
            state = config.get(state_key, {})
            if isinstance(state, dict):
                state = dict(state)
                state.pop(library_id, None)
                config[state_key] = state
        if config.get("last_library") == library_id:
            config["last_library"] = "movies"

        ok, error = save_config()
        if not ok:
            config.clear()
            config.update(old_config)
            QMessageBox.critical(self, "Mentési hiba", f"Nem sikerült törölni a médiatárat:\n{error}")
            return
        try:
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
                conn.execute("DELETE FROM library_card_cache WHERE library_id = ?", (library_id,))
                conn.execute("DELETE FROM scan_directory_cache WHERE library_id = ?", (library_id,))
                for table in ('recommendation_cache', 'recommendation_feedback', 'recommendation_seen'):
                    conn.execute('DELETE FROM ' + table + ' WHERE library_id=?', (library_id,))
                conn.commit()
        except sqlite3.Error:
            LOGGER.exception("Nem sikerült törölni a(z) %s médiatár beolvasási gyorsítótárát.", library_id)

        if self.current_library_key == library_id:
            self.switch_page(self.stack.indexOf(self.movies_page), self.btn_movies)
        page = self.library_pages.pop(library_id, None)
        row = self.library_nav_rows.pop(library_id, None)
        self.library_buttons.pop(library_id, None)
        if page is not None:
            self.stack.removeWidget(page)
            page.deleteLater()
        if row is not None:
            self.library_nav_layout.removeWidget(row)
            row.deleteLater()

    def create_custom_library(self):
        name, accepted = QInputDialog.getText(self, "Új médiatár", "Médiatár neve:")
        if not accepted:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Hiányzó név", "Adj meg egy nevet a médiatárnak.")
            return
        reserved_names = {"filmek", "tv műsorok"}
        if name.casefold() in reserved_names or any(
            lib.get("name", "").casefold() == name.casefold()
            for lib in config.get("custom_libraries", [])
        ):
            QMessageBox.warning(self, "Már létezik", "Ezzel a névvel már van médiatár.")
            return

        type_dialog = QMessageBox(self)
        type_dialog.setIcon(QMessageBox.Icon.Question)
        type_dialog.setWindowTitle(translate_text("Médiatár típusa"))
        type_dialog.setText(translate_text("Mit tartalmaz ez a médiatár?"))
        movies_button = type_dialog.addButton(
            translate_text("Filmek"), QMessageBox.ButtonRole.AcceptRole
        )
        shows_button = type_dialog.addButton(
            translate_text("TV Műsorok"), QMessageBox.ButtonRole.ActionRole
        )
        type_dialog.addButton(translate_text("Mégse"), QMessageBox.ButtonRole.RejectRole)
        type_dialog.exec()
        selected_type = type_dialog.clickedButton()
        if selected_type is movies_button:
            media_type = "movies"
        elif selected_type is shows_button:
            media_type = "shows"
        else:
            return

        library = {
            "id": uuid.uuid4().hex, "name": name,
            "media_type": media_type, "paths": [],
        }

        if not self.manage_paths(new_library=library):
            return

        page = self.add_custom_library_ui(library)
        page.set_message("A médiatár létrejött. Beolvasás folyamatban…")
        self.switch_page(self.stack.indexOf(page), self.library_buttons[library["id"]])
        self.start_library_scan(library["id"])

    def configure_tmdb(self):
        """TMDB-kulcs megadása és a korábbi metaadat-cache újraépítése."""
        value, ok = QInputDialog.getText(
            self,
            "TMDB API-kulcs",
            "Illeszd be a TMDB API Read Access Token / API-kulcs értékét.\n"
            "A kulcs a Windows-fiókodhoz kötött DPAPI-védelemmel kerül mentésre:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        value = value.strip()
        if not value:
            QMessageBox.warning(self, "Hiányzó kulcs", "Nem adtál meg TMDB API-kulcsot.")
            return
        config["tmdb_api_key"] = value
        saved, error = save_config()
        if not saved:
            QMessageBox.critical(self, "Mentési hiba", f"Nem sikerült elmenteni a kulcsot:\n{error}")
            return
        # Új kulcsnál vagy kifejezett újratöltésnél a korábbi, hiányos metaadatok
        # ne akadályozzák a plakátok/leírások ismételt lekérését.
        try:
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
                conn.execute("DELETE FROM media_cache")
                conn.commit()
        except sqlite3.Error as exc:
            QMessageBox.warning(self, "Adatbázis hiba", f"A kulcs mentve, de a metaadat-cache nem törölhető:\n{exc}")
        self.start_library_scan()
        QMessageBox.information(
            self,
            "TMDB beállítva",
            "A kulcs el lett mentve, a műsortár újra lekéri a címeket, leírásokat és plakátokat.\n"
            "A letöltés az internetkapcsolattól és a találatok számától függően eltarthat egy ideig."
        )

    # --- médiamappák kezelése ---
    def browse_source_local(self, parent):
        return QFileDialog.getExistingDirectory(
            parent, translate_text("Mappa kiválasztása"), local_media_browse_directory(),
            QFileDialog.Option.ShowDirsOnly,
        )

    def browse_source_nas(self, parent):
        dialog = RemoteQuickConnectDialog(parent, folder_picker=True)
        try:
            # Reuse saved credentials, without requiring users to log in again.
            if (config.get("quickconnect_id") or config.get("nas_direct_url") or config.get("nas_local_url")) and all(config.get(key) for key in ("nas_username", "nas_password")):
                QTimer.singleShot(0, dialog.connect_nas)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                return dialog.selected_folder
            return None
        finally:
            dialog.deleteLater()

    def manage_paths(self, _checked=False, new_library=None):
        libraries = [("movies", translate_text("Filmek")), ("shows", translate_text("TV Műsorok"))]
        libraries.extend((lib["id"], lib["name"]) for lib in config.get("custom_libraries", []))
        if new_library: libraries.append((new_library["id"], new_library["name"]))
        try:
            records = records_from_settings(config, libraries)
        except ValueError as error:
            QMessageBox.warning(self, "Forrásmappák", str(error))
            return False
        def save(records):
            if new_library and not any(row['library_id'] == new_library['id'] for row in records):
                raise ValueError("Válassz legalább egy mappát az új médiatárhoz.")
            self.save_library_sources(records, new_library)
        dialog = SourceFoldersDialog(self, records, libraries, save,
            self.browse_source_local, self.browse_source_nas, translate_text,
            selected=new_library['id'] if new_library else self.current_library_key,
            edit_menu=_install_localized_edit_context_menu, text_prompt=QInputDialog.getText, settings=lambda: config)
        try:
            self._source_editing = True
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
        finally:
            self._source_editing = False
            dialog.deleteLater()
        deferred_scan = getattr(self, '_source_scan_deferred', False)
        deferred_sync = getattr(self, '_source_sync_deferred', False)
        self._source_scan_deferred = self._source_sync_deferred = False
        force_refresh = self.pending_scan_force_remote_refresh if deferred_scan else False
        if deferred_scan: self.pending_scan_force_remote_refresh = False
        if not new_library and (accepted or deferred_scan): self.start_library_scan(force_remote_refresh=force_refresh)
        elif deferred_scan: QTimer.singleShot(0, lambda:self.start_library_scan(force_remote_refresh=force_refresh))
        if deferred_sync: QTimer.singleShot(0, self.sync_shared_pairings)
        return accepted

    def migrate_unified_sources(self):
        local = config.get('nas_local_url', '')
        if self.is_closing or not local or config.get('unified_sources_local_url') == local:
            return
        if getattr(self, '_source_editing', False):
            QTimer.singleShot(750, self.migrate_unified_sources)
            return
        libraries = [('movies', 'Filmek'), ('shows', 'TV')]
        libraries.extend((lib['id'], lib['name']) for lib in config.get('custom_libraries', []))
        try:
            self.save_library_sources(records_from_settings(config, libraries))
        except SourcesBusy:
            QTimer.singleShot(750, self.migrate_unified_sources)
        except (ValueError, OSError, RuntimeError, sqlite3.Error):
            LOGGER.warning('A korábbi források automatikus átalakítása nem sikerült; a Forrásmappák ablakban ellenőrizhetők.')

    def save_library_sources(self, records, new_library=None):
        records = unify_records(records, config)
        settings = copy.deepcopy(config)
        if new_library: settings.setdefault('custom_libraries', []).append(copy.deepcopy(new_library))
        known = {'movies', 'shows'} | {lib['id'] for lib in settings.get('custom_libraries', [])}
        if any(row['library_id'] not in known for row in records):
            raise ValueError("A kiválasztott médiatár már nem létezik.")
        router = FolderMigrationRouter(records, settings)
        settings = canonicalize_config(settings, router, source_router())
        for key in ('movies', 'shows'):
            settings[key + '_paths'] = [row['remote_root'] or row['local_root'] for row in records if row['library_id'] == key]
            settings[key + '_path'] = settings[key + '_paths'][0] if settings[key + '_paths'] else ''
            settings['remote_' + key + '_path'] = ''
        for lib in settings.get('custom_libraries', []):
            lib['paths'] = [row['remote_root'] or row['local_root'] for row in records if row['library_id'] == lib['id']]
        # Automatically derived SMB paths follow the profile and are not persisted as explicit aliases.
        explicit = [row for row in records if row['local_root'] and row['remote_root']]
        settings['paired_sources'] = explicit
        settings['unified_sources_local_url'] = settings.get('nas_local_url', '')
        self.save_source_pairs(explicit, _settings=settings, _router=router)

    @staticmethod
    def _deduplicate_paths(paths):
        result = []
        seen = set()
        for path in paths:
            path = path.strip().strip('"')
            if not path:
                continue
            key = normalize_path(path)
            if key not in seen:
                seen.add(key)
                result.append(path)
        return result

    @staticmethod
    def _deduplicate_media_paths(paths):
        result = []
        seen = set()
        for path in paths:
            path = path.strip().strip('"')
            if not path:
                continue
            key = normalize_media_path(path)
            if key not in seen:
                seen.add(key)
                result.append(path)
        return result

    def _add_path_to_list(self, list_widget, path):
        normalized = normalize_media_path(path)
        for i in range(list_widget.count()):
            if normalize_media_path(list_widget.item(i).text()) == normalized:
                QMessageBox.information(self, "Mappa már hozzáadva", "Ez az útvonal már szerepel a listában.")
                return
        list_widget.addItem(path)

    def open_remote_quickconnect(self):
        dlg = RemoteQuickConnectDialog(self, connection_only=True)
        dlg.exec()
        dlg.deleteLater()

    def open_quickconnect_test(self):
        dlg = QuickConnectTestDialog(self)
        dlg.exec()
        dlg.deleteLater()

    # --- beolvasás ---
    def _library_cache_paths(self, library_id):
        if library_id in ("movies", "shows"):
            return configured_paths(library_id)
        return configured_paths(f"custom:{library_id}")

    def recommendation_context(self, library_id):
        # Only already known identities leave this machine, via TMDB's existing
        # recommendation endpoints. No NAS paths or files are submitted.
        roots_by_library = {key:[normalize_media_path(path) for path in self._library_cache_paths(key)] for key in self.library_pages}
        all_roots = [root for roots in roots_by_library.values() for root in roots]
        try:
            stat = os.stat(DB_FILE)
            generation = (stat.st_mtime_ns, stat.st_size)
        except OSError: generation = None
        revision = (library_id, generation,
            tuple((key, page._data_revision, tuple(roots_by_library[key])) for key, page in self.library_pages.items()))
        cached_context = getattr(self, '_recommendation_context_cache', None)
        if cached_context and cached_context[0] == revision: return cached_context[1]
        def within(path, roots):
            return bool(path) and any(media_path_is_within(normalize_media_path(path), root) for root in roots)
        with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
            overrides = {path:(media_id, kind) for path, media_id, kind in conn.execute(
                'SELECT file_path,tmdb_id,is_movie FROM manual_overrides')}
            cached = conn.execute('SELECT file_path,tmdb_id,is_movie FROM media_cache').fetchall()
        owned = set()
        for path, media_id, kind in cached:
            if not within(path, all_roots): continue
            media_id, kind = overrides.get(path, (media_id,kind))
            key = recommendations.identity(dict(id=media_id, is_movie=kind))
            if key: owned.add(key)
        for path, (media_id,kind) in overrides.items():
            key = recommendations.identity(dict(id=media_id, is_movie=kind))
            if key and within(path, all_roots): owned.add(key)
        seeds = []
        for key, page in self.library_pages.items():
            roots = roots_by_library[key]
            items = {normalize_media_path(item.get('file_path','')):dict(item) for item in self._cached_page_items(key)}
            for _title, card in list(page.cards):
                item = dict(card.item)
                items[normalize_media_path(item.get('file_path',''))] = item
            for path, item in items.items():
                if not within(path, roots): continue
                if path in overrides:
                    item['id'], item['is_movie'] = overrides[path]
                else: item.setdefault('is_movie', media_item_is_movie(item))
                media_key = recommendations.identity(item)
                if media_key: owned.add(media_key)
                if key == library_id and not media_is_excluded(path) and media_key: seeds.append(item)
        result = dict(seeds=recommendations.seed_items(seeds), owned=owned)
        self._recommendation_context_cache = (revision, result)
        return result

    def show_recommendations(self, library_id):
        if self.is_closing or library_id not in self.library_pages: return
        name = (translate_text('Filmek') if library_id == 'movies' else translate_text('TV Műsorok') if library_id == 'shows'
                else next((lib['name'] for lib in config.get('custom_libraries', []) if lib['id'] == library_id), library_id))
        dialog = RecommendationsDialog(self, library_id, name, recommendations.RecommendationStore(DB_FILE),
            lambda:self.recommendation_context(library_id), tmdb_request, current_tmdb_language(),
            run_worker, NasTask, download_and_cache_poster, placeholder_pixmap,
            os.path.join(RESOURCE_DIR, 'assets', 'tmdb.png'), translate_text,
            edit_menu=lambda widget:_install_localized_edit_context_menu(widget, multiline=True),
            prefer_hungarian=bool(config.get("recommendation_prefer_hungarian", True)))
        try: dialog.exec()
        finally: dialog.deleteLater()

    def _cached_page_items(self, library_id):
        """Load the last completed card snapshot for instant display before a NAS check."""
        roots = [normalize_media_path(path) for path in self._library_cache_paths(library_id)]
        if not roots:
            return []

        def belongs_to_library(path):
            normalized = normalize_media_path(path)
            return bool(normalized) and any(media_path_is_within(normalized, root) for root in roots)

        cached_items = []
        try:
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
                rows = conn.execute(
                    "SELECT c.file_path, c.payload, m.is_movie FROM library_card_cache c "
                    "LEFT JOIN media_cache m ON m.file_path = c.file_path WHERE c.library_id = ?",
                    (library_id,),
                ).fetchall()
            for file_path, payload, cached_is_movie in rows:
                try:
                    item = json.loads(payload)
                except (TypeError, json.JSONDecodeError):
                    continue
                if not isinstance(item, dict) or not belongs_to_library(file_path) or media_is_excluded(file_path):
                    continue
                item.setdefault("file_path", file_path)
                item["_scan_library_id"] = library_id
                item["library_id"] = library_id
                if item.get("is_movie") is None:
                    item["is_movie"] = bool(cached_is_movie) if cached_is_movie in (0, 1) else media_item_is_movie(item)
                try:
                    cached_media_id = int(item.get("id") or -1)
                except (TypeError, ValueError):
                    cached_media_id = -1
                if (cached_media_id <= 0 and item.get("overview")
                        and item.get("overview") not in {NO_MATCH_TEXT, LOW_CONFIDENCE_TEXT}):
                    # Older snapshots may have stored a scan/API error in the
                    # card description. Keep that information in the log only.
                    item["overview"] = ""
                poster = item.get("poster")
                if poster and not is_cached_file(poster):
                    item["poster"] = None
                cached_items.append(item)
        except sqlite3.Error:
            LOGGER.exception("Nem sikerült betölteni a(z) %s médiatár korábbi kártyáit.", library_id)

        # Upgrade existing databases once: earlier releases kept TMDB rows but
        # did not persist the finished card grouping. This lightweight fallback
        # makes the old library visible while its first 1.46 scan runs.
        if not cached_items:
            cached_items = self._legacy_cached_page_items(library_id, belongs_to_library)
        return cached_items

    def _legacy_cached_page_items(self, library_id, belongs_to_library):
        target_is_movie = True
        if library_id == "shows":
            target_is_movie = False
        elif library_id not in ("movies", "shows"):
            library = next(
                (entry for entry in config.get("custom_libraries", [])
                 if entry.get("id") == library_id),
                None,
            )
            if library is None:
                return []
            target_is_movie = custom_library_is_movie(library)

        try:
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
                rows = conn.execute(
                    "SELECT file_path, tmdb_id, title, overview, poster_url, release_date, "
                    "is_movie, file_mtime, status FROM media_cache"
                ).fetchall()
        except sqlite3.Error:
            LOGGER.exception("Nem sikerült beolvasni a(z) %s médiatár régi gyorsítótárát.", library_id)
            return []

        manual_groups = []
        for group in config.get("manual_show_groups", []):
            if not isinstance(group, dict):
                continue
            group_library_id = str(group.get("library_id") or "shows")
            if group_library_id != library_id:
                continue
            paths = [path for path in group.get("paths", []) if isinstance(path, str) and path]
            if paths:
                manual_groups.append((group, paths))

        items = []
        used_manual_groups = set()
        for (file_path, tmdb_id, title, overview, poster_url, release_date,
             row_is_movie, file_mtime, status) in rows:
            row_is_movie = bool(row_is_movie)
            if media_is_excluded(file_path) or not belongs_to_library(file_path) or status not in {"success", "no_result"}:
                continue
            if row_is_movie and not target_is_movie:
                continue
            media_id = int(tmdb_id or -1)
            media_type = "movie" if row_is_movie else "tv"
            poster = os.path.join(CACHE_DIR, f"{media_type}_{media_id}.jpg") if media_id > 0 else None
            if not poster or not is_cached_file(poster):
                poster = None
            item = {
                "file_path": file_path,
                "title": title or os.path.basename(file_path.rstrip("/\\")) or file_path,
                "overview": overview or "",
                "poster": poster,
                "date": release_date or "",
                "id": media_id,
                "is_movie": row_is_movie,
                "added_at": float(file_mtime or 0),
                "_scan_library_id": library_id,
                "library_id": library_id,
            }
            if not row_is_movie:
                item["episode_roots"] = [file_path]
                for group, paths in manual_groups:
                    normalized_paths = {normalize_media_path(path) for path in paths}
                    if normalize_media_path(file_path) in normalized_paths:
                        group_id = str(group.get("id") or "")
                        if group_id in used_manual_groups:
                            item = None
                            break
                        used_manual_groups.add(group_id)
                        item["file_path"] = paths[0]
                        item["episode_roots"] = paths
                        item["manual_group_id"] = group_id
                        item["title"] = item["title"] or str(group.get("title") or "")
                        break
            if item is not None:
                items.append(item)
        return items

    def _scan_pages_for_library(self, library_key):
        if library_key is None:
            return list(self.library_pages)
        return [library_key] if library_key in self.library_pages else []

    def start_library_scan(self, library_key=None, force_remote_refresh=False):
        if self.is_closing:
            return
        if getattr(self, '_source_editing', False):
            self._source_scan_deferred = True
            self.pending_scan_force_remote_refresh = self.pending_scan_force_remote_refresh or force_remote_refresh
            return
        # Show the last finished snapshot immediately, even when this library
        # has not yet been checked during the current application session.
        if library_key is None:
            cache_targets = list(self.library_pages)
        else:
            cache_targets = [library_key] if library_key in self.library_pages else []
        for target_id in cache_targets:
            page = self.library_pages[target_id]
            if page.count() == 0:
                cached_items = self._cached_page_items(target_id)
                if cached_items:
                    page.replace_items(cached_items)

        if self.scanner_thread is not None:
            if not self.pending_scan:
                self.pending_scan_library = library_key
            elif self.pending_scan_library != library_key:
                # Különböző kérések esetén a teljes beolvasás lefedi a részbeolvasásokat.
                self.pending_scan_library = None
            self.pending_scan = True
            self.pending_scan_force_remote_refresh = (
                self.pending_scan_force_remote_refresh or force_remote_refresh
            )
            return

        self._last_inventory_check = time.monotonic()
        self.scanner_scope = library_key
        self.scanner_tmdb_language = current_tmdb_language()
        self.scan_errors = []
        self.scan_page_keys = self._scan_pages_for_library(library_key)
        self.scan_seen_paths = {key: set() for key in self.scan_page_keys}
        pages = [self.library_pages[key] for key in self.scan_page_keys]
        for page in pages:
            page.begin_bulk_update()
            page.set_message(
                "A korábbi lista betöltve; háttérben ellenőrzöm a változásokat..."
                if page.count() else "Beolvasás folyamatban..."
            )
        self.status_lbl.setText("Beolvasás folyamatban...")

        thread = LibraryScannerThread(
            configured_paths("movies"), configured_paths("shows"),
            config.get("custom_libraries", []), library_key,
            config.get("manual_show_groups", []),
            force_remote_refresh=force_remote_refresh,
        )
        thread.preview_ready.connect(self.on_item_ready)
        thread.inventory_ready.connect(self.on_inventory_ready)
        thread.item_ready.connect(self.on_item_ready)
        thread.pairings_notice.connect(self.show_pairing_notice)
        thread.scan_completed.connect(self.on_scan_completed)
        thread.finished.connect(self.on_scanner_finished)
        self.scanner_thread = thread
        thread.start()

    def check_library_changes(self):
        if (self.is_closing or self.scanner_thread is not None or getattr(self, '_source_editing', False)
                or self.pending_override is not None or self._pairing_sync_running): return
        try: minutes = max(0, int(config.get('library_refresh_minutes', 5)))
        except (ValueError, TypeError): minutes = 5
        if not minutes or time.monotonic() - self._last_inventory_check < minutes * 60: return
        self._last_inventory_check = time.monotonic()
        self.start_library_scan()

    def on_inventory_ready(self, inventory):
        if self.is_closing: return
        if self.scan_item_queue:
            QTimer.singleShot(20, lambda:self.on_inventory_ready(inventory)); return
        page = self.library_pages.get(inventory['library'])
        if page is not None:
            page.prune_scan_source(inventory['library'], set(inventory['paths']))
            page.schedule_reflow()

    def on_item_ready(self, item, is_movie):
        if not self.is_closing:
            self.scan_item_queue.append((item, is_movie))
            if not self.scan_item_timer.isActive():
                self.scan_item_timer.start(0)

    def drain_scan_items(self):
        if self.is_closing:
            self.scan_item_queue.clear()
            return
        deadline = time.perf_counter() + 0.005
        processed = 0
        while self.scan_item_queue and processed < 32 and time.perf_counter() < deadline:
            self._apply_scan_item(*self.scan_item_queue.popleft())
            processed += 1
        if processed and time.monotonic() >= self._scan_next_repaint:
            self._scan_next_repaint = time.monotonic() + 0.15
            for page in self.library_pages.values():
                if page.isVisible():
                    page.schedule_reflow()
        if self.scan_item_queue:
            self.scan_item_timer.start(1)
            return
        if self._pending_scan_errors is not None:
            errors = self._pending_scan_errors
            self._pending_scan_errors = None
            self._finish_scan_completed(errors)
        if self._scanner_finished_waiting:
            self._scanner_finished_waiting = False
            self.on_scanner_finished()

    def _apply_scan_item(self, item, is_movie):
        if self.is_closing or media_is_excluded(item.get("file_path", "")):
            return
        item["is_movie"] = is_movie  # a részletező ablak ebből tudja, sorozat-e (nem kell a hálózaton vizsgálni)
        library_id = item.get("library_id")
        page = self.library_pages.get(library_id) if library_id else (self.movies_page if is_movie else self.shows_page)
        if page is None:
            return
        scan_library_id = str(item.get("_scan_library_id") or library_id or ("movies" if is_movie else "shows"))
        if scan_library_id in self.scan_seen_paths:
            path = item.get("file_path")
            if path:
                self.scan_seen_paths[scan_library_id].add(normalize_media_path(path))
        if "_pairing_token" in item:
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
                if not pairing_item_is_current(conn, item):
                    return
        page.set_message("")
        page.add_item(item)

    def on_scan_completed(self, errors):
        if self.scan_item_queue:
            self._pending_scan_errors = errors
            if not self.scan_item_timer.isActive():
                self.scan_item_timer.start(0)
        else:
            self._finish_scan_completed(errors)

    def _finish_scan_completed(self, errors):
        if self.is_closing:
            return
        scanned_libraries = (
            list(self.library_pages) if self.scanner_scope is None else [self.scanner_scope]
        )
        scanner = self.scanner_thread
        failed_metadata_libraries = getattr(scanner, "metadata_failed_libraries", set())
        failed_libraries = getattr(scanner, "failed_libraries", set())
        unattributed_scan_error = bool(getattr(scanner, "unattributed_scan_error", False))
        for library_id in scanned_libraries:
            if (library_id not in failed_metadata_libraries
                    and library_id not in failed_libraries
                    and not unattributed_scan_error):
                self.library_metadata_language[library_id] = self.scanner_tmdb_language
        self.scan_errors = errors
        if errors:
            LOGGER.warning("A médiatár-beolvasás %d figyelmeztetéssel zárult.", len(errors))
            for warning in errors[:100]:
                LOGGER.warning("Beolvasási figyelmeztetés: %s", warning)
            if len(errors) > 100:
                LOGGER.warning("A további %d figyelmeztetés nem került be a naplóba.", len(errors) - 100)
            error_library_ids = getattr(scanner, "error_library_ids", {})
            for warning in errors:
                affected_ids = error_library_ids.get(warning, set())
                names = []
                for library_id in affected_ids:
                    if library_id is None:
                        names.append("nem azonosított médiatár")
                    elif library_id in self.library_buttons:
                        names.append(self.library_buttons[library_id].text())
                    else:
                        library = next((entry for entry in config.get("custom_libraries", [])
                                        if entry.get("id") == library_id), None)
                        names.append(library.get("name", str(library_id)) if library else str(library_id))
                library_label = ", ".join(sorted(set(names))) or "nem azonosított médiatár"
                SCAN_ERROR_LOGGER.error("[%s] %s", library_label, warning)
        pages = (list(self.library_pages.values()) if self.scanner_scope is None
                 else [self.library_pages[self.scanner_scope]] if self.scanner_scope in self.library_pages else [])
        for page in pages:
            page_key = next((key for key, candidate in self.library_pages.items() if candidate is page), None)
            if page_key:
                for source_key in self.scan_page_keys:
                    if (source_key not in failed_libraries
                            and not unattributed_scan_error):
                        page.prune_scan_source(
                            source_key, self.scan_seen_paths.get(source_key, set())
                        )
            page.end_bulk_update()
            if page.count() == 0:
                page.set_message("Nincs megjeleníthető elem ebben a médiatárban.")

        scan_state = config.get("library_scan_state", {})
        if not isinstance(scan_state, dict):
            scan_state = {}
        else:
            scan_state = dict(scan_state)
        scan_state_changed = False
        if scanner is not None and not unattributed_scan_error:
            for library_id in scanned_libraries:
                if (library_id in failed_libraries
                        or library_id in failed_metadata_libraries
                        or not self._library_cache_paths(library_id)):
                    continue
                page = self.library_pages.get(library_id)
                if page is None:
                    continue
                scan_state[library_id] = {
                    "last_success": time.time(),
                    "item_count": page.count(),
                }
                scan_state_changed = True
        if scan_state_changed:
            config["library_scan_state"] = scan_state
            saved, error = save_config()
            if not saved:
                LOGGER.error("Nem sikerült elmenteni a médiatárak sikeres frissítési idejét: %s", error)
        custom_counts = [
            f"{lib['name']}: {self.library_pages[lib['id']].count()}"
            for lib in config.get("custom_libraries", []) if lib.get("id") in self.library_pages
        ]
        if self.scanner_scope is None:
            summary = f"Kész: {self.movies_page.count()} film, {self.shows_page.count()} TV műsor"
            if custom_counts:
                summary += " | " + ", ".join(custom_counts)
        else:
            page = self.library_pages.get(self.scanner_scope)
            button = self.library_buttons.get(self.scanner_scope)
            label = button.text() if button else "médiatár"
            summary = f"Kész: {page.count() if page else 0} elem – {label}"
        self.status_lbl.setText(summary)

    def on_scanner_finished(self):
        if not self.is_closing and (self.scan_item_queue or self._pending_scan_errors is not None):
            self._scanner_finished_waiting = True
            if not self.scan_item_timer.isActive():
                self.scan_item_timer.start(0)
            return
        thread = self.scanner_thread
        self.scanner_thread = None
        if thread is not None:
            thread.wait()
        if self.is_closing:
            return
        if self.pending_scan:
            next_library = self.pending_scan_library
            force_remote_refresh = self.pending_scan_force_remote_refresh
            self.pending_scan = False
            self.pending_scan_library = None
            self.pending_scan_force_remote_refresh = False
            self.scanner_scope = None
            self.start_library_scan(next_library, force_remote_refresh=force_remote_refresh)
        else:
            self.scanner_scope = None
            self.start_download_refresh()

    def show_library_status(self):
        dialog = QDialog(self.settings_dialog)
        dialog.setWindowTitle(translate_text("Médiatár állapota"))
        dialog.resize(760, max(300, min(620, 170 + 48 * len(self.library_pages))))
        layout = QVBoxLayout(dialog)
        table = QTableWidget(len(self.library_pages), 3, dialog)
        table.setHorizontalHeaderLabels([
            translate_text("Médiatár"), translate_text("Kártyák"),
            translate_text("Utolsó sikeres frissítés"),
        ])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        state = config.get("library_scan_state", {})
        if not isinstance(state, dict):
            state = {}
        for row, (library_id, page) in enumerate(self.library_pages.items()):
            button = self.library_buttons.get(library_id)
            name = button.text() if button else str(library_id)
            saved_state = state.get(library_id, {})
            if not isinstance(saved_state, dict):
                saved_state = {}
            try:
                last_success = float(saved_state.get("last_success") or 0)
            except (TypeError, ValueError):
                last_success = 0
            last_success_text = (
                time.strftime("%Y-%m-%d %H:%M", time.localtime(last_success))
                if last_success > 0 else translate_text("Még nem volt sikeres frissítés")
            )
            for column, value in enumerate((name, str(page.count()), last_success_text)):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, column, item)
        table.horizontalHeader().setStretchLastSection(True)
        table.resizeColumnsToContents()
        layout.addWidget(table, 1)
        layout.addWidget(QLabel(translate_text(
            "A kártyaszám a legutóbb betöltött listát mutatja."
        )))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=dialog)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def open_scan_error_log(self):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(SCAN_ERROR_LOG_FILE, "a", encoding="utf-8"):
                pass
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(SCAN_ERROR_LOG_FILE)):
                raise OSError("A naplófájl megnyitása sikertelen.")
        except OSError as exc:
            QMessageBox.warning(
                self.settings_dialog, translate_text("Hibanapló megnyitása"),
                f"{exc}\n\n{SCAN_ERROR_LOG_FILE}",
            )

    def refresh_library(self, force_metadata=False):
        """Csak az éppen megnyitott médiatárat olvassa be újra."""
        library_key = self.current_library_key
        if not force_metadata:
            self.start_library_scan(library_key)
            return
        try:
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
                paths = configured_paths(library_key if library_key in ("movies", "shows")
                                         else f"custom:{library_key}")
                if library_key in ("movies", "shows"):
                    is_movie = library_key == "movies"
                else:
                    library = next(
                        (entry for entry in config.get("custom_libraries", [])
                         if entry.get("id") == library_key),
                        {},
                    )
                    is_movie = custom_library_is_movie(library)
                rows = conn.execute(
                    "SELECT file_path FROM media_cache WHERE status = 'no_result' AND is_movie = ?",
                    (1 if is_movie else 0,),
                ).fetchall()
                roots = [normalize_media_path(path) for path in paths]
                stale = [row[0] for row in rows if any(
                    media_path_is_within(row[0], root) for root in roots
                )]
                conn.executemany("DELETE FROM media_cache WHERE file_path = ? AND status = 'no_result'",
                                 [(path,) for path in stale])
                conn.commit()
        except sqlite3.Error as e:
            QMessageBox.warning(self, "Adatbázis hiba", f"Nem sikerült a frissítés előkészítése: {e}")
            return
        if self.scanner_thread is not None:
            self.start_library_scan(library_key, force_remote_refresh=force_metadata)
            return
        self.start_library_scan(library_key, force_remote_refresh=force_metadata)

    # --- videoinformációk lekérése közvetlenül a megnyitott kártyáról ---
    def start_video_info_lookup(self, item, detail_dialog=None):
        if self.pending_override is not None:
            QMessageBox.information(self, "Folyamatban", "Már fut egy videoinformációs keresés.")
            return

        file_path = item.get("file_path")
        is_movie = media_item_is_movie(item)
        is_show = not is_movie
        if not file_path:
            QMessageBox.warning(self, "Hiányzó útvonal", "Ehhez a kártyához nem tartozik elérési útvonal.")
            return

        suggested_title = item.get("title", "")
        lookup_dialog = QDialog(detail_dialog or self)
        lookup_dialog.setWindowTitle("Videoinformációk lekérése")
        lookup_layout = QVBoxLayout(lookup_dialog)
        lookup_layout.addWidget(QLabel("Milyen címet keressünk a TMDB-n?"))
        title_input = QLineEdit(suggested_title)
        title_input.selectAll()
        lookup_layout.addWidget(title_input)

        undo_button = QPushButton("Kézi párosítás visszavonása", lookup_dialog)
        undo_button.setToolTip(
            "Eltávolítja a kézi TMDB-párosítást, majd újra megpróbálja az automatikus párosítást."
        )
        undo_button.setVisible(bool(self.manual_override_paths_for_item(item, is_show)))

        def undo_pairing_from_lookup():
            self.undo_manual_pairing(item, is_show, None, lookup_dialog)
            if not self.manual_override_paths_for_item(item, is_show):
                lookup_dialog.reject()
                if detail_dialog is not None:
                    detail_dialog.accept()

        undo_button.clicked.connect(undo_pairing_from_lookup)
        lookup_layout.addWidget(undo_button, alignment=Qt.AlignmentFlag.AlignLeft)

        lookup_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        search_button = lookup_buttons.button(QDialogButtonBox.StandardButton.Ok)
        search_button.setText("Keresés")
        search_button.setDefault(True)
        lookup_buttons.accepted.connect(lookup_dialog.accept)
        lookup_buttons.rejected.connect(lookup_dialog.reject)
        lookup_layout.addWidget(lookup_buttons)

        dialog_result = lookup_dialog.exec()
        title = title_input.text()
        lookup_dialog.deleteLater()
        if dialog_result != QDialog.DialogCode.Accepted:
            return
        title = title.strip()
        if not title:
            QMessageBox.warning(detail_dialog or self, "Hiányzó cím", "Adj meg egy címet a kereséshez.")
            return

        normalized = normalize_media_path(file_path)
        self.pending_override = {
            "fpath": normalized,
            "fpath_raw": file_path,
            "title": title,
            "is_movie": is_movie,
            "detail_dialog": detail_dialog,
            "library_id": item.get("library_id"),
        }
        self.set_override_busy("Keresés a TMDB-n...")
        worker = TmdbSearchWorker(title, is_movie)
        worker.search_done.connect(self.on_override_search_done)
        run_worker(worker)

    # --- videoinformációk lekérése ---
    def create_override_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("Videoinformációk lekérése")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        desc = QLabel("Itt rendelhetsz hozzá megfelelő TMDB-adatokat egy videóhoz vagy TV-műsor mappához. "
                      "A NAS-on lévő eredeti fájl érintetlen marad!")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #b3b3b3; margin-bottom: 20px;")
        layout.addWidget(desc)

        form_layout = QFormLayout()
        self.input_filepath = QLineEdit()
        self.input_filepath.setPlaceholderText(
            r"Pl. \\NAS\Filmek\ppnhmr.fulcrum.mkv vagy \\NAS\TV_sorozatok\Breaking Bad")

        self.input_media_type = QComboBox()
        self.input_media_type.addItem("Film", True)
        self.input_media_type.addItem("TV műsor", False)

        self.input_tmdb_title = QLineEdit()
        self.input_tmdb_title.setPlaceholderText("Pl. Oppenheimer vagy Breaking Bad")

        form_layout.addRow("Fájl / Mappa teljes útvonala:", self.input_filepath)
        form_layout.addRow("Média típusa:", self.input_media_type)
        form_layout.addRow("Helyes cím (TMDB):", self.input_tmdb_title)
        layout.addLayout(form_layout)

        self.btn_save = QPushButton(self.SAVE_TEXT)
        self.btn_save.setProperty("class", "ActionBtn")
        self.btn_save.clicked.connect(self.handle_save_override)
        layout.addWidget(self.btn_save)

        layout.addStretch()
        return page

    def set_override_busy(self, text=None):
        self.btn_save.setEnabled(text is None)
        self.btn_save.setText(self.SAVE_TEXT if text is None else text)

    def finish_override(self):
        self.pending_override = None
        self.set_override_busy(None)

    def handle_save_override(self):
        if self.pending_override is not None:
            return  # már fut egy ellenőrzés / keresés

        # A Windows "Másolás elérési útként" idézőjelet tesz köré.
        fpath_raw = self.input_filepath.text().strip().strip('"')
        search_title = self.input_tmdb_title.text().strip()
        is_movie = self.input_media_type.currentData()

        if not fpath_raw or not search_title:
            QMessageBox.warning(self, "Hiba", "Minden mezőt ki kell tölteni!")
            return

        fpath = normalize_media_path(fpath_raw)
        self.pending_override = {"fpath": fpath, "fpath_raw": fpath_raw,
                                 "title": search_title, "is_movie": is_movie,
                                 "detail_dialog": None}
        self.set_override_busy("Útvonal ellenőrzése...")
        # Az útvonal-ellenőrzés és a TMDB-keresés háttérszálon fut, hogy a felület ne fagyjon le.
        worker = PathCheckWorker(fpath, is_movie)
        worker.check_done.connect(self.on_override_path_checked)
        run_worker(worker)

    def on_override_path_checked(self, result):
        ctx = self.pending_override
        if self.is_closing or ctx is None:
            return
        is_movie = ctx["is_movie"]

        problems = {
            "missing": ("Érvénytelen útvonal",
                        f"A megadott útvonal nem létezik vagy nem érhető el:\n{ctx['fpath_raw']}"),
            "not_file": ("Típus hiba", "A megadott útvonal nem egy fájl, pedig film lett kiválasztva."),
            "not_dir": ("Típus hiba", "A megadott útvonal nem egy mappa, pedig TV műsor lett kiválasztva."),
            "error": ("Útvonal hiba", f"Az útvonal ellenőrzése nem sikerült:\n{ctx['fpath_raw']}"),
        }
        if result in problems:
            title, text = problems[result]
            self.finish_override()
            QMessageBox.warning(self, title, text)
            return

        library_dirs = [
            normalize_media_path(path)
            for path in configured_paths("movies" if is_movie else "shows")
        ]
        if not any(media_path_is_within(ctx["fpath"], base) for base in library_dirs):
            what = "fájl nem a konfigurált filmkönyvtárak egyikében" if is_movie else "mappa nem a konfigurált TV-műsor könyvtárak egyikében"
            answer = QMessageBox.question(
                self, "Könyvtáron kívüli útvonal",
                f"A megadott {what} van.\nBiztosan folytatni kívánja?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.No:
                self.finish_override()
                return

        self.set_override_busy("Keresés a TMDB-n...")
        worker = TmdbSearchWorker(ctx["title"], is_movie)
        worker.search_done.connect(self.on_override_search_done)
        run_worker(worker)

    def on_override_search_done(self, res):
        ctx = self.pending_override
        self.finish_override()
        if self.is_closing or ctx is None:
            return
        fpath = ctx["fpath"]
        is_movie = ctx["is_movie"]

        if res["status"] == "error":
            QMessageBox.critical(self, "TMDB Hiba", f"Nem sikerült kapcsolódni a TMDB-hez:\n{res['message']}")
            return
        results = res["results"]
        if not results:
            QMessageBox.warning(self, "Nem található", "A TMDB nem talált ilyen címet a megadott kategóriában.")
            return

        # Egyetlen találatnál is megerősítést kérünk: a cél, hogy a felhasználó tényleg a megfelelő címet rendelje hozzá.
        dlg = TmdbChoiceDialog(self, results, is_movie)
        if res.get("partial"):
            dlg.setWindowTitle(dlg.windowTitle() + " – " + translate_text("Részleges találatok"))
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        selected = dlg.selected_result() if accepted else None
        dlg.deleteLater()
        if selected is None:
            return

        try:
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO manual_overrides (file_path, tmdb_id, custom_title, is_movie)
                    VALUES (?, ?, ?, ?)
                ''', (fpath, selected["id"], selected["title"], 1 if is_movie else 0))
                portable_event = record_portable_edit(conn, fpath, is_movie, selected["id"], selected["title"], library_id=ctx.get("library_id"))
                conn.commit()
        except sqlite3.Error as e:
            LOGGER.exception("Nem sikerült elmenteni a kézi TMDB-párosítást (%s).", fpath)
            QMessageBox.critical(self, "Adatbázis hiba", f"Nem sikerült menteni a videoinformációkat: {e}")
            return

        if portable_event is not None:
            self.sync_shared_pairings()
        else:
            self.show_pairing_notice(translate_text("A párosítás csak helyben menthető, mert nem tartozik beállított médiatárhoz."))
        QMessageBox.information(self, "Siker", f"Videoinformációk hozzárendelve: {selected['title']} (ID: {selected['id']})")
        self.input_filepath.clear()
        self.input_tmdb_title.clear()
        library_id = ctx.get("library_id")
        if library_id in self.library_pages:
            self.switch_page(self.stack.indexOf(self.library_pages[library_id]), self.library_buttons[library_id])
        else:
            self.switch_page(0 if is_movie else 1, self.btn_movies if is_movie else self.btn_shows)
        self.set_override_busy("Adatok frissítése...")
        worker = ManualOverrideRefreshWorker(fpath, is_movie, selected["id"])
        worker.refresh_done.connect(
            lambda item, movie, error, context=ctx: self.on_override_refresh_done(item, movie, error, context)
        )
        worker.finished.connect(lambda: self.set_override_busy(None) if not self.is_closing else None)
        run_worker(worker)

    def on_override_refresh_done(self, item, is_movie, error, ctx):
        if self.is_closing:
            return
        if error:
            LOGGER.warning("A kézi TMDB-párosítás metaadat-frissítése hibával zárult: %s", error)
            QMessageBox.warning(
                self, "Frissítési figyelmeztetés",
                f"A kézi TMDB-párosítás mentve, de az adatok betöltése nem sikerült:\n{error}",
            )
            return

        if "_pairing_token" in item:
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
                if not pairing_item_is_current(conn, item):
                    return
        item["is_movie"] = is_movie
        library_id = ctx.get("library_id")
        if library_id:
            item["library_id"] = library_id
        page = self.library_pages.get(library_id) if library_id else (self.movies_page if is_movie else self.shows_page)
        if page is None:
            return
        updated = page.update_item(item)
        if updated is None:
            return  # Kézzel megadott útvonal: nincs hozzá jelenleg betöltött kártya.

        # Persist the user's visible choice too, independently of an older full scan.
        snapshot_library = library_id or ("movies" if is_movie else "shows")
        with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                if pairing_item_is_current(conn, updated):
                    conn.execute(
                        "INSERT OR REPLACE INTO library_card_cache(library_id,file_path,payload) VALUES (?,?,?)",
                        (snapshot_library, normalize_media_path(updated["file_path"]), json.dumps(updated, ensure_ascii=False)),
                    )

        detail_dialog = ctx.get("detail_dialog")
        if detail_dialog is not None:
            try:
                refresh_metadata = getattr(detail_dialog, "_synostream_refresh_metadata", None)
                if callable(refresh_metadata):
                    refresh_metadata(updated)
                title_lbl = detail_dialog.findChild(QLabel, "DetailTitle")
                date_lbl = detail_dialog.findChild(QLabel, "DetailDate")
                overview_lbl = detail_dialog.findChild(QLabel, "DetailOverview")
                poster_lbl = detail_dialog.findChild(QLabel, "Poster")
                if title_lbl:
                    title_lbl.setRawText(updated["title"])
                if date_lbl:
                    date_lbl.setText(f"Megjelenés: {updated['date']}" if updated.get("date") else "")
                    date_lbl.setVisible(bool(updated.get("date")))
                if overview_lbl:
                    overview = updated.get("overview") or ""
                    if overview:
                        overview_lbl.setRawText(overview)
                    else:
                        overview_lbl.setText("Nincs leírás.")
                if poster_lbl:
                    pixmap = load_pixmap(updated.get("poster"), 200, 280)
                    if pixmap:
                        poster_lbl.setPixmap(pixmap)
                    else:
                        poster_lbl.setPixmap(placeholder_pixmap(updated.get("file_path") or updated.get("title"), 200, 280))
            except RuntimeError:
                # A felhasználó a frissítés közben bezárhatta a részletező ablakot.
                pass

    # --- részletek ---
    @staticmethod
    def show_item_roots(item):
        roots = item.get("episode_roots") or [item.get("file_path", "")]
        result = []
        seen = set()
        for path in roots:
            if not isinstance(path, str) or not path:
                continue
            key = normalize_media_path(path)
            if key and key not in seen:
                result.append(path)
                seen.add(key)
        return result

    @staticmethod
    def path_belongs_to_library(path, library_key):
        if not path or not library_key:
            return False
        path_kind = (
            library_key if library_key in {"movies", "shows"}
            else f"custom:{library_key}"
        )
        normalized_path = normalize_media_path(path)
        return any(
            media_path_is_within(normalized_path, normalize_media_path(root))
            for root in configured_paths(path_kind)
        )

    def manual_override_paths_for_item(self, item, is_show):
        paths = sorted({normalize_media_path(path) for path in self.show_item_roots(item) if path})
        if not paths:
            return []
        placeholders = ",".join("?" for _ in paths)
        try:
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
                rows = conn.execute(
                    f"SELECT file_path FROM manual_overrides WHERE is_movie = ? AND file_path IN ({placeholders})",
                    [0 if is_show else 1, *paths],
                ).fetchall()
            return [row[0] for row in rows]
        except sqlite3.Error:
            LOGGER.exception("Nem sikerült lekérdezni a média kézi TMDB-párosítását.")
            return []

    def undo_manual_pairing(self, item, is_show, detail_dialog=None, prompt_dialog=None):
        message_parent = prompt_dialog or detail_dialog or self
        paths = self.manual_override_paths_for_item(item, is_show)
        if not paths:
            QMessageBox.information(message_parent, "Nincs kézi párosítás",
                                    "Ehhez az elemhez nem tartozik visszavonható kézi párosítás.")
            return
        answer = QMessageBox.question(
            message_parent,
            "Kézi párosítás visszavonása",
            "Visszavonod a kézi TMDB-párosítást? A program ezután újra megpróbálja az automatikus párosítást.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        placeholders = ",".join("?" for _ in paths)
        is_movie_flag = 0 if is_show else 1
        try:
            with contextlib.closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
                for path in paths:
                    record_portable_edit(conn, path, not is_show, deleted=True, library_id=item.get("library_id"))
                conn.execute(
                    f"DELETE FROM manual_overrides WHERE is_movie = ? AND file_path IN ({placeholders})",
                    [is_movie_flag, *paths],
                )
                conn.execute(
                    f"DELETE FROM media_cache WHERE is_movie = ? AND signature LIKE 'override:%' AND file_path IN ({placeholders})",
                    [is_movie_flag, *paths],
                )
                conn.commit()
        except sqlite3.Error as exc:
            LOGGER.exception("Nem sikerült visszavonni a kézi TMDB-párosítást.")
            QMessageBox.critical(message_parent, "Adatbázishiba",
                                 f"Nem sikerült visszavonni a párosítást:\n{exc}")
            return

        self.sync_shared_pairings()
        LOGGER.info("Kézi TMDB-párosítás visszavonva (%d útvonal).", len(paths))
        if detail_dialog is not None:
            detail_dialog.accept()
        library_key = item.get("library_id") or ("shows" if is_show else "movies")
        self.start_library_scan(library_key)

    def merge_show_cards(self, item, detail_dialog=None):
        library_key = item.get("library_id") or self.current_library_key
        library_page = self.library_pages.get(library_key)
        if library_page is None:
            QMessageBox.information(
                detail_dialog or self, "Médiatár nem található",
                "Nem találom a megnyitott kártya médiatárát."
            )
            return

        current_roots = self.show_item_roots(item)
        current_keys = {normalize_media_path(path) for path in current_roots}
        choices = []
        labels = []
        for _title, card in library_page.cards:
            other = card.item
            if (other.get("library_id") or library_key) != library_key:
                continue
            if other.get("is_movie", False):
                continue
            other_roots = self.show_item_roots(other)
            other_keys = {normalize_media_path(path) for path in other_roots}
            if not other_roots or current_keys.intersection(other_keys):
                continue
            label = f"{other.get('title', 'Ismeretlen műsor')} — {other_roots[0]}"
            labels.append(label)
            choices.append(other)

        if not choices:
            QMessageBox.information(
                detail_dialog or self, "Nincs másik kártya",
                "Az aktuális médiatárban legalább két külön TV-műsor-kártyának kell lennie az összevonáshoz."
            )
            return

        selected_index, accepted = QInputDialog.getItem(
            detail_dialog or self, "Műsorok összevonása",
            "Válaszd ki, melyik másik kártyát kapcsoljam ehhez:", labels, 0, False,
            return_index=True,
        )
        if not accepted:
            return
        if not 0 <= selected_index < len(choices):
            return
        target = choices[selected_index]
        title = str(target.get("title") or "").strip()

        merged_paths = []
        selected_keys = set()
        for path in self.show_item_roots(target) + current_roots:
            key = normalize_media_path(path)
            if key and key not in selected_keys:
                merged_paths.append(path)
                selected_keys.add(key)

        old_groups = config.get("manual_show_groups", [])
        if not isinstance(old_groups, list):
            old_groups = []
        remaining = [group for group in old_groups if isinstance(group, dict)]
        while True:
            untouched = []
            joined_another = False
            for group in remaining:
                group_library_id = str(group.get("library_id") or "")
                if group_library_id and group_library_id != library_key:
                    untouched.append(group)
                    continue
                paths = [path for path in group.get("paths", [])
                         if isinstance(path, str) and path.strip()]
                current_library_paths = [
                    path for path in paths
                    if self.path_belongs_to_library(path, library_key)
                ]
                other_library_paths = [
                    path for path in paths
                    if not self.path_belongs_to_library(path, library_key)
                ]
                group_keys = {normalize_media_path(path) for path in current_library_paths}
                if selected_keys.intersection(group_keys):
                    joined_another = True
                    for path in current_library_paths:
                        key = normalize_media_path(path)
                        if key and key not in selected_keys:
                            merged_paths.append(path)
                            selected_keys.add(key)
                    if other_library_paths:
                        remaining_group = dict(group)
                        remaining_group["paths"] = other_library_paths
                        remaining_group["library_id"] = None
                        untouched.append(remaining_group)
                else:
                    untouched.append(group)
            remaining = untouched
            if not joined_another:
                break

        new_groups = remaining + [{
            "id": uuid.uuid4().hex,
            "title": title,
            "paths": merged_paths,
            "library_id": library_key,
        }]
        config["manual_show_groups"] = new_groups
        ok, error = save_config()
        if not ok:
            config["manual_show_groups"] = old_groups
            QMessageBox.critical(
                detail_dialog or self, "Mentési hiba",
                f"Nem sikerült elmenteni az összevonást:\n{error}"
            )
            return

        if detail_dialog is not None:
            detail_dialog.accept()
        self.start_library_scan(library_key)

    def unmerge_show_group(self, group_id, detail_dialog=None, library_key=None):
        old_groups = config.get("manual_show_groups", [])
        if not isinstance(old_groups, list):
            old_groups = []
        found = False
        remaining = []
        for index, group in enumerate(old_groups):
            current_id = str(group.get("id") or f"manual-{index}") if isinstance(group, dict) else ""
            if current_id == group_id:
                found = True
            else:
                remaining.append(group)
        if not found:
            return

        answer = QMessageBox.question(
            detail_dialog or self, "Manuális összevonás feloldása",
            "Feloldod ezt az összevonást? A mappák külön kártyák lesznek, kivéve ha a nevük alapján automatikusan is összetartoznak.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        config["manual_show_groups"] = remaining
        ok, error = save_config()
        if not ok:
            config["manual_show_groups"] = old_groups
            QMessageBox.critical(
                detail_dialog or self, "Mentési hiba",
                f"Nem sikerült feloldani az összevonást:\n{error}"
            )
            return

        if detail_dialog is not None:
            detail_dialog.accept()
        self.start_library_scan(library_key or self.current_library_key)

    def delete_media_item(self, item, detail_dialog=None):
        library_id=item.get('library_id') or ('movies' if item.get('is_movie',True) else 'shows')
        movie=bool(item.get('is_movie',True))
        seeds=[source_router().canonical(p) for p in ([item['file_path']] if movie else self.show_item_roots(item))]
        roots=[p for p in self._library_cache_paths(library_id) if is_remote_path(p)]
        if not roots or not all(is_remote_path(p) for p in seeds):
            QMessageBox.warning(self,'Törlés a NAS-ról','Ehhez a műsorhoz NAS-forrásmappa szükséges. A helyi fájlokat ez a gomb nem törli.')
            return
        protected=[]
        for other in self._cached_page_items(library_id):
            if normalize_media_path(other.get('file_path',''))==normalize_media_path(item['file_path']):continue
            for path in other.get('episode_roots') or [other.get('file_path','')]:
                canonical=source_router().canonical(path)
                if is_remote_path(canonical) and canonical not in seeds:protected.append(canonical)
        credentials={key:config.get(key,'') for key in ('quickconnect_id','nas_username','nas_password','nas_direct_url','nas_local_url','nas_device_tokens')}
        def factory(stop):return _RemoteNASClient(credentials,stop,extra_apis=('SYNO.FileStation.Delete',))
        def completed(result):
            gone=[REMOTE_PREFIX+p for p in result['files']+result['folders']]
            def removed(path):
                canonical=source_router().canonical(path)
                return any(deletion_within(canonical,p) for p in gone)
            for group in list(config.get('manual_show_groups',[])):
                group['paths']=[path for path in group.get('paths',[]) if not removed(path)]
            config['manual_show_groups']=[group for group in config.get('manual_show_groups',[]) if group.get('paths')]
            save_config()
            with contextlib.closing(sqlite3.connect(DB_FILE,timeout=10)) as conn:
                for table in ('media_cache','playback_state','manual_overrides','library_card_cache'):
                    keys=[row[0] for row in conn.execute('SELECT file_path FROM '+table) if removed(row[0])]
                    conn.executemany('DELETE FROM '+table+' WHERE file_path=?',[(p,) for p in keys])
                if movie or result['all_seasons']:
                    conn.execute('DELETE FROM library_card_cache WHERE library_id=? AND file_path=?',(library_id,normalize_media_path(item['file_path'])))
                conn.commit()
            page=self.library_pages.get(library_id)
            if page:page.replace_items(self._cached_page_items(library_id))
            if detail_dialog:detail_dialog.accept()
        dialog=DeleteMediaDialog(detail_dialog or self,item.get('title',''),movie,seeds,roots,protected,factory,NasTask,run_worker,
            lambda:self.scanner_thread is None and not self.scan_item_queue and self._pending_scan_errors is None and not self._pairing_sync_running and self.pending_override is None,completed,translate_text,edit_menu=lambda widget:_install_localized_edit_context_menu(widget,multiline=True))
        previous=getattr(self,'_source_editing',False);self._source_editing=True
        try:accepted=dialog.exec()==QDialog.DialogCode.Accepted
        finally:
            self._source_editing=previous
            attempted=dialog.attempted
            dialog.deleteLater()
        # Also reconcile uncertain partial operations, without retrying the delete.
        if attempted or getattr(self,"_source_scan_deferred",False):self.start_library_scan(library_id)

    def exclude_media_item(self, item, detail_dialog=None):
        paths = self.show_item_roots(item)
        previous = list(config.get("excluded_media_paths", []))
        config["excluded_media_paths"] = list(dict.fromkeys(previous + [normalize_media_path(path) for path in paths]))
        saved, error = save_config()
        if not saved:
            config["excluded_media_paths"] = previous
            QMessageBox.warning(detail_dialog or self, "Mentési hiba", str(error))
            return
        if detail_dialog is not None:
            detail_dialog.accept()
        for page in self.library_pages.values():
            page.replace_items([dict(card.item) for _title, card in page.cards if not media_is_excluded(card.item.get("file_path", ""))])
        self.start_library_scan(item.get("library_id") or ("movies" if item.get("is_movie", True) else "shows"), force_remote_refresh=True)

    def manage_excluded_media(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Kihagyott fájlok és műsorok")
        dialog.resize(720, 380)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("A fájlok a helyükön maradnak. Jelöld ki a visszaállítandó elemeket."))
        listing = QListWidget()
        listing.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        listing.addItems(list(config.get("excluded_media_paths", [])))
        layout.addWidget(listing)
        restore = QPushButton("Kijelöltek visszaállítása")
        layout.addWidget(restore)
        def restore_selected():
            selected = {entry.text() for entry in listing.selectedItems()}
            if not selected:
                return
            previous = list(config.get("excluded_media_paths", []))
            config["excluded_media_paths"] = [path for path in previous if path not in selected]
            saved, error = save_config()
            if not saved:
                config["excluded_media_paths"] = previous
                QMessageBox.warning(dialog, "Mentési hiba", str(error))
                return
            dialog.accept()
            self.start_library_scan(force_remote_refresh=True)
        restore.clicked.connect(restore_selected)
        dialog.exec()

    def open_media_detail(self, item):
        file_path = item["file_path"]
        is_movie = media_item_is_movie(item)
        is_show = not is_movie

        dlg = QDialog(self)
        dlg.setWindowTitle("Média Részletek")
        if is_show:
            screen = dlg.screen()
            available = screen.availableGeometry() if screen else None
            if available:
                dialog_width = min(850, max(740, available.width() - 48))
                dialog_height = min(740, max(660, available.height() - 48))
            else:
                dialog_width, dialog_height = 850, 740
            dlg.resize(dialog_width, dialog_height)
            dlg.setMinimumSize(min(dialog_width, 740), min(dialog_height, 660))
        else:
            dlg.resize(715, 495)
        detail_state = {"closed": False, "generation": 0}
        dlg.finished.connect(lambda _result: detail_state.update(closed=True))

        main_layout = QHBoxLayout(dlg)

        poster_lbl = QLabel()
        poster_lbl.setObjectName("Poster")
        poster_lbl.setFixedSize(200, 280)
        poster_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = load_pixmap(item.get("poster"), 200, 280)
        if pixmap:
            poster_lbl.setPixmap(pixmap)
        else:
            poster_lbl.setPixmap(placeholder_pixmap(item.get("file_path") or item.get("title"), 200, 280))
        main_layout.addWidget(poster_lbl, 0, Qt.AlignmentFlag.AlignTop)

        right = QVBoxLayout()
        title_row = QHBoxLayout()
        title_lbl = QLabel()
        title_lbl.setRawText(item["title"])
        title_lbl.setObjectName("DetailTitle")
        title_lbl.setWordWrap(True)
        title_row.addWidget(title_lbl, 1)

        info_button = QPushButton("i", dlg)
        info_button.setFixedSize(26, 26)
        info_button.setCursor(Qt.CursorShape.PointingHandCursor)
        info_button.setToolTip("Videoinformációk hozzáadása")
        info_button.setStyleSheet(
            "QPushButton { background: #25232d; color: white; border: 1px solid #655B70; "
            "border-radius: 13px; font-size: 14px; font-weight: bold; padding: 0; }"
            "QPushButton:hover { background: #5B5264; }"
        )
        info_button.clicked.connect(
            lambda _checked=False, media=item: self.start_video_info_lookup(media, dlg)
        )
        title_row.addWidget(info_button)
        exclude_button = QPushButton("", dlg)
        icon_pixmap = QPixmap(24, 24)
        icon_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(icon_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("white"), 2))
        painter.drawEllipse(4, 4, 16, 16)
        painter.drawLine(6, 18, 18, 6)
        painter.end()
        exclude_button.setIcon(QIcon(icon_pixmap))
        exclude_button.setIconSize(QSize(16, 16))
        exclude_button.setAccessibleName(translate_text("Kihagyás a médiatárból – a fájl megmarad"))
        exclude_button.setObjectName("ExcludeMedia")
        exclude_button.setFixedSize(26, 26)
        exclude_button.setCursor(Qt.CursorShape.PointingHandCursor)
        exclude_button.setToolTip("Kihagyás a médiatárból – a fájl megmarad")
        exclude_button.setStyleSheet(info_button.styleSheet())
        exclude_button.clicked.connect(lambda _checked=False: self.exclude_media_item(item, dlg))
        title_row.addWidget(exclude_button)
        trash_button=QPushButton('',dlg)
        trash_icon=QPixmap(24,24);trash_icon.fill(Qt.GlobalColor.transparent)
        trash_painter=QPainter(trash_icon);trash_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        trash_painter.setPen(QPen(QColor('white'),2));trash_painter.drawLine(5,6,19,6);trash_painter.drawLine(9,3,15,3)
        trash_painter.drawRect(7,7,10,14);trash_painter.drawLine(10,10,10,18);trash_painter.drawLine(14,10,14,18);trash_painter.end()
        trash_button.setIcon(QIcon(trash_icon));trash_button.setIconSize(QSize(16,16));trash_button.setFixedSize(26,26)
        trash_button.setObjectName('DeleteMediaFiles');trash_button.setAccessibleName(translate_text('Törlés a NAS-ról'))
        trash_button.setToolTip('Törlés a NAS-ról');trash_button.setStyleSheet(info_button.styleSheet());trash_button.setCursor(Qt.CursorShape.PointingHandCursor)
        trash_button.clicked.connect(lambda _=False:self.delete_media_item(item,dlg));title_row.addWidget(trash_button)
        if is_show:
            merge_button = QPushButton("+", dlg)
            merge_button.setFixedSize(26, 26)
            merge_button.setCursor(Qt.CursorShape.PointingHandCursor)
            merge_button.setToolTip("Másik TV-műsor kártyával összevonás")
            merge_button.setStyleSheet(
                "QPushButton { background: #25232d; color: white; border: 1px solid #655B70; "
                "border-radius: 13px; font-size: 16px; font-weight: bold; padding: 0; }"
                "QPushButton:hover { background: #5B5264; }"
            )
            merge_button.clicked.connect(
                lambda _checked=False, media=item: self.merge_show_cards(media, dlg)
            )
            title_row.addWidget(merge_button)
            if item.get("manual_group_id"):
                unmerge_button = QPushButton("−", dlg)
                unmerge_button.setFixedSize(26, 26)
                unmerge_button.setCursor(Qt.CursorShape.PointingHandCursor)
                unmerge_button.setToolTip("Manuális összevonás feloldása")
                unmerge_button.setStyleSheet(
                    "QPushButton { background: #25232d; color: white; border: 1px solid #655B70; "
                    "border-radius: 13px; font-size: 16px; font-weight: bold; padding: 0; }"
                    "QPushButton:hover { background: #5B5264; }"
                )
                unmerge_button.clicked.connect(
                    lambda _checked=False, group_id=item["manual_group_id"]:
                        self.unmerge_show_group(
                            group_id, dlg,
                            item.get("library_id") or self.current_library_key,
                        )
                )
                title_row.addWidget(unmerge_button)
        right.addLayout(title_row)

        date_lbl = QLabel(f"Megjelenés: {item['date']}" if item.get("date") else "")
        date_lbl.setObjectName("DetailDate")
        date_lbl.setStyleSheet("color: #888888;")
        date_lbl.setVisible(bool(item.get("date")))
        right.addWidget(date_lbl)

        metadata_lbl = QLabel("További adatok betöltése…")
        metadata_lbl.setObjectName("DetailMetadata")
        metadata_lbl.setWordWrap(True)
        metadata_lbl.setStyleSheet("color: #B7A9C8; font-size: 12px;")
        right.addWidget(metadata_lbl)

        overview_lbl = QLabel()
        if item.get("overview"):
            overview_lbl.setRawText(item["overview"])
        else:
            overview_lbl.setText("Nincs leírás.")
        overview_lbl.setObjectName("DetailOverview")
        overview_lbl.setWordWrap(True)
        overview_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        overview_lbl.setStyleSheet("color: #cccccc; font-size: 12px;")
        if is_show:
            overview_lbl.setMaximumHeight(120)
            overview_lbl.setToolTip(item.get("overview") or "")
        right.addWidget(overview_lbl)

        def show_media_metadata(metadata, generation):
            if detail_state["closed"] or generation != detail_state["generation"]:
                return
            if metadata.get("status") != "success":
                metadata_lbl.setText("További adatok most nem tölthetők be.")
                return
            item["original_language"] = str(metadata.get("original_language") or "").strip().lower()
            for key in ("genres", "rating", "runtime", "cast"):
                if key in metadata:
                    item[key] = metadata[key]
            for key in (
                "certification", "certification_country", "certification_order",
                "certification_checked", "certification_error",
            ):
                if key in metadata:
                    item[key] = metadata[key]
            page = self.library_pages.get(item.get("library_id"))
            if page is None:
                page = self.shows_page if is_show else self.movies_page
            card = page.card_by_path.get(normalize_media_path(item.get("file_path", "")))
            if card is not None and card.item.get("id") == item.get("id"):
                for key in ("original_language", "genres", "rating", "runtime", "cast", "certification",
                            "certification_country", "certification_order", "certification_checked", "certification_error"):
                    if key in item:
                        card.item[key] = item[key]
            page._data_revision += 1
            page.schedule_reflow()
            lines = []
            certification = str(metadata.get("certification") or "").strip()
            if certification:
                country = str(metadata.get("certification_country") or "HU").strip().upper()
                lines.append(f"Korhatár ({country}): {certification}")
            elif metadata.get("certification_checked") is True:
                lines.append(
                    "Korhatár-besorolás nem tölthető be"
                    if metadata.get("certification_error") else "Nincs korhatár-besorolás"
                )
            else:
                lines.append("Korhatár-besorolás nem tölthető be")
            genres = metadata.get("genres") or []
            if genres:
                lines.append("Műfaj: " + ", ".join(genres))
            rating = metadata.get("rating")
            if isinstance(rating, (int, float)) and rating > 0:
                lines.append(f"TMDB értékelés: {rating:.1f}/10")
            runtime = metadata.get("runtime")
            if isinstance(runtime, int) and runtime > 0:
                lines.append(f"{'Epizódhossz' if is_show else 'Játékidő'}: {runtime} perc")
            cast = metadata.get("cast") or []
            if cast:
                lines.append("Szereplők: " + ", ".join(cast))
            metadata_lbl.setText("\n".join(lines) if lines else "Nincs további TMDB-adat.")

        def refresh_detail_metadata(updated=None):
            if detail_state["closed"]:
                return
            if updated is not None:
                updated = dict(updated)
                item.clear()
                item.update(updated)
            detail_state["generation"] += 1
            generation = detail_state["generation"]
            metadata_lbl.setText("További adatok betöltése…")
            try:
                tmdb_id = int(item.get("id") or 0)
            except (TypeError, ValueError):
                tmdb_id = 0
            if tmdb_id <= 0:
                metadata_lbl.setText("További adatokhoz előbb párosítsd a médiát a TMDB-vel.")
                return
            cache_key = f"media:{'tv' if is_show else 'movie'}:{tmdb_id}"
            cached_metadata, _cache_fresh = read_tmdb_metadata_cache(cache_key)
            if cached_metadata:
                show_media_metadata({"status": "success", **cached_metadata}, generation)
            metadata_worker = TmdbMediaMetadataWorker(tmdb_id, not is_show)
            metadata_worker.metadata_ready.connect(lambda metadata, request=generation: show_media_metadata(metadata, request))
            run_worker(metadata_worker)

        dlg._synostream_refresh_metadata = refresh_detail_metadata
        refresh_detail_metadata()

        right.addWidget(QLabel("Lejátszó: MPV"))

        if is_show:
            ep_label = QLabel("Epizódok (a kiválasztott résztől folytatva):")
            ep_label.setStyleSheet("font-weight: bold; color: #ffffff; margin-top: 5px;")
            show_watched_button = QPushButton("Megjelölés megnézettként", dlg)
            show_watched_button.setCheckable(True)
            show_watched_button.setEnabled(False)
            show_watched_button.setToolTip("A sorozat összes epizódját megjelöli megnézettként vagy nézetlenként.")
            episode_header = QHBoxLayout()
            episode_header.addWidget(ep_label, 1)
            episode_header.addWidget(show_watched_button)
            right.addLayout(episode_header)

            ep_status = QLabel("Epizódok betöltése...")
            ep_status.setWordWrap(True)
            ep_status.setStyleSheet("color: #888888; font-style: italic;")
            right.addWidget(ep_status)

            ep_list = QTreeWidget()
            ep_list.setHeaderHidden(True)
            ep_list.setIndentation(18)
            ep_list.setMinimumHeight(300)
            ep_list.hide()
            right.addWidget(ep_list, 100)

            btn_play_ep = QPushButton("Lejátszás innen")
            btn_play_ep.setProperty("class", "ActionBtn")
            btn_play_ep.setToolTip(
                "A lejátszás a kijelölt résszel indul, majd MPV automatikusan elindítja a soron következőt."
            )
            btn_play_ep.hide()
            btn_play_ep.setEnabled(False)
            right.addWidget(btn_play_ep)
            right.addStretch(1)
            episode_entries = []

            def update_show_watched_button():
                episode_states = []
                for season_index in range(ep_list.topLevelItemCount()):
                    season_item = ep_list.topLevelItem(season_index)
                    for episode_index in range(season_item.childCount()):
                        episode_item = season_item.child(episode_index)
                        if episode_item.data(0, Qt.ItemDataRole.UserRole):
                            episode_states.append(
                                episode_item.checkState(0) == Qt.CheckState.Checked
                            )
                all_watched = bool(episode_states) and all(episode_states)
                was_blocked = show_watched_button.blockSignals(True)
                show_watched_button.setChecked(all_watched)
                show_watched_button.setText(
                    "✓ Megnézve" if all_watched else "Megjelölés megnézettként"
                )
                show_watched_button.blockSignals(was_blocked)

            def refresh_episode_state(file_path):
                if detail_state["closed"]:
                    return
                target = normalize_media_path(file_path)
                was_blocked = ep_list.blockSignals(True)
                try:
                    for season_index in range(ep_list.topLevelItemCount()):
                        season_item = ep_list.topLevelItem(season_index)
                        for episode_index in range(season_item.childCount()):
                            episode_item = season_item.child(episode_index)
                            path = episode_item.data(0, Qt.ItemDataRole.UserRole)
                            if path and normalize_media_path(path) == target:
                                saved = get_playback_state(path) or {}
                                episode_item.setCheckState(0, Qt.CheckState.Checked if saved.get("watched") else Qt.CheckState.Unchecked)
                finally:
                    ep_list.blockSignals(was_blocked)
                update_show_watched_button()

            self.playback_state_changed.connect(refresh_episode_state)
            def disconnect_episode_updates(_result):
                with contextlib.suppress(TypeError, RuntimeError):
                    self.playback_state_changed.disconnect(refresh_episode_state)
            dlg.finished.connect(disconnect_episode_updates)

            def on_show_watched_toggled(watched):
                if not episode_entries:
                    return
                self.persist_watched_states(episode_entries, watched)
                was_blocked = ep_list.blockSignals(True)
                try:
                    target_state = Qt.CheckState.Checked if watched else Qt.CheckState.Unchecked
                    for season_index in range(ep_list.topLevelItemCount()):
                        season_item = ep_list.topLevelItem(season_index)
                        for episode_index in range(season_item.childCount()):
                            episode_item = season_item.child(episode_index)
                            if episode_item.data(0, Qt.ItemDataRole.UserRole):
                                episode_item.setCheckState(0, target_state)
                finally:
                    ep_list.blockSignals(was_blocked)
                update_show_watched_button()

            show_watched_button.toggled.connect(on_show_watched_toggled)

            def play_selected_episode():
                current = ep_list.currentItem()
                full_path = current.data(0, Qt.ItemDataRole.UserRole) if current else None
                if full_path:
                    selected_index = next((index for index, entry in enumerate(episode_entries)
                                           if normalize_media_path(entry["path"]) == normalize_media_path(full_path)), None)
                    queue = episode_entries[selected_index:] if selected_index is not None else [{
                        "path": full_path,
                        "episode_title": current.data(0, Qt.ItemDataRole.UserRole + 1) or current.text(0),
                    }]
                    media_info = {
                        "media_title": item.get("title", ""),
                        "episode_title": queue[0].get("episode_title", ""),
                        "poster": item.get("poster", ""),
                        "is_movie": False,
                        "original_language": item.get("original_language", ""),
                    }
                    for entry in queue:
                        entry["media_title"] = media_info["media_title"]
                        entry["poster"] = media_info["poster"]
                        entry["is_movie"] = False
                        entry["original_language"] = media_info["original_language"]
                    play_media(
                        dlg, full_path, item.get("title"),
                        media_info=media_info, playlist_entries=queue,
                    )
                else:
                    QMessageBox.warning(dlg, "Figyelmeztetés", "Válassz ki egy epizódot a listából!")

            btn_play_ep.clicked.connect(play_selected_episode)
            ep_list.itemActivated.connect(lambda *_args: play_selected_episode())
            ep_list.currentItemChanged.connect(
                lambda current, _previous: btn_play_ep.setEnabled(
                    bool(current and current.data(0, Qt.ItemDataRole.UserRole))
                )
            )

            # Az epizódok bejárása háttérszálon fut (NAS-on lassú lehet); a bejárási hibát jelezzük.
            state = {"closed": False}

            def on_episodes(episodes, error):
                if state["closed"]:
                    return
                seasons = {}
                parsed_episodes = []
                used_episode_numbers = {}
                for rel_path, full_ep_path in episodes:
                    season, episode, has_explicit_number = parse_episode_position(rel_path)
                    range_hint = parse_episode_range_hint(rel_path)
                    if has_explicit_number:
                        used_episode_numbers.setdefault(season, set()).add(episode)
                    parsed_episodes.append((
                        season, episode, has_explicit_number, full_ep_path, range_hint,
                    ))

                next_fallback_number = {}
                active_range_scope = {}
                for season, episode, has_explicit_number, full_ep_path, range_hint in parsed_episodes:
                    if range_hint:
                        range_scope, range_start, _range_end = range_hint
                        if active_range_scope.get(season) != range_scope:
                            next_fallback_number[season] = range_start
                            active_range_scope[season] = range_scope
                    if not has_explicit_number:
                        used = used_episode_numbers.setdefault(season, set())
                        episode = next_fallback_number.get(season, 1)
                        while episode in used:
                            episode += 1
                        used.add(episode)
                        next_fallback_number[season] = episode + 1
                    seasons.setdefault(season, []).append((episode, full_ep_path))
                for season in sorted(seasons):
                    season_item = QTreeWidgetItem([f"{season}. évad"])
                    season_item.setData(0, Qt.ItemDataRole.UserRole + 2, season)
                    ep_list.addTopLevelItem(season_item)
                    for episode, full_ep_path in sorted(seasons[season], key=lambda row: row[0]):
                        episode_item = QTreeWidgetItem([f"{episode}. rész"])
                        episode_item.setData(0, Qt.ItemDataRole.UserRole, full_ep_path)
                        episode_title = f"S{str(season).zfill(2)}E{int(episode):02d}"
                        episode_item.setData(0, Qt.ItemDataRole.UserRole + 1, episode_title)
                        episode_item.setData(0, Qt.ItemDataRole.UserRole + 2, int(episode))
                        episode_item.setFlags(episode_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        saved_state = get_playback_state(full_ep_path)
                        episode_item.setCheckState(
                            0, Qt.CheckState.Checked if saved_state and saved_state["watched"]
                            else Qt.CheckState.Unchecked,
                        )
                        season_item.addChild(episode_item)
                        episode_entries.append({
                            "path": full_ep_path,
                            "episode_title": episode_title,
                            "season_number": int(season),
                            "episode_number": int(episode),
                            "media_title": item.get("title", ""),
                            "poster": item.get("poster", ""),
                            "is_movie": False,
                        })
                    season_item.setExpanded(len(seasons) == 1)
                if episodes:
                    def on_episode_check_changed(tree_item, column):
                        if column != 0:
                            return
                        episode_path = tree_item.data(0, Qt.ItemDataRole.UserRole)
                        if not episode_path:
                            return
                        self.persist_watched_state(
                            episode_path, item.get("title", ""),
                            tree_item.data(0, Qt.ItemDataRole.UserRole + 1) or tree_item.text(0),
                            item.get("poster", ""), False,
                            tree_item.checkState(0) == Qt.CheckState.Checked,
                        )
                        update_show_watched_button()

                    ep_list.itemChanged.connect(on_episode_check_changed)
                    show_watched_button.setEnabled(True)
                    update_show_watched_button()
                    ep_list.show()
                    btn_play_ep.show()
                    btn_play_ep.setEnabled(False)
                    if error:
                        ep_status.setText(f"⚠ Részleges lista. {error}")
                        ep_status.setStyleSheet("color: #e67e22; font-style: italic;")
                    else:
                        ep_status.hide()

                    if tmdb_id > 0:
                        def on_season_metadata(metadata_by_season, _metadata_error):
                            if state["closed"]:
                                return
                            was_blocked = ep_list.blockSignals(True)
                            try:
                                for season_index in range(ep_list.topLevelItemCount()):
                                    season_item = ep_list.topLevelItem(season_index)
                                    season_number = season_item.data(0, Qt.ItemDataRole.UserRole + 2)
                                    season_data = metadata_by_season.get(season_number, {})
                                    if not isinstance(season_data, dict):
                                        continue
                                    for child_index in range(season_item.childCount()):
                                        episode_item = season_item.child(child_index)
                                        episode_number = episode_item.data(0, Qt.ItemDataRole.UserRole + 2)
                                        episode_data = season_data.get(episode_number, {})
                                        if not isinstance(episode_data, dict):
                                            continue
                                        episode_name = episode_data.get("name") or ""
                                        if episode_name:
                                            episode_label = (
                                                f"{episode_number}. {episode_name}"
                                                if UI_LANGUAGE == "hu"
                                                else f"Episode {episode_number}: {episode_name}"
                                            )
                                            episode_item.setRawText(0, episode_label)
                                            playback_title = (
                                                f"S{int(season_number):02d}E{int(episode_number):02d} – {episode_name}"
                                            )
                                            episode_item.setData(
                                                0, Qt.ItemDataRole.UserRole + 1, playback_title
                                            )
                                            full_path = episode_item.data(0, Qt.ItemDataRole.UserRole)
                                            for entry in episode_entries:
                                                if normalize_media_path(entry["path"]) == normalize_media_path(full_path):
                                                    entry["episode_title"] = playback_title
                                                    break
                                        tooltip_lines = []
                                        if episode_name:
                                            tooltip_lines.append(episode_name)
                                        if episode_data.get("air_date"):
                                            tooltip_lines.append(f"Megjelenés: {episode_data['air_date']}")
                                        if episode_data.get("overview"):
                                            tooltip_lines.append(episode_data["overview"])
                                        if tooltip_lines:
                                            episode_item.setToolTip(0, "\n\n".join(tooltip_lines))
                            finally:
                                ep_list.blockSignals(was_blocked)

                        season_worker = TmdbSeasonMetadataWorker(tmdb_id, seasons.keys())
                        season_worker.metadata_ready.connect(on_season_metadata)
                        run_worker(season_worker)
                else:
                    ep_status.setText(error or "Nem találhatók videófájlok ebben a mappában.")
                    ep_status.setStyleSheet("color: #e67e22; font-style: italic;")

            worker = EpisodeScanWorker(item.get("episode_roots") or file_path)
            worker.episodes_found.connect(on_episodes)

            def on_dialog_finished(_result):
                state["closed"] = True
                worker.requestInterruption()

            dlg.finished.connect(on_dialog_finished)
            run_worker(worker)
        else:
            saved_state = get_playback_state(file_path) or {}
            watched_button = QPushButton(
                "✓ Megnézve" if saved_state.get("watched") else "Megjelölés megnézettként"
            )
            watched_button.setCheckable(True)
            watched_button.setChecked(bool(saved_state.get("watched")))

            def on_movie_watched_changed(checked):
                watched_button.setText("✓ Megnézve" if checked else "Megjelölés megnézettként")
                self.persist_watched_state(
                    file_path, item.get("title", ""), "", item.get("poster", ""), True, checked
                )

            watched_button.toggled.connect(on_movie_watched_changed)
            right.addWidget(watched_button, alignment=Qt.AlignmentFlag.AlignLeft)
            right.addStretch()
            has_saved_position = saved_state.get("position", 0) >= 15 and not saved_state.get("watched")
            can_resume = has_saved_position
            btn_play = QPushButton("Folytatás" if can_resume else "Lejátszás")
            btn_play.setProperty("class", "ActionBtn")
            btn_play.clicked.connect(
                lambda: play_media(
                    dlg, file_path, item["title"],
                    media_info={
                        "media_title": item.get("title", ""), "poster": item.get("poster", ""),
                        "is_movie": True,
                        "original_language": item.get("original_language", ""),
                    },
                )
            )
            right.addWidget(btn_play)
            btn_restart = QPushButton("Lejátszás elölről")
            btn_restart.setVisible(can_resume)
            if has_saved_position:
                btn_restart.clicked.connect(
                    lambda: play_media(
                        dlg, file_path, item["title"],
                        media_info={
                            "media_title": item.get("title", ""), "poster": item.get("poster", ""),
                            "is_movie": True,
                            "original_language": item.get("original_language", ""),
                        },
                        resume_position=0,
                    )
                )
                right.addWidget(btn_restart)

        main_layout.addLayout(right, 1)
        dlg.exec()
        dlg.deleteLater()

    # --- bezárás ---
    def running_threads(self):
        threads = list(_background_workers)
        if self.scanner_thread is not None:
            threads.append(self.scanner_thread)
        return [t for t in threads if t.isRunning()]

    def closeEvent(self, event):
        try:
            config["window_geometry"] = bytes(self.saveGeometry().toHex()).decode("ascii")
            ok, error = save_config()
            if not ok:
                LOGGER.error("Nem sikerült menteni az ablakméretet és az alkalmazás állapotát: %s", error)
        except Exception:
            LOGGER.exception("Nem sikerült menteni az ablakgeometriát.")
        self.is_closing = True
        self.downloads_page.shutdown()
        threads = self.running_threads()
        active_playback = [
            thread for thread in threads
            if isinstance(thread, MpvPlaybackMonitor) and thread.process.poll() is None
        ]
        for t in threads:
            if t not in active_playback:
                t.requestInterruption()

        # Keep the hidden app and its local NAS proxy alive until MPV exits; otherwise
        # remote playback would break and the playback monitor could not save progress.
        all_stopped = not active_playback
        for thread in threads:
            if thread in active_playback:
                continue
            if not thread.wait(500):
                all_stopped = False
        if all_stopped:
            event.accept()
            return

        # Valamelyik szál még hálózati kérésre vár: elrejtjük az ablakot,
        # és kilépünk, amint minden szál leállt.
        event.ignore()
        self.hide()
        for dialog in self.findChildren(QDialog):
            if dialog.isVisible():
                dialog.hide()
        if active_playback:
            LOGGER.info("Az alkalmazás a háttérben marad az MPV-lejátszás végéig.")
        if self.close_timer is None:
            self.close_timer = QTimer(self)
            self.close_timer.setInterval(250)
            self.close_timer.timeout.connect(self.finish_close)
            self.close_timer.start()

    def finish_close(self):
        if not self.running_threads():
            self.close_timer.stop()
            QApplication.quit()


# ==========================================
# INDÍTÁS
# ==========================================
def main():
    smoke_test = "--smoke-test" in sys.argv
    if smoke_test and not os.environ.get("SYNOSTREAM_DATA_DIR"):
        return 2  # Automated smoke checks must explicitly choose an isolated data directory.
    app = QApplication(sys.argv)
    if os.path.isfile(APP_ICON_FILE):
        app.setWindowIcon(app._synostream_application_icon)
    app.setStyleSheet(DS_VIDEO_PURPLE_FIXED_QSS)

    if CACHE_DIR_INIT_ERROR is not None:
        LOGGER.critical("Nem hozható létre a plakátcache mappája: %s", CACHE_DIR_INIT_ERROR)
        QMessageBox.critical(
            None, "Írási hiba",
            f"Az adatmappába nem lehet írni, ezért a SynoStream nem indítható el:\n\n"
            f"{BASE_DIR}\n\nEllenőrizd az adatmappa írási jogosultságát.",
        )
        return 1

    try:
        init_db()
        prune_poster_cache()
    except (sqlite3.Error, OSError) as e:
        LOGGER.critical("Alkalmazásindítási hiba az adatbázis inicializálásakor: %s", e, exc_info=True)
        QMessageBox.critical(None, "Adatbázis hiba", f"Nem sikerült inicializálni az adatbázist:\n{e}")
        return 1

    if smoke_test:
        config["startup_scan_mode"] = "none"
    window = DSVideoWindow()
    retranslate_ui()
    window.show()
    QTimer.singleShot(0, lambda: acknowledge_update(sys.argv, APP_VERSION))
    if not smoke_test:
        QTimer.singleShot(2000, lambda: window.updater.check(False))
        QTimer.singleShot(30000, cleanup_completed_updates)
    QTimer.singleShot(0, lambda: set_windows_frame_colors(window))
    if smoke_test:
        def finish_smoke_test():
            with contextlib.closing(sqlite3.connect(DB_FILE)) as conn:
                schema = conn.execute("PRAGMA user_version").fetchone()[0]
            report = {"app_version": APP_VERSION, "schema_version": schema,
                      "library_created": window.stack.currentWidget() is window.library_pages[window.current_library_key],
                      "data_directory": BASE_DIR,
                      "downloads_created": window.stack.indexOf(window.downloads_page) >= 0,
                      "title_bar_visible": window._syno_title_bar.isVisible(),
                      "window_fullscreen": window.isFullScreen(),
                      "windows_app_id_set": app._synostream_app_id_set,
                      "window_icon_present": not window.windowIcon().isNull()}
            with open(os.path.join(BASE_DIR, "smoke_test.json"), "w", encoding="utf-8") as output:
                json.dump(report, output, indent=2)
            window.close()
            app.quit()
        QTimer.singleShot(300, finish_smoke_test)
    elif CONFIG_WARNING:
        QMessageBox.warning(window, "Konfigurációs figyelmeztetés", CONFIG_WARNING)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())








