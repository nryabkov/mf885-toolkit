#!/usr/bin/env python3
"""Deterministic Community R2.7 extension built from exact golden.

R2.7 deliberately does not carry the R2.5 browser bundle forward.  It reuses
only R2.5's reviewed stock-record replacements and adds a small isolated
extension entry, stylesheet and controller.  The extension entry never starts
the legacy synchronous init/login/SMS stack.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r25 as r25


PROFILE = "0.2.7-community-r2"
MARKER = b"MF885 Community R2.7 extension 0.2.7-community-r2"
REMOVED_RECORDS = r25.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r25.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r27.html"
APP_PATH = "www\\js\\r27app.js"
CSS_PATH = "www\\css\\r27ui.css"

CUSTOM_FILES = {
    ENTRY_PATH: (
        "firmware/community-r2.7/r27.html",
        6_916,
        "eba933080f047712892a2be5304eba517b5751b6ba943fcef7b12c645320ec59",
    ),
    APP_PATH: (
        "firmware/community-r2.7/r27app.js",
        41_604,
        "f7358656d2aca3db1bbd4ecd7e12acfc91d50ce6c6fe2ba957db2c294f2eb2c9",
    ),
    CSS_PATH: (
        "firmware/community-r2.7/r27ui.css",
        6_735,
        "6e4301d738cc3c6e23f61283fd5060dc2defe85ce9a9b018fc0cda31f795b8a6",
    ),
}

# Independently derived output bytes from the exact reviewed golden.
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "13928fe9e9b8d05e899d25c3ea45d48aaf6bf23fd3b126edf9e4ca1d84a2e969"),
    "www\\index.html": (26_636, "08d8ee87cda3907330540366ad7bf02c01029d2bb973c55053741222a4231fc4"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    target: (size, digest, source)
    for target, (source, size, digest) in CUSTOM_FILES.items()
}


class CommunityR27Error(Exception):
    pass


def _load_exact(root: Path, source: str, size: int, digest: str) -> bytes:
    try:
        data = (root / source).read_bytes()
    except OSError as exc:
        raise CommunityR27Error(f"could not read exact Community R2.7 source {source}") from exc
    try:
        return r2.require_exact(data, size, digest, source)
    except r2.CommunityR2Error as exc:
        raise CommunityR27Error(str(exc)) from exc


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.2.5-community-r2", b"0.2.7-community-r2"),
        (b"R2.5", b"R2.7"),
        (b"r25", b"r27"),
        (b"R25", b"R27"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR27Error(f"{label} has no R2.5 revision anchor")
    return data


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        parent_replacements, _parent_additions, removals = r25.build_patch_set(records, root)
    except r25.CommunityR25Error as exc:
        raise CommunityR27Error(str(exc)) from exc

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
        raise CommunityR27Error("R2.7 replacement path set changed")
    if set(additions) != {ENTRY_PATH, APP_PATH, CSS_PATH}:
        raise CommunityR27Error("R2.7 extension asset set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR27Error("R2.7 removed-locale set changed")
    if MARKER not in additions[APP_PATH]:
        raise CommunityR27Error("R2.7 marker is absent")
    if additions[ENTRY_PATH].count(b"r27app.js") != 1 or additions[ENTRY_PATH].count(b"r27ui.css") != 1:
        raise CommunityR27Error("R2.7 entry does not bind its assets exactly once")
    if b"initIndex" in additions[ENTRY_PATH] or b"ajax_calls.js" in additions[ENTRY_PATH]:
        raise CommunityR27Error("R2.7 entry starts the legacy blocking stack")
    if b"async:false" in additions[APP_PATH].replace(b" ", b""):
        raise CommunityR27Error("R2.7 controller contains synchronous XHR")
    if b"setInterval" in additions[APP_PATH] or b"RestoreFw" in additions[APP_PATH]:
        raise CommunityR27Error("R2.7 controller contains polling or firmware control")
    if b'href="/r27.html"' not in replacements["www\\index.html"]:
        raise CommunityR27Error("canonical login does not link R2.7")
    if b'href="/r27.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR27Error("shared header does not link R2.7")
    return replacements, additions, removals


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS:
        raise CommunityR27Error("R2.7 derived output records are not pinned; retained build is disabled")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR27Error("R2.7 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR27Error("R2.7 addition provenance gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR27Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR27Error(str(exc)) from exc
    return replacements, additions, removals
