#!/usr/bin/env python3
"""Deterministic Community R3.9 modular TTL extension from exact R3.8.

The accepted R2.9 product surface is retained.  R3.9 replaces only the locked
TTL comparator with a separately loaded controller and a narrow bridge in the
main controller.  The UI describes ``diagnostic.arg`` as the last requested
value; it never treats readback as packet-path proof.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r38 as r38


PROFILE = "0.3.9-community-r2"
MARKER = b"MF885 Community R3.9 extension 0.3.9-community-r2"
REMOVED_RECORDS = r38.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r38.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r39.html"
APP_PATH = "www\\js\\r39app.js"
CSS_PATH = "www\\css\\r39ui.css"
TTL_APP_PATH = "www\\js\\r39ttl.js"
TTL_CSS_PATH = "www\\css\\r39ttl.css"

FRAGMENT_FILES: dict[str, tuple[str, int, str]] = {
    "ttl_panel": (
        "firmware/community-r3.9/ttl_panel.html",
        3_188,
        "27c96b79da5b563277df32570927349fb654529d15ed491a23ccd11abab3e69b",
    ),
    "ttl_controller": (
        "firmware/community-r3.9/ttl_controller.js",
        15_547,
        "2a4ebc32fec9ad5e750865fb45a0e556b4b4ca0ff3201a7687cfc13f80d6e829",
    ),
    "ttl_styles": (
        "firmware/community-r3.9/ttl_styles.css",
        959,
        "7bb15e0f01e9c971f6f49c0a086772a60da72d427e668df0036099f84db3f3f7",
    ),
}

OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "303b75b097c6cdd5c4cbebd7c966e83c59c433968e030f9de4d084a8efadb6e4"),
    "www\\index.html": (26_636, "6118c41412445573b770ece4d50a6802074a72caba513781a8942f8d6af0be3f"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    ENTRY_PATH: (16_497, "f7c0bc4633bb7e99d94ead2ce262c535c735f7d885ae4af483aa7258c0c15ac6", "R3.8 cumulative UI with the R3.9 TTL request panel"),
    APP_PATH: (64_751, "90e474f41b968a64bd54a82c244197b7bf053a16c5901f113b7a79fed8e7fe56", "R3.8 controller with a narrow modular TTL transport/scheduler bridge"),
    CSS_PATH: (7_925, "50b977ba920c226a4a9c03895c47d1457439adba0eefd169c20e2cca21244578", "byte-identical reviewed Community CSS"),
    TTL_APP_PATH: (15_547, "2a4ebc32fec9ad5e750865fb45a0e556b4b4ca0ff3201a7687cfc13f80d6e829", "standalone fail-closed TTL requested-value controller"),
    TTL_CSS_PATH: (959, "7bb15e0f01e9c971f6f49c0a086772a60da72d427e668df0036099f84db3f3f7", "standalone responsive TTL styles"),
}


class CommunityR39Error(Exception):
    pass


def _replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    count = data.count(old)
    if count != 1:
        raise CommunityR39Error(f"{label} anchor count is {count}, expected 1")
    return data.replace(old, new, 1)


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.3.8-community-r2", b"0.3.9-community-r2"),
        (b"0.3.8", b"0.3.9"),
        (b"R3.8", b"R3.9"),
        (b"r38", b"r39"),
        (b"R38", b"R39"),
        (b"JS38", b"JS39"),
        (b"LIVE38", b"LIVE39"),
        (b"S38", b"S39"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR39Error(f"{label} has no R3.8 revision anchor")
    return data


def _load_exact(root: Path, key: str) -> bytes:
    source, size, digest = FRAGMENT_FILES[key]
    try:
        value = (root / source).read_bytes()
    except OSError as exc:
        raise CommunityR39Error(f"could not read exact R3.9 fragment {source}") from exc
    try:
        return r2.require_exact(value, size, digest, source)
    except r2.CommunityR2Error as exc:
        raise CommunityR39Error(str(exc)) from exc


def _patch_core(app: bytes) -> bytes:
    data = app
    data = _replace_once(
        data,
        b"function syncRouterControls(){var busy=routerOwner!==null,",
        b"function syncRouterControls(){var ttlExtension=w.MF885CommunityR39TTL;if(ttlExtension&&typeof ttlExtension.syncControls==='function')ttlExtension.syncControls();var busy=routerOwner!==null,",
        "modular TTL control synchronization",
    )
    data = _replace_once(
        data,
        b"function modelUrl(name){if(ENDPOINTS.indexOf(name)<0)throw new Error('Unsupported router model.');",
        b"function modelUrl(name){if(ENDPOINTS.indexOf(name)<0&&name!=='diagnostic')throw new Error('Unsupported router model.');",
        "diagnostic read allowlist",
    )
    data = _replace_once(
        data,
        b"  function updateLiveControl()",
        b"  function ttlExtension(){return w.MF885CommunityR39TTL||null}\n  function ttlRead(trigger){var value=ttlExtension();return value?value.read(trigger):Promise.resolve(null)}\n  function ttlDue(now){var value=ttlExtension();return !!value&&value.due(now)}\n  function ttlDueAt(){var value=ttlExtension();return value?value.dueAt():Number.POSITIVE_INFINITY}\n  function ttlResetDue(){var value=ttlExtension();if(value)value.resetDue()}\n\n  function updateLiveControl()",
        "modular TTL scheduler bridge",
    )
    data = _replace_once(
        data,
        b"function universalDueAt(){var snapshotDue=nextSnapshotAt||Date.now(),messagesDue=nextMessagesAt||Date.now();return Math.min(snapshotDue,messagesDue)}",
        b"function universalDueAt(){var snapshotDue=nextSnapshotAt||Date.now(),messagesDue=nextMessagesAt||Date.now();return Math.min(snapshotDue,messagesDue,ttlDueAt())}",
        "universal TTL due time",
    )
    data = _replace_once(
        data,
        b"messageDue=now>=(nextMessagesAt||0),snapshotDue=now>=(nextSnapshotAt||0),messageAllowed=!mutationLocked;liveLog(id,'variables',{activePage:activePage,refreshScope:'all-safe-data',visible:visible,routerOwner:routerOwner,mutationBusy:mutationBusy,mutationLocked:mutationLocked,messageDue:messageDue,snapshotDue:snapshotDue,nextMessagesAt:nextMessagesAt,nextSnapshotAt:nextSnapshotAt,automaticRetryCeiling:0});",
        b"messageDue=now>=(nextMessagesAt||0),snapshotDue=now>=(nextSnapshotAt||0),ttlReadDue=ttlDue(now),messageAllowed=!mutationLocked;liveLog(id,'variables',{activePage:activePage,refreshScope:'all-safe-data-including-ttl-readback',visible:visible,routerOwner:routerOwner,mutationBusy:mutationBusy,mutationLocked:mutationLocked,messageDue:messageDue,snapshotDue:snapshotDue,ttlReadDue:ttlReadDue,nextMessagesAt:nextMessagesAt,nextSnapshotAt:nextSnapshotAt,nextTtlAt:ttlDueAt(),automaticRetryCeiling:0});",
        "universal TTL variables",
    )
    data = _replace_once(
        data,
        b"liveCondition(id,'universal_refresh_due',true,messageDue||snapshotDue,messageDue||snapshotDue);",
        b"liveCondition(id,'universal_refresh_due',true,messageDue||snapshotDue||ttlReadDue,messageDue||snapshotDue||ttlReadDue);",
        "universal TTL due condition",
    )
    data = _replace_once(
        data,
        b"if(!dispatchCount)liveLog(id,'terminal',{terminal_reason:'UNIVERSAL_REFRESH_NOT_DUE',requestCount:0,retryCount:0});return flow.finally(function(){scheduleLive()})",
        b"if(ttlReadDue){dispatchCount++;liveLog(id,'dispatch',{kind:'ttl-request-readback',getCeiling:1,postCeiling:0});flow=flow.then(function(){return ttlRead('live:'+id)}).catch(function(error){logFailure(error,'Universal TTL read failed.');return null})}if(!dispatchCount)liveLog(id,'terminal',{terminal_reason:'UNIVERSAL_REFRESH_NOT_DUE',requestCount:0,retryCount:0});return flow.finally(function(){scheduleLive()})",
        "universal TTL dispatch",
    )
    data = _replace_once(
        data,
        b"return loadMessagesPreview((trigger||'manual')+':'+id)}).finally(function(){scheduleLive()})",
        b"return loadMessagesPreview((trigger||'manual')+':'+id)}).then(function(){return ttlRead((trigger||'manual')+':ttl:'+id).catch(function(error){logFailure(error,'Universal TTL read failed.');return null})}).finally(function(){scheduleLive()})",
        "manual universal TTL refresh",
    )
    data = _replace_once(
        data,
        b"if(liveEnabled){nextMessagesAt=0;nextSnapshotAt=0;scheduleLive(0)}else stopLive()",
        b"if(liveEnabled){nextMessagesAt=0;nextSnapshotAt=0;ttlResetDue();scheduleLive(0)}else stopLive()",
        "TTL live preference reset",
    )
    data = _replace_once(
        data,
        b"first.then(second).catch(function(error){showError('dashboardStatus',error,'Automatic first load did not complete.');return null}).finally(function(){",
        b"first.then(second).then(function(){return ttlRead('bootstrap')}).catch(function(error){showError('dashboardStatus',error,'Automatic first load did not complete.');return null}).finally(function(){",
        "TTL authenticated bootstrap",
    )
    data = _replace_once(
        data,
        b"function finishLocalLogout(message,error){cancelCurrent();session=null;stopLive();",
        b"function finishLocalLogout(message,error){cancelCurrent();session=null;stopLive();var ttl=ttlExtension();if(ttl)ttl.logout();",
        "TTL logout reset",
    )
    data = _replace_once(
        data,
        b"if(session&&liveEnabled&&visible){nextMessagesAt=0;nextSnapshotAt=0;scheduleLive(0)}",
        b"if(session&&liveEnabled&&visible){nextMessagesAt=0;nextSnapshotAt=0;ttlResetDue();scheduleLive(0)}",
        "TTL visibility refresh",
    )
    data = _replace_once(
        data,
        b"setLiveEnabled:setLiveEnabled};",
        b"setLiveEnabled:setLiveEnabled,ttlBridge:{status:status,showError:showError,fault:fault,begin:beginRouterOperation,end:endRouterOperation,sessionPresent:function(){return session!==null},routerBusy:function(){return routerOwner!==null},get:function(owner){return modelGet('diagnostic',owner)},post:function(body,owner){return request({method:'POST',url:'/xml_action.cgi?method=set&module=duster&file=diagnostic',authorization:nextHeader('POST'),body:body,owner:owner})},xmlDeclaration:XML_DECLARATION}};",
        "narrow TTL transport bridge",
    )
    return data


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        replacements, parent_additions, removals = r38._derive_unpinned_patch_set(
            records, root
        )
    except r38.CommunityR38Error as exc:
        raise CommunityR39Error(str(exc)) from exc

    replacements = {
        path: _revise(value, f"R3.9 replacement {path}")
        if path in {"www\\index.html", "www\\html\\adminApp.html"}
        else value
        for path, value in replacements.items()
    }
    try:
        parent_entry = parent_additions[r38.ENTRY_PATH]
        parent_app = parent_additions[r38.APP_PATH]
        parent_css = parent_additions[r38.CSS_PATH]
        old_panel = (root / r38.FRAGMENT_FILE).read_bytes()
    except (KeyError, OSError) as exc:
        raise CommunityR39Error("R3.8 assets are incomplete") from exc

    entry = _revise(parent_entry, "R3.9 entry")
    entry = _replace_once(
        entry,
        _revise(old_panel, "R3.9 inherited panel anchor"),
        _load_exact(root, "ttl_panel"),
        "R3.9 TTL panel",
    )
    entry = _replace_once(
        entry,
        b"TTL remains visibly unavailable while its native callback is isolated. ",
        b"The last TTL request also loads automatically and is labelled separately from packet proof. ",
        "R3.9 dashboard TTL summary",
    )
    entry = _replace_once(
        entry,
        b'  <link rel="stylesheet" href="css/r39ui.css">\n',
        b'  <link rel="stylesheet" href="css/r39ui.css">\n  <link rel="stylesheet" href="css/r39ttl.css">\n',
        "R3.9 TTL stylesheet",
    )
    entry = _replace_once(
        entry,
        b'  <script defer src="js/r39app.js"></script>\n',
        b'  <script defer src="js/r39app.js"></script>\n  <script defer src="js/r39ttl.js"></script>\n',
        "R3.9 TTL controller",
    )
    entry = _replace_once(
        entry,
        b"if(!window.MF885CommunityR39){",
        b"if(!window.MF885CommunityR39||!window.MF885CommunityR39TTL){",
        "R3.9 dual-module boot check",
    )
    entry = _replace_once(
        entry,
        b"r39app.js did not expose its runtime",
        b"r39app.js or r39ttl.js did not expose its runtime",
        "R3.9 boot failure detail",
    )
    additions = {
        ENTRY_PATH: entry,
        APP_PATH: _patch_core(_revise(parent_app, "R3.9 controller")),
        CSS_PATH: parent_css,
        TTL_APP_PATH: _load_exact(root, "ttl_controller"),
        TTL_CSS_PATH: _load_exact(root, "ttl_styles"),
    }
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR39Error("R3.9 marker is absent")
    if b'href="/r39.html"' not in replacements["www\\index.html"]:
        raise CommunityR39Error("canonical login does not link R3.9")
    if b'href="/r39.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR39Error("shared header does not link R3.9")
    if entry.count(b'id="page-ttl"') != 1:
        raise CommunityR39Error("R3.9 TTL page count changed")
    if entry.count(b'src="js/r39ttl.js"') != 1 or entry.count(b'href="css/r39ttl.css"') != 1:
        raise CommunityR39Error("R3.9 modular asset references changed")
    ttl_app = additions[TTL_APP_PATH]
    if ttl_app.count(b"method:'POST'") != 0:
        raise CommunityR39Error("R3.9 TTL module bypasses its narrow POST bridge")
    if ttl_app.count(b"core.ttlBridge.post(body,owner)") != 1:
        raise CommunityR39Error("R3.9 TTL module POST count changed")
    if (
        ttl_app.count(b"<command>ttl</command><arg>") != 1
        or b"</arg><output" in ttl_app
    ):
        raise CommunityR39Error("R3.9 command/arg-only request template changed")
    if b"setInterval" in joined or b"SystemChannelName" in joined or b"debugmodeon" in joined:
        raise CommunityR39Error("R3.9 browser assets contain a forbidden live path")
    return replacements, additions, set(removals)


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR39Error("R3.9 output records are not pinned")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR39Error("R3.9 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR39Error("R3.9 addition record gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR39Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR39Error(str(exc)) from exc
    return replacements, additions, removals


__all__ = [
    "PROFILE",
    "MARKER",
    "REMOVED_RECORDS",
    "REMOVED_ARCHIVE_BYTES",
    "ENTRY_PATH",
    "APP_PATH",
    "CSS_PATH",
    "TTL_APP_PATH",
    "TTL_CSS_PATH",
    "OUTPUT_RECORDS",
    "ADDITION_OUTPUT_RECORDS",
    "CommunityR39Error",
    "build_patch_set",
]
