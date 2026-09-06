#!/usr/bin/env python3
"""Deterministic Community R4.4 fixed64 forwarding UI."""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r43 as r43


PROFILE = "0.4.4-community-r2"
MARKER = b"MF885 Community R4.4 extension 0.4.4-community-r2"
REMOVED_RECORDS = r43.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r43.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r44.html"
APP_PATH = "www\\js\\r44app.js"
CSS_PATH = "www\\css\\r44ui.css"

FRAGMENT_FILE = "firmware/community-r4.4/ttl_fixed64_panel.html"
FRAGMENT_BYTES = 685
FRAGMENT_SHA256 = "f0ebc848b457e3b2e7524686ff463ca3d7214cf7ad2d43e2cd1ff8efbeffdb7d"

OUTPUT_RECORDS = {'www\\help_en.html': (21381,
                       '00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2'),
 'www\\html\\adminApp.html': (4766,
                              'dcb4787177423bfd819a2eadc0a105259d97f3167c5338465b9bd4ceb2b5c91b'),
 'www\\index.html': (26636,
                     'd5bac81adf569134675f4088be76f3232ae77abc89b7d15323d341b13b89742d'),
 'www\\js\\base\\ajax_calls.js': (21467,
                                  'f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127'),
 'www\\js\\base\\utils.js': (16873,
                             '5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103'),
 'www\\properties\\Messages_en.properties': (46943,
                                             '2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c')}
ADDITION_OUTPUT_RECORDS = {'www\\css\\r44ui.css': (7925,
                         '50b977ba920c226a4a9c03895c47d1457439adba0eefd169c20e2cca21244578',
                         'R4.4 versioned UI; fixed64 status without browser '
                         'TTL requests'),
 'www\\js\\r44app.js': (63060,
                        'b277389fee4f4be9d552fcc3eae32c7ecdb527a2cf1a5a4ce64fa0a3e23034a6',
                        'R4.4 versioned UI; fixed64 status without browser TTL '
                        'requests'),
 'www\\r44.html': (13856,
                   '2d45548b4904cc47522a3a367eee99fd633afec94212395e8aa7965b1f33fc55',
                   'R4.4 versioned UI; fixed64 status without browser TTL '
                   'requests')}


class CommunityR44Error(Exception):
    pass


def _replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    count = data.count(old)
    if count != 1:
        raise CommunityR44Error(f"{label} anchor count is {count}, expected 1")
    return data.replace(old, new, 1)


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.4.3-community-r2", b"0.4.4-community-r2"),
        (b"0.4.3", b"0.4.4"), (b"R4.3", b"R4.4"),
        (b"r43", b"r44"), (b"R43", b"R44"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR44Error(f"{label} has no R4.3 revision anchor")
    return data


def _fragment(root: Path) -> bytes:
    try:
        value = (root / FRAGMENT_FILE).read_bytes()
    except OSError as exc:
        raise CommunityR44Error("could not read exact R4.4 fixed64 panel") from exc
    try:
        return r2.require_exact(value, FRAGMENT_BYTES, FRAGMENT_SHA256, FRAGMENT_FILE)
    except r2.CommunityR2Error as exc:
        raise CommunityR44Error(str(exc)) from exc


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        replacements, parent_additions, removals = r43.build_patch_set(
            records, root
        )
    except r43.CommunityR43Error as exc:
        raise CommunityR44Error(str(exc)) from exc

    replacements = {
        path: _revise(value, f"R4.4 replacement {path}")
        if path in {"www\\index.html", "www\\html\\adminApp.html"}
        else value
        for path, value in replacements.items()
    }
    try:
        parent_entry = parent_additions[r43.ENTRY_PATH]
        parent_app = parent_additions[r43.APP_PATH]
        parent_css = parent_additions[r43.CSS_PATH]
    except (KeyError, OSError) as exc:
        raise CommunityR44Error("R4.3 comparator assets are incomplete") from exc

    entry = _revise(parent_entry, "R4.4 entry")
    # Pin the inherited fixed64 panel without changing product behavior.
    if _fragment(root) not in entry:
        raise CommunityR44Error("R4.4 fixed64 panel is absent")
    additions = {
        ENTRY_PATH: entry,
        APP_PATH: _revise(parent_app, "R4.4 controller"),
        CSS_PATH: parent_css,
    }
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR44Error("R4.4 marker is absent")
    if b'href="/r44.html"' not in replacements["www\\index.html"]:
        raise CommunityR44Error("canonical login does not link R4.4")
    if b'href="/r44.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR44Error("shared header does not link R4.4")
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
        raise CommunityR44Error("R4.4 browser assets contain a forbidden live path")
    if b"setInterval" in additions[APP_PATH]:
        raise CommunityR44Error("R4.4 contains unsafe interval polling")
    return replacements, additions, set(removals)


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR44Error("R4.4 output records are not pinned")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR44Error("R4.4 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR44Error("R4.4 addition record gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR44Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR44Error(str(exc)) from exc
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
    "CommunityR44Error",
    "build_patch_set",
]
