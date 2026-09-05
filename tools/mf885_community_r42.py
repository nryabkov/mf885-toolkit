#!/usr/bin/env python3
"""Deterministic Community R4.2 guarded context-read comparator UI."""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r41 as r41


PROFILE = "0.4.2-community-r2"
MARKER = b"MF885 Community R4.2 extension 0.4.2-community-r2"
REMOVED_RECORDS = r41.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r41.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r42.html"
APP_PATH = "www\\js\\r42app.js"
CSS_PATH = "www\\css\\r42ui.css"

FRAGMENT_FILE = "firmware/community-r4.2/ttl_context_type_read_panel.html"
FRAGMENT_BYTES = 720
FRAGMENT_SHA256 = "f8a4f6cd0c8337d0bc997803bb5254fa716e4fae80f54dbbb4f81fd6789d5dd2"

OUTPUT_RECORDS: dict[str, tuple[int, str]] = {'www\\help_en.html': (21381, '00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2'),
 'www\\html\\adminApp.html': (4766, '1580d0861f62a00b8b07a7d5c6d55d7560fc8a8c19e1adee0fc03c3c3c4f9269'),
 'www\\index.html': (26636, 'c3ea3ac0494cd1ffd33e5efc498a48f8ec36341bceee42f335a29015292f70db'),
 'www\\js\\base\\ajax_calls.js': (21467, 'f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127'),
 'www\\js\\base\\utils.js': (16873, '5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103'),
 'www\\properties\\Messages_en.properties': (46943,
                                             '2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c')}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {'www\\css\\r42ui.css': (7925,
                         '50b977ba920c226a4a9c03895c47d1457439adba0eefd169c20e2cca21244578',
                         'R4.2 versioned cumulative UI; zero browser diagnostic traffic'),
 'www\\js\\r42app.js': (63060,
                        '8cfb05f03f1f15c47d3e00be192411e0e1ff7649476f1a0217ca4e8367736c1c',
                        'R4.2 versioned cumulative UI; zero browser diagnostic traffic'),
 'www\\r42.html': (13875,
                   '9fe9aa701c9d9bd5a259fb5a57855f129a8c03475256c89f8a8d2644d6c863fd',
                   'R4.2 versioned cumulative UI; zero browser diagnostic traffic')}


class CommunityR42Error(Exception):
    pass


def _replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    count = data.count(old)
    if count != 1:
        raise CommunityR42Error(f"{label} anchor count is {count}, expected 1")
    return data.replace(old, new, 1)


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.4.1-community-r2", b"0.4.2-community-r2"),
        (b"0.4.1", b"0.4.2"),
        (b"R4.1", b"R4.2"),
        (b"r41", b"r42"),
        (b"R41", b"R42"),
        (b"JS40", b"JS41"),
        (b"LIVE40", b"LIVE41"),
        (b"S40", b"S41"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR42Error(f"{label} has no R4.1 revision anchor")
    return data


def _fragment(root: Path) -> bytes:
    try:
        value = (root / FRAGMENT_FILE).read_bytes()
    except OSError as exc:
        raise CommunityR42Error("could not read exact R4.2 context-read panel") from exc
    try:
        return r2.require_exact(value, FRAGMENT_BYTES, FRAGMENT_SHA256, FRAGMENT_FILE)
    except r2.CommunityR2Error as exc:
        raise CommunityR42Error(str(exc)) from exc


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        replacements, parent_additions, removals = r41.build_patch_set(
            records, root
        )
    except r41.CommunityR41Error as exc:
        raise CommunityR42Error(str(exc)) from exc

    replacements = {
        path: _revise(value, f"R4.2 replacement {path}")
        if path in {"www\\index.html", "www\\html\\adminApp.html"}
        else value
        for path, value in replacements.items()
    }
    try:
        parent_entry = parent_additions[r41.ENTRY_PATH]
        parent_app = parent_additions[r41.APP_PATH]
        parent_css = parent_additions[r41.CSS_PATH]
        old_panel = (root / r41.FRAGMENT_FILE).read_bytes()
    except (KeyError, OSError) as exc:
        raise CommunityR42Error("R4.1 comparator assets are incomplete") from exc

    entry = _revise(parent_entry, "R4.2 entry")
    entry = _replace_once(
        entry,
        _revise(old_panel, "R4.2 inherited panel anchor"),
        _fragment(root),
        "R4.2 context-read panel",
    )
    entry = _replace_once(
        entry,
        b"TTL remains visibly unavailable while its low-entry return-zero leaf is isolated. ",
        b"TTL remains unavailable while the native context-read probe is evaluated. ",
        "R4.2 dashboard TTL summary",
    )
    additions = {
        ENTRY_PATH: entry,
        APP_PATH: _revise(parent_app, "R4.2 controller"),
        CSS_PATH: parent_css,
    }
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR42Error("R4.2 marker is absent")
    if b'href="/r42.html"' not in replacements["www\\index.html"]:
        raise CommunityR42Error("canonical login does not link R4.2")
    if b'href="/r42.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR42Error("shared header does not link R4.2")
    forbidden = (
        b"modelGet('diagnostic'",
        b"file=diagnostic",
        b"file=ttl_set",
        b"<command>ttl</command>",
        b"SystemChannelName",
        b"debugmodeon",
        b"Engineering_mode>",
        b"RestoreFw",
        b"r39ttl.js",
    )
    if any(value in joined for value in forbidden):
        raise CommunityR42Error("R4.2 browser assets contain a forbidden live path")
    if b"setInterval" in additions[APP_PATH]:
        raise CommunityR42Error("R4.2 contains unsafe interval polling")
    return replacements, additions, set(removals)


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR42Error("R4.2 output records are not pinned")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR42Error("R4.2 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR42Error("R4.2 addition record gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR42Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR42Error(str(exc)) from exc
    return replacements, additions, removals


__all__ = [
    "PROFILE",
    "MARKER",
    "REMOVED_RECORDS",
    "REMOVED_ARCHIVE_BYTES",
    "ENTRY_PATH",
    "APP_PATH",
    "CSS_PATH",
    "OUTPUT_RECORDS",
    "ADDITION_OUTPUT_RECORDS",
    "CommunityR42Error",
    "build_patch_set",
]
