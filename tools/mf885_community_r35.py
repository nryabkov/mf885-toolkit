#!/usr/bin/env python3
"""Deterministic Community R3.5 same-model TTL repair.

R3.5 remains an extension of the stock MF885 interface.  It restores the TTL
page on top of the proved R2.9 UI, but reads only ``diagnostic.output`` and
keeps the write template separate.  The browser enables writes only after a
fresh, strict read proves the native transport.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r33 as r33


PROFILE = "0.3.5-community-r2"
MARKER = b"MF885 Community R3.5 extension 0.3.5-community-r2"
REMOVED_RECORDS = r33.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r33.REMOVED_ARCHIVE_BYTES

ENTRY_PATH = "www\\r35.html"
APP_PATH = "www\\js\\r35app.js"
CSS_PATH = "www\\css\\r35ui.css"
TTL_SET_PATH = "www\\xmldata\\ttl_set.xml"
DIAGNOSTIC_PATH = "www\\xmldata\\diagnostic.xml"

CUSTOM_FILES: dict[str, tuple[str, int, str]] = {}
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "09ae1e21c319918ae4935500bdac44181bbc784b011a89802dc88263be4dd8bf"),
    "www\\index.html": (26_636, "3bf5cb6c39f6b69569f61ded8e1a264e62feaf5329068c847dc3804fa2c51d84"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
    DIAGNOSTIC_PATH: (107, "e6bfeecef30e22a1a7fd64ec99613f91a232934cd988d03d38e5fbcc8f6ab00e"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    ENTRY_PATH: (15_535, "bb04c81281f51f27dcea1d568239f8b1327e0c58a2cec1f1222d7c7e6a99923c", "derived from reviewed R3.3 TTL UI with explicit volatile state text"),
    APP_PATH: (76_227, "97043bc4487c650e27213536b212f7835dd36acbd57614988873567eb0a75d11", "derived from reviewed R3.3 controller with strict same-model diagnostic.output transport"),
    CSS_PATH: (9_232, "84eaad60ed768f9a8daf1bee296bb9e9a6971214f494b3636f25cd331c023576", "byte-identical reviewed TTL CSS under cache-safe R3.5 path"),
    TTL_SET_PATH: (133, "5305b719dfcc22d5984048d1bd875086bc2c53cfd81a67da84c6c533c9e19e4b", "isolated diagnostic command/arg TTL set template"),
}

DIAGNOSTIC_READ_TEMPLATE = (
    b'<?xml version="1.0" encoding="US-ASCII"?>\r\n'
    b'<RGW>\r\n'
    b'  <diagnostic>\r\n'
    b'    <output />\r\n'
    b'  </diagnostic>\r\n'
    b'</RGW>\r\n'
)


class CommunityR35Error(Exception):
    pass


def _revise(data: bytes, label: str) -> bytes:
    replacements = (
        (b"0.3.3-community-r2", b"0.3.5-community-r2"),
        (b"0.3.3", b"0.3.5"),
        (b"R3.3", b"R3.5"),
        (b"r33", b"r35"),
        (b"R33", b"R35"),
        (b"JS33", b"JS35"),
        (b"LIVE33", b"LIVE35"),
        (b"S33", b"S35"),
        (b"TTL30", b"TTL35"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR35Error(f"{label} has no R3.3 revision anchor")
    return data


def _replace_block(data: bytes, start: bytes, end: bytes, replacement: bytes, label: str) -> bytes:
    if data.count(start) != 1 or data.count(end) != 1:
        raise CommunityR35Error(f"{label} block anchors are not unique")
    left = data.index(start)
    right = data.index(end, left)
    if left >= right:
        raise CommunityR35Error(f"{label} block anchors are reversed")
    return data[:left] + replacement + data[right:]


def _rewrite_ttl_transport(data: bytes) -> bytes:
    ttl_state = b"""  function ttlState(doc){
    var id=doc&&doc.mfRequestId||nextTtlId(),root=doc&&doc.documentElement,rootNodes=root&&root.childNodes?root.childNodes:[],rootTag=String(root&&root.nodeName||''),rootAttrCount=root&&root.attributes?root.attributes.length:0,rootElementCount=0,rootSignificantText=false,models=[];
    for(var i=0;i<rootNodes.length;i++){if(rootNodes[i].nodeType===1){rootElementCount++;if(String(rootNodes[i].nodeName||'')==='diagnostic')models.push(rootNodes[i])}else if((rootNodes[i].nodeType===3||rootNodes[i].nodeType===4)&&/\\S/.test(String(rootNodes[i].nodeValue||'')))rootSignificantText=true}
    var model=models.length===1?models[0]:null,modelNodes=model&&model.childNodes?model.childNodes:[],modelAttrCount=model&&model.attributes?model.attributes.length:null,modelElementCount=0,modelSignificantText=false,outputCount=0,extraFields=[],outputNode=null;
    for(var j=0;j<modelNodes.length;j++){if(modelNodes[j].nodeType===1){modelElementCount++;if(String(modelNodes[j].nodeName||'')==='output'){outputCount++;outputNode=modelNodes[j]}else extraFields.push(String(modelNodes[j].nodeName||''))}else if((modelNodes[j].nodeType===3||modelNodes[j].nodeType===4)&&/\\S/.test(String(modelNodes[j].nodeValue||'')))modelSignificantText=true}
    var outputAttrCount=outputNode&&outputNode.attributes?outputNode.attributes.length:null,outputNodes=outputNode&&outputNode.childNodes?outputNode.childNodes:[],outputElementCount=0;for(var k=0;k<outputNodes.length;k++)if(outputNodes[k].nodeType===1)outputElementCount++;
    var value=outputCount===1?String(outputNode.textContent||''):null,parsed=ttlValueInfo(value),rootExact=rootTag==='RGW'&&rootAttrCount===0&&rootElementCount===1&&!rootSignificantText,modelExact=models.length===1&&modelAttrCount===0&&modelElementCount===1&&!modelSignificantText,outputExact=outputCount===1&&outputAttrCount===0&&outputElementCount===0&&extraFields.length===0,passed=rootExact&&modelExact&&outputExact&&parsed.accepted;
    ttlLog(id,'state variables',{rootTag:rootTag,rootAttributeCount:rootAttrCount,rootElementCount:rootElementCount,rootSignificantText:rootSignificantText,readModel:'diagnostic',readModelCount:models.length,modelAttributeCount:modelAttrCount,modelElementCount:modelElementCount,modelSignificantText:modelSignificantText,readField:'output',outputCount:outputCount,outputAttributeCount:outputAttrCount,outputElementCount:outputElementCount,extraFields:extraFields,value:value,valueOff:parsed.off,valueCanonicalDecimal:parsed.canonical,valueNumeric:parsed.numeric,valueInRange:parsed.inRange,valueAccepted:parsed.accepted,rootExact:rootExact,modelExact:modelExact,outputExact:outputExact,acceptedMinimum:1,acceptedMaximum:255,automaticRetryCeiling:0});
    ttlCondition(id,'root_tag','RGW',rootTag,rootTag==='RGW');ttlCondition(id,'root_attribute_count',0,rootAttrCount,rootAttrCount===0);ttlCondition(id,'root_element_count',1,rootElementCount,rootElementCount===1);ttlCondition(id,'root_significant_text',false,rootSignificantText,!rootSignificantText);ttlCondition(id,'diagnostic_model_count',1,models.length,models.length===1);ttlCondition(id,'diagnostic_attribute_count',0,modelAttrCount,modelAttrCount===0);ttlCondition(id,'diagnostic_element_count',1,modelElementCount,modelElementCount===1);ttlCondition(id,'diagnostic_significant_text',false,modelSignificantText,!modelSignificantText);ttlCondition(id,'diagnostic_output_count',1,outputCount,outputCount===1);ttlCondition(id,'output_attribute_count',0,outputAttrCount,outputAttrCount===0);ttlCondition(id,'output_element_count',0,outputElementCount,outputElementCount===0);ttlCondition(id,'diagnostic_extra_field_count',0,extraFields.length,extraFields.length===0);ttlCondition(id,'output_is_off_or_canonical_decimal',true,parsed.off||parsed.canonical,parsed.off||parsed.canonical);ttlCondition(id,'output_numeric_in_range_or_off','off|1..255',value,parsed.accepted);
    if(!passed)throw fault('E_TTL_RESPONSE','The router returned an invalid same-model TTL state.',id,{rootTag:rootTag,rootAttributeCount:rootAttrCount,rootElementCount:rootElementCount,rootSignificantText:rootSignificantText,modelCount:models.length,modelAttributeCount:modelAttrCount,modelElementCount:modelElementCount,modelSignificantText:modelSignificantText,outputCount:outputCount,outputAttributeCount:outputAttrCount,outputElementCount:outputElementCount,extraFields:extraFields,value:value});
    return {value:value,output:'DIAGNOSTIC_OUTPUT',requestId:id};
  }
"""
    data = _replace_block(
        data,
        b"  function ttlState(doc){",
        b"  function ttlXml(value){",
        ttl_state,
        "R3.5 TTL response parser",
    )
    old_log = b"var id=nextTtlId();ttlLog(id,'read variables',{trigger:trigger||'manual',owner:owner,template:'diagnostic',triggerModel:'diagnostic',readModel:'SystemChannelName',readField:'PRODUCT_CHANNEL',stockRestoreExpected:'release',method:'GET',automaticRetryCeiling:0});"
    new_log = b"var id=nextTtlId();ttlLog(id,'read variables',{trigger:trigger||'manual',owner:owner,template:'diagnostic',readModel:'diagnostic',readField:'output',expectedFieldCount:1,method:'GET',automaticRetryCeiling:0});"
    if data.count(old_log) != 1:
        raise CommunityR35Error("R3.5 TTL read-log anchor is not unique")
    data = data.replace(old_log, new_log)
    old_read = b"return ttlGet('ttl-read',trigger).catch(function(error){showError('ttlStatus',error,'TTL state read failed.');throw error}).finally(function(){endRouterOperation('ttl-read')});"
    new_read = b"return ttlGet('ttl-read',trigger).catch(function(error){ttlRuntime.locked=true;syncTtlControls();showError('ttlStatus',error,'TTL state read failed.',' TTL writes are locked until a fresh valid read.');throw error}).finally(function(){endRouterOperation('ttl-read')});"
    if data.count(old_read) != 1:
        raise CommunityR35Error("R3.5 TTL fail-closed read anchor is not unique")
    data = data.replace(old_read, new_read)
    if b"SystemChannelName" in data or b"PRODUCT_CHANNEL" in data:
        raise CommunityR35Error("R3.5 browser controller retains the failed cross-model bridge")
    return data


def derive_assets(root: Path) -> dict[str, bytes]:
    parent = r33.derive_assets(root)
    app = _rewrite_ttl_transport(_revise(parent[r33.APP_PATH], f"R3.5 asset {APP_PATH}"))
    try:
        ttl_set = (root / "firmware" / "community-r3.5" / "ttl_set.xml").read_bytes()
    except OSError as exc:
        raise CommunityR35Error("R3.5 TTL-set template is unavailable") from exc
    entry = _revise(parent[r33.ENTRY_PATH], f"R3.5 asset {ENTRY_PATH}")
    entry = entry.replace(
        b"Choose the TTL written to IPv4 packets forwarded through this MF885.",
        b"Read and set the TTL written to IPv4 packets forwarded through this MF885.",
        1,
    )
    return {
        ENTRY_PATH: entry,
        APP_PATH: app,
        CSS_PATH: parent[r33.CSS_PATH],
        TTL_SET_PATH: ttl_set.replace(b"\n", b"\r\n"),
    }


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        parent_replacements, _parent_additions, removals = r33.build_patch_set(records, root)
    except r33.CommunityR33Error as exc:
        raise CommunityR35Error(str(exc)) from exc
    replacements = dict(parent_replacements)
    for path in ("www\\index.html", "www\\html\\adminApp.html"):
        replacements[path] = _revise(replacements[path], f"R3.5 replacement {path}")
    replacements[DIAGNOSTIC_PATH] = DIAGNOSTIC_READ_TEMPLATE
    additions = derive_assets(root)
    removals = set(removals)
    expected_replacements = set(r33.OUTPUT_RECORDS)
    if set(replacements) != expected_replacements:
        raise CommunityR35Error("R3.5 replacement path set changed")
    if set(additions) != {ENTRY_PATH, APP_PATH, CSS_PATH, TTL_SET_PATH}:
        raise CommunityR35Error("R3.5 extension asset set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR35Error("R3.5 removed-locale set changed")
    joined = b"\n".join(additions.values())
    if MARKER not in joined:
        raise CommunityR35Error("R3.5 marker is absent")
    if b'href="/r35.html"' not in replacements["www\\index.html"]:
        raise CommunityR35Error("canonical login does not link R3.5")
    if b'href="/r35.html"' not in replacements["www\\html\\adminApp.html"]:
        raise CommunityR35Error("shared header does not link R3.5")
    if any(old in joined for old in (b"0.3.3-community-r2", b"R3.3", b"r33app.js", b"r33ui.css", b"TTL30")):
        raise CommunityR35Error("R3.5 assets retain an old cache or flow identity")
    app = additions[APP_PATH]
    if app.count(b"<command>ttl</command>") != 1:
        raise CommunityR35Error("R3.5 TTL set command contract changed")
    if app.count(b"file=ttl_set") != 1 or app.count(b"modelGet('diagnostic'") != 1:
        raise CommunityR35Error("R3.5 TTL read/set routes are not isolated")
    if app.count(b"readModel:'diagnostic'") != 2 or app.count(b"readField:'output'") != 2:
        raise CommunityR35Error("R3.5 same-model response contract is incomplete")
    if any(value in joined for value in (b"SystemChannelName", b"PRODUCT_CHANNEL", b"debugmodeon", b"Engineering_mode>")):
        raise CommunityR35Error("R3.5 browser assets contain a retired or Engineering bridge")
    if b"setInterval" in app or b"RestoreFw" in app:
        raise CommunityR35Error("R3.5 contains interval polling or firmware control")
    return replacements, additions, removals


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR35Error("R3.5 output records are not pinned; retained build is disabled")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR35Error("R3.5 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR35Error("R3.5 addition record gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR35Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR35Error(str(exc)) from exc
    return replacements, additions, removals
