#!/usr/bin/env python3
"""Deterministic Community R3.8 return-zero post-set comparator UI."""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r37 as r37


PROFILE = "0.3.8-community-r2"
MARKER = b"MF885 Community R3.8 extension 0.3.8-community-r2"
REMOVED_RECORDS = r37.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r37.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r38.html"
APP_PATH = "www\\js\\r38app.js"
CSS_PATH = "www\\css\\r38ui.css"

FRAGMENT_FILE = "firmware/community-r3.8/ttl_return_zero_panel.html"
FRAGMENT_BYTES = 1_746
FRAGMENT_SHA256 = "0b150d0281896d252ed21d16ae50e3c14c613c7515e21c6e3856682587ca4804"

OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "c1a8f981fd9c72db55446ec182b36374fa9dbdd2d5cebab88e4197286d12534d"),
    "www\\index.html": (26_636, "dd8506e544671341dc1078a673450cb6d1aedb642a540d17dec07413e4aa8b1c"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    ENTRY_PATH: (14_898, "a004c6c52b7197bda081d240f386c6d0d8639bfc858d997277ccf6930473f412", "R3.8 cumulative UI with a visibly locked return-zero comparator"),
    APP_PATH: (63_060, "b8e74d02eb01ac356e02076fd771bb6045825128ddfaf4470f1470fe3f4ade89", "R2.9 controller with static comparator routing and no diagnostic request"),
    CSS_PATH: (7_925, "50b977ba920c226a4a9c03895c47d1457439adba0eefd169c20e2cca21244578", "byte-identical reviewed Community CSS"),
}


class CommunityR38Error(Exception):
    pass


def _replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    count = data.count(old)
    if count != 1:
        raise CommunityR38Error(f"{label} anchor count is {count}, expected 1")
    return data.replace(old, new, 1)


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.3.7-community-r2", b"0.3.8-community-r2"),
        (b"0.3.7", b"0.3.8"),
        (b"R3.7", b"R3.8"),
        (b"r37", b"r38"),
        (b"R37", b"R38"),
        (b"JS37", b"JS38"),
        (b"LIVE37", b"LIVE38"),
        (b"S37", b"S38"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR38Error(f"{label} has no R3.7 revision anchor")
    return data


def _fragment(root: Path) -> bytes:
    try:
        value = (root / FRAGMENT_FILE).read_bytes()
    except OSError as exc:
        raise CommunityR38Error("could not read exact R3.8 comparator panel") from exc
    if FRAGMENT_BYTES and FRAGMENT_SHA256:
        try:
            return r2.require_exact(value, FRAGMENT_BYTES, FRAGMENT_SHA256, FRAGMENT_FILE)
        except r2.CommunityR2Error as exc:
            raise CommunityR38Error(str(exc)) from exc
    return value


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        replacements, parent_additions, removals = r37._derive_unpinned_patch_set(
            records, root
        )
    except r37.CommunityR37Error as exc:
        raise CommunityR38Error(str(exc)) from exc

    replacements = {
        path: _revise(value, f"R3.8 replacement {path}")
        if path in {"www\\index.html", "www\\html\\adminApp.html"}
        else value
        for path, value in replacements.items()
    }
    try:
        parent_entry = parent_additions[r37.ENTRY_PATH]
        parent_app = parent_additions[r37.APP_PATH]
        parent_css = parent_additions[r37.CSS_PATH]
        old_panel = (root / r37.FRAGMENT_FILES["ttl_panel"][0]).read_bytes()
    except (KeyError, OSError) as exc:
        raise CommunityR38Error("R3.7 comparator assets are incomplete") from exc

    entry = _revise(parent_entry, "R3.8 entry")
    entry = _replace_once(
        entry,
        _revise(old_panel, "R3.8 inherited panel anchor"),
        _fragment(root),
        "R3.8 return-zero panel",
    )
    additions = {
        ENTRY_PATH: entry,
        APP_PATH: _revise(parent_app, "R3.8 controller"),
        CSS_PATH: parent_css,
    }
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR38Error("R3.8 marker is absent")
    if b'href="/r38.html"' not in replacements["www\\index.html"]:
        raise CommunityR38Error("canonical login does not link R3.8")
    if b'href="/r38.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR38Error("shared header does not link R3.8")
    forbidden = (
        b"modelGet('diagnostic'",
        b"file=ttl_set",
        b"<command>ttl</command>",
        b"SystemChannelName",
        b"debugmodeon",
        b"Engineering_mode>",
        b"RestoreFw",
    )
    if any(value in joined for value in forbidden):
        raise CommunityR38Error("R3.8 browser assets contain a forbidden live path")
    if b"setInterval" in additions[APP_PATH]:
        raise CommunityR38Error("R3.8 contains unsafe interval polling")
    return replacements, additions, set(removals)


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR38Error("R3.8 output records are not pinned")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR38Error("R3.8 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR38Error("R3.8 addition record gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR38Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR38Error(str(exc)) from exc
    return replacements, additions, removals
