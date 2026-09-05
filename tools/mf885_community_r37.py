#!/usr/bin/env python3
"""Deterministic Community R3.7 stock-shaped return discriminator UI.

The accepted R2.9 product surface remains intact.  The TTL page is explanatory
and permanently locked: firmware qualification is performed by a separate
one-shot helper, never by automatic or interactive browser traffic.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r34 as r34


PROFILE = "0.3.7-community-r2"
MARKER = b"MF885 Community R3.7 extension 0.3.7-community-r2"
REMOVED_RECORDS = r34.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r34.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r37.html"
APP_PATH = "www\\js\\r37app.js"
CSS_PATH = "www\\css\\r37ui.css"

CUSTOM_FILES: dict[str, tuple[str, int, str]] = {}
FRAGMENT_FILES: dict[str, tuple[str, int, str]] = {
    "ttl_panel": (
        "firmware/community-r3.7/ttl_return_discriminator_panel.html",
        1_643,
        "1c2dc74883981746fc49b25f7b728d5c53cabfb442a63ff07d96da4879830bbf",
    ),
}
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "077d6c4f2138612d318c73b3fbbdeba60139eb8e1a367938fc480ae748d32035"),
    "www\\index.html": (26_636, "f1586033ef20ef28e88260f6d99815b1873b1deaaa879455abc2d8f49f9989aa"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    ENTRY_PATH: (14_795, "37074a98339431bc424579868531b86b6dfa59de4e9fecac979ae45330c24e00", "R3.7 cumulative UI with a visibly locked return-path discriminator"),
    APP_PATH: (63_060, "3d27cfe36a3cec7157e72c4aa33a43351c7712c8aa50d9fa952fbad4f3a56c2b", "R2.9 controller with static TTL routing and no diagnostic request"),
    CSS_PATH: (7_925, "50b977ba920c226a4a9c03895c47d1457439adba0eefd169c20e2cca21244578", "byte-identical reviewed five-column Community CSS"),
}


class CommunityR37Error(Exception):
    pass


def _replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    count = data.count(old)
    if count != 1:
        raise CommunityR37Error(f"{label} anchor count is {count}, expected 1")
    return data.replace(old, new, 1)


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.3.4-community-r2", b"0.3.7-community-r2"),
        (b"0.3.4", b"0.3.7"),
        (b"R3.4", b"R3.7"),
        (b"r34", b"r37"),
        (b"R34", b"R37"),
        (b"JS34", b"JS37"),
        (b"LIVE34", b"LIVE37"),
        (b"S34", b"S37"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR37Error(f"{label} has no R3.4 revision anchor")
    return data


def _load_fragment(root: Path) -> bytes:
    source, size, digest = FRAGMENT_FILES["ttl_panel"]
    try:
        value = (root / source).read_bytes()
    except OSError as exc:
        raise CommunityR37Error(f"could not read exact R3.7 fragment {source}") from exc
    try:
        return r2.require_exact(value, size, digest, source)
    except r2.CommunityR2Error as exc:
        raise CommunityR37Error(str(exc)) from exc


def derive_assets(root: Path) -> dict[str, bytes]:
    parent = r34.derive_assets(root)
    entry = _revise(parent[r34.ENTRY_PATH], "R3.7 entry")
    try:
        old_panel = (root / r34.FRAGMENT_FILES["ttl_panel"][0]).read_bytes()
    except OSError as exc:
        raise CommunityR37Error("could not read exact R3.4 TTL panel") from exc
    entry = _replace_once(
        entry,
        _revise(old_panel, "R3.7 inherited panel anchor"),
        _load_fragment(root),
        "R3.7 return-path panel",
    )
    app = _revise(parent[r34.APP_PATH], "R3.7 controller")
    return {
        ENTRY_PATH: entry,
        APP_PATH: app,
        CSS_PATH: parent[r34.CSS_PATH],
    }


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        parent_replacements, _parent_additions, removals = r34._derive_unpinned_patch_set(
            records, root
        )
    except r34.CommunityR34Error as exc:
        raise CommunityR37Error(str(exc)) from exc
    replacements = dict(parent_replacements)
    for path in ("www\\index.html", "www\\html\\adminApp.html"):
        replacements[path] = _revise(replacements[path], f"R3.7 replacement {path}")
    additions = derive_assets(root)
    if set(replacements) != set(r34.OUTPUT_RECORDS):
        raise CommunityR37Error("R3.7 replacement path set changed")
    if set(additions) != {ENTRY_PATH, APP_PATH, CSS_PATH}:
        raise CommunityR37Error("R3.7 extension asset set changed")
    if set(removals) != set(REMOVED_RECORDS):
        raise CommunityR37Error("R3.7 removed-locale set changed")
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR37Error("R3.7 marker is absent")
    if b'href="/r37.html"' not in replacements["www\\index.html"]:
        raise CommunityR37Error("canonical login does not link R3.7")
    if b'href="/r37.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR37Error("shared header does not link R3.7")
    entry = additions[ENTRY_PATH]
    app = additions[APP_PATH]
    if entry.count(b'id="page-ttl"') != 1 or b"TTL control locked" not in entry:
        raise CommunityR37Error("R3.7 locked TTL panel changed")
    forbidden = (
        b"modelGet('diagnostic'",
        b"file=ttl_set",
        b"<command>ttl</command>",
        b"SystemChannelName",
        b"PRODUCT_CHANNEL",
        b"debugmodeon",
        b"Engineering_mode>",
        b"RestoreFw",
    )
    if any(value in joined for value in forbidden):
        raise CommunityR37Error("R3.7 browser assets contain a forbidden live path")
    if b"setInterval" in app:
        raise CommunityR37Error("R3.7 contains unsafe interval polling")
    return replacements, additions, set(removals)


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR37Error("R3.7 output records are not pinned")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR37Error("R3.7 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR37Error("R3.7 addition record gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR37Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR37Error(str(exc)) from exc
    return replacements, additions, removals
