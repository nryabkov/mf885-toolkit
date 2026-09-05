#!/usr/bin/env python3
"""Deterministic Community R4.3 fixed64 forwarding UI."""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r42 as r42


PROFILE = "0.4.3-community-r2"
MARKER = b"MF885 Community R4.3 extension 0.4.3-community-r2"
REMOVED_RECORDS = r42.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r42.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r43.html"
APP_PATH = "www\\js\\r43app.js"
CSS_PATH = "www\\css\\r43ui.css"

FRAGMENT_FILE = "firmware/community-r4.3/ttl_fixed64_panel.html"
FRAGMENT_BYTES = 685
FRAGMENT_SHA256 = "f0ebc848b457e3b2e7524686ff463ca3d7214cf7ad2d43e2cd1ff8efbeffdb7d"

OUTPUT_RECORDS: dict[str, tuple[int, str]] = {'www\\help_en.html': (21381,
                       '00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2'),
 'www\\html\\adminApp.html': (4766,
                              'd39c1ffd952d10517c50a992bed131c8fb31f18e0d3828d78a0bccb48985187c'),
 'www\\index.html': (26636,
                     '572e579530f032504ec3216357912b1aa7f33dda74e52afbf854c0ef5c3020d9'),
 'www\\js\\base\\ajax_calls.js': (21467,
                                  'f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127'),
 'www\\js\\base\\utils.js': (16873,
                             '5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103'),
 'www\\properties\\Messages_en.properties': (46943,
                                             '2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c')}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {'www\\css\\r43ui.css': (7925,
                         '50b977ba920c226a4a9c03895c47d1457439adba0eefd169c20e2cca21244578',
                         'R4.3 versioned UI; fixed64 status with no browser '
                         'TTL requests'),
 'www\\js\\r43app.js': (63060,
                        'b92d2ad4dd58be8002c2f5b99c06df235cc2f1ad4f4d98ff3ba8610796463382',
                        'R4.3 versioned UI; fixed64 status with no browser TTL '
                        'requests'),
 'www\\r43.html': (13856,
                   '0715bb2963175b10e7843ef42128b9eb1bd030c5ad5200ed50d306a26eceaef8',
                   'R4.3 versioned UI; fixed64 status with no browser TTL '
                   'requests')}


class CommunityR43Error(Exception):
    pass


def _replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    count = data.count(old)
    if count != 1:
        raise CommunityR43Error(f"{label} anchor count is {count}, expected 1")
    return data.replace(old, new, 1)


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.4.2-community-r2", b"0.4.3-community-r2"),
        (b"0.4.2", b"0.4.3"),
        (b"R4.2", b"R4.3"),
        (b"r42", b"r43"),
        (b"R42", b"R43"),
        (b"JS41", b"JS42"),
        (b"LIVE41", b"LIVE42"),
        (b"S41", b"S42"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR43Error(f"{label} has no R4.2 revision anchor")
    return data


def _fragment(root: Path) -> bytes:
    try:
        value = (root / FRAGMENT_FILE).read_bytes()
    except OSError as exc:
        raise CommunityR43Error("could not read exact R4.3 fixed64 panel") from exc
    try:
        return r2.require_exact(value, FRAGMENT_BYTES, FRAGMENT_SHA256, FRAGMENT_FILE)
    except r2.CommunityR2Error as exc:
        raise CommunityR43Error(str(exc)) from exc


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        replacements, parent_additions, removals = r42.build_patch_set(
            records, root
        )
    except r42.CommunityR42Error as exc:
        raise CommunityR43Error(str(exc)) from exc

    replacements = {
        path: _revise(value, f"R4.3 replacement {path}")
        if path in {"www\\index.html", "www\\html\\adminApp.html"}
        else value
        for path, value in replacements.items()
    }
    try:
        parent_entry = parent_additions[r42.ENTRY_PATH]
        parent_app = parent_additions[r42.APP_PATH]
        parent_css = parent_additions[r42.CSS_PATH]
        old_panel = (root / r42.FRAGMENT_FILE).read_bytes()
    except (KeyError, OSError) as exc:
        raise CommunityR43Error("R4.2 comparator assets are incomplete") from exc

    entry = _revise(parent_entry, "R4.3 entry")
    entry = _replace_once(
        entry,
        _revise(old_panel, "R4.3 inherited panel anchor"),
        _fragment(root),
        "R4.3 fixed64 panel",
    )
    entry = _replace_once(
        entry,
        b"TTL remains unavailable while the native context-read probe is evaluated. ",
        b"Forwarded IPv4 uses fixed TTL 64 in this experimental build; live measurement is pending. ",
        "R4.3 dashboard TTL summary",
    )
    additions = {
        ENTRY_PATH: entry,
        APP_PATH: _revise(parent_app, "R4.3 controller"),
        CSS_PATH: parent_css,
    }
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR43Error("R4.3 marker is absent")
    if b'href="/r43.html"' not in replacements["www\\index.html"]:
        raise CommunityR43Error("canonical login does not link R4.3")
    if b'href="/r43.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR43Error("shared header does not link R4.3")
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
        raise CommunityR43Error("R4.3 browser assets contain a forbidden live path")
    if b"setInterval" in additions[APP_PATH]:
        raise CommunityR43Error("R4.3 contains unsafe interval polling")
    return replacements, additions, set(removals)


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR43Error("R4.3 output records are not pinned")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR43Error("R4.3 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR43Error("R4.3 addition record gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR43Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR43Error(str(exc)) from exc
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
    "CommunityR43Error",
    "build_patch_set",
]
