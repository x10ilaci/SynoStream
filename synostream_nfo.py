"""Bounded NFO parsing and conservative sidecar association. No network or Qt."""
import re
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath

MAX_NFO_BYTES = 1024 * 1024


def decode_nfo(payload):
    if len(payload) > MAX_NFO_BYTES:
        return ''
    if payload.startswith((b'\xff\xfe', b'\xfe\xff')):
        encodings = ['utf-16']
    else:
        encodings = ['utf-8-sig', 'cp1250', 'cp437']
    for encoding in encodings:
        try:
            return payload.decode(encoding)
        except UnicodeError:
            pass
    return ''


def parse_nfo(payload, is_movie=True):
    text = decode_nfo(payload)
    if not text or '<!doctype' in text.casefold() or '<!entity' in text.casefold():
        return {}
    titles, years, imdb, tmdb = [], [], set(), set()
    kind = 'movie' if is_movie else 'tv'
    root = None
    try:
        root = ET.fromstring(text.strip())
    except ET.ParseError:
        pass
    if root is not None:
        tag = root.tag.rsplit('}', 1)[-1].casefold()
        if tag == 'episodedetails' or tag in ('movie', 'tvshow') and (tag == 'movie') != is_movie:
            return {}
        for node in root.iter():
            name = node.tag.rsplit('}', 1)[-1].casefold()
            value = (node.text or '').strip()
            if name in ('title', 'originaltitle') and node in list(root):
                titles.append(value)
            elif name == 'year':
                years.append(value)
            elif name == 'uniqueid':
                identifier_type = node.get('type', '').casefold()
                if identifier_type == 'tmdb' and re.fullmatch(r'[1-9]\d{0,9}', value):
                    tmdb.add(int(value))
                elif identifier_type == 'imdb' and re.fullmatch(r'tt\d{7,10}', value, re.I):
                    imdb.add(value.lower())
            elif name == 'tmdbid' and re.fullmatch(r'[1-9]\d{0,9}', value):
                tmdb.add(int(value))
            elif name in ('imdbid', 'id') and re.fullmatch(r'tt\d{7,10}', value, re.I):
                imdb.add(value.lower())
        # Structured IDs take precedence over incidental URLs in plot/credits.
        if not imdb:
            imdb.update(value.lower() for value in re.findall(r'(?i)\btt\d{7,10}\b', text))
    else:
        imdb.update(value.lower() for value in re.findall(r'(?i)\btt\d{7,10}\b', text))
        for label, value in re.findall(r'(?im)^\s*[|\[\]* ._-]*(original\s*title|movie\s*title|title|cím|cim|eredeti\s*cím|eredeti\s*cim|year|év|ev)\s*[:=]\s*(.+?)\s*$', text):
            value = value.strip(' |[]')
            if label.casefold() in ('year', 'év', 'ev'):
                years.append(value)
            else:
                titles.append(value)
    if not tmdb:
        for media_kind, identifier in re.findall(r'(?i)(?:themoviedb\.org|tmdb\.org)/(movie|tv)/(\d+)', text):
            if media_kind.casefold() == kind and 0 < int(identifier) < 10**10:
                tmdb.add(int(identifier))
    result = {}
    if len(imdb) == 1:
        result['imdb_id'] = next(iter(imdb))
    if len(tmdb) == 1:
        result['tmdb_id'] = next(iter(tmdb))
    clean_titles = list(dict.fromkeys(t for t in titles if t and len(t) <= 500 and not re.search(r'[\x00-\x1f]', t)))
    if clean_titles:
        result['titles'] = clean_titles[:2]
    years = [v for v in years if re.fullmatch(r'(?:18|19|20|21)\d{2}', v)]
    if len(set(years)) == 1:
        result['year'] = years[0]
    return result


def select_nfo_names(names, media_name, is_movie, video_count=0):
    names = [n for n in names if isinstance(n, str) and n.casefold().endswith('.nfo')]
    stem = PurePosixPath(media_name.replace('\\', '/')).stem if is_movie else media_name
    exact = [n for n in names if n.casefold() == (stem + '.nfo').casefold()]
    if exact:
        return exact if len(exact) == 1 else []
    conventional = 'movie.nfo' if is_movie else 'tvshow.nfo'
    if not is_movie or video_count == 1:
        standard = [n for n in names if n.casefold() == conventional]
        if standard:
            return standard if len(standard) == 1 else []
        if len(names) == 1:
            return names
    return []
