#!/usr/bin/env python3
"""Deterministic Community R3.6 pre-GET TTL repair."""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r35 as r35


PROFILE = "0.3.6-community-r2"
MARKER = b"MF885 Community R3.6 extension 0.3.6-community-r2"
REMOVED_RECORDS = r35.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r35.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r36.html"
APP_PATH = "www\\js\\r36app.js"
CSS_PATH = "www\\css\\r36ui.css"
TTL_SET_PATH = r35.TTL_SET_PATH
DIAGNOSTIC_PATH = r35.DIAGNOSTIC_PATH

OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "804932da5bf6468aee2561577428bd563ba6877a9327cdea41b6758e4d0675a0"),
    "www\\index.html": (26_636, "cf44fe14d5ce291203b1b8fcfe606e419a1ed59da49bf12f41ed5927eee6a169"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
    DIAGNOSTIC_PATH: (107, "e6bfeecef30e22a1a7fd64ec99613f91a232934cd988d03d38e5fbcc8f6ab00e"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    ENTRY_PATH: (15_539, "a04971c67d94713dcf7b3c09de33de003ce8f4c7582b3b5cb91c093c739cbf5e", "R3.6 cumulative UI with explicit manual-only TTL qualification"),
    APP_PATH: (75_999, "afcc1ab8087f900425ed3201fe1206500c27cf912218bb0ae655acfa1694a415", "R3.6 controller with no bootstrap or background TTL GET"),
    CSS_PATH: (9_232, "84eaad60ed768f9a8daf1bee296bb9e9a6971214f494b3636f25cd331c023576", "byte-identical reviewed TTL CSS under cache-safe R3.6 path"),
    TTL_SET_PATH: (121, "8de4597280dfac12c8e33bc6db32aec30e99e13d4e8583a7bfa67da448b23bd8", "isolated diagnostic command/arg TTL set template"),
}


class CommunityR36Error(Exception):
    pass


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.3.5-community-r2", b"0.3.6-community-r2"),
        (b"0.3.5", b"0.3.6"),
        (b"R3.5", b"R3.6"),
        (b"r35", b"r36"),
        (b"R35", b"R36"),
        (b"JS35", b"JS36"),
        (b"LIVE35", b"LIVE36"),
        (b"S35", b"S36"),
        (b"TTL35", b"TTL36"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR36Error(f"{label} has no R3.5 revision anchor")
    return data


def _replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    if data.count(old) != 1:
        raise CommunityR36Error(f"{label} anchor count is {data.count(old)}, expected 1")
    return data.replace(old, new, 1)


def _manual_ttl_only(data: bytes) -> bytes:
    replacements = (
        (
            b" \xc2\xb7 automatic refresh in 30 seconds.",
            b" \xc2\xb7 manual refresh only until target qualification.",
            "TTL success status",
        ),
        (
            b"function universalDueAt(){var snapshotDue=nextSnapshotAt||Date.now(),messagesDue=nextMessagesAt||Date.now(),ttlDue=ttlRuntime.nextAt||Date.now();return Math.min(snapshotDue,messagesDue,ttlDue)}",
            b"function universalDueAt(){var snapshotDue=nextSnapshotAt||Date.now(),messagesDue=nextMessagesAt||Date.now();return Math.min(snapshotDue,messagesDue)}",
            "universal due calculation",
        ),
        (
            b",ttlDue=now>=(ttlRuntime.nextAt||0),messageAllowed=",
            b",ttlDue=false,messageAllowed=",
            "live TTL due variable",
        ),
        (
            b"if(ttlDue){dispatchCount++;ttlRuntime.nextAt=now+SNAPSHOT_POLL_MS;liveLog(id,'dispatch',{kind:'ttl-state',getCeiling:1});flow=flow.then(function(){return readTtlState('live:'+id)}).catch(function(error){logFailure(error,'Universal TTL refresh failed.');return null})}",
            b"",
            "live TTL dispatch",
        ),
        (
            b"if(liveEnabled){nextMessagesAt=0;nextSnapshotAt=0;ttlRuntime.nextAt=0;scheduleLive(0)}",
            b"if(liveEnabled){nextMessagesAt=0;nextSnapshotAt=0;scheduleLive(0)}",
            "live enable TTL scheduling",
        ),
        (
            b".then(function(){return readTtlState('bootstrap')})",
            b".then(function(){ttlRuntime.current=null;ttlRuntime.locked=true;ttlRuntime.nextAt=0;syncTtlControls();status('ttlStatus','TTL is not read automatically in R3.6. Use Read current state for one explicit check.');return null})",
            "bootstrap TTL request",
        ),
        (
            b"status('ttlStatus','Current state will load automatically after sign-in and refresh every 30 seconds.');",
            b"status('ttlStatus','TTL is manual-only until its first target qualification. Use Read current state explicitly.');",
            "logout TTL status",
        ),
        (
            b"nextMessagesAt=0;nextSnapshotAt=0;ttlRuntime.nextAt=0;scheduleLive(0)",
            b"nextMessagesAt=0;nextSnapshotAt=0;scheduleLive(0)",
            "visibility TTL scheduling",
        ),
    )
    for old, new, label in replacements:
        data = _replace_once(data, old, new, label)
    next_at = b"ttlRuntime.nextAt=Date.now()+SNAPSHOT_POLL_MS;"
    if data.count(next_at) != 2:
        raise CommunityR36Error(
            f"TTL next-at anchor count is {data.count(next_at)}, expected 2"
        )
    data = data.replace(next_at, b"ttlRuntime.nextAt=0;")
    if data.count(b"readTtlState('bootstrap')") != 0:
        raise CommunityR36Error("R3.6 retains a bootstrap TTL request")
    dispatch_count = data.count(b"kind:'ttl-state'")
    live_call_count = data.count(b"readTtlState('live:")
    if dispatch_count or live_call_count:
        raise CommunityR36Error(
            "R3.6 retains a background TTL request: "
            f"dispatch={dispatch_count}, live_call={live_call_count}"
        )
    if data.count(b"readTtlState('manual-ttl')") != 1:
        raise CommunityR36Error("R3.6 manual TTL refresh is absent or duplicated")
    return data


def derive_assets(root: Path) -> dict[str, bytes]:
    parent = r35.derive_assets(root)
    app = _manual_ttl_only(_revise(parent[r35.APP_PATH], f"R3.6 asset {APP_PATH}"))
    entry = _revise(parent[r35.ENTRY_PATH], f"R3.6 asset {ENTRY_PATH}")
    entry = _replace_once(
        entry,
        b"Messages, device health, radio details and TTL state start loading as soon as sign-in completes. One universal refresh keeps every screen current.",
        b"Messages, device health and radio details load after sign-in and stay current. TTL remains manual-only until its first target qualification.",
        "entry automatic-load statement",
    )
    entry = _replace_once(
        entry,
        b"Current state will load automatically after sign-in and refresh every 30 seconds.",
        b"TTL is manual-only until its first target qualification. Use Read current state explicitly.",
        "entry TTL status",
    )
    try:
        ttl_set = (root / "firmware" / "community-r3.6" / "ttl_set.xml").read_bytes()
    except OSError as exc:
        raise CommunityR36Error("R3.6 TTL-set template is unavailable") from exc
    return {
        ENTRY_PATH: entry,
        APP_PATH: app,
        CSS_PATH: parent[r35.CSS_PATH],
        TTL_SET_PATH: ttl_set.replace(b"\n", b"\r\n"),
    }


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        parent_replacements, _parent_additions, removals = r35._derive_unpinned_patch_set(
            records, root
        )
    except r35.CommunityR35Error as exc:
        raise CommunityR36Error(str(exc)) from exc
    replacements = dict(parent_replacements)
    for path in ("www\\index.html", "www\\html\\adminApp.html"):
        replacements[path] = _revise(replacements[path], f"R3.6 replacement {path}")
    additions = derive_assets(root)
    if set(replacements) != set(r35.OUTPUT_RECORDS):
        raise CommunityR36Error("R3.6 replacement path set changed")
    if set(additions) != {ENTRY_PATH, APP_PATH, CSS_PATH, TTL_SET_PATH}:
        raise CommunityR36Error("R3.6 extension asset set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR36Error("R3.6 removed-locale set changed")
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR36Error("R3.6 marker is absent")
    if b'href="/r36.html"' not in replacements["www\\index.html"]:
        raise CommunityR36Error("canonical login does not link R3.6")
    if b'href="/r36.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR36Error("shared header does not link R3.6")
    app = additions[APP_PATH]
    if app.count(b"file=ttl_set") != 1 or app.count(b"modelGet('diagnostic'") != 1:
        raise CommunityR36Error("R3.6 TTL read/set routes are not isolated")
    if app.count(b"readTtlState('manual-ttl')") != 1:
        raise CommunityR36Error("R3.6 explicit TTL read control changed")
    if b"readTtlState('bootstrap')" in app or b"kind:'ttl-state'" in app:
        raise CommunityR36Error("R3.6 contains an automatic TTL request")
    if any(value in joined for value in (b"SystemChannelName", b"PRODUCT_CHANNEL", b"debugmodeon", b"Engineering_mode>")):
        raise CommunityR36Error("R3.6 browser assets contain a retired or Engineering bridge")
    return replacements, additions, set(removals)


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR36Error("R3.6 output records are not pinned; retained build is disabled")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR36Error("R3.6 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR36Error("R3.6 addition record gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR36Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR36Error(str(exc)) from exc
    return replacements, additions, removals
