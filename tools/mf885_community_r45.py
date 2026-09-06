#!/usr/bin/env python3
"""Deterministic Community R4.5 fixed64 forwarding UI."""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r44 as r44


PROFILE = "0.4.5-community-r2"
MARKER = b"MF885 Community R4.5 extension 0.4.5-community-r2"
REMOVED_RECORDS = r44.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r44.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r45.html"
APP_PATH = "www\\js\\r45app.js"
CSS_PATH = "www\\css\\r45ui.css"

FRAGMENT_FILE = "firmware/community-r4.5/ttl_fixed64_panel.html"
FRAGMENT_BYTES = 685
FRAGMENT_SHA256 = "f0ebc848b457e3b2e7524686ff463ca3d7214cf7ad2d43e2cd1ff8efbeffdb7d"

OUTPUT_RECORDS = {'www\\help_en.html': (21381,
                       '00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2'),
 'www\\html\\adminApp.html': (4766,
                              '457140ba3ecb7ddc8e005cc22706807529a8f3d275480e1d954927fee177d889'),
 'www\\index.html': (26636,
                     'e2c38d76e4ea635287e4e3bf8e43c92b6e6a01db90909d9d5091eae8211e0bcf'),
 'www\\js\\base\\ajax_calls.js': (21467,
                                  'f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127'),
 'www\\js\\base\\utils.js': (16873,
                             '5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103'),
 'www\\properties\\Messages_en.properties': (46943,
                                             '2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c')}
ADDITION_OUTPUT_RECORDS = {'www\\css\\r45ui.css': (7925,
                         '50b977ba920c226a4a9c03895c47d1457439adba0eefd169c20e2cca21244578',
                         'R4.5 versioned UI; fixed64 status without browser '
                         'TTL requests'),
 'www\\js\\r45app.js': (63060,
                        '7f6dbb0fc17441c4dd3e769af03ab674f234f2c8cf00e726d46ac32ce5f20be6',
                        'R4.5 versioned UI; fixed64 status without browser TTL '
                        'requests'),
 'www\\r45.html': (13856,
                   'dd1b29d3b6e3f03942515a5e3b6610656bbdb44bff93b95d0caa71e07a988dbe',
                   'R4.5 versioned UI; fixed64 status without browser TTL '
                   'requests')}


class CommunityR45Error(Exception):
    pass


def _replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    count = data.count(old)
    if count != 1:
        raise CommunityR45Error(f"{label} anchor count is {count}, expected 1")
    return data.replace(old, new, 1)


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.4.4-community-r2", b"0.4.5-community-r2"),
        (b"0.4.4", b"0.4.5"), (b"R4.4", b"R4.5"),
        (b"r44", b"r45"), (b"R44", b"R45"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR45Error(f"{label} has no R4.4 revision anchor")
    return data


def _fragment(root: Path) -> bytes:
    try:
        value = (root / FRAGMENT_FILE).read_bytes()
    except OSError as exc:
        raise CommunityR45Error("could not read exact R4.5 fixed64 panel") from exc
    try:
        return r2.require_exact(value, FRAGMENT_BYTES, FRAGMENT_SHA256, FRAGMENT_FILE)
    except r2.CommunityR2Error as exc:
        raise CommunityR45Error(str(exc)) from exc


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        replacements, parent_additions, removals = r44.build_patch_set(
            records, root
        )
    except r44.CommunityR44Error as exc:
        raise CommunityR45Error(str(exc)) from exc

    replacements = {
        path: _revise(value, f"R4.5 replacement {path}")
        if path in {"www\\index.html", "www\\html\\adminApp.html"}
        else value
        for path, value in replacements.items()
    }
    try:
        parent_entry = parent_additions[r44.ENTRY_PATH]
        parent_app = parent_additions[r44.APP_PATH]
        parent_css = parent_additions[r44.CSS_PATH]
    except (KeyError, OSError) as exc:
        raise CommunityR45Error("R4.4 comparator assets are incomplete") from exc

    entry = _revise(parent_entry, "R4.5 entry")
    # Pin the inherited fixed64 panel without changing product behavior.
    if _fragment(root) not in entry:
        raise CommunityR45Error("R4.5 fixed64 panel is absent")
    additions = {
        ENTRY_PATH: entry,
        APP_PATH: _revise(parent_app, "R4.5 controller"),
        CSS_PATH: parent_css,
    }
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR45Error("R4.5 marker is absent")
    if b'href="/r45.html"' not in replacements["www\\index.html"]:
        raise CommunityR45Error("canonical login does not link R4.5")
    if b'href="/r45.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR45Error("shared header does not link R4.5")
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
        raise CommunityR45Error("R4.5 browser assets contain a forbidden live path")
    if b"setInterval" in additions[APP_PATH]:
        raise CommunityR45Error("R4.5 contains unsafe interval polling")
    return replacements, additions, set(removals)


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR45Error("R4.5 output records are not pinned")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR45Error("R4.5 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR45Error("R4.5 addition record gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR45Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR45Error(str(exc)) from exc
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
    "CommunityR45Error",
    "build_patch_set",
]
