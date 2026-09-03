#!/usr/bin/env python3
"""Deterministic Community R2.9 MF885-interface extension from exact golden.

R2.9 retains the proven R2.8 router transport and Messages contract while
making the authenticated shell usable immediately, restoring bounded
universal live updates and documenting the complete read-only modem surface.
The browser bundle contains no external modem-command or debug-profile path.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r28 as r28


PROFILE = "0.2.9-community-r2"
MARKER = b"MF885 Community R2.9 extension 0.2.9-community-r2"
REMOVED_RECORDS = r28.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r28.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r29.html"
APP_PATH = "www\\js\\r29app.js"
CSS_PATH = "www\\css\\r29ui.css"

CUSTOM_FILES = {
    ENTRY_PATH: (
        "firmware/community-r2.9/r29.html",
        12_936,
        "a897edb453fa4be45406f9da6982d4b0c2fa548f6d8ebc08c415630dca14af8e",
    ),
    APP_PATH: (
        "firmware/community-r2.9/r29app.js",
        63_056,
        "5ae06b6c63d62f1f6edbdad54f7fbd73d7d05e2ed6153e7e7ec0c5984b150267",
    ),
    CSS_PATH: (
        "firmware/community-r2.9/r29ui.css",
        7_925,
        "29cb3ffb6f35564a761f43ce858e5ec11704c22fb16ef1eecc570d49c1f01417",
    ),
}

# Independently derived output bytes from the exact reviewed golden.
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (
        21_381,
        "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2",
    ),
    "www\\html\\adminApp.html": (
        4_766,
        "269610f501d8329fee07e0ffffd5a8e0d564e1a672cd29241f682c35aeaf6dc8",
    ),
    "www\\index.html": (
        26_636,
        "c532ec54279aac493d7855c7cb4e5fb666b745de2e6b112e0db2f58e3efa66ed",
    ),
    "www\\js\\base\\ajax_calls.js": (
        21_467,
        "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127",
    ),
    "www\\js\\base\\utils.js": (
        16_873,
        "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103",
    ),
    "www\\properties\\Messages_en.properties": (
        46_943,
        "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c",
    ),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    target: (size, digest, source)
    for target, (source, size, digest) in CUSTOM_FILES.items()
}


class CommunityR29Error(Exception):
    pass


def _load_exact(root: Path, source: str, size: int, digest: str) -> bytes:
    try:
        data = (root / source).read_bytes()
    except OSError as exc:
        raise CommunityR29Error(f"could not read exact Community R2.9 source {source}") from exc
    try:
        return r2.require_exact(data, size, digest, source)
    except r2.CommunityR2Error as exc:
        raise CommunityR29Error(str(exc)) from exc


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.2.8-community-r2", b"0.2.9-community-r2"),
        (b"R2.8", b"R2.9"),
        (b"r28", b"r29"),
        (b"R28", b"R29"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR29Error(f"{label} has no R2.8 revision anchor")
    return data


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        parent_replacements, _parent_additions, removals = r28.build_patch_set(records, root)
    except r28.CommunityR28Error as exc:
        raise CommunityR29Error(str(exc)) from exc

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

    if set(replacements) != set(r28.OUTPUT_RECORDS):
        raise CommunityR29Error("R2.9 replacement path set changed")
    if set(additions) != {ENTRY_PATH, APP_PATH, CSS_PATH}:
        raise CommunityR29Error("R2.9 extension asset set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR29Error("R2.9 removed-locale set changed")
    if MARKER not in additions[APP_PATH]:
        raise CommunityR29Error("R2.9 marker is absent")
    if additions[ENTRY_PATH].count(b'<script defer src="js/r29app.js"></script>') != 1 or additions[ENTRY_PATH].count(b'<link rel="stylesheet" href="css/r29ui.css">') != 1:
        raise CommunityR29Error("R2.9 entry does not bind its assets exactly once")
    if b"initIndex" in additions[ENTRY_PATH] or b"ajax_calls.js" in additions[ENTRY_PATH]:
        raise CommunityR29Error("R2.9 entry starts the legacy blocking stack")
    compact_app = additions[APP_PATH].replace(b" ", b"")
    if b"async:false" in compact_app:
        raise CommunityR29Error("R2.9 controller contains synchronous XHR")
    if b"setInterval" in additions[APP_PATH] or b"RestoreFw" in additions[APP_PATH]:
        raise CommunityR29Error("R2.9 controller contains interval polling or firmware control")
    if b"SNAPSHOT_POLL_MS=30000" not in additions[APP_PATH] or b"MESSAGES_POLL_MS=60000" not in additions[APP_PATH]:
        raise CommunityR29Error("R2.9 bounded live scheduler is absent")
    for forbidden in (
        b'page-modem-lab',
        b'data-page="modem-lab"',
        b'modemLab',
        b'/community-api/modem-lab/',
        b'AT+CSQ',
        b'Direct signal check',
        b'X-MF885-Community-Gateway',
    ):
        if forbidden.lower() in additions[ENTRY_PATH].lower() or forbidden.lower() in additions[APP_PATH].lower():
            raise CommunityR29Error("R2.9 browser bundle still exposes the removed external modem-command surface")
    for required in (
        b"What the modem can report",
        b"Observed on this MF885",
        b"Router status schema",
        b"Firmware schema",
        b"Private when returned",
        b"Engineering mode",
        b"Not provided here",
    ):
        if required not in additions[ENTRY_PATH]:
            raise CommunityR29Error("R2.9 complete modem help catalogue is absent")
    for forbidden in (b"Open LuCI", b"luci-static", b"/cgi-bin/luci", b"raw_command_input:true"):
        if forbidden.lower() in additions[ENTRY_PATH].lower() or forbidden.lower() in additions[APP_PATH].lower():
            raise CommunityR29Error("R2.9 browser bundle exposes the rejected external GL.iNet product surface")
    if b'href="/r29.html"' not in replacements["www\\index.html"]:
        raise CommunityR29Error("canonical login does not link R2.9")
    if b'href="/r29.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR29Error("shared header does not link R2.9")
    return replacements, additions, removals


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS:
        raise CommunityR29Error("R2.9 derived output records are not pinned; retained build is disabled")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR29Error("R2.9 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR29Error("R2.9 addition provenance gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR29Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR29Error(str(exc)) from exc
    return replacements, additions, removals
