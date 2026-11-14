"""Per-library TMDB recommendations, local feedback and rotating discovery batches."""
import contextlib
import json
import math
import random
import re
import sqlite3
import time

CACHE_TTL = 7 * 86400
MAX_REQUESTS = 4
MAX_LOCALIZATION_REQUESTS = 8
BATCH_SIZE = 12


def init_tables(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS recommendation_cache (
            library_id TEXT NOT NULL, media_type TEXT NOT NULL, seed_id INTEGER NOT NULL,
            language TEXT NOT NULL, payload TEXT NOT NULL, fetched_at REAL NOT NULL,
            PRIMARY KEY(library_id,media_type,seed_id,language));
        CREATE TABLE IF NOT EXISTS recommendation_feedback (
            library_id TEXT NOT NULL, media_type TEXT NOT NULL, tmdb_id INTEGER NOT NULL,
            state TEXT NOT NULL, payload TEXT NOT NULL, updated_at REAL NOT NULL,
            PRIMARY KEY(library_id,media_type,tmdb_id));
        CREATE TABLE IF NOT EXISTS recommendation_seen (
            library_id TEXT NOT NULL, media_type TEXT NOT NULL, tmdb_id INTEGER NOT NULL,
            shown_at REAL NOT NULL, shown_count INTEGER NOT NULL,
            PRIMARY KEY(library_id,media_type,tmdb_id));
        CREATE TABLE IF NOT EXISTS recommendation_localization (
            media_type TEXT NOT NULL, tmdb_id INTEGER NOT NULL, language TEXT NOT NULL,
            has_overview INTEGER NOT NULL, payload TEXT NOT NULL, checked_at REAL NOT NULL,
            PRIMARY KEY(media_type,tmdb_id,language));
    ''')


def identity(item):
    try:
        value = item.get('id')
        if isinstance(value, bool) or isinstance(value, float) and not value.is_integer(): return None
        value = int(value or 0)
        kind = item.get('media_type')
        if kind not in ('movie', 'tv'):
            if item.get('is_movie') is None: return None
            kind = 'movie' if item['is_movie'] else 'tv'
        return (kind, value) if value > 0 else None
    except (ValueError, TypeError, AttributeError):
        return None


def normalize_result(item, kind):
    if not isinstance(item, dict) or item.get('adult'): return None
    key = identity(dict(item, media_type=kind))
    title = item.get('title') if kind == 'movie' else item.get('name')
    title = title or item.get('original_title') or item.get('original_name')
    if not key or not isinstance(title, str) or not title.strip(): return None
    poster = item.get('poster_path') or ''
    if not isinstance(poster, str) or not re.fullmatch(r'/[A-Za-z0-9_-]+\.(?:jpg|png|webp)', poster, re.I): poster = ''
    return dict(id=key[1], media_type=kind, title=title.strip()[:500],
                overview=str(item.get('overview') or '')[:12000],
                date=str(item.get('release_date') or item.get('first_air_date') or '')[:10],
                poster_url='https://image.tmdb.org/t/p/w342' + poster if poster else '')


def seed_items(items):
    result = {}
    for item in items:
        key = identity(item)
        if key:
            result[key] = dict(id=key[1], media_type=key[0], title=str(item.get('title') or item.get('name') or '')[:500])
    return list(result.values())


def poster_names(conn):
    result = set()
    for table in ('recommendation_cache', 'recommendation_feedback'):
        try: rows = conn.execute('SELECT payload FROM ' + table).fetchall()
        except sqlite3.Error: continue
        for payload, in rows:
            try: data = json.loads(payload)
            except (ValueError, TypeError): continue
            for item in data if isinstance(data, list) else [data]:
                key = identity(item)
                if key: result.add(f'{key[0]}_{key[1]}.jpg')
    return result


class RecommendationStore:
    def __init__(self, database): self.database = str(database)

    @contextlib.contextmanager
    def connection(self):
        with contextlib.closing(sqlite3.connect(self.database, timeout=10)) as conn:
            yield conn

    def feedback(self, library_id):
        with self.connection() as conn:
            result = {}
            for kind, media_id, state, payload in conn.execute(
                    'SELECT media_type,tmdb_id,state,payload FROM recommendation_feedback WHERE library_id=? ORDER BY updated_at DESC', (library_id,)):
                try: item = json.loads(payload)
                except (TypeError, ValueError): continue
                if identity(item) == (kind, media_id): result[(kind, media_id)] = (state, item)
            return result

    def set_feedback(self, library_id, item, state):
        key = identity(item)
        if not key or state not in ('interested', 'dismissed', 'neutral'): raise ValueError('Érvénytelen ajánlói visszajelzés.')
        with self.connection() as conn, conn:
            if state == 'neutral':
                conn.execute('DELETE FROM recommendation_feedback WHERE library_id=? AND media_type=? AND tmdb_id=?', (library_id, *key))
            else:
                conn.execute('INSERT OR REPLACE INTO recommendation_feedback VALUES (?,?,?,?,?,?)',
                             (library_id, *key, state, json.dumps(item, ensure_ascii=False), time.time()))

    def saved(self, library_id, owned):
        return [item for key, (state, item) in self.feedback(library_id).items() if state == 'interested' and key not in owned]

    def mark_seen(self, library_id, items):
        now = time.time()
        with self.connection() as conn, conn:
            for item in items:
                key = identity(item)
                if key:
                    conn.execute('''INSERT INTO recommendation_seen VALUES (?,?,?,?,1)
                        ON CONFLICT(library_id,media_type,tmdb_id) DO UPDATE SET
                        shown_at=excluded.shown_at,shown_count=shown_count+1''', (library_id, *key, now))

    def pool(self, library_id, seeds, language):
        keys = {identity(seed) for seed in seeds}
        result = {}
        ages = {}
        with self.connection() as conn:
            for kind, seed_id, payload, fetched in conn.execute(
                    'SELECT media_type,seed_id,payload,fetched_at FROM recommendation_cache WHERE library_id=? AND language=?', (library_id, language)):
                seed_key = (kind, seed_id)
                if seed_key not in keys: continue
                try: items = json.loads(payload)
                except (TypeError, ValueError): continue
                if not isinstance(items, list): continue
                ages[seed_key] = fetched
                seen_in_seed = set()
                for rank, item in enumerate(items[:60]):
                    key = identity(item)
                    if not key or key[0] != kind or key in seen_in_seed: continue
                    if not isinstance(item.get('title'), str) or not item['title'].strip(): continue
                    seen_in_seed.add(key)
                    if key not in result: result[key] = dict(item, score=0.0, source_keys=[])
                    candidate = result[key]
                    candidate['score'] += 1 / (4 + rank)
                    candidate['source_keys'].append(seed_key)
        titles = {identity(seed):seed['title'] for seed in seeds}
        for candidate in result.values():
            candidate['reasons'] = [titles[key] for key in candidate['source_keys'] if titles.get(key)][:3]
        self.apply_localization(result, language)
        return result, ages

    def localization(self):
        with self.connection() as conn:
            result = {}
            for kind, media_id, has_overview, payload, checked in conn.execute(
                    "SELECT media_type,tmdb_id,has_overview,payload,checked_at FROM recommendation_localization WHERE language='hu'"):
                try: data = json.loads(payload)
                except (TypeError, ValueError): continue
                if isinstance(data, dict): result[(kind, media_id)] = (bool(has_overview), data, checked)
            return result

    def apply_localization(self, pool, language):
        known = self.localization()
        for key, item in pool.items():
            entry = known.get(key)
            # Unknown is not the same as a confirmed missing translation.
            item['has_hu_metadata'] = entry[0] if entry else None
            if entry and entry[0] and str(language).startswith('hu'):
                title = entry[1].get('title')
                overview = entry[1].get('overview')
                if isinstance(title, str) and title.strip(): item['title'] = title[:500]
                if isinstance(overview, str) and overview.strip(): item['overview'] = overview[:12000]

    def check_hungarian(self, library_id, pool, owned, request, stop, previous=()):
        known = self.localization()
        feedback = self.feedback(library_id)
        previous = set(previous)
        pending = [key for key in pool if key not in owned and key not in feedback
                   and time.time() - known.get(key, (None, None, 0))[2] >= CACHE_TTL]
        random.SystemRandom().shuffle(pending)
        pending.sort(key=lambda key:(key in previous, -float(pool[key].get('score') or 0)))
        requests = errors = 0
        for key in pending[:MAX_LOCALIZATION_REQUESTS]:
            if stop(): raise InterruptedError()
            requests += 1
            try:
                response = request(f'{key[0]}/{key[1]}/translations', {})
                if stop(): raise InterruptedError()
                translations = response.get('translations') if isinstance(response, dict) else ([] if response is None else None)
                if not isinstance(translations, list): raise ValueError('Hibás TMDB-fordítási válasz.')
                localized = []
                for translation in translations:
                    if not isinstance(translation, dict) or translation.get('iso_639_1') != 'hu': continue
                    data = translation.get('data')
                    if isinstance(data, dict) and isinstance(data.get('overview'), str) and data['overview'].strip():
                        localized.append(translation)
                localized.sort(key=lambda t:t.get('iso_3166_1') != 'HU')
                data = localized[0]['data'] if localized else {}
                title = data.get('title' if key[0] == 'movie' else 'name')
                payload = dict(title=title if isinstance(title, str) else '', overview=data.get('overview') or '')
                with self.connection() as conn, conn:
                    conn.execute('INSERT OR REPLACE INTO recommendation_localization VALUES (?,?,?,?,?,?)',
                                 (*key, 'hu', int(bool(localized)), json.dumps(payload, ensure_ascii=False), time.time()))
            except InterruptedError: raise
            except sqlite3.Error: raise
            except Exception:
                # A timeout/authentication error is not evidence of missing Hungarian data.
                errors += 1
                break
        return requests, errors

    def draw(self, library_id, pool, owned, previous=(), limit=BATCH_SIZE, rng=None, prefer_hungarian=False):
        feedback = self.feedback(library_id)
        candidates = {key: item for key, item in pool.items() if key not in owned and key not in feedback}
        rng = rng or random.Random()
        with self.connection() as conn:
            seen = {(kind, media_id):(count, shown) for kind, media_id, shown, count in conn.execute(
                'SELECT media_type,tmdb_id,shown_at,shown_count FROM recommendation_seen WHERE library_id=?', (library_id,))}
        previous = set(previous)
        alternatives = {key:item for key,item in candidates.items() if key not in previous}
        # Avoid the preceding batch when possible; retain a small-pool fallback.
        if len(alternatives) >= limit: candidates = alternatives
        def rank(entry):
            key, item = entry
            count, shown = seen.get(key, (0, 0))
            weight = max(0.01, float(item.get('score') or 0.01))
            if prefer_hungarian and item.get('has_hu_metadata') is True: weight *= 4
            sample = -math.log(max(1e-12, rng.random())) / weight
            return (count, key in previous, sample)
        selected = [item for key, item in sorted(candidates.items(), key=rank)[:limit]]
        if prefer_hungarian: selected.sort(key=lambda item:item.get('has_hu_metadata') is not True)
        return selected

    def load(self, library_id, seeds, owned, language, request, stop=lambda:False, previous=(), prefer_hungarian=False):
        """At most four seed requests plus bounded optional language checks; reuse cached results."""
        seeds = seed_items(seeds)
        if not seeds: return dict(items=[], pool={}, seed_count=0, errors=0, requests=0)
        feedback = self.feedback(library_id)
        # Positive feedback also contributes to this library's next recommendations.
        seeds = seed_items(seeds + [item for state, item in feedback.values() if state == 'interested'])
        pool, ages = self.pool(library_id, seeds, language)
        now = time.time()
        pending = [seed for seed in seeds if now - ages.get(identity(seed), 0) >= CACHE_TTL]
        random.SystemRandom().shuffle(pending)
        pending.sort(key=lambda seed:ages.get(identity(seed), 0))
        errors = requests = 0
        for seed in pending[:MAX_REQUESTS]:
            if stop(): raise InterruptedError()
            kind, media_id = identity(seed)
            requests += 1
            try:
                response = request(f'{kind}/{media_id}/recommendations', {'language':language, 'page':1})
                if stop(): raise InterruptedError()
                # A disappeared seed is an empty list, not a transient network error.
                raw = response.get('results') if isinstance(response, dict) else ([] if response is None else None)
                if not isinstance(raw, list): raise ValueError('Hibás TMDB-ajánlói válasz.')
                results = [normalized for item in raw[:60] if (normalized := normalize_result(item, kind))]
                with self.connection() as conn, conn:
                    conn.execute('INSERT OR REPLACE INTO recommendation_cache VALUES (?,?,?,?,?,?)',
                                 (library_id, kind, media_id, language, json.dumps(results, ensure_ascii=False), now))
            except InterruptedError: raise
            except sqlite3.Error: raise
            except Exception: errors += 1
        if stop(): raise InterruptedError()
        pool, ages = self.pool(library_id, seeds, language)
        localization_requests = 0
        if prefer_hungarian and not (requests and errors == requests):
            localization_requests, localization_errors = self.check_hungarian(library_id, pool, owned, request, stop, previous)
            errors += localization_errors
            self.apply_localization(pool, language)
        if stop(): raise InterruptedError()
        items = self.draw(library_id, pool, owned, previous, prefer_hungarian=prefer_hungarian)
        return dict(items=items, pool=pool, seed_count=len(ages), errors=errors, requests=requests,
                    localization_requests=localization_requests)

    def delete_library(self, library_id):
        with self.connection() as conn, conn:
            for table in ('recommendation_cache', 'recommendation_feedback', 'recommendation_seen'):
                conn.execute('DELETE FROM ' + table + ' WHERE library_id=?', (library_id,))
