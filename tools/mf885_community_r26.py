#!/usr/bin/env python3
"""Deterministic Community R2.6 non-blocking UI built from exact golden.

R2.6 deliberately does not carry the R2.5 browser bundle forward.  It reuses
only R2.5's reviewed stock-record replacements and adds a small standalone
entry, stylesheet and controller.  The standalone entry never starts the
legacy synchronous init/login/SMS stack.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r25 as r25


PROFILE = "0.2.6-community-r2"
MARKER = b"MF885 Community R2.6 non-blocking shell 0.2.6-community-r2"
REMOVED_RECORDS = r25.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r25.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r26.html"
APP_PATH = "www\\js\\r26app.js"
CSS_PATH = "www\\css\\r26ui.css"

CUSTOM_FILES = {
    ENTRY_PATH: (
        "firmware/community-r2.6/r26.html",
        5_269,
        "e57665e8667429268c0eea7f46c00ef9a3c91b5e555d8120fb091495912d656a",
    ),
    APP_PATH: (
        "firmware/community-r2.6/r26app.js",
        24_765,
        "742a520d1d36cb6c569b43d014e4d595d637f195e743b738fbece94c8bcf3c54",
    ),
    CSS_PATH: (
        "firmware/community-r2.6/r26ui.css",
        5_052,
        "3f5192c823c21818b0861f5b9bb2eee8fbc68b4c8b43b106eb9272cc73a29c8b",
    ),
}

# Independently derived output bytes from the exact reviewed golden.
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "5626ba085d18cb4189560f02d3de592937287290d48cb6c76420a24be259de11"),
    "www\\index.html": (26_636, "51e3d077c499fb6183bcdf39ad8429ea71fcb2a4c3ad62f3731bc6783476efc4"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    target: (size, digest, source)
    for target, (source, size, digest) in CUSTOM_FILES.items()
}


class CommunityR26Error(Exception):
    pass


def _load_exact(root: Path, source: str, size: int, digest: str) -> bytes:
    try:
        data = (root / source).read_bytes()
    except OSError as exc:
        raise CommunityR26Error(f"could not read exact Community R2.6 source {source}") from exc
    try:
        return r2.require_exact(data, size, digest, source)
    except r2.CommunityR2Error as exc:
        raise CommunityR26Error(str(exc)) from exc


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.2.5-community-r2", b"0.2.6-community-r2"),
        (b"R2.5", b"R2.6"),
        (b"r25", b"r26"),
        (b"R25", b"R26"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR26Error(f"{label} has no R2.5 revision anchor")
    return data


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        parent_replacements, _parent_additions, removals = r25.build_patch_set(records, root)
    except r25.CommunityR25Error as exc:
        raise CommunityR26Error(str(exc)) from exc

    replacements = dict(parent_replacements)
    replacements["www\\index.html"] = _revise(
        replacements["www\\index.html"], "canonical Community link"
    )
    replacements["www\\html\\adminApp.html"] = _revise(
        replacements["www\\html\\adminApp.html"], "shared Community header"
    )
    additions = {
        target: _load_exact(root, source, size, digest)
        for target, (source, size, digest) in CUSTOM_FILES.items()
    }
    removals = set(removals)

    if set(replacements) != set(r25.OUTPUT_RECORDS):
        raise CommunityR26Error("R2.6 replacement path set changed")
    if set(additions) != {ENTRY_PATH, APP_PATH, CSS_PATH}:
        raise CommunityR26Error("R2.6 standalone asset set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR26Error("R2.6 removed-locale set changed")
    if MARKER not in additions[APP_PATH]:
        raise CommunityR26Error("R2.6 marker is absent")
    if additions[ENTRY_PATH].count(b"r26app.js") != 1 or additions[ENTRY_PATH].count(b"r26ui.css") != 1:
        raise CommunityR26Error("R2.6 entry does not bind its assets exactly once")
    if b"initIndex" in additions[ENTRY_PATH] or b"ajax_calls.js" in additions[ENTRY_PATH]:
        raise CommunityR26Error("R2.6 entry starts the legacy blocking stack")
    if b"async:false" in additions[APP_PATH].replace(b" ", b""):
        raise CommunityR26Error("R2.6 controller contains synchronous XHR")
    if b"setInterval" in additions[APP_PATH] or b"RestoreFw" in additions[APP_PATH]:
        raise CommunityR26Error("R2.6 controller contains polling or firmware control")
    if b'href="/r26.html"' not in replacements["www\\index.html"]:
        raise CommunityR26Error("canonical login does not link R2.6")
    if b'href="/r26.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR26Error("shared header does not link R2.6")
    return replacements, additions, removals


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS:
        raise CommunityR26Error("R2.6 derived output records are not pinned; retained build is disabled")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR26Error("R2.6 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR26Error("R2.6 addition provenance gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR26Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR26Error(str(exc)) from exc
    return replacements, additions, removals
