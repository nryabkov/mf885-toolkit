#!/usr/bin/env python3
"""Deterministic Community R4.1 low-entry leaf comparator UI."""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r40 as r40


PROFILE = "0.4.1-community-r2"
MARKER = b"MF885 Community R4.1 extension 0.4.1-community-r2"
REMOVED_RECORDS = r40.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r40.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r41.html"
APP_PATH = "www\\js\\r41app.js"
CSS_PATH = "www\\css\\r41ui.css"

FRAGMENT_FILE = "firmware/community-r4.1/ttl_low_entry_return_zero_panel.html"
FRAGMENT_BYTES = 2_037
FRAGMENT_SHA256 = "ba7c53e586f88c0f928e711e65e77e659746e058bd544d1e9d18481a77148759"

OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "5fb14e3c0b5c2f719fbd009c16dcbc5783e6bf9910e9e84f7831cb2a0e591323"),
    "www\\index.html": (26_636, "f927951ac065cc4e4b804e1f64a4e266717b3d9d4fbf366f0f7d449cca9f25b2"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    ENTRY_PATH: (15_200, "efbdfbaeefcb98eec6715140be7ace47472acefef15803c5d9edfdfc026a0656", "R4.0 cumulative UI with a visibly locked low-entry leaf comparator"),
    APP_PATH: (63_060, "cf4c43715827942a7d4af765c534fc9a54362b1d4b6f3fe43723eb37361b50b8", "R4.0 controller with revised static routing and zero diagnostic traffic"),
    CSS_PATH: (7_925, "50b977ba920c226a4a9c03895c47d1457439adba0eefd169c20e2cca21244578", "byte-identical reviewed Community CSS"),
}


class CommunityR41Error(Exception):
    pass


def _replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    count = data.count(old)
    if count != 1:
        raise CommunityR41Error(f"{label} anchor count is {count}, expected 1")
    return data.replace(old, new, 1)


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.4.0-community-r2", b"0.4.1-community-r2"),
        (b"0.4.0", b"0.4.1"),
        (b"R4.0", b"R4.1"),
        (b"r40", b"r41"),
        (b"R40", b"R41"),
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
        raise CommunityR41Error(f"{label} has no R4.0 revision anchor")
    return data


def _fragment(root: Path) -> bytes:
    try:
        value = (root / FRAGMENT_FILE).read_bytes()
    except OSError as exc:
        raise CommunityR41Error("could not read exact R4.1 low-entry panel") from exc
    try:
        return r2.require_exact(value, FRAGMENT_BYTES, FRAGMENT_SHA256, FRAGMENT_FILE)
    except r2.CommunityR2Error as exc:
        raise CommunityR41Error(str(exc)) from exc


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        replacements, parent_additions, removals = r40._derive_unpinned_patch_set(
            records, root
        )
    except r40.CommunityR40Error as exc:
        raise CommunityR41Error(str(exc)) from exc

    replacements = {
        path: _revise(value, f"R4.1 replacement {path}")
        if path in {"www\\index.html", "www\\html\\adminApp.html"}
        else value
        for path, value in replacements.items()
    }
    try:
        parent_entry = parent_additions[r40.ENTRY_PATH]
        parent_app = parent_additions[r40.APP_PATH]
        parent_css = parent_additions[r40.CSS_PATH]
        old_panel = (root / r40.FRAGMENT_FILE).read_bytes()
    except (KeyError, OSError) as exc:
        raise CommunityR41Error("R4.0 comparator assets are incomplete") from exc

    entry = _revise(parent_entry, "R4.1 entry")
    entry = _replace_once(
        entry,
        _revise(old_panel, "R4.1 inherited panel anchor"),
        _fragment(root),
        "R4.1 low-entry return-zero panel",
    )
    entry = _replace_once(
        entry,
        b"TTL remains visibly unavailable while its direct request-tree parser is isolated. ",
        b"TTL remains visibly unavailable while its low-entry return-zero leaf is isolated. ",
        "R4.1 dashboard TTL summary",
    )
    additions = {
        ENTRY_PATH: entry,
        APP_PATH: _revise(parent_app, "R4.1 controller"),
        CSS_PATH: parent_css,
    }
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR41Error("R4.1 marker is absent")
    if b'href="/r41.html"' not in replacements["www\\index.html"]:
        raise CommunityR41Error("canonical login does not link R4.1")
    if b'href="/r41.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR41Error("shared header does not link R4.1")
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
        raise CommunityR41Error("R4.1 browser assets contain a forbidden live path")
    if b"setInterval" in additions[APP_PATH]:
        raise CommunityR41Error("R4.1 contains unsafe interval polling")
    return replacements, additions, set(removals)


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR41Error("R4.1 output records are not pinned")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR41Error("R4.1 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR41Error("R4.1 addition record gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR41Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR41Error(str(exc)) from exc
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
    "CommunityR41Error",
    "build_patch_set",
]
