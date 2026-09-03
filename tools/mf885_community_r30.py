#!/usr/bin/env python3
"""Deterministic Community R3.0 TTL extension from exact Community R2.9.

R3.0 keeps every accepted R2.9 WebUI change and adds a small authenticated TTL
page.  The complete R3.0 assets are derived from byte-pinned R2.9 sources plus
three byte-pinned fragments; no device or network operation is performed here.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r29 as r29


PROFILE = "0.3.0-community-r2"
MARKER = b"MF885 Community R3.0 extension 0.3.0-community-r2"
REMOVED_RECORDS = r29.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r29.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r30.html"
APP_PATH = "www\\js\\r30app.js"
CSS_PATH = "www\\css\\r30ui.css"

FRAGMENT_FILES = {
    "panel": (
        "firmware/community-r3.0/ttl_panel.html",
        2_435,
        "c26b4dd9870d0895595ab7e68bb33511e5129da3a5be2ff59638995411920963",
    ),
    "controller": (
        "firmware/community-r3.0/ttl_controller.js",
        8_338,
        "0bc3ff6e52202a8aa8b0e2e15423ba7a089604ba5f614c451b104a6ea663e5b5",
    ),
    "styles": (
        "firmware/community-r3.0/ttl_styles.css",
        1_307,
        "282023dab91374aa05ba4edd8a8f6d99a328bbe4eab57834428c236d7e30a667",
    ),
}

# R3.0 assets are derived, not copied from standalone full-file sources.
CUSTOM_FILES: dict[str, tuple[str, int, str]] = {}

# Independently derived output bytes from the exact reviewed golden.
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (
        21_381,
        "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2",
    ),
    "www\\html\\adminApp.html": (
        4_766,
        "bccb2733333106f5c0becebf340e8d0cd09196e9a31657e2e2eef967b7434882",
    ),
    "www\\index.html": (
        26_636,
        "2d39ad6f7f0ac055ad78b2a8bba0bb8b4a08b9cf6959ff9354498a1053505e1f",
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
    ENTRY_PATH: (
        15_529,
        "1cc0d54a68ea0f423ae88e7cbff3d700adf978ce1ad13c19f6c7c1c144ca69b2",
        "derived from exact R2.9 HTML plus byte-pinned TTL panel",
    ),
    APP_PATH: (
        73_163,
        "872a28e96ccab80d61aecd56ec3e15f4b2e3330eef4ad97bff3585a07f53d154",
        "derived from exact R2.9 controller plus byte-pinned TTL controller",
    ),
    CSS_PATH: (
        9_232,
        "84eaad60ed768f9a8daf1bee296bb9e9a6971214f494b3636f25cd331c023576",
        "derived from exact R2.9 CSS plus byte-pinned TTL styles",
    ),
}


class CommunityR30Error(Exception):
    pass


def _load_exact(root: Path, source: str, size: int, digest: str) -> bytes:
    try:
        data = (root / source).read_bytes()
    except OSError as exc:
        raise CommunityR30Error(f"could not read exact Community R3.0 fragment {source}") from exc
    try:
        return r2.require_exact(data, size, digest, source)
    except r2.CommunityR2Error as exc:
        raise CommunityR30Error(str(exc)) from exc


def _replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    count = data.count(old)
    if count != 1:
        raise CommunityR30Error(f"{label} anchor count is {count}, expected 1")
    return data.replace(old, new, 1)


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.2.9-community-r2", b"0.3.0-community-r2"),
        (b"0.2.9", b"0.3.0"),
        (b"R2.9", b"R3.0"),
        (b"r29", b"r30"),
        (b"R29", b"R30"),
        (b"JS29", b"JS30"),
        (b"LIVE29", b"LIVE30"),
        (b"S29", b"S30"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR30Error(f"{label} has no R2.9 revision anchor")
    return data


def _derive_html(base: bytes, panel: bytes) -> bytes:
    data = _revise(base, "Community entry")
    data = _replace_once(
        data,
        b'        <button type="button" data-page="modem">Modem</button>\n',
        b'        <button type="button" data-page="modem">Modem</button>\n'
        b'        <button type="button" data-page="ttl">TTL</button>\n',
        "primary TTL navigation",
    )
    data = _replace_once(
        data,
        b'          <button type="button" data-page="modem" class="secondary">Radio and signal</button>\n',
        b'          <button type="button" data-page="modem" class="secondary">Radio and signal</button>\n'
        b'          <button type="button" data-page="ttl" class="secondary">TTL control</button>\n',
        "dashboard TTL action",
    )
    data = _replace_once(
        data,
        b"Messages, device health and radio details start loading as soon as sign-in completes.",
        b"Messages, device health, radio details and TTL state start loading as soon as sign-in completes.",
        "dashboard immediate-load copy",
    )
    data = _replace_once(
        data,
        b"    </main>\n\n    <footer>",
        panel + b"\n    </main>\n\n    <footer>",
        "TTL panel insertion",
    )
    return data


def _derive_css(base: bytes, styles: bytes) -> bytes:
    if not base.endswith(b"\n"):
        base += b"\n"
    return base + styles + (b"" if styles.endswith(b"\n") else b"\n")


def _derive_js(base: bytes, controller: bytes) -> bytes:
    data = _revise(base, "Community controller")
    data = _replace_once(
        data,
        b"function syncRouterControls(){var busy=routerOwner!==null,",
        b"function syncRouterControls(){syncTtlControls();var busy=routerOwner!==null,",
        "TTL control synchronization",
    )
    data = _replace_once(
        data,
        b"function modelUrl(name){if(ENDPOINTS.indexOf(name)<0)throw new Error('Unsupported router model.');",
        b"function modelUrl(name){if(ENDPOINTS.indexOf(name)<0&&name!=='diagnostic')throw new Error('Unsupported router model.');",
        "shared diagnostic model allowlist",
    )
    data = _replace_once(
        data,
        b"function validPage(name){return /^(?:dashboard|messages|diagnostics|modem)$/.test(String(name||''))}",
        b"function validPage(name){return /^(?:dashboard|messages|diagnostics|modem|ttl)$/.test(String(name||''))}",
        "TTL page routing",
    )
    data = _replace_once(
        data,
        b"  function updateLiveControl()",
        controller + b"\n\n  function updateLiveControl()",
        "TTL controller insertion",
    )
    data = _replace_once(
        data,
        b"function universalDueAt(){var snapshotDue=nextSnapshotAt||Date.now(),messagesDue=nextMessagesAt||Date.now();return Math.min(snapshotDue,messagesDue)}",
        b"function universalDueAt(){var snapshotDue=nextSnapshotAt||Date.now(),messagesDue=nextMessagesAt||Date.now(),ttlDue=ttlRuntime.nextAt||Date.now();return Math.min(snapshotDue,messagesDue,ttlDue)}",
        "universal TTL due time",
    )
    data = _replace_once(
        data,
        b"else if(activePage==='modem')status('modemStatus',text,true)",
        b"else if(activePage==='modem')status('modemStatus',text,true);else if(activePage==='ttl')status('ttlStatus',text,true)",
        "TTL deferred status",
    )
    data = _replace_once(
        data,
        b"messageDue=now>=(nextMessagesAt||0),snapshotDue=now>=(nextSnapshotAt||0),messageAllowed=!mutationLocked;liveLog(id,'variables',{activePage:activePage,refreshScope:'all-safe-data',visible:visible,routerOwner:routerOwner,mutationBusy:mutationBusy,mutationLocked:mutationLocked,messageDue:messageDue,snapshotDue:snapshotDue,nextMessagesAt:nextMessagesAt,nextSnapshotAt:nextSnapshotAt,automaticRetryCeiling:0});",
        b"messageDue=now>=(nextMessagesAt||0),snapshotDue=now>=(nextSnapshotAt||0),ttlDue=now>=(ttlRuntime.nextAt||0),messageAllowed=!mutationLocked;liveLog(id,'variables',{activePage:activePage,refreshScope:'all-safe-data',visible:visible,routerOwner:routerOwner,mutationBusy:mutationBusy,mutationLocked:mutationLocked,messageDue:messageDue,snapshotDue:snapshotDue,ttlDue:ttlDue,nextMessagesAt:nextMessagesAt,nextSnapshotAt:nextSnapshotAt,nextTtlAt:ttlRuntime.nextAt,automaticRetryCeiling:0});",
        "TTL live variables",
    )
    data = _replace_once(
        data,
        b"liveCondition(id,'universal_refresh_due',true,messageDue||snapshotDue,messageDue||snapshotDue);",
        b"liveCondition(id,'universal_refresh_due',true,messageDue||snapshotDue||ttlDue,messageDue||snapshotDue||ttlDue);",
        "TTL universal due condition",
    )
    data = _replace_once(
        data,
        b"if(!dispatchCount)liveLog(id,'terminal',{terminal_reason:'UNIVERSAL_REFRESH_NOT_DUE',requestCount:0,retryCount:0});return flow.finally(function(){scheduleLive()})",
        b"if(ttlDue){dispatchCount++;ttlRuntime.nextAt=now+SNAPSHOT_POLL_MS;liveLog(id,'dispatch',{kind:'ttl-state',getCeiling:1});flow=flow.then(function(){return readTtlState('live:'+id)}).catch(function(error){logFailure(error,'Universal TTL refresh failed.');return null})}if(!dispatchCount)liveLog(id,'terminal',{terminal_reason:'UNIVERSAL_REFRESH_NOT_DUE',requestCount:0,retryCount:0});return flow.finally(function(){scheduleLive()})",
        "TTL live dispatch",
    )
    data = _replace_once(
        data,
        b"return loadMessagesPreview((trigger||'manual')+':'+id)}).finally(function(){scheduleLive()})",
        b"return loadMessagesPreview((trigger||'manual')+':'+id)}).then(function(){return readTtlState((trigger||'manual')+':'+id).catch(function(error){logFailure(error,'Universal TTL refresh failed.');return null})}).finally(function(){scheduleLive()})",
        "manual universal TTL refresh",
    )
    data = _replace_once(
        data,
        b"if(liveEnabled){nextMessagesAt=0;nextSnapshotAt=0;scheduleLive(0)}else stopLive()",
        b"if(liveEnabled){nextMessagesAt=0;nextSnapshotAt=0;ttlRuntime.nextAt=0;scheduleLive(0)}else stopLive()",
        "TTL live preference reset",
    )
    data = _replace_once(
        data,
        b"first.then(second).catch(function(error){showError('dashboardStatus',error,'Automatic first load did not complete.');return null}).finally(function(){bootstrapBusy=false;nextSnapshotAt=Date.now()+SNAPSHOT_POLL_MS;nextMessagesAt=Date.now()+MESSAGES_POLL_MS;",
        b"first.then(second).then(function(){return readTtlState('bootstrap')}).catch(function(error){showError('dashboardStatus',error,'Automatic first load did not complete.');return null}).finally(function(){bootstrapBusy=false;nextSnapshotAt=Date.now()+SNAPSHOT_POLL_MS;nextMessagesAt=Date.now()+MESSAGES_POLL_MS;ttlRuntime.nextAt=Date.now()+SNAPSHOT_POLL_MS;",
        "TTL authenticated bootstrap",
    )
    data = _replace_once(
        data,
        b"nextSnapshotAt=0;nextMessagesAt=0;lastMessagesAt=null;node('app').hidden=true;",
        b"nextSnapshotAt=0;nextMessagesAt=0;ttlRuntime.current=null;ttlRuntime.locked=false;ttlRuntime.nextAt=0;node('ttlCurrent').textContent='Loading...';node('ttlCurrentDetail').textContent='No TTL state has been read yet.';status('ttlStatus','Current state will load automatically after sign-in and refresh every 30 seconds.');lastMessagesAt=null;node('app').hidden=true;",
        "TTL logout reset",
    )
    data = _replace_once(
        data,
        b"node('diagnosticsRefresh').addEventListener('click',function(){refreshAll('manual-diagnostics')});node('modemRefresh').addEventListener('click',function(){refreshAll('manual-modem')});",
        b"node('diagnosticsRefresh').addEventListener('click',function(){refreshAll('manual-diagnostics')});node('modemRefresh').addEventListener('click',function(){refreshAll('manual-modem')});node('ttlRefresh').addEventListener('click',function(){readTtlState('manual-ttl').catch(function(){return null})});var ttlButtons=w.document.querySelectorAll('button[data-ttl-value]');for(var ttlIndex=0;ttlIndex<ttlButtons.length;ttlIndex++)ttlButtons[ttlIndex].addEventListener('click',function(){setTtl(this.getAttribute('data-ttl-value'))});node('ttlCustomApply').addEventListener('click',function(){setTtl(node('ttlCustom').value)});node('ttlCustom').addEventListener('keydown',function(event){if(event.key==='Enter'){event.preventDefault();setTtl(this.value)}});",
        "TTL event bindings",
    )
    data = _replace_once(
        data,
        b"if(session&&liveEnabled&&visible){nextMessagesAt=0;nextSnapshotAt=0;scheduleLive(0)}",
        b"if(session&&liveEnabled&&visible){nextMessagesAt=0;nextSnapshotAt=0;ttlRuntime.nextAt=0;scheduleLive(0)}",
        "TTL visibility refresh",
    )
    data = _replace_once(
        data,
        b"setLiveEnabled:setLiveEnabled};",
        b"setLiveEnabled:setLiveEnabled,ttlValueInfo:ttlValueInfo,ttlState:ttlState,ttlXml:ttlXml,readTtlState:readTtlState,setTtl:setTtl,ttlRuntime:ttlRuntime};",
        "TTL public test surface",
    )
    return data


def derive_assets(root: Path) -> dict[str, bytes]:
    """Derive the three complete R3.0 assets from exact pinned local sources."""

    parent_assets = {
        target: _load_exact(root, source, size, digest)
        for target, (source, size, digest) in r29.CUSTOM_FILES.items()
    }
    fragments = {
        name: _load_exact(root, source, size, digest)
        for name, (source, size, digest) in FRAGMENT_FILES.items()
    }
    return {
        ENTRY_PATH: _derive_html(parent_assets[r29.ENTRY_PATH], fragments["panel"]),
        APP_PATH: _derive_js(parent_assets[r29.APP_PATH], fragments["controller"]),
        CSS_PATH: _derive_css(parent_assets[r29.CSS_PATH], fragments["styles"]),
    }


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        parent_replacements, parent_additions, removals = r29.build_patch_set(records, root)
    except r29.CommunityR29Error as exc:
        raise CommunityR30Error(str(exc)) from exc

    replacements = dict(parent_replacements)
    replacements["www\\index.html"] = _revise(
        replacements["www\\index.html"], "canonical Community link"
    )
    replacements["www\\html\\adminApp.html"] = _revise(
        replacements["www\\html\\adminApp.html"], "shared Community header"
    )
    additions = derive_assets(root)
    for parent_path, parent_value in parent_additions.items():
        expected = _load_exact(root, *r29.CUSTOM_FILES[parent_path])
        if parent_value != expected:
            raise CommunityR30Error(f"exact R2.9 parent asset drifted: {parent_path}")
    removals = set(removals)

    if set(replacements) != set(r29.OUTPUT_RECORDS):
        raise CommunityR30Error("R3.0 replacement path set changed")
    if set(additions) != {ENTRY_PATH, APP_PATH, CSS_PATH}:
        raise CommunityR30Error("R3.0 extension asset set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR30Error("R3.0 removed-locale set changed")
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR30Error("R3.0 marker is absent")
    if additions[ENTRY_PATH].count(b'data-page="ttl"') != 2:
        raise CommunityR30Error("R3.0 TTL navigation/action count changed")
    if additions[ENTRY_PATH].count(b'id="page-ttl"') != 1:
        raise CommunityR30Error("R3.0 TTL panel count changed")
    if additions[APP_PATH].count(b"command>ttl") != 1:
        raise CommunityR30Error("R3.0 TTL command contract changed")
    if b"setInterval" in additions[APP_PATH] or b"RestoreFw" in additions[APP_PATH]:
        raise CommunityR30Error("R3.0 contains interval polling or firmware control")
    if b'href="/r30.html"' not in replacements["www\\index.html"]:
        raise CommunityR30Error("canonical login does not link R3.0")
    if b'href="/r30.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR30Error("shared header does not link R3.0")
    return replacements, additions, removals


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR30Error("R3.0 derived output records are not pinned; retained build is disabled")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR30Error("R3.0 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR30Error("R3.0 addition provenance gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR30Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR30Error(str(exc)) from exc
    return replacements, additions, removals
