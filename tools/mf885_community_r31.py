#!/usr/bin/env python3
"""Deterministic Community R3.1 TTL-repair extension from exact golden.

R3.1 preserves the complete R3.0 browser behavior and changes only revisioned
asset identities.  Its functional change is the separately verified native
low-page TTL payload; this module keeps the WebUI cumulative and cache-safe.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r30 as r30


PROFILE = "0.3.1-community-r2"
MARKER = b"MF885 Community R3.1 extension 0.3.1-community-r2"
REMOVED_RECORDS = r30.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r30.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r31.html"
APP_PATH = "www\\js\\r31app.js"
CSS_PATH = "www\\css\\r31ui.css"

CUSTOM_FILES: dict[str, tuple[str, int, str]] = {}
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "0354093bee3208b6c8ba8d184378b255c6f7e95f2538e55bfb71bf4b4e63a29b"),
    "www\\index.html": (26_636, "86f9c2bc61a7a41ee982a0ea3aa484b9edd214f149c38710aea22c8472985dd3"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    ENTRY_PATH: (15_529, "3fd323aae54eae62c2c98b0d500ff7fd630a8bd362d730173b9896d1c8977da9", "derived byte-exact from reviewed R3.0 HTML"),
    APP_PATH: (73_163, "1945ddd1f9981be204c9d5c39f8fde4b9c5f734af9dca34800bfd2b531e44309", "derived byte-exact from reviewed R3.0 controller"),
    CSS_PATH: (9_232, "84eaad60ed768f9a8daf1bee296bb9e9a6971214f494b3636f25cd331c023576", "byte-identical reviewed R3.0 CSS under cache-safe R3.1 path"),
}


class CommunityR31Error(Exception):
    pass


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.3.0-community-r2", b"0.3.1-community-r2"),
        (b"0.3.0", b"0.3.1"),
        (b"R3.0", b"R3.1"),
        (b"r30", b"r31"),
        (b"R30", b"R31"),
        (b"JS30", b"JS31"),
        (b"LIVE30", b"LIVE31"),
        (b"S30", b"S31"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR31Error(f"{label} has no R3.0 revision anchor")
    return data


def derive_assets(root: Path) -> dict[str, bytes]:
    """Derive the three complete R3.1 assets from pinned R3.0 inputs."""

    parent = r30.derive_assets(root)
    return {
        ENTRY_PATH: _revise(parent[r30.ENTRY_PATH], f"R3.1 asset {ENTRY_PATH}"),
        APP_PATH: _revise(parent[r30.APP_PATH], f"R3.1 asset {APP_PATH}"),
        CSS_PATH: parent[r30.CSS_PATH],
    }


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        parent_replacements, parent_additions, removals = r30.build_patch_set(records, root)
    except r30.CommunityR30Error as exc:
        raise CommunityR31Error(str(exc)) from exc

    replacements = dict(parent_replacements)
    for path in ("www\\index.html", "www\\html\\adminApp.html"):
        replacements[path] = _revise(replacements[path], f"R3.1 replacement {path}")

    additions = derive_assets(root)
    removals = set(removals)

    if set(replacements) != set(r30.OUTPUT_RECORDS):
        raise CommunityR31Error("R3.1 replacement path set changed")
    if set(additions) != {ENTRY_PATH, APP_PATH, CSS_PATH}:
        raise CommunityR31Error("R3.1 extension asset set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR31Error("R3.1 removed-locale set changed")
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR31Error("R3.1 marker is absent")
    if b'href="/r31.html"' not in replacements["www\\index.html"]:
        raise CommunityR31Error("canonical login does not link R3.1")
    if b'href="/r31.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR31Error("shared header does not link R3.1")
    if any(old in joined for old in (b"0.3.0-community-r2", b"R3.0", b"r30app.js", b"r30ui.css")):
        raise CommunityR31Error("R3.1 assets retain an R3.0 cache or revision identity")
    if additions[APP_PATH].count(b"command>ttl") != 1:
        raise CommunityR31Error("R3.1 TTL command contract changed")
    if b"setInterval" in additions[APP_PATH] or b"RestoreFw" in additions[APP_PATH]:
        raise CommunityR31Error("R3.1 contains interval polling or firmware control")
    return replacements, additions, removals


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR31Error("R3.1 output records are not pinned; retained build is disabled")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR31Error("R3.1 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR31Error("R3.1 addition record gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR31Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR31Error(str(exc)) from exc
    return replacements, additions, removals
