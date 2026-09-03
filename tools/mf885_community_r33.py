#!/usr/bin/env python3
"""Deterministic Community R3.3 isolated TTL-transport repair.

R3.3 remains a cumulative extension of R3.2.  It keeps both Engineering-mode
implementations unchanged, reads TTL through a one-field stock response bridge,
and routes TTL writes through a separate diagnostic-only XML template.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r32 as r32


PROFILE = "0.3.3-community-r2"
MARKER = b"MF885 Community R3.3 extension 0.3.3-community-r2"
REMOVED_RECORDS = r32.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r32.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r33.html"
APP_PATH = "www\\js\\r33app.js"
CSS_PATH = "www\\css\\r33ui.css"
TTL_SET_PATH = "www\\xmldata\\ttl_set.xml"
DIAGNOSTIC_PATH = "www\\xmldata\\diagnostic.xml"

CUSTOM_FILES: dict[str, tuple[str, int, str]] = {}
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "181195c8c1b76b412e188779bfa219179d9e0aafd59cd8962e31441ece987de6"),
    "www\\index.html": (26_636, "c6158c61388015718962449a6b2d34906183b390fd7ab62b77e1f3d6b92097f7"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
    DIAGNOSTIC_PATH: (148, "a3e8cb4db652dbd9607f4f360a0f82afa258b242c7e2c6cd292d268ffa246c46"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    ENTRY_PATH: (15_529, "4c9de90b24b22a5ec0f4ef2dcdde4a9aad2b4e5779cbe6938242d04061a51552", "derived byte-exact from reviewed R3.2 HTML"),
    APP_PATH: (73_226, "cdf9b90089e9b2440cee6e431997c8605bd970df97e1e43d087d370dad2bb4d3", "derived from reviewed R3.2 controller with isolated TTL transport"),
    CSS_PATH: (9_232, "84eaad60ed768f9a8daf1bee296bb9e9a6971214f494b3636f25cd331c023576", "byte-identical reviewed R3.2 CSS under cache-safe R3.3 path"),
    TTL_SET_PATH: (133, "5305b719dfcc22d5984048d1bd875086bc2c53cfd81a67da84c6c533c9e19e4b", "reviewed diagnostic-only TTL set template"),
}

DIAGNOSTIC_READ_TEMPLATE = (
    b'<?xml version="1.0" encoding="US-ASCII"?>\r\n'
    b'<RGW>\r\n'
    b'  <diagnostic />\r\n'
    b'  <SystemChannelName>\r\n'
    b'    <PRODUCT_CHANNEL />\r\n'
    b'  </SystemChannelName>\r\n'
    b'</RGW>\r\n'
)


class CommunityR33Error(Exception):
    pass


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.3.2-community-r2", b"0.3.3-community-r2"),
        (b"0.3.2", b"0.3.3"),
        (b"R3.2", b"R3.3"),
        (b"r32", b"r33"),
        (b"R32", b"R33"),
        (b"JS32", b"JS33"),
        (b"LIVE32", b"LIVE33"),
        (b"S32", b"S33"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR33Error(f"{label} has no R3.2 revision anchor")
    return data


def _replace_block(data: bytes, start: bytes, end: bytes, replacement: bytes, label: str) -> bytes:
    if data.count(start) != 1 or data.count(end) != 1:
        raise CommunityR33Error(f"{label} block anchors are not unique")
    left = data.index(start)
    right = data.index(end, left)
    if left >= right:
        raise CommunityR33Error(f"{label} block anchors are reversed")
    return data[:left] + replacement + data[right:]


def _rewrite_ttl_transport(data: bytes) -> bytes:
    ttl_state = b"""  function ttlState(doc){
    var id=doc&&doc.mfRequestId||nextTtlId(),root=doc&&doc.documentElement,triggers=children(root,'diagnostic'),trigger=triggers.length===1?triggers[0]:null,models=children(root,'SystemChannelName'),model=models.length===1?models[0]:null,value=model?one(model,'PRODUCT_CHANNEL'):null,parsed=ttlValueInfo(value),triggerCount=triggers.length,modelCount=models.length,passed=triggerCount===1&&modelCount===1&&parsed.accepted;
    ttlLog(id,'state variables',{triggerModel:'diagnostic',triggerModelCount:triggerCount,readModel:'SystemChannelName',readModelCount:modelCount,readField:'PRODUCT_CHANNEL',value:value,valueOff:parsed.off,valueCanonicalDecimal:parsed.canonical,valueNumeric:parsed.numeric,valueInRange:parsed.inRange,valueAccepted:parsed.accepted,acceptedMinimum:1,acceptedMaximum:255,stockRestoreExpected:'release',automaticRetryCeiling:0});
    ttlCondition(id,'diagnostic_trigger_model_count',1,triggerCount,triggerCount===1);ttlCondition(id,'system_channel_model_count',1,modelCount,modelCount===1);ttlCondition(id,'product_channel_is_off_or_canonical_decimal',true,parsed.off||parsed.canonical,parsed.off||parsed.canonical);ttlCondition(id,'product_channel_numeric_in_range_or_off','off|1..255',value,parsed.accepted);
    if(!passed)throw fault('E_TTL_RESPONSE','The router returned an invalid TTL bridge state.',id,{triggerModelCount:triggerCount,readModelCount:modelCount,value:value});
    return {value:value,output:'SYSTEM_CHANNEL_BRIDGE',requestId:id};
  }
"""
    data = _replace_block(
        data,
        b"  function ttlState(doc){",
        b"  function ttlXml(value){",
        ttl_state,
        "TTL response parser",
    )
    old_xml = b"  function ttlXml(value){var parsed=ttlValueInfo(value);if(!parsed.accepted)throw fault('E_TTL_VALUE','TTL must be Off or an integer from 1 to 255.');return xmlDocument('<RGW><diagnostic><command>ttl</command><arg>'+parsed.raw+'</arg><output></output></diagnostic></RGW>')}\n"
    new_xml = b"  function ttlXml(value){var parsed=ttlValueInfo(value);if(!parsed.accepted)throw fault('E_TTL_VALUE','TTL must be Off or an integer from 1 to 255.');return xmlDocument('<RGW><diagnostic><command>ttl</command><arg>'+parsed.raw+'</arg></diagnostic></RGW>')}\n"
    if data.count(old_xml) != 1:
        raise CommunityR33Error("TTL request XML anchor is not unique")
    data = data.replace(old_xml, new_xml)
    old_log = b"var id=nextTtlId();ttlLog(id,'read variables',{trigger:trigger||'manual',owner:owner,model:'diagnostic',method:'GET',automaticRetryCeiling:0});"
    new_log = b"var id=nextTtlId();ttlLog(id,'read variables',{trigger:trigger||'manual',owner:owner,template:'diagnostic',triggerModel:'diagnostic',readModel:'SystemChannelName',readField:'PRODUCT_CHANNEL',stockRestoreExpected:'release',method:'GET',automaticRetryCeiling:0});"
    if data.count(old_log) != 1:
        raise CommunityR33Error("TTL read log anchor is not unique")
    data = data.replace(old_log, new_log)
    old_post = b"url:'/xml_action.cgi?method=set&module=duster&file=diagnostic'"
    new_post = b"url:'/xml_action.cgi?method=set&module=duster&file=ttl_set'"
    if data.count(old_post) != 1:
        raise CommunityR33Error("TTL POST route anchor is not unique")
    data = data.replace(old_post, new_post)
    if data.count(b"call i32"):
        raise CommunityR33Error("native source leaked into browser controller")
    return data


def derive_assets(root: Path) -> dict[str, bytes]:
    """Derive the complete R3.3 UI and its isolated TTL-set template."""

    parent = r32.derive_assets(root)
    app = _rewrite_ttl_transport(_revise(parent[r32.APP_PATH], f"R3.3 asset {APP_PATH}"))
    try:
        ttl_set = (root / "firmware" / "community-r3.3" / "ttl_set.xml").read_bytes()
    except OSError as exc:
        raise CommunityR33Error("R3.3 TTL-set template is unavailable") from exc
    return {
        ENTRY_PATH: _revise(parent[r32.ENTRY_PATH], f"R3.3 asset {ENTRY_PATH}"),
        APP_PATH: app,
        CSS_PATH: parent[r32.CSS_PATH],
        TTL_SET_PATH: ttl_set.replace(b"\n", b"\r\n"),
    }


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        parent_replacements, _parent_additions, removals = r32.build_patch_set(records, root)
    except r32.CommunityR32Error as exc:
        raise CommunityR33Error(str(exc)) from exc

    replacements = dict(parent_replacements)
    for path in ("www\\index.html", "www\\html\\adminApp.html"):
        replacements[path] = _revise(replacements[path], f"R3.3 replacement {path}")
    stock_diagnostic = records.get(DIAGNOSTIC_PATH)
    if stock_diagnostic is None:
        raise CommunityR33Error("exact stock diagnostic template is absent")
    try:
        r2.require_exact(
            stock_diagnostic,
            172,
            "37db50389df6076c533355db173dc7ea9fcc16661ecb9d1608e7300278e0a3b7",
            "stock diagnostic template",
        )
    except r2.CommunityR2Error as exc:
        raise CommunityR33Error(str(exc)) from exc
    replacements[DIAGNOSTIC_PATH] = DIAGNOSTIC_READ_TEMPLATE

    additions = derive_assets(root)
    removals = set(removals)
    expected_replacements = set(r32.OUTPUT_RECORDS) | {DIAGNOSTIC_PATH}
    if set(replacements) != expected_replacements:
        raise CommunityR33Error("R3.3 replacement path set changed")
    if set(additions) != {ENTRY_PATH, APP_PATH, CSS_PATH, TTL_SET_PATH}:
        raise CommunityR33Error("R3.3 extension asset set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR33Error("R3.3 removed-locale set changed")
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR33Error("R3.3 marker is absent")
    if b'href="/r33.html"' not in replacements["www\\index.html"]:
        raise CommunityR33Error("canonical login does not link R3.3")
    if b'href="/r33.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR33Error("shared header does not link R3.3")
    if any(old in joined for old in (b"0.3.2-community-r2", b"R3.2", b"r32app.js", b"r32ui.css")):
        raise CommunityR33Error("R3.3 assets retain an R3.2 cache or revision identity")
    app = additions[APP_PATH]
    if app.count(b"<command>ttl</command>") != 1:
        raise CommunityR33Error("R3.3 TTL set command contract changed")
    if app.count(b"file=ttl_set") != 1 or app.count(b"modelGet('diagnostic'") != 1:
        raise CommunityR33Error("R3.3 TTL read/set routes are not isolated")
    if app.count(b"SystemChannelName") < 2 or app.count(b"PRODUCT_CHANNEL") < 2:
        raise CommunityR33Error("R3.3 TTL response bridge is incomplete")
    if b"debugmodeon" in joined or b"Engineering_mode>" in joined:
        raise CommunityR33Error("R3.3 browser assets contain an Engineering mutation")
    if b"setInterval" in app or b"RestoreFw" in app:
        raise CommunityR33Error("R3.3 contains interval polling or firmware control")
    return replacements, additions, removals


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR33Error("R3.3 output records are not pinned; retained build is disabled")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR33Error("R3.3 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR33Error("R3.3 addition record gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR33Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR33Error(str(exc)) from exc
    return replacements, additions, removals
