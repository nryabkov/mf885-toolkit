#!/usr/bin/env python3
"""Deterministic Community R2.8 MF885-interface extension from exact golden.

R2.8 retains the proven R2.7 stock-record fixes and replaces its isolated
Community entry with a fifth in-interface Modem Lab tab.  GL.iNet is not a
second product surface: only the exact same-origin Community gateway namespace
is referenced by the browser bundle.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r27 as r27


PROFILE = "0.2.8-community-r2"
MARKER = b"MF885 Community R2.8 extension 0.2.8-community-r2"
REMOVED_RECORDS = r27.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r27.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r28.html"
APP_PATH = "www\\js\\r28app.js"
CSS_PATH = "www\\css\\r28ui.css"

CUSTOM_FILES = {
    ENTRY_PATH: (
        "firmware/community-r2.8/r28.html",
        9_731,
        "fe49076cc0f9eb1ba9090105bbebc7bfd3a0b5c687a49f1342f49867684abba5",
    ),
    APP_PATH: (
        "firmware/community-r2.8/r28app.js",
        66_911,
        "76aa907526698b22bd1e4ea0a3a32916d12fd022c6c45d1bcf42a750c779c929",
    ),
    CSS_PATH: (
        "firmware/community-r2.8/r28ui.css",
        8_048,
        "4cb7682bbb0d8592f03f18573a17b0072f9008825e1f474f11e6f2dcb400c5e0",
    ),
}

# Independently derived output bytes from the exact reviewed golden.
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "b11e74443ede6c92e9772c1fbf42c754b0509c75efe9bb20374a12d81ebd52c8"),
    "www\\index.html": (26_636, "4fed5c4b497e2c9be1a86212466f0ae426512aac7f7b19ebd7d4c68387fdde86"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    target: (size, digest, source)
    for target, (source, size, digest) in CUSTOM_FILES.items()
}


class CommunityR28Error(Exception):
    pass


def _load_exact(root: Path, source: str, size: int, digest: str) -> bytes:
    try:
        data = (root / source).read_bytes()
    except OSError as exc:
        raise CommunityR28Error(f"could not read exact Community R2.8 source {source}") from exc
    try:
        return r2.require_exact(data, size, digest, source)
    except r2.CommunityR2Error as exc:
        raise CommunityR28Error(str(exc)) from exc


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.2.7-community-r2", b"0.2.8-community-r2"),
        (b"R2.7", b"R2.8"),
        (b"r27", b"r28"),
        (b"R27", b"R28"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR28Error(f"{label} has no R2.7 revision anchor")
    return data


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        parent_replacements, _parent_additions, removals = r27.build_patch_set(records, root)
    except r27.CommunityR27Error as exc:
        raise CommunityR28Error(str(exc)) from exc

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

    if set(replacements) != set(r27.OUTPUT_RECORDS):
        raise CommunityR28Error("R2.8 replacement path set changed")
    if set(additions) != {ENTRY_PATH, APP_PATH, CSS_PATH}:
        raise CommunityR28Error("R2.8 extension asset set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR28Error("R2.8 removed-locale set changed")
    if MARKER not in additions[APP_PATH]:
        raise CommunityR28Error("R2.8 marker is absent")
    if additions[ENTRY_PATH].count(b"r28app.js") != 1 or additions[ENTRY_PATH].count(b"r28ui.css") != 1:
        raise CommunityR28Error("R2.8 entry does not bind its assets exactly once")
    if b"initIndex" in additions[ENTRY_PATH] or b"ajax_calls.js" in additions[ENTRY_PATH]:
        raise CommunityR28Error("R2.8 entry starts the legacy blocking stack")
    compact_app = additions[APP_PATH].replace(b" ", b"")
    if b"async:false" in compact_app:
        raise CommunityR28Error("R2.8 controller contains synchronous XHR")
    if b"setInterval" in additions[APP_PATH] or b"RestoreFw" in additions[APP_PATH]:
        raise CommunityR28Error("R2.8 controller contains polling or firmware control")
    if additions[ENTRY_PATH].count(b'data-page="modem-lab"') != 2:
        raise CommunityR28Error("R2.8 Modem Lab is not an exact in-interface page and home entry")
    if b"/community-api/modem-lab/" not in additions[APP_PATH]:
        raise CommunityR28Error("R2.8 narrow same-origin Modem Lab namespace is absent")
    for forbidden in (b"Open LuCI", b"luci-static", b"/cgi-bin/luci", b"raw_command_input:true"):
        if forbidden.lower() in additions[ENTRY_PATH].lower() or forbidden.lower() in additions[APP_PATH].lower():
            raise CommunityR28Error("R2.8 browser bundle exposes the rejected external GL.iNet product surface")
    if b'href="/r28.html"' not in replacements["www\\index.html"]:
        raise CommunityR28Error("canonical login does not link R2.8")
    if b'href="/r28.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR28Error("shared header does not link R2.8")
    return replacements, additions, removals


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS:
        raise CommunityR28Error("R2.8 derived output records are not pinned; retained build is disabled")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR28Error("R2.8 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR28Error("R2.8 addition provenance gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR28Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR28Error(str(exc)) from exc
    return replacements, additions, removals
