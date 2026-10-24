"""Pure parsing and title-matching helpers used by SynoStream.

Kept independent from the Qt application so the behavior can be covered by pytest
without importing the desktop UI or making network requests.
"""

# Copyright (C) 2026 Lőrincz László
# SPDX-License-Identifier: GPL-3.0-only
# Modified version: SynoStream 1.53, 2026-10-24.
# This file is part of SynoStream and is licensed under the GNU GPL version 3 only.
# It is distributed without any warranty; see LICENSE for the complete terms.

import os
import re
import unicodedata


STOPWORDS = {"the", "a", "an", "of", "and", "az", "egy"}

NOISE_RE = re.compile(
    r"\b(?:2160p|1080[pi]|720p|576[pi]|480p|4k|uhd|web[ -]?dl|web[ -]?rip|hdrip|brrip|bdrip|"
    r"dvdrip|hdtv|blu[ -]?ray|remux|x ?26[45]|h ?26[45]|xvid|divx|hevc|avc|aac|ac3|"
    r"dts(?:-hd)?|dd ?p? ?\d ?\d|atmos|hdr(?:10\+?)?|10 ?bit|dovi|dolby[ ._-]?vision)\b"
    r"|\bS\d{1,2}(?:E\d{1,3})?\b"
    r"|\bE0*\d{3,5}(?:[ ._-]*[-–][ ._-]*E?0*\d{3,5})?\b"
    r"|\bseason\s*\d{1,3}(?!\d)\b|\b\d{1,3}\s*\.?\s*(?:évad|evad)\b",
    re.IGNORECASE,
)
LANGUAGE_TAG_RE = re.compile(r"(?i)\b(?:hun|eng|multi)\b")
# 1900-2029; a "Blade Runner 2049" így nem évszám.
YEAR_RE = re.compile(r"\b(19\d\d|20[0-2]\d)\b")
EPISODE_RANGE_RE = re.compile(
    r"(?i)(?:^|[^a-z0-9])E0*(\d{3,5})[ ._-]*[-–][ ._-]*E?0*(\d{3,5})(?=$|[^0-9])"
)


def clean_name(name, is_file=True):
    """Return a cleaned title and a detected release year."""
    if is_file:
        name = os.path.splitext(name)[0]

    # Fulcrum is a release-group prefix, not part of the media title.
    name = re.sub(r"(?i)^fulcrum[-_. ]+", "", name)

    text = re.sub(r"\[.*?\]|\{.*?\}", " ", name)
    text = text.replace("(", " ").replace(")", " ")
    text = re.sub(r"[._]+", " ", text)

    noise = NOISE_RE.search(text)
    language_tag = LANGUAGE_TAG_RE.search(text)
    # Hun/Eng/Multi önmagában lehet a cím része. Csak akkor kezeljük kiadási
    # címkeként, ha egy ismert technikai jelölés is van a fájlnévben.
    if language_tag and noise and language_tag.start() < noise.start():
        noise_start = language_tag.start() if text[:language_tag.start()].strip(" -") else noise.start()
    else:
        noise_start = noise.start() if noise else None
    # A név elején álló rövid szavakat nem vágjuk le zajként.
    if noise_start is not None and text[:noise_start].strip(" -"):
        text = text[:noise_start]

    year = None
    last = None
    for match in YEAR_RE.finditer(text):
        if text[:match.start()].strip(" -"):
            last = match
    if last:
        year = last.group(1)
        text = text[:last.start()]

    title = re.sub(r"\s+", " ", text).strip(" -")
    if not title:
        title = re.sub(r"\s+", " ", re.sub(r"[._]+", " ", name)).strip()
    return title, year


def normalize_title(text):
    """Lowercase title without accents and punctuation, with single spaces."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[\W_]+", " ", text.casefold()).split())


def _title_tokens(normalized):
    tokens = normalized.split()
    return {token for token in tokens if token not in STOPWORDS} or set(tokens)


def title_similarity(query, candidate):
    """Return a 0..1 Dice score for two already-normalized titles."""
    if not query or not candidate:
        return 0.0
    if query == candidate:
        return 1.0
    query_tokens = _title_tokens(query)
    candidate_tokens = _title_tokens(candidate)
    if not query_tokens or not candidate_tokens:
        return 0.0
    return 2 * len(query_tokens & candidate_tokens) / (len(query_tokens) + len(candidate_tokens))


def _season_number(text):
    """Parse an explicit season label without mistaking an episode number for it."""
    match = re.search(r"(?i)\bseason[ ._-]*0*(\d{1,3})(?!\d)", text)
    if match:
        return int(match.group(1))
    match = re.search(r"(?i)(?<!\d)0*(\d{1,3})\s*\.?\s*(?:évad|evad)\b", text)
    if match:
        return int(match.group(1))

    match = re.search(r"(?i)\b(?:évad|evad)[ ._-]*0*(\d{1,3})(?!\d)", text)
    if not match:
        return None
    remainder = text[match.end():]
    episode_marker = re.match(r"(?i)\s*\.?\s*(?:rész|resz|epizód|epizod)\b", remainder)
    if episode_marker:
        # "Évad 12. rész" means episode 12 with an unspecified season; in
        # "Évad 3 rész 12", the second number confirms season 3.
        episode_number = re.match(
            r"(?i)\s*\.?\s*(?:rész|resz|epizód|epizod)\s*0*\d{1,4}(?!\d)",
            remainder,
        )
        if not episode_number:
            return None
    return int(match.group(1))


def parse_episode_position(relative_path):
    """Return (season, episode, explicit_number_found) from a media path."""
    normalized = relative_path.replace("\\", "/")
    parts = normalized.split("/")
    season = 1
    has_explicit_season = False
    for part in parts[:-1]:
        parsed_season = _season_number(part)
        if parsed_season is not None:
            season = parsed_season
            has_explicit_season = True
            continue
        match = re.search(r"(?i)(?:^|[^a-z])S[ ._-]*0*(\d{1,2})(?:[^0-9]|$)", part)
        if match:
            season = int(match.group(1))
            has_explicit_season = True

    filename = os.path.splitext(parts[-1])[0] if parts else normalized
    inline_season = _season_number(filename)
    if inline_season is not None:
        season = inline_season
        has_explicit_season = True

    filename_range = EPISODE_RANGE_RE.search(filename)
    if filename_range:
        # A range in the filename describes a pack, not every child episode.
        # The UI assigns distinct fallback numbers using parse_episode_range_hint.
        season_match = re.search(r"(?i)(?:^|[^a-z0-9])S[ ._-]*0*(\d{1,2})[ ._-]*E", filename)
        if season_match:
            season = int(season_match.group(1))
        return season, None, False

    range_hint = parse_episode_range_hint(relative_path)
    if range_hint:
        _range_scope, range_start, range_end = range_hint
        local_episode = re.search(
            r"(?i)(?:^|[^a-z0-9])(?:EPISODE|EP|E)[ ._-]*0*(\d{1,5})(?!\d)",
            filename,
        )
        if local_episode:
            number = int(local_episode.group(1))
            range_length = max(0, range_end - range_start + 1)
            if range_start <= number <= range_end:
                return season, number, True
            if 1 <= number <= range_length:
                return season, range_start + number - 1, True
        local_bare_number = re.fullmatch(r"(?i)\s*0*(\d{1,4})\s*", filename)
        if local_bare_number:
            number = int(local_bare_number.group(1))
            range_length = max(0, range_end - range_start + 1)
            if 1 <= number <= range_length:
                return season, range_start + number - 1, True

    episode_match = re.search(
        r"(?i)S[ ._-]*0*(\d{1,2})[ ._-]*E[ ._-]*0*(\d{1,5})", normalized,
    )
    if episode_match:
        return int(episode_match.group(1)), int(episode_match.group(2)), True

    absolute_episode = re.search(
        r"(?i)(?:^|[^a-z0-9])E(\d{5,})(?!\d)", filename,
    )
    if absolute_episode:
        return season, int(absolute_episode.group(1)), True

    # Do not mistake a resolution such as 1280x720 for an episode marker.
    episode_match = re.search(r"(?i)(?<![A-Za-z0-9])(\d{1,2})\s*x\s*0*(\d{1,3})(?!\d)", normalized)
    if episode_match:
        return int(episode_match.group(1)), int(episode_match.group(2)), True

    # The legacy E7xx-E9xx season/episode shorthand remains supported for
    # names such as E801/E710. Without a season folder, E1xx-E6xx is treated
    # as an absolute episode number to avoid collisions in long-running shows.
    compact_episode = re.search(r"(?i)(?:^|[^a-z])E(\d{3,4})(?=$|[^0-9])", normalized)
    if compact_episode:
        digits = compact_episode.group(1)
        suffix = normalized[compact_episode.end():]
        is_resolution = bool(re.match(r"(?i)[pi]\b", suffix))
        if not is_resolution:
            if len(digits) == 3 and int(digits[0]) <= 6 and not has_explicit_season:
                return 1, int(digits), True
            if len(digits) == 3:
                compact_number = int(digits[1:])
            else:
                compact_number = int(digits[2:])
            compact_season = season if has_explicit_season else (
                int(digits[0]) if len(digits) == 3 else int(digits[:2])
            )
            if compact_season > 0 and compact_number > 0:
                return compact_season, compact_number, True

    episode_match = re.search(
        r"(?i)(?:^|[^a-z])(?:E|EP|EPISODE|RÉSZ)[ ._-]*0*(\d{1,4})(?!\d)(?![pi]\b)",
        filename,
    )
    if episode_match:
        return season, int(episode_match.group(1)), True
    # A bare number is a common episode name (01.avi, 02.avi). This helper is
    # called for files already inside a known show folder, so it is safe to
    # interpret that number as the episode even without a Season/S01 directory.
    bare_episode = re.fullmatch(r"(?i)\s*0*(\d{1,3})\s*", filename)
    if bare_episode and int(bare_episode.group(1)) > 0:
        return season, int(bare_episode.group(1)), True
    episode_match = re.match(r"(?i)^\s*0*(\d{1,3})\s*[-–.]\s*", filename)
    if episode_match and int(episode_match.group(1)) > 0:
        return season, int(episode_match.group(1)), True
    episode_match = re.search(r"(?i)(?<!\d)[ ._-]0*(\d{2,3})$", filename)
    same_as_parent = (
        len(parts) > 1 and normalize_title(parts[-2]) == normalize_title(filename)
    )
    season_only_name = inline_season is not None and _season_number(filename) is not None
    if episode_match and not same_as_parent and not season_only_name:
        if int(episode_match.group(1)) > 0:
            return season, int(episode_match.group(1)), True
    episode_match = re.search(
        r"(?i)(?<!\d)0*(\d{1,4})\s*\.?\s*(?:rész|resz|epizód|epizod)\b",
        filename,
    )
    if episode_match:
        return season, int(episode_match.group(1)), True
    episode_match = re.search(
        r"(?<!\d)[–-]\s*0*(\d{1,3})(?=\s*(?:$|[\[({]))",
        filename,
    )
    if episode_match:
        return season, int(episode_match.group(1)), True
    return season, None, False


def parse_episode_range_hint(relative_path):
    """Return (scope, first, last) for an E001-E100 range in a folder or filename."""
    normalized = (relative_path or "").replace("\\", "/")
    parts = normalized.split("/")
    filename = os.path.splitext(parts[-1])[0] if parts else normalized

    # A range in a directory seeds numbering for its children. A range in a
    # filename seeds numbering for files beside it, rather than labeling every
    # file in that pack with the same first episode.
    for index in range(len(parts) - 1, -1, -1):
        part = filename if index == len(parts) - 1 else parts[index]
        match = EPISODE_RANGE_RE.search(part)
        if not match:
            continue
        scope_parts = parts[:index + 1] if index < len(parts) - 1 else parts[:index]
        scope = "/".join(scope_parts).casefold() or "."
        return scope, int(match.group(1)), int(match.group(2))
    return None
