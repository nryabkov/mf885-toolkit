#!/usr/bin/env python3
"""Deterministic Community R3.4 diagnostic no-op WebUI from exact R2.9.

R3.4 deliberately returns to the proven R2.9 browser transport. It keeps the
TTL page visible as an honest unavailable-state explanation, but contains no
TTL router request, mutation, polling, or external modem dependency.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r29 as r29


PROFILE = "0.3.4-community-r2"
MARKER = b"MF885 Community R3.4 extension 0.3.4-community-r2"
REMOVED_RECORDS = r29.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r29.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r34.html"
APP_PATH = "www\\js\\r34app.js"
CSS_PATH = "www\\css\\r34ui.css"

CUSTOM_FILES: dict[str, tuple[str, int, str]] = {}
FRAGMENT_FILES: dict[str, tuple[str, int, str]] = {
    "ttl_panel": (
        "firmware/community-r3.4/ttl_unavailable_panel.html",
        1_475,
        "668725303b8936432b0f3ffaf461d136bf980e753b03fbd7cf8258b751f89482",
    ),
}
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "549bb9f637a117e7149012e6e63610bffd192d4fd772581e1cdbef41a94cade0"),
    "www\\index.html": (26_636, "2c71a272eadc17aebf56fa0dcc193170f083829b771a7dffa47c1f8086b738cc"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    ENTRY_PATH: (14_627, "1b9f35405088216a7d1e81d1c6d59e2385d92c3a051edff21426fa79e1146c48", "derived from exact R2.9 HTML plus the pinned static TTL-unavailable panel"),
    APP_PATH: (63_060, "b5de8a702ba1445afb951c017cc47189e5fb171f90e0434d3f13f41c269e721f", "derived from exact R2.9 controller with static TTL page routing only"),
    CSS_PATH: (7_925, "50b977ba920c226a4a9c03895c47d1457439adba0eefd169c20e2cca21244578", "derived from exact R2.9 CSS with five-column mobile navigation"),
}


class CommunityR34Error(Exception):
    pass


def _load_r29_assets(root: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for target, (source, size, digest) in r29.CUSTOM_FILES.items():
        try:
            value = (root / source).read_bytes()
        except OSError as exc:
            raise CommunityR34Error(f"could not read exact R2.9 source {source}") from exc
        try:
            result[target] = r2.require_exact(value, size, digest, source)
        except r2.CommunityR2Error as exc:
            raise CommunityR34Error(str(exc)) from exc
    return result


def _replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    count = data.count(old)
    if count != 1:
        raise CommunityR34Error(f"{label} anchor count is {count}, expected 1")
    return data.replace(old, new, 1)


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.2.9-community-r2", b"0.3.4-community-r2"),
        (b"0.2.9", b"0.3.4"),
        (b"R2.9", b"R3.4"),
        (b"r29", b"r34"),
        (b"R29", b"R34"),
        (b"JS29", b"JS34"),
        (b"LIVE29", b"LIVE34"),
        (b"S29", b"S34"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR34Error(f"{label} has no R2.9 revision anchor")
    return data


def _load_fragment(root: Path, name: str) -> bytes:
    source, size, digest = FRAGMENT_FILES[name]
    try:
        value = (root / source).read_bytes()
    except OSError as exc:
        raise CommunityR34Error(f"could not read exact R3.4 fragment {source}") from exc
    try:
        return r2.require_exact(value, size, digest, source)
    except r2.CommunityR2Error as exc:
        raise CommunityR34Error(str(exc)) from exc


def derive_assets(root: Path) -> dict[str, bytes]:
    parent = _load_r29_assets(root)
    ttl_panel = _load_fragment(root, "ttl_panel")
    html = _revise(parent[r29.ENTRY_PATH], "R3.4 entry")
    html = _replace_once(
        html,
        b'        <button type="button" data-page="modem">Modem</button>\n',
        b'        <button type="button" data-page="modem">Modem</button>\n'
        b'        <button type="button" data-page="ttl">TTL</button>\n',
        "R3.4 primary TTL navigation",
    )
    html = _replace_once(
        html,
        b'          <button type="button" data-page="modem" class="secondary">Radio and signal</button>\n',
        b'          <button type="button" data-page="modem" class="secondary">Radio and signal</button>\n'
        b'          <button type="button" data-page="ttl" class="secondary">TTL status</button>\n',
        "R3.4 dashboard TTL action",
    )
    html = _replace_once(
        html,
        b"Messages, device health and radio details start loading as soon as sign-in completes.",
        b"Messages, device health and radio details start loading as soon as sign-in completes. TTL remains visibly unavailable while its native callback is isolated.",
        "R3.4 dashboard explanation",
    )
    html = _replace_once(
        html,
        b"    </main>\n\n    <footer>",
        ttl_panel + b"    </main>\n\n    <footer>",
        "R3.4 TTL unavailable panel",
    )

    app = _revise(parent[r29.APP_PATH], "R3.4 controller")
    app = _replace_once(
        app,
        b"function validPage(name){return /^(?:dashboard|messages|diagnostics|modem)$/.test(String(name||''))}",
        b"function validPage(name){return /^(?:dashboard|messages|diagnostics|modem|ttl)$/.test(String(name||''))}",
        "R3.4 static TTL page routing",
    )
    css = parent[r29.CSS_PATH].replace(
        b"nav{order:3;flex-basis:100%;display:grid;grid-template-columns:repeat(4,1fr)}",
        b"nav{order:3;flex-basis:100%;display:grid;grid-template-columns:repeat(5,1fr)}",
    )
    if css == parent[r29.CSS_PATH]:
        raise CommunityR34Error("R3.4 mobile navigation anchor is absent")
    return {ENTRY_PATH: html, APP_PATH: app, CSS_PATH: css}


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        parent_replacements, parent_additions, removals = r29.build_patch_set(records, root)
    except r29.CommunityR29Error as exc:
        raise CommunityR34Error(str(exc)) from exc
    replacements = dict(parent_replacements)
    replacements["www\\index.html"] = _revise(
        replacements["www\\index.html"], "R3.4 canonical Community link"
    )
    replacements["www\\html\\adminApp.html"] = _revise(
        replacements["www\\html\\adminApp.html"], "R3.4 shared Community header"
    )
    additions = derive_assets(root)
    for parent_path, parent_value in parent_additions.items():
        if parent_value != _load_r29_assets(root)[parent_path]:
            raise CommunityR34Error(f"exact R2.9 parent asset drifted: {parent_path}")
    removals = set(removals)
    joined = b"\n".join(additions.values())
    if set(replacements) != set(r29.OUTPUT_RECORDS):
        raise CommunityR34Error("R3.4 replacement path set changed")
    if set(additions) != {ENTRY_PATH, APP_PATH, CSS_PATH}:
        raise CommunityR34Error("R3.4 extension asset set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR34Error("R3.4 removed-locale set changed")
    if MARKER not in joined:
        raise CommunityR34Error("R3.4 marker is absent")
    if additions[ENTRY_PATH].count(b'data-page="ttl"') != 2:
        raise CommunityR34Error("R3.4 TTL navigation/action count changed")
    if additions[ENTRY_PATH].count(b'id="page-ttl"') != 1:
        raise CommunityR34Error("R3.4 TTL unavailable panel count changed")
    if b"modelGet('diagnostic'" in additions[APP_PATH] or b"SystemChannelName" in additions[APP_PATH]:
        raise CommunityR34Error("R3.4 browser controller contains the retired TTL transport")
    if any(value in additions[APP_PATH] for value in (b"command>ttl", b"ttl_set", b"setInterval", b"RestoreFw")):
        raise CommunityR34Error("R3.4 browser controller contains TTL mutation or unsafe polling")
    if b'href="/r34.html"' not in replacements["www\\index.html"]:
        raise CommunityR34Error("canonical login does not link R3.4")
    if b'href="/r34.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR34Error("shared header does not link R3.4")
    return replacements, additions, removals


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR34Error("R3.4 output records are not pinned; retained build is disabled")
    if set(OUTPUT_RECORDS) != set(replacements) or set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR34Error("R3.4 output pin set is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR34Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR34Error(str(exc)) from exc
    return replacements, additions, removals
