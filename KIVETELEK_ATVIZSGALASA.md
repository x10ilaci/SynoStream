# Elnyelt kivételek átvizsgálása – Windows 1.105

Az eredeti kiadott forrás 32 egyutas `except …: pass` kezelőjét AST-alapon, fájlonként egyszer vizsgáltuk. A helyek az eredeti kiadás sorszámai. Nem minden elkapott kivétel hiba.

| Hely | Kivétel | Művelet | Értékelés | Intézkedés / indok |
|---|---|---|---|---|
| SynoStream_1.105.py:1409 | (AttributeError, OSError, TypeError, ValueError, ctypes.ArgumentError) | set_windows_frame_colors | Ártalmatlan / szándékos kezelés | Nem támogatott DWM-ablakdíszítés; az ablak működését nem érinti. |
| SynoStream_1.105.py:2472 | (OSError, sqlite3.Error, TypeError, ValueError) | write_tmdb_metadata_cache | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| SynoStream_1.105.py:2499 | (OSError, sqlite3.Error, TypeError, ValueError) | merge_tmdb_metadata_cache | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| SynoStream_1.105.py:3217 | InterruptedError | run | Ártalmatlan / szándékos kezelés | Szándékos megszakítás vagy erőforrás-takarítás; nincs elhallgatott adatmentés. |
| SynoStream_1.105.py:6002 | (ValueError, TypeError) | _begin_inventory | Ártalmatlan / szándékos kezelés | Hibás gyorsítótár-bejegyzést kihagy; a következő beolvasás pótolja. |
| SynoStream_1.105.py:6644 | OSError | play_with_mpv | Ártalmatlan / szándékos kezelés | Ideiglenes lejátszólista takarítása; a médiafájl érintetlen. |
| SynoStream_1.105.py:10171 | RuntimeError | on_override_refresh_done | Ártalmatlan / szándékos kezelés | Időközben bezárt Qt-ablak; a mentett médiainfó már megvan. |
| SynoStream_1.105.py:2491 | (TypeError, ValueError) | merge_tmdb_metadata_cache | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| SynoStream_1.105.py:3743 | requests.RequestException | run | Ártalmatlan / szándékos kezelés | Szándékos megszakítás vagy erőforrás-takarítás; nincs elhallgatott adatmentés. |
| SynoStream_1.105.py:6557 | OSError | play_with_mpv | Ártalmatlan / szándékos kezelés | Ideiglenes lejátszólista takarítása; a médiafájl érintetlen. |
| SynoStream_1.105.py:4213 | Exception | do_GET | Ártalmatlan / szándékos kezelés | Nem tartós adatot érintő, szándékos takarítás vagy diagnosztikai kijelentkezés. |
| SynoStream_1.105.py:6352 | Exception | do_GET | Ártalmatlan / szándékos kezelés | Nem tartós adatot érintő, szándékos takarítás vagy diagnosztikai kijelentkezés. |
| synostream_file_selection_ui.py:108 | (TypeError, ValueError) | update_summary | Ártalmatlan / szándékos kezelés | Hibás méretmező kihagyása; nem módosít fájlt. |
| synostream_nas.py:421 | requests.RequestException | close | Ártalmatlan / szándékos kezelés | Kijelentkezés legjobb igyekezet szerint; a szerver munkamenete lejár. |
| synostream_nfo.py:33 | ET.ParseError | parse_nfo | Ártalmatlan / szándékos kezelés | Nem XML-es NFO esetén szöveges feldolgozás következik. |
| synostream_nfo.py:19 | UnicodeError | decode_nfo | Ártalmatlan / szándékos kezelés | Következő karakterkódolás kipróbálása. |
| synostream_playback.py:272 | Exception | run | Ártalmatlan / szándékos kezelés | Szándékos megszakítás vagy erőforrás-takarítás; nincs elhallgatott adatmentés. |
| synostream_playback.py:277 | FileNotFoundError | run | Ártalmatlan / szándékos kezelés | Szándékos megszakítás vagy erőforrás-takarítás; nincs elhallgatott adatmentés. |
| synostream_recommendation_ui.py:124 | Exception | preview_loaded | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| synostream_recommendation_ui.py:201 | Exception | filter_owned | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| synostream_source_migration.py:68 | (ValueError, TypeError) | migrate_database | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| synostream_source_migration.py:74 | (ValueError, TypeError, KeyError) | migrate_database | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| synostream_source_migration.py:139 | (ValueError, TypeError) | migrate_database | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| synostream_sources.py:328 | (OSError, TimeoutError) | open_stream | Ártalmatlan / szándékos kezelés | Sikertelen helyi olvasás után NAS-os visszaesés. |
| synostream_torrent_selection.py:133 | Exception | prepare | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| synostream_update_ui.py:124 | (OSError, ValueError, updates.UpdateError) | _download_automatic | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| synostream_update_ui.py:240 | (OSError, ValueError) | install | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| synostream_updates.py:313 | (ValueError, IndexError, OSError, TypeError, AttributeError) | acknowledge_update | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| synostream_updates.py:345 | OSError | _retire_failed_install | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| synostream_updates.py:248 | OSError | launch_pending_update | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| synostream_updates.py:437 | OSError | helper_main | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |
| synostream_updates.py:417 | (OSError, subprocess.SubprocessError) | install_job | Hibát vagy állapotvesztést rejthet | Statikus, titokmentes figyelmeztető napló került bele. |

Az új MPV-telepítőben a már lecserélt régi könyvtár zárolás miatti sikertelen törlése takarítási kivétel: a teljes `.old-*` könyvtár megmarad, az új telepítés érvényes. Nem töröljük erőből. A naplóüzenetek nem tartalmaznak hitelesítő adatot, URL-t, munkamenetet vagy beolvasott payloadot.
