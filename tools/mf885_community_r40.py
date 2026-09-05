#!/usr/bin/env python3
"""Deterministic Community R4.0 direct-context parser discriminator UI."""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r38 as r38


PROFILE = "0.4.0-community-r2"
MARKER = b"MF885 Community R4.0 extension 0.4.0-community-r2"
REMOVED_RECORDS = r38.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r38.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r40.html"
APP_PATH = "www\\js\\r40app.js"
CSS_PATH = "www\\css\\r40ui.css"

FRAGMENT_FILE = "firmware/community-r4.0/ttl_context_parser_panel.html"
FRAGMENT_BYTES = 1_972
FRAGMENT_SHA256 = "62802a9ce4193c0d38254d4d4a63ca1cf28f8e41ee8881646fda9501b92e08f1"

OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "1d86c9fd77e498f6909c5c94d9f93cae121ee137e663facf3b16ad89389f3c31"),
    "www\\index.html": (26_636, "8a4af012400e0353885cdef90eb284992fa85f15cc0c477b9b7d1af203166d29"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    ENTRY_PATH: (15_135, "c458a57453491aab79bb4562a85d73e1f769ba96471b4ba96113b74a82f09fd1", "R2.9 cumulative UI with a visibly locked direct-context parser discriminator"),
    APP_PATH: (63_060, "75066246d6bf6203eac413f931dbf6a3598c42e89a8f52c143ee8493857e78f7", "R2.9 controller with static parser routing and zero diagnostic traffic"),
    CSS_PATH: (7_925, "50b977ba920c226a4a9c03895c47d1457439adba0eefd169c20e2cca21244578", "byte-identical reviewed Community CSS"),
}


class CommunityR40Error(Exception):
    pass


def _replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    count = data.count(old)
    if count != 1:
        raise CommunityR40Error(f"{label} anchor count is {count}, expected 1")
    return data.replace(old, new, 1)


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.3.8-community-r2", b"0.4.0-community-r2"),
        (b"0.3.8", b"0.4.0"),
        (b"R3.8", b"R4.0"),
        (b"r38", b"r40"),
        (b"R38", b"R40"),
        (b"JS38", b"JS40"),
        (b"LIVE38", b"LIVE40"),
        (b"S38", b"S40"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR40Error(f"{label} has no R3.8 revision anchor")
    return data


def _fragment(root: Path) -> bytes:
    try:
        value = (root / FRAGMENT_FILE).read_bytes()
    except OSError as exc:
        raise CommunityR40Error("could not read exact R4.0 parser panel") from exc
    try:
        return r2.require_exact(value, FRAGMENT_BYTES, FRAGMENT_SHA256, FRAGMENT_FILE)
    except r2.CommunityR2Error as exc:
        raise CommunityR40Error(str(exc)) from exc


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        replacements, parent_additions, removals = r38._derive_unpinned_patch_set(
            records, root
        )
    except r38.CommunityR38Error as exc:
        raise CommunityR40Error(str(exc)) from exc

    replacements = {
        path: _revise(value, f"R4.0 replacement {path}")
        if path in {"www\\index.html", "www\\html\\adminApp.html"}
        else value
        for path, value in replacements.items()
    }
    try:
        parent_entry = parent_additions[r38.ENTRY_PATH]
        parent_app = parent_additions[r38.APP_PATH]
        parent_css = parent_additions[r38.CSS_PATH]
        old_panel = (root / r38.FRAGMENT_FILE).read_bytes()
    except (KeyError, OSError) as exc:
        raise CommunityR40Error("R3.8 comparator assets are incomplete") from exc

    entry = _revise(parent_entry, "R4.0 entry")
    entry = _replace_once(
        entry,
        _revise(old_panel, "R4.0 inherited panel anchor"),
        _fragment(root),
        "R4.0 direct-context parser panel",
    )
    entry = _replace_once(
        entry,
        b"TTL remains visibly unavailable while its native callback is isolated. ",
        b"TTL remains visibly unavailable while its direct request-tree parser is isolated. ",
        "R4.0 dashboard TTL summary",
    )
    additions = {
        ENTRY_PATH: entry,
        APP_PATH: _revise(parent_app, "R4.0 controller"),
        CSS_PATH: parent_css,
    }
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR40Error("R4.0 marker is absent")
    if b'href="/r40.html"' not in replacements["www\\index.html"]:
        raise CommunityR40Error("canonical login does not link R4.0")
    if b'href="/r40.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR40Error("shared header does not link R4.0")
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
        raise CommunityR40Error("R4.0 browser assets contain a forbidden live path")
    if b"setInterval" in additions[APP_PATH]:
        raise CommunityR40Error("R4.0 contains unsafe interval polling")
    return replacements, additions, set(removals)


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR40Error("R4.0 output records are not pinned")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR40Error("R4.0 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR40Error("R4.0 addition record gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR40Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR40Error(str(exc)) from exc
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
    "CommunityR40Error",
    "build_patch_set",
]
