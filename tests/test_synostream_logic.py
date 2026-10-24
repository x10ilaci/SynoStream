# Copyright (C) 2026 Lőrincz László
# SPDX-License-Identifier: GPL-3.0-only
# Modified version: SynoStream 1.28, 2026-10-24.
# This file is part of SynoStream and is licensed under the GNU GPL version 3 only.
# It is distributed without any warranty; see LICENSE for the complete terms.

import pytest

from synostream_logic import (
    clean_name,
    normalize_title,
    parse_episode_position,
    title_similarity,
)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("The.Matrix.1999.1080p.BluRay.x264-GRP.mkv", ("The Matrix", "1999")),
        ("Blade Runner 2049.mkv", ("Blade Runner 2049", None)),
        ("1917 2019.mp4", ("1917", "2019")),
        ("Dune (2021) [WEB-DL].mkv", ("Dune", "2021")),
        ("Season of the Witch (2011).mkv", ("Season of the Witch", "2011")),
        ("Multi (2010).avi", ("Multi", "2010")),
        ("Eng Kalandor (1999).mkv", ("Eng Kalandor", "1999")),
        ("Attila the Hun (2001).mkv", ("Attila the Hun", "2001")),
        ("Movie HDR DVDRip Xvid.mkv", ("Movie", None)),
        ("A Complete Unknown (2024).mkv", ("A Complete Unknown", "2024")),
    ],
)
def test_clean_name(filename, expected):
    assert clean_name(filename) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("Show/Season 02/Show.S02E03.mkv", (2, 3, True)),
        ("Show/S08/Show E801.mkv", (8, 1, True)),
        ("Show/S07/Show E710.mkv", (7, 10, True)),
        ("Show/Show E710.mkv", (7, 10, True)),
        ("Show/Show E1020.mkv", (10, 20, True)),
        ("Show/Season 3/Episode 12.mkv", (3, 12, True)),
        ("Show/S02/Show.1280x720.mkv", (2, None, False)),
        ("Barátok közt/2. évad/05. rész.mkv", (2, 5, True)),
        ("Show/Season 1/Show E101.mkv", (1, 1, True)),
        ("One Piece/One.Piece.E101.mkv", (1, 101, True)),
        ("One Piece/One.Piece.E201.mkv", (1, 201, True)),
        ("Show/Show.E1080p.mkv", (1, None, False)),
        ("Show/S01/Show - 05 [1080p].mkv", (1, 5, True)),
        ("Show/Season 2019/Episode 4.mkv", (1, 4, True)),
        ("Show/Season 4/2024-02-10.mkv", (4, None, False)),
        ("Show/Show 3. évad 12. rész.mkv", (3, 12, True)),
        ("Show/Show Évad 3 Rész 12.mkv", (3, 12, True)),
        ("Show/Évad 3/01.mkv", (3, 1, True)),
        ("Show/Season 1/01.mkv", (1, 1, True)),
        ("Show/Show - 05.mkv", (1, 5, True)),
        ("Show/01 - Pilot.mkv", (1, 1, True)),
        ("Mad Max 2/Mad Max 2.mkv", (1, None, False)),
        ("10 Things.mkv", (1, None, False)),
    ],
)
def test_parse_episode_position(path, expected):
    assert parse_episode_position(path) == expected


def test_title_similarity_uses_normalized_tokens_and_stopwords():
    first = normalize_title("A nagy pénzrablás")
    second = normalize_title("Nagy penzrablás")
    assert title_similarity(first, second) == 1.0


def test_title_similarity_handles_empty_and_unrelated_titles():
    assert title_similarity("", "breaking bad") == 0.0
    assert title_similarity("breaking bad", "the office") == 0.0

