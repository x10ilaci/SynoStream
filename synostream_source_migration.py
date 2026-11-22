import logging
"""Transactional source alias migration. Call inside settings_transaction + SQLite transaction."""
import copy
import json
import ntpath
from synostream_sources import expand_mapped_path


def canonicalize_config(settings, router, previous=None):
    result = copy.deepcopy(settings)
    convert = (lambda value: router.rebase(value,previous)) if previous is not None else router.canonical
    def paths(values):
        return list(dict.fromkeys(convert(value) for value in values))
    for key in ('movies_paths', 'shows_paths', 'excluded_media_paths'):
        if isinstance(result.get(key), list): result[key] = paths(result[key])
    for key in ('movies_path', 'shows_path'):
        if result.get(key): result[key] = convert(result[key])
    for key in ('remote_movies_path','remote_shows_path'):
        if result.get(key): result[key] = convert('syno://' + result[key])[7:]
    for library in result.get('custom_libraries', []):
        library['paths'] = paths(library.get('paths', []))
    for group in result.get('manual_show_groups', []):
        group['paths'] = paths(group.get('paths', []))
    # Moving a pair changes ownership of its root. Remove the old library's
    # representations after rebasing, including its legacy singular fields.
    previous_pairs = {pair.id: pair for pair in getattr(previous, 'pairs', ())}
    for pair in router.pairs:
        old = previous_pairs.get(pair.id)
        if old is None or old.library_id == pair.library_id: continue
        if old.library_id in ('movies', 'shows'):
            field = old.library_id + '_paths'
            result[field] = [path for path in result.get(field, []) if path != pair.remote]
            singular = old.library_id + '_path'
            if result.get(singular) == pair.remote: result[singular] = ''
            remote_field = 'remote_' + singular
            if result.get(remote_field) == pair.remote[7:]: result[remote_field] = ''
        else:
            library = next((lib for lib in result.get('custom_libraries', []) if lib.get('id') == old.library_id), None)
            if library is not None:
                library['paths'] = [path for path in library.get('paths', []) if path != pair.remote]
    for pair in router.pairs:
        key = pair.library_id
        if key in ('movies', 'shows'):
            field = key + '_paths'
            result[field] = paths([*result.get(field, []), pair.remote])
        else:
            library = next((lib for lib in result.get('custom_libraries', []) if lib.get('id') == key), None)
            if library is None: raise ValueError('Az összerendelés médiatára már nem létezik.')
            library['paths'] = paths([*library.get('paths', []), pair.remote])
    result['paired_sources'] = [pair.to_dict() for pair in router.pairs]
    return result


def migrate_database(conn, old_router, new_router):
    """Preserve manual choices, latest playback, portable events and card payloads."""
    preferred = {}
    def remember(value):
        value = expand_mapped_path(value)
        if isinstance(value, str) and value.startswith(('\\\\', '//')):
            preferred[ntpath.normcase(ntpath.normpath(value))] = value
    for payload, in conn.execute('SELECT payload FROM library_card_cache'):
        try: item = json.loads(payload)
        except (ValueError, TypeError): continue
        remember(item.get('file_path'))
        for value in item.get('episode_roots', []): remember(value)
    for payload, in conn.execute('SELECT playlist_paths FROM playback_state'):
        try:
            for value in json.loads(payload): remember(value)
        except (ValueError, TypeError): logging.getLogger("SynoStream").warning('Nem sikerült egy művelet: migrate_database. A korábbi adatokat vagy állapotot ellenőrizni kell.')
    for saved_root, saved_payload in conn.execute('SELECT root,payload FROM portable_events'):
        try:
            event = json.loads(saved_payload)
            if saved_root.startswith(('\\\\','//')):
                remember(ntpath.join(saved_root,*event['relative_path'].split('/')))
        except (ValueError,TypeError,KeyError): logging.getLogger("SynoStream").warning('Nem sikerült egy művelet: migrate_database. A korábbi adatokat vagy állapotot ellenőrizni kell.')
    # UNC database keys are case-folded by Windows. Existing NAS keys preserve
    # the real spelling, and let us merge a legacy key without changing identity.
    remote_spelling = {}
    for table in ('media_cache', 'playback_state', 'manual_overrides', 'library_card_cache'):
        for value, in conn.execute('SELECT file_path FROM ' + table):
            if not isinstance(value, str) or not value.startswith('syno://'): continue
            local = new_router.physical(value)
            if local:
                key = ntpath.normcase(ntpath.normpath(local))
                if key in remote_spelling and remote_spelling[key] != value:
                    raise ValueError('A NAS-on csak kis- és nagybetűben eltérő fájlnevek vannak. Ezeket az SMB-elérés nem különbözteti meg; használd ehhez a mappához a QuickConnect-elérést.')
                remote_spelling[key] = value
                remember(local)
    def convert(value):
        if not isinstance(value, str): return value
        mapped = expand_mapped_path(value)
        if mapped != value and new_router.pair_for(mapped): value = mapped
        if value.startswith(('\\\\', '//')):
            value = preferred.get(ntpath.normcase(ntpath.normpath(value)), value)
        return new_router.rebase(value,old_router)
    def payload(value, paths=False):
        if isinstance(value, list): return [payload(part, paths) for part in value]
        if isinstance(value, dict):
            return {key: payload(part, key in ('file_path', 'episode_roots', 'path', 'paths', 'playlist_paths')) for key, part in value.items()}
        return convert(value) if paths else value
    # Legacy UNC keys lacking any preserved spelling are resolved lazily by the
    # scan worker. Do not publish a guessed lowercase relative path to the NAS.
    pending = []
    for table in ('manual_overrides', 'playback_state'):
        for value, in conn.execute('SELECT file_path FROM ' + table):
            mapped = expand_mapped_path(value)
            if isinstance(mapped, str) and mapped.startswith(('\\\\','//')) and ntpath.normcase(ntpath.normpath(mapped)) not in preferred:
                converted = convert(value)
                pair = new_router.pair_for(converted)
                if pair: pending.append((converted,pair.remote))
    tables = ('manual_overrides', 'media_cache', 'playback_state', 'library_card_cache',
              'portable_events', 'portable_outbox', 'portable_state', 'portable_event_index', 'portable_file_checks', 'source_route_pending')
    plans = {}
    for table in tables:
        schema = conn.execute('PRAGMA table_info(' + table + ')').fetchall()
        if not schema: continue
        names = [column[1] for column in schema]
        primary = [column[1] for column in sorted(schema, key=lambda column: column[5]) if column[5]]
        grouped = {}
        for values in conn.execute('SELECT * FROM ' + table):
            row = dict(zip(names, values)); before = dict(row)
            for column in ('file_path', 'root'):
                if column in row:
                    row[column] = convert(row[column])
                    if isinstance(row[column], str) and not row[column].startswith('syno://'):
                        row[column] = ntpath.normcase(ntpath.normpath(row[column]))
            if table == 'source_route_pending' and not row['file_path'].startswith('syno://'):
                # Local Windows paths are case-insensitive; they no longer need
                # the NAS spelling check that previously deferred publication.
                continue
            if table == 'library_card_cache':
                previous_pairs = {pair.id: pair for pair in getattr(old_router, 'pairs', ())}
                for pair in new_router.pairs:
                    old = previous_pairs.get(pair.id)
                    if (old and old.library_id != pair.library_id
                            and row.get('library_id') == old.library_id
                            and (row['file_path'] == pair.remote or row['file_path'].startswith(pair.remote + '/'))):
                        row['library_id'] = pair.library_id
                try: row['payload'] = json.dumps(payload(json.loads(row['payload'])), ensure_ascii=False)
                except (ValueError, TypeError): logging.getLogger("SynoStream").warning('Nem sikerült egy művelet: migrate_database. A korábbi adatokat vagy állapotot ellenőrizni kell.')
            if table == 'playback_state':
                try: row['playlist_paths'] = json.dumps(payload(json.loads(row['playlist_paths']), True), ensure_ascii=False)
                except (ValueError, TypeError): row['playlist_paths'] = '[]'
            identity = tuple(row[column] for column in primary)
            grouped.setdefault(identity, []).append((row, row == before))
        chosen = []
        for candidates in grouped.values():
            rows = [row for row, unchanged in candidates]
            if table == 'manual_overrides':
                valid = {(row['tmdb_id'], row['is_movie']) for row in rows if (row.get('tmdb_id') or 0) > 0}
                if len(valid) > 1:
                    raise ValueError('Ugyanahhoz a fájlhoz eltérő kézi párosítás tartozik a két elérésen. Előbb egyeztesd a párosításokat; az összerendelés nem módosított adatot.')
                rank = lambda item: ((item[0].get('tmdb_id') or 0) > 0, bool(item[0].get('custom_title')), item[1])
            elif table == 'playback_state':
                rank = lambda item: (item[0].get('last_played') or 0, bool(item[0].get('watched')), item[0].get('position') or 0)
            elif table == 'media_cache':
                rank = lambda item: (str(item[0].get('signature', '')).startswith('override:'), item[0].get('status') == 'success', item[0].get('lookup_at') or 0, item[1])
            elif table in ('portable_events', 'portable_outbox'):
                if len({row['payload'] for row in rows}) > 1:
                    raise ValueError('Egy közös párosítási esemény azonosítója eltérő tartalommal szerepel. Az összerendelés nem menthető adatvesztés nélkül.')
                rank = lambda item: (item[1],)
            else:
                rank = lambda item: (item[1],)
            chosen.append(max(candidates, key=rank)[0])
        plans[table] = (names, chosen)
    # Prepare every merge before mutating anything; the outer transaction also
    # restores JSON/DPAPI files if either database or configuration save fails.
    changed = 0
    for table, (names, rows) in plans.items():
        conn.execute('DELETE FROM ' + table)
        placeholders = ','.join('?' for name in names)
        conn.executemany('INSERT INTO ' + table + '(' + ','.join(names) + ') VALUES (' + placeholders + ')',
                         [tuple(row[name] for name in names) for row in rows])
        changed += len(rows)
    # Directory fingerprints depend on the transport and are safe to rebuild.
    conn.execute('DELETE FROM scan_directory_cache')
    conn.execute('DELETE FROM portable_file_checks')
    conn.execute('CREATE TABLE IF NOT EXISTS source_route_pending(file_path TEXT PRIMARY KEY, root TEXT NOT NULL)')
    conn.executemany('INSERT OR IGNORE INTO source_route_pending VALUES (?,?)',pending)
    return changed


def resolve_pending_cases(conn, root, client, router):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_route_pending'").fetchone(): return
    rows = conn.execute('SELECT file_path FROM source_route_pending WHERE root=?',(root,)).fetchall()
    if not rows: return
    replacements = {}
    directory_cache = {}
    for path, in rows:
        try:
            if hasattr(client,'resolve_case'):
                actual = client.resolve_case(path)
            else:
                current = root.rstrip('/')
                for part in path[len(current):].strip('/').split('/'):
                    if current not in directory_cache: directory_cache[current] = client.list_folder(current[7:])
                    matches = [entry['name'] for entry in directory_cache[current] if str(entry.get('name','')).casefold() == part.casefold()]
                    if not matches: raise FileNotFoundError(path)
                    if len(matches) != 1: raise ValueError('Nem egyértelmű fájlnév.')
                    current += '/' + matches[0]
                actual = current
            replacements[path] = actual
        except (FileNotFoundError,ValueError):
            # A removed/ambiguous file must not block unrelated good pairings.
            continue
    if not replacements: return
    class IdentitySpelling:
        def canonical(self, path):return replacements.get(path,path)
    with conn:
        migrate_database(conn,IdentitySpelling(),router)
        conn.executemany('DELETE FROM source_route_pending WHERE file_path=?',[(path,) for path in set(replacements) | set(replacements.values())])
