#!/usr/bin/env python3
"""Deterministic Community R3.2 TTL-response repair from exact golden.

The browser contract is intentionally unchanged from R3.1.  New revisioned
paths prevent stale cache identity while the native builder moves the TTL
publisher from Duster post-get to pre-get.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r31 as r31


PROFILE = "0.3.2-community-r2"
MARKER = b"MF885 Community R3.2 extension 0.3.2-community-r2"
REMOVED_RECORDS = r31.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r31.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r32.html"
APP_PATH = "www\\js\\r32app.js"
CSS_PATH = "www\\css\\r32ui.css"

CUSTOM_FILES: dict[str, tuple[str, int, str]] = {}
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "d4de223739768337a0da5db3d303484871f16428fc0378bc43b7a1044fb269f1"),
    "www\\index.html": (26_636, "6d6fb9ca7dd1b6ce03e9a1c0384e4297628f30ae04691235c8657ac4025cf0dd"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    ENTRY_PATH: (15_529, "acff54c8206074bcfa39a5f480a095ccff0d84faaba9716945e17dcc80fc8706", "derived byte-exact from reviewed R3.1 HTML"),
    APP_PATH: (73_163, "94bad38e59554bc39a6c338b54240c4e5dd156838684cccf31be4f76e913b21f", "derived byte-exact from reviewed R3.1 controller"),
    CSS_PATH: (9_232, "84eaad60ed768f9a8daf1bee296bb9e9a6971214f494b3636f25cd331c023576", "byte-identical reviewed R3.1 CSS under cache-safe R3.2 path"),
}


class CommunityR32Error(Exception):
    pass


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.3.1-community-r2", b"0.3.2-community-r2"),
        (b"0.3.1", b"0.3.2"),
        (b"R3.1", b"R3.2"),
        (b"r31", b"r32"),
        (b"R31", b"R32"),
        (b"JS31", b"JS32"),
        (b"LIVE31", b"LIVE32"),
        (b"S31", b"S32"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR32Error(f"{label} has no R3.1 revision anchor")
    return data


def derive_assets(root: Path) -> dict[str, bytes]:
    """Derive the three complete R3.2 assets from pinned R3.1 inputs."""

    parent = r31.derive_assets(root)
    return {
        ENTRY_PATH: _revise(parent[r31.ENTRY_PATH], f"R3.2 asset {ENTRY_PATH}"),
        APP_PATH: _revise(parent[r31.APP_PATH], f"R3.2 asset {APP_PATH}"),
        CSS_PATH: parent[r31.CSS_PATH],
    }


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        parent_replacements, parent_additions, removals = r31.build_patch_set(records, root)
    except r31.CommunityR31Error as exc:
        raise CommunityR32Error(str(exc)) from exc

    replacements = dict(parent_replacements)
    for path in ("www\\index.html", "www\\html\\adminApp.html"):
        replacements[path] = _revise(replacements[path], f"R3.2 replacement {path}")

    additions = derive_assets(root)
    removals = set(removals)
    if set(replacements) != set(r31.OUTPUT_RECORDS):
        raise CommunityR32Error("R3.2 replacement path set changed")
    if set(additions) != {ENTRY_PATH, APP_PATH, CSS_PATH}:
        raise CommunityR32Error("R3.2 extension asset set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR32Error("R3.2 removed-locale set changed")
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR32Error("R3.2 marker is absent")
    if b'href="/r32.html"' not in replacements["www\\index.html"]:
        raise CommunityR32Error("canonical login does not link R3.2")
    if b'href="/r32.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR32Error("shared header does not link R3.2")
    if any(old in joined for old in (b"0.3.1-community-r2", b"R3.1", b"r31app.js", b"r31ui.css")):
        raise CommunityR32Error("R3.2 assets retain an R3.1 cache or revision identity")
    if additions[APP_PATH].count(b"command>ttl") != 1:
        raise CommunityR32Error("R3.2 TTL command contract changed")
    if b"setInterval" in additions[APP_PATH] or b"RestoreFw" in additions[APP_PATH]:
        raise CommunityR32Error("R3.2 contains interval polling or firmware control")
    return replacements, additions, removals


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR32Error("R3.2 output records are not pinned; retained build is disabled")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR32Error("R3.2 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR32Error("R3.2 addition record gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR32Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR32Error(str(exc)) from exc
    return replacements, additions, removals
