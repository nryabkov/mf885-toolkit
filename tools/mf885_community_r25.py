#!/usr/bin/env python3
"""Deterministic Community R2.5 patch set built on immutable R2.4.

R2.5 keeps all R2.4 safety and mutation boundaries.  It adds a compact,
versioned Community entry in the shared authenticated header, makes both
read-only watchers default-on with an explicit per-tab opt-out, explains radio
terms compactly, and interprets only the radio report indices proven by the
live device and primary standards evidence.  It never enables Engineering mode.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r24 as r24


PROFILE = "0.2.5-community-r2"
MARKER = b"MF885 Community R2.5 Modem Monitor 0.2.5-community-r2"
REMOVED_RECORDS = r24.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r24.REMOVED_ARCHIVE_BYTES

AUTH_PATH = "www\\js\\r25auth.js"
BOOT_PATH = "www\\js\\r25boot.js"
CSS_PATH = "www\\css\\r25ui.css"
SMS_JS_PATH = "www\\js\\panel\\SMS\\r25sms.js"
SMS_HTML_PATH = "www\\html\\Community\\r25sms.html"
DIAGNOSTICS_JS_PATH = "www\\js\\r25diag.js"
DIAGNOSTICS_HTML_PATH = "www\\html\\Community\\r25diag.html"
MODEM_JS_PATH = "www\\js\\r25modem.js"
MODEM_HTML_PATH = "www\\html\\Community\\r25modem.html"
DASHBOARD_JS_PATH = "www\\js\\panel\\r25dash.js"
DASHBOARD_HTML_PATH = "www\\html\\Community\\r25dash.html"
UTILS_PATH = "www\\js\\r25utils.js"
LAYOUT_PATH = "www\\js\\r25layout.js"
MENU_PATH = "www\\xml\\r25ui.xml"
ENTRY_PATH = "www\\r25.html"

# Exact R2.5 outputs derived from the immutable, pinned R2.4 transformer.
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_766, "5e395b88d706db11d74f46f631b72552c755974f70262f32f9c91a59b9eacf04"),
    "www\\index.html": (26_636, "5a49ed409aea7064b20b48fa907c3ac193b5e9f038c68d8aa4062b1c87f747b0"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    AUTH_PATH: (8_084, "3bbd513b1578d2d3684c2b55cd683376df1b9c3e63c6508634e307143c7880b8", "derived cache-safe R2.5 tab authentication"),
    BOOT_PATH: (2_852, "e2815b57a6215c36679a656819ea16fab7e7bb03a4a4869b9ff103e353a14a53", "derived cache-safe R2.5 identity bootstrap"),
    CSS_PATH: (13_976, "509098c37062bf50f031d5b40e9c5b80294198d85ca309c240c4d79f59fd8e9f", "derived cache-safe R2.5 visual system with compact radio-term help and aligned Diagnostics grid"),
    SMS_JS_PATH: (28_745, "d1b9c0c46bd9f8e7c603b95c39b8bba1e04e610c37dc97de0ebb2d1a2303e630", "derived R2.5 default-on SMS controller"),
    SMS_HTML_PATH: (2_014, "e8203a180b658919beee00b83363f2a142bf0eb20cbbc4fb9d9d0114557f7a5a", "derived cache-safe R2.5 Messages page"),
    DIAGNOSTICS_JS_PATH: (20_742, "bc62c003caf86d20a5d4073aa8c4d30bef59474a62cc36b44cbd81649ba6c497", "derived R2.5 diagnostics controller with standards-backed RSRP/RSRQ display"),
    DIAGNOSTICS_HTML_PATH: (2_801, "de555b3b5478aa79319cd794ed3ed54f07e8b5ab556962c8df50bb444cfb0c25", "derived cache-safe R2.5 Diagnostics page with compact radio-term help"),
    MODEM_JS_PATH: (30_994, "b780afd17584980b2c7f99c1ed8a4c431e25bf91ac4176d9bae401fafc0b8a05", "derived R2.5 read-only Modem monitor with safe report-index evidence"),
    MODEM_HTML_PATH: (4_486, "35595b44d7673814591e4697b67efbb08229d796f4ffb719a67efe72c62382d4", "derived cache-safe R2.5 Modem page with compact radio-term help"),
    DASHBOARD_JS_PATH: (59_938, "1e62c75d3cee098a89d95241fd7ebce0ee2bd53b390ed40fe477d741974a5b9d", "derived cache-safe R2.5 dashboard controller"),
    DASHBOARD_HTML_PATH: (10_265, "e766925da04d77459a7e5b2f9a5476892f12a0caaeb887500bd75b560bf00d19", "derived R2.5 exact-version dashboard"),
    UTILS_PATH: (17_049, "b0df72c786ed53df5bc3b19d92fcee540edad8b51f454235c13c7d21d2d46ad4", "derived cache-safe R2.5 utility controller"),
    LAYOUT_PATH: (11_457, "3a3187b65bf55cf3ca2840ba70a5532c349d37647d37554ba864ab72981630ed", "derived cache-safe R2.5 menu loader"),
    MENU_PATH: (3_002, "dacc4fc1efbf70085dcc115d354e3d77c06a07491402bf10d0e93c47d057478c", "unchanged private Community menu on a cache-safe R2.5 path"),
    ENTRY_PATH: (26_969, "41c4ff48058008c0534ce660d1639776796475b4e0c3c332098e3bd7c36c2c10", "derived cache-safe R2.5 entry document"),
}
CUSTOM_FILES: dict[str, tuple[str, int, str]] = {}


class CommunityR25Error(Exception):
    pass


def _replace_count(data: bytes, old: bytes, new: bytes, count: int, label: str) -> bytes:
    if data.count(old) != count:
        raise CommunityR25Error(f"{label} anchor count changed")
    return data.replace(old, new)


def _revise(data: bytes, label: str) -> bytes:
    """Move one R2.4-owned asset to its immutable R2.5 identity."""
    replacements = (
        (b"0.2.4-community-r2", b"0.2.5-community-r2"),
        (b"R2.4", b"R2.5"),
        (b"r24", b"r25"),
        (b"R24", b"R25"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR25Error(f"{label} has no R2.4 revision anchor")
    return data


def _patch_admin_app(data: bytes) -> bytes:
    old = (
        b'<div class="loginArea"><label id="lableWelcome" style="display: none">Welcome</label> '
        b'<a id="lvhomepage" target="_blank" href="http://www.zmifi.com">Official website</a>'
    )
    new = (
        b'<div class="loginArea"><a id="mfCommunityHeaderLink" href="/r25.html" title="Open Community UI 0.2.5-community-r2" '
        b'style="display:inline-flex;align-items:center;gap:5px;padding:3px 8px;border:1px solid #b8d7f2;border-radius:999px;background:#f4f9fe;color:#0b5f9c;font-weight:bold;line-height:1.2;text-decoration:none">'
        b'<span>Community</span><span id="mfCommunityHeaderVersion" style="color:#52738e;font-size:10px">0.2.5</span></a>'
        b'<label id="lableWelcome" style="display:none">Welcome</label>'
        b'<a id="lvhomepage" target="_blank" href="http://www.zmifi.com" style="display:none">Official website</a>'
    )
    return _replace_count(data, old, new, 1, "shared Community header")


def _patch_dashboard(data: bytes) -> bytes:
    data = _revise(data, "dashboard")
    data = _replace_count(data, b"Community UI", b"Community R2.5", 1, "dashboard build badge")
    return _replace_count(
        data,
        b'<span class="mfCommunityBase">base 2.5.94</span>',
        b'<span class="mfCommunityBase">0.2.5-community-r2 \xc2\xb7 base 2.5.94</span>',
        1,
        "dashboard exact version",
    )


def _radio_terms_panel(panel_id: str) -> bytes:
    terms = (
        ("SIM", "Subscriber Identity Module"),
        ("RAT", "Radio Access Technology"),
        ("PDP", "Packet Data Protocol session"),
        ("APN", "Access Point Name"),
        ("WAN", "Wide Area Network"),
        ("DNS", "Domain Name System"),
        ("LTE", "Long-Term Evolution"),
        ("RSRP", "Reference Signal Received Power"),
        ("RSRQ", "Reference Signal Received Quality"),
        ("SINR", "Signal-to-Interference-plus-Noise Ratio"),
        ("RSSI", "Received Signal Strength Indicator"),
        ("EARFCN", "E-UTRA Absolute Radio Frequency Channel Number"),
        ("PCI", "Physical Cell Identity"),
        ("TAC", "Tracking Area Code"),
        ("LAC", "Location Area Code"),
        ("CQI", "Channel Quality Indicator"),
        ("DL / UL", "Downlink / Uplink"),
        ("UMTS", "Universal Mobile Telecommunications System"),
        ("PSC", "Primary Scrambling Code"),
        ("ARFCN", "Absolute Radio Frequency Channel Number"),
        ("RSCP", "Received Signal Code Power"),
        ("GSM", "Global System for Mobile Communications"),
        ("GPRS", "General Packet Radio Service"),
    )
    items = b"".join(
        (
            '<li><strong>{}</strong><span>{}</span></li>'.format(short, long)
        ).encode("ascii")
        for short, long in terms
    )
    return (
        f'<section id="{panel_id}" class="mfRadioTerms" hidden '
        'aria-label="Radio term explanations"><ul class="mfRadioTermsList">'
    ).encode("ascii") + items + b"</ul></section>"


def _patch_diagnostics_html(data: bytes) -> bytes:
    data = _revise(data, "Diagnostics page")
    data = _replace_count(
        data,
        b'<button type="button" id="mfDiagCopy" class="mfCommunityButton" disabled>Copy safe snapshot</button>',
        b'<button type="button" id="mfDiagCopy" class="mfCommunityButton" disabled>Copy safe snapshot</button>\n'
        b'    <button type="button" id="mfDiagTerms" class="mfCommunityButton mfTermsButton" aria-expanded="false" aria-controls="mfDiagTermsPanel">Radio terms</button>',
        1,
        "Diagnostics terms button",
    )
    return _replace_count(
        data,
        b'  <div id="mfDiagStatus" role="status" aria-live="polite" class="mfCommunityStatus">',
        b'  ' + _radio_terms_panel("mfDiagTermsPanel") + b'\n  <div id="mfDiagStatus" role="status" aria-live="polite" class="mfCommunityStatus">',
        1,
        "Diagnostics terms panel",
    )


def _patch_modem_html(data: bytes) -> bytes:
    data = _revise(data, "Modem page")
    data = _replace_count(
        data,
        b'<button type="button" id="mfModemCopy" class="mfCommunityButton" disabled>Copy safe trace</button>',
        b'<button type="button" id="mfModemCopy" class="mfCommunityButton" disabled>Copy safe trace</button>\n'
        b'    <button type="button" id="mfModemTerms" class="mfCommunityButton mfTermsButton" aria-expanded="false" aria-controls="mfModemTermsPanel">Radio terms</button>',
        1,
        "Modem terms button",
    )
    return _replace_count(
        data,
        b'  <div id="mfModemStatus" role="status" aria-live="polite" class="mfCommunityStatus">',
        b'  ' + _radio_terms_panel("mfModemTermsPanel") + b'\n  <div id="mfModemStatus" role="status" aria-live="polite" class="mfCommunityStatus">',
        1,
        "Modem terms panel",
    )


def _patch_css(data: bytes) -> bytes:
    data = _revise(data, "visual system")
    if b".mfRadioTerms" in data:
        raise CommunityR25Error("radio terms styles already exist")
    return data + b"""

/* Compact radio-term help: hidden until explicitly opened. */
.mfTermsButton { padding-left:10px; padding-right:10px; font-weight:normal; }
.mfRadioTerms {
  margin:0 0 10px 0;
  padding:10px 12px;
  border:1px solid #d8e3ec;
  border-radius:6px;
  background:#f8fafc;
}
.mfRadioTerms[hidden] { display:none !important; }
.mfRadioTermsList {
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:5px 18px;
  margin:0;
  padding:0;
  list-style:none;
}
.mfRadioTermsList li { min-width:0; color:#475467; font-size:11px; line-height:15px; }
.mfRadioTermsList strong { display:inline-block; min-width:62px; margin-right:6px; color:#243447; }
.mfCommunityValues {
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  column-gap:3%;
  overflow:visible;
}
.mfCommunityValue { float:none; width:auto; margin:0; }
.mfHasTerm { display:inline-block; width:auto; cursor:help; border-bottom:1px dotted #98a2b3; }
@media screen and (max-width:720px) {
  .mfCommunityValues,
  .mfRadioTermsList { grid-template-columns:1fr; }
}
"""


def _patch_sms(data: bytes) -> bytes:
    data = _revise(data, "SMS controller")
    data = _replace_count(
        data,
        b"try{state.enabled=!!(w.sessionStorage&&w.sessionStorage.getItem(WATCH_KEY)==='1')}catch(_){state.enabled=false}",
        b"try{if(!w.sessionStorage)throw new Error('storage');var preference=w.sessionStorage.getItem(WATCH_KEY);state.enabled=preference===null||preference==='1'}catch(_){state.enabled=false}",
        1,
        "SMS default-on preference",
    )
    data = _replace_count(
        data,
        b"if(value)w.sessionStorage.setItem(WATCH_KEY,'1');else w.sessionStorage.removeItem(WATCH_KEY);",
        b"w.sessionStorage.setItem(WATCH_KEY,value?'1':'0');",
        1,
        "SMS explicit opt-out preference",
    )
    data = _replace_count(
        data,
        b"On \xc2\xb7 checks once a minute. Browser alerts are unavailable on this HTTP address; the in-page badge still works.",
        b"On \xc2\xb7 every minute \xc2\xb7 in-page alerts only (system alerts need HTTPS).",
        1,
        "SMS HTTP active hint",
    )
    data = _replace_count(
        data,
        b"Browser alerts are unavailable on this HTTP address; the in-page badge still works.",
        b"System alerts need HTTPS; in-page alerts stay active.",
        1,
        "SMS HTTP permission hint",
    )
    data = _replace_count(
        data,
        b"On \xc2\xb7 checks once a minute while this tab stays open.",
        b"On \xc2\xb7 every minute while this tab is open.",
        1,
        "SMS secure active hint",
    )
    return data


def _patch_diagnostics(data: bytes) -> bytes:
    data = _revise(data, "Diagnostics controller")
    data = _replace_count(
        data,
        b"battery:[['batteryinfo','Battery_percent']],batteryState:[['batteryinfo','Battery_status']],chargerStatus:[['batteryinfo','Charger_status']],chargerCurrent:[['batteryinfo','Charger_current']],outputCurrent:[['batteryinfo','Output_current']]",
        b"battery:[['batteryinfo','Battery_percent']],batteryState:[['batteryinfo','Battery_status']],chargerStatus:[['batteryinfo','Charger_status']],chargerCurrent:[['batteryinfo','Charger_current']],outputCurrent:[['batteryinfo','Output_current']],signalIndex:[['wan','cellular','rssi'],['wan','rssi']]",
        1,
        "Diagnostics status signal index",
    )
    data = _replace_count(
        data,
        b"dns1:[['wan','dns1'],['wan','cellular','dns1'],['wan','cellular','v4dns1'],['wan','cellular','pdp_context_list','Item','v4dns1']],dns2:[['wan','dns2'],['wan','cellular','dns2'],['wan','cellular','v4dns2'],['wan','cellular','pdp_context_list','Item','v4dns2']],gateway:[['wan','gateway'],['wan','cellular','gateway'],['wan','cellular','v4gateway'],['wan','cellular','pdp_context_list','Item','v4gateway']]",
        b"dns1:[['wan','dns1'],['wan','cellular','dns1'],['wan','cellular','v4dns1'],['wan','cellular','pdp_context_list','Item','v4dns1']],dns2:[['wan','dns2'],['wan','cellular','dns2'],['wan','cellular','v4dns2'],['wan','cellular','pdp_context_list','Item','v4dns2']],gateway:[['wan','gateway'],['wan','cellular','gateway'],['wan','cellular','v4gateway'],['wan','cellular','pdp_context_list','Item','v4gateway']],engineeringMode:[['wan','Engineering_mode']]",
        1,
        "Diagnostics Engineering mode",
    )
    old_engineer = (
        b"band:[['Engineer_parameter','LTE_band'],['Engineer_parameter','lte_band'],['Engineer_parameter','band']],earfcn:[['Engineer_parameter','EARFCN'],['Engineer_parameter','earfcn']],pci:[['Engineer_parameter','PCI'],['Engineer_parameter','pci']],\n"
        b"      cell:[['Engineer_parameter','Cell_ID'],['Engineer_parameter','cell_id'],['Engineer_parameter','cellid']],tac:[['Engineer_parameter','TAC'],['Engineer_parameter','tac'],['Engineer_parameter','LAC'],['Engineer_parameter','lac']],\n"
        b"      rsrp:[['Engineer_parameter','RSRP'],['Engineer_parameter','rsrp']],rsrq:[['Engineer_parameter','RSRQ'],['Engineer_parameter','rsrq']],sinr:[['Engineer_parameter','SINR'],['Engineer_parameter','sinr']],rssi:[['Engineer_parameter','RSSI'],['Engineer_parameter','rssi']]"
    )
    new_engineer = (
        b"band:[['Engineer_parameter','LTE_band'],['Engineer_parameter','lte_band'],['Engineer_parameter','band'],['Engi','LTE','band']],earfcn:[['Engineer_parameter','EARFCN'],['Engineer_parameter','earfcn'],['Engi','LTE','dlEuArfcn']],pci:[['Engineer_parameter','PCI'],['Engineer_parameter','pci'],['Engi','LTE','phyCellId']],\n"
        b"      cell:[['Engineer_parameter','Cell_ID'],['Engineer_parameter','cell_id'],['Engineer_parameter','cellid'],['Engi','LTE','cellId']],tac:[['Engineer_parameter','TAC'],['Engineer_parameter','tac'],['Engineer_parameter','LAC'],['Engineer_parameter','lac'],['Engi','LTE','tac']],\n"
        b"      rsrp:[['Engineer_parameter','RSRP'],['Engineer_parameter','rsrp'],['Engi','LTE','rsrp']],rsrq:[['Engineer_parameter','RSRQ'],['Engineer_parameter','rsrq'],['Engi','LTE','rsrq']],sinr:[['Engineer_parameter','SINR'],['Engineer_parameter','sinr'],['Engi','LTE','sinr']],rssi:[['Engineer_parameter','RSSI'],['Engineer_parameter','rssi'],['Engi','LTE','rssi']]"
    )
    data = _replace_count(data, old_engineer, new_engineer, 1, "Diagnostics nested engineering schema")
    data = _replace_count(
        data,
        b"chargerStatus:{'0':'Normal charging','4':'Full','5':'Abnormal charging'}};",
        b"chargerStatus:{'0':'Normal charging','4':'Full','5':'Abnormal charging'},engineeringMode:{'0':'Disabled','1':'Enabled'}};",
        1,
        "Diagnostics Engineering mode mapping",
    )
    data = _replace_count(
        data,
        b"function mapped(name,raw){var table=MAPS[name];return raw===null?null:table&&table[raw]!==undefined?table[raw]:table?'Unknown (raw: '+raw+')':raw}",
        b"function reportNumber(raw){return /^-?\\d+(?:\\.\\d+)?$/.test(String(raw||''))?Number(raw):null}\n"
        b"  function decimal(value){return Math.round(value)===value?String(value):value.toFixed(1)}\n"
        b"  function rsrpValue(raw){var value=reportNumber(raw);if(value===null)return 'Unknown';if(value<0)return decimal(value)+' dBm';if(value===0)return '< -140 dBm \\u00b7 index 0';if(value===97)return '>= -44 dBm \\u00b7 index 97';return value>0&&value<97?decimal(value-140)+' dBm \\u00b7 index '+value:'Unknown (raw: '+raw+')'}\n"
        b"  function rsrqValue(raw){var value=reportNumber(raw);if(value===null)return 'Unknown';if(value<0)return decimal(value)+' dB';if(value===0)return '< -19.5 dB \\u00b7 index 0';if(value===34)return '>= -3 dB \\u00b7 index 34';return value>0&&value<34?decimal(-19.5+(value*.5))+' dB \\u00b7 index '+value:'Unknown (raw: '+raw+')'}\n"
        b"  function mapped(name,raw){var table=MAPS[name];if(raw===null)return null;if(name==='rsrp')return rsrpValue(raw);if(name==='rsrq')return rsrqValue(raw);if(name==='sinr'||name==='rssi'){var numeric=reportNumber(raw);return numeric===null?'Unknown':'raw '+decimal(numeric)}return table&&table[raw]!==undefined?table[raw]:table?'Unknown (raw: '+raw+')':raw}",
        1,
        "Diagnostics standards-backed radio values",
    )
    data = _replace_count(
        data,
        b"'rsrp','rsrq','sinr','rssi','txTotal'",
        b"'rsrp','rsrq','sinr','rssi','signalIndex','engineeringMode','txTotal'",
        1,
        "Diagnostics normalized evidence fields",
    )
    data = _replace_count(
        data,
        b"['rat','Radio'],['operator','Operator']",
        b"['rat','Radio'],['engineeringMode','Engineering mode'],['signalIndex','Signal quality (vendor scale)'],['operator','Operator']",
        1,
        "Diagnostics evidence labels",
    )
    data = _replace_count(
        data,
        b"var labels=[['community','Community version']",
        b"var TERMS={'SIM':'Subscriber Identity Module','PDP':'Packet Data Protocol session','PDP type':'Packet Data Protocol session type','APN':'Access Point Name','IPv4':'Internet Protocol version 4','IPv6':'Internet Protocol version 6','DNS 1':'Domain Name System server 1','DNS 2':'Domain Name System server 2','EARFCN':'E-UTRA Absolute Radio Frequency Channel Number','PCI':'Physical Cell Identity','TAC / LAC':'Tracking Area Code / Location Area Code','RSRP':'Reference Signal Received Power','RSRQ':'Reference Signal Received Quality','SINR':'Signal-to-Interference-plus-Noise Ratio','RSSI':'Received Signal Strength Indicator','WAN uploaded (total bytes)':'Wide Area Network uploaded, total bytes','WAN downloaded (total bytes)':'Wide Area Network downloaded, total bytes','WAN uploaded (session bytes)':'Wide Area Network uploaded, session bytes','WAN downloaded (session bytes)':'Wide Area Network downloaded, session bytes'};\n"
        b"      function explainLabel(node,label){var term=TERMS[label];node.textContent=label;if(term){node.className+=' mfHasTerm';node.setAttribute('title',term);node.setAttribute('aria-label',label+' \\u2014 '+term)}}\n"
        b"      var labels=[['community','Community version']",
        1,
        "Diagnostics term titles",
    )
    old_render = (
        b"      function renderValues(){\n"
        b"        valuesRoot.textContent='';for(var i=0;i<labels.length;i++){var key=labels[i][0],row=w.document.createElement('div'),title=w.document.createElement('span'),value=w.document.createElement('strong');\n"
        b"          row.className='mfCommunityValue';title.className='mfCommunityValueLabel';title.textContent=labels[i][1];\n"
        b"          value.className='mfCommunityValueText';value.textContent=values[key]&&values[key].value!==null?values[key].value:'Not returned';row.appendChild(title);row.appendChild(value);if(values[key]&&values[key].stale){row.style.opacity='.65';title.textContent+=' (previous)'}valuesRoot.appendChild(row)}\n"
        b"      }"
    )
    new_render = (
        b"      function detailedRadioReturned(){var keys=['band','earfcn','pci','cell','tac','rsrp','rsrq','sinr','rssi'];for(var i=0;i<keys.length;i++)if(values[keys[i]]&&values[keys[i]].value!==null)return true;return false}\n"
        b"      function renderValues(){\n"
        b"        valuesRoot.textContent='';var detailKeys={band:1,earfcn:1,pci:1,cell:1,tac:1,rsrp:1,rsrq:1,sinr:1,rssi:1},hasDetail=detailedRadioReturned();for(var i=0;i<labels.length;i++){var key=labels[i][0],item=values[key];if(detailKeys[key]&&(!item||item.value===null))continue;var row=w.document.createElement('div'),title=w.document.createElement('span'),value=w.document.createElement('strong');\n"
        b"          row.className='mfCommunityValue';title.className='mfCommunityValueLabel';explainLabel(title,labels[i][1]);\n"
        b"          value.className='mfCommunityValueText';value.textContent=item&&item.value!==null?item.value:'Not returned';row.appendChild(title);row.appendChild(value);if(item&&item.stale){row.style.opacity='.65';title.textContent+=' (previous)'}valuesRoot.appendChild(row)}\n"
        b"        if(!hasDetail){var row=w.document.createElement('div'),title=w.document.createElement('span'),value=w.document.createElement('strong');row.className='mfCommunityValue';title.className='mfCommunityValueLabel';title.textContent='Detailed radio metrics';value.className='mfCommunityValueText';value.textContent='Not returned';row.appendChild(title);row.appendChild(value);valuesRoot.appendChild(row)}\n"
        b"      }"
    )
    data = _replace_count(data, old_render, new_render, 1, "concise Diagnostics radio rows")
    data = _replace_count(
        data,
        b"var refresh=w.document.getElementById('mfDiagRefresh'),copy=w.document.getElementById('mfDiagCopy'),status=w.document.getElementById('mfDiagStatus'),valuesRoot=w.document.getElementById('mfDiagValues');",
        b"var refresh=w.document.getElementById('mfDiagRefresh'),copy=w.document.getElementById('mfDiagCopy'),terms=w.document.getElementById('mfDiagTerms'),termsPanel=w.document.getElementById('mfDiagTermsPanel'),status=w.document.getElementById('mfDiagStatus'),valuesRoot=w.document.getElementById('mfDiagValues');",
        1,
        "Diagnostics terms controls",
    )
    data = _replace_count(
        data,
        b"setStatus(failed?'Partial diagnostics: '+failed+' endpoint'+(failed===1?'':'s')+' failed.':'Diagnostics updated from three fixed endpoints.',failed>0);",
        b"if(!failed&&values.engineeringMode&&/^[01]$/.test(values.engineeringMode.raw)&&!detailedRadioReturned())setStatus('Diagnostics updated. Engineering mode is '+(values.engineeringMode.raw==='1'?'Enabled':'Disabled')+'; detailed radio metrics were not returned.');else setStatus(failed?'Partial diagnostics: '+failed+' endpoint'+(failed===1?'':'s')+' failed.':'Diagnostics updated from three fixed endpoints.',failed>0);",
        1,
        "Diagnostics Engineering-mode explanation",
    )
    data = _replace_count(
        data,
        b"pdpType:safeItem('pdpType'),band:safeItem('band'),rsrp:safeItem('rsrp')",
        b"pdpType:safeItem('pdpType'),engineeringMode:safeItem('engineeringMode'),signalQuality:safeItem('signalIndex'),band:safeItem('band'),rsrp:safeItem('rsrp')",
        1,
        "safe Diagnostics radio evidence",
    )
    data = _replace_count(
        data,
        b"refresh.addEventListener('click',run);copy.addEventListener('click',copyReport);this.onLoad=function(){run()};",
        b"terms.addEventListener('click',function(){var open=termsPanel.hidden;termsPanel.hidden=!open;terms.setAttribute('aria-expanded',open?'true':'false')});refresh.addEventListener('click',run);copy.addEventListener('click',copyReport);this.onLoad=function(){run()};",
        1,
        "Diagnostics terms toggle",
    )
    return data


def _patch_modem(data: bytes) -> bytes:
    data = _revise(data, "Modem monitor")
    data = _replace_count(
        data,
        b"apEnabled:[['wlan_settings','wlan_enable']],apChannel:[['wlan_settings','current_channel'],['wlan_settings','channel']],\n      battery:",
        b"apEnabled:[['wlan_settings','wlan_enable']],apChannel:[['wlan_settings','current_channel'],['wlan_settings','channel']],signalIndex:[['wan','cellular','rssi'],['wan','rssi']],\n      battery:",
        1,
        "Modem status signal index",
    )
    data = _replace_count(
        data,
        b"wanConn:[['wan','wan_conn_status']],wifiSsid:[['wan','wifi','ssid']],wifiSignal:[['wan','wifi','signal']]\n    },",
        b"wanConn:[['wan','wan_conn_status']],wifiSsid:[['wan','wifi','ssid']],wifiSignal:[['wan','wifi','signal']],engineeringMode:[['wan','Engineering_mode']]\n    },",
        1,
        "Modem Engineering mode",
    )
    data = _replace_count(
        data,
        b"batteryState:{'1':'Charging input','2':'Powering USB-A','3':'On battery'},wanProto:{'cellular':'Cellular','wifi':'Wi-Fi uplink','disabled':'Disabled'},apEnabled:{'0':'Off','1':'On'}",
        b"batteryState:{'1':'Charging input','2':'Powering USB-A','3':'On battery'},wanProto:{'cellular':'Cellular','wifi':'Wi-Fi uplink','disabled':'Disabled'},apEnabled:{'0':'Off','1':'On'},engineeringMode:{'0':'Disabled','1':'Enabled'}",
        1,
        "Modem Engineering mode mapping",
    )
    data = _replace_count(
        data,
        b"function mapped(name,raw){var map=MAPS[name];return raw===null?'Not returned':map&&map[raw]!==undefined?map[raw]:map?'Unknown (raw: '+raw+')':raw}",
        b"function reportNumber(raw){return /^-?\\d+(?:\\.\\d+)?$/.test(String(raw||''))?Number(raw):null}\n"
        b"  function decimal(value){return Math.round(value)===value?String(value):value.toFixed(1)}\n"
        b"  function rsrpValue(raw){var value=reportNumber(raw);if(value===null)return 'Unknown';if(value<0)return decimal(value)+' dBm';if(value===0)return '< -140 dBm \\u00b7 index 0';if(value===97)return '>= -44 dBm \\u00b7 index 97';return value>0&&value<97?decimal(value-140)+' dBm \\u00b7 index '+value:'Unknown (raw: '+raw+')'}\n"
        b"  function rsrqValue(raw){var value=reportNumber(raw);if(value===null)return 'Unknown';if(value<0)return decimal(value)+' dB';if(value===0)return '< -19.5 dB \\u00b7 index 0';if(value===34)return '>= -3 dB \\u00b7 index 34';return value>0&&value<34?decimal(-19.5+(value*.5))+' dB \\u00b7 index '+value:'Unknown (raw: '+raw+')'}\n"
        b"  function mapped(name,raw){var map=MAPS[name];if(raw===null)return 'Not returned';if(name==='rsrp'||name==='mainRsrp'||name==='diversityRsrp')return rsrpValue(raw);if(name==='rsrq'||name==='mainRsrq'||name==='diversityRsrq')return rsrqValue(raw);if(name==='sinr'||name==='rssi'||name==='bandwidth'){var numeric=reportNumber(raw);return numeric===null?'Unknown':'raw '+decimal(numeric)}return map&&map[raw]!==undefined?map[raw]:map?'Unknown (raw: '+raw+')':raw}",
        1,
        "Modem standards-backed radio values",
    )
    data = _replace_count(
        data,
        b"function radio(models){var raw=first(models,'ratMode');if(raw!==null)return mapped('ratMode',raw);raw=first(models,'ratType');return mapped('ratType',raw)}",
        b"function radio(models){var raw=first(models,'ratMode');if(raw!==null)return mapped('ratMode',raw);raw=first(models,'ratType');return mapped('ratType',raw)}\n  function signalBars(models){var raw=first(models,'signalIndex'),mode=first(models,'ratMode');if(raw===null||!/^\\d+$/.test(raw))return null;var value=parseInt(raw,10);if(mode==='3')return value<=15?1:value<=20?2:value<=25?3:4;if(mode==='4'||mode==='5')return value<=25?1:value<=30?2:value<=35?3:4;if(mode==='6'||mode==='17')return value<=23?1:value<=32?2:value<=39?3:4;return null}\n  function signalLabel(models){var raw=first(models,'signalIndex'),bars=signalBars(models);return raw===null?'Not returned':raw+(bars===null?' / vendor scale':' / '+bars+'/4 bars / vendor scale')}",
        1,
        "stock signal-quality mapping",
    )
    data = _replace_count(
        data,
        b"cqi:mapped('cqi',first(models,'cqi')),\n      rsrp:",
        b"cqi:mapped('cqi',first(models,'cqi')),engineeringMode:mapped('engineeringMode',first(models,'engineeringMode')),signalIndex:mapped('signalIndex',first(models,'signalIndex')),signalBars:signalBars(models),signalLevel:signalLabel(models),\n      rsrp:",
        1,
        "Modem evidence snapshot",
    )
    data = _replace_count(
        data,
        b"band:safeNumeric(item.band,0,255),bandwidth:safeNumeric(item.bandwidth,0,100),cqi:safeNumeric(item.cqi,0,30),",
        b"band:safeNumeric(item.band,0,255),bandwidth:safeRawNumeric(item.bandwidth,0,100),cqi:safeNumeric(item.cqi,0,30),engineeringMode:safeState(item.engineeringMode,['Disabled','Enabled']),signalIndex:safeNumeric(item.signalIndex,0,99),signalBars:typeof item.signalBars==='number'&&item.signalBars>=1&&item.signalBars<=4?item.signalBars:null,",
        1,
        "safe Modem evidence snapshot",
    )
    data = _replace_count(
        data,
        b"function safeNumeric(value,minimum,maximum){\n    value=String(value||'').trim();if(!/^-?\\d+(?:\\.\\d+)?$/.test(value))return null;\n    var numeric=Number(value);return isFinite(numeric)&&numeric>=minimum&&numeric<=maximum?value:null;\n  }",
        b"function safeNumeric(value,minimum,maximum){\n    value=String(value||'').trim();if(!/^-?\\d+(?:\\.\\d+)?$/.test(value))return null;\n    var numeric=Number(value);return isFinite(numeric)&&numeric>=minimum&&numeric<=maximum?value:null;\n  }\n"
        b"  function safeMeasurement(value,minimum,maximum){var match=String(value||'').match(/^(?:< |>= )?(-?\\d+(?:\\.\\d+)?) (?:dBm|dB)(?: \\u00b7 index \\d+)?$/);if(!match)return null;var numeric=Number(match[1]);return isFinite(numeric)&&numeric>=minimum&&numeric<=maximum?match[1]:null}\n"
        b"  function safeIndex(value,maximum){var match=String(value||'').match(/\\u00b7 index (\\d+)$/);if(!match)return null;var numeric=Number(match[1]);return isFinite(numeric)&&numeric>=0&&numeric<=maximum?numeric:null}\n"
        b"  function safeRawNumeric(value,minimum,maximum){var match=String(value||'').match(/^raw (-?\\d+(?:\\.\\d+)?)$/);return match?safeNumeric(match[1],minimum,maximum):null}",
        1,
        "safe Modem radio evidence helpers",
    )
    data = _replace_count(
        data,
        b"rsrp:safeNumeric(item.rsrp,-200,0),rsrq:safeNumeric(item.rsrq,-60,60),sinr:safeNumeric(item.sinr,-100,100),rssi:safeNumeric(item.rssi,-200,0),\n      mainRsrp:safeNumeric(item.mainRsrp,-200,0),diversityRsrp:safeNumeric(item.diversityRsrp,-200,0),mainRsrq:safeNumeric(item.mainRsrq,-60,60),diversityRsrq:safeNumeric(item.diversityRsrq,-60,60),battery:safeNumeric(item.battery,0,100)",
        b"rsrp:safeMeasurement(item.rsrp,-200,0),rsrpIndex:safeIndex(item.rsrp,97),rsrq:safeMeasurement(item.rsrq,-60,60),rsrqIndex:safeIndex(item.rsrq,34),sinr:safeRawNumeric(item.sinr,-100,100),rssi:safeRawNumeric(item.rssi,-200,200),\n      mainRsrp:safeMeasurement(item.mainRsrp,-200,0),mainRsrpIndex:safeIndex(item.mainRsrp,97),diversityRsrp:safeMeasurement(item.diversityRsrp,-200,0),diversityRsrpIndex:safeIndex(item.diversityRsrp,97),mainRsrq:safeMeasurement(item.mainRsrq,-60,60),mainRsrqIndex:safeIndex(item.mainRsrq,34),diversityRsrq:safeMeasurement(item.diversityRsrq,-60,60),diversityRsrqIndex:safeIndex(item.diversityRsrq,34),battery:safeNumeric(item.battery,0,100)",
        1,
        "safe Modem mapped radio evidence",
    )
    data = _replace_count(
        data,
        b"try{state.enabled=!!(w.sessionStorage&&w.sessionStorage.getItem(WATCH_KEY)==='1')}catch(_){state.enabled=false}",
        b"try{if(!w.sessionStorage)throw new Error('storage');var preference=w.sessionStorage.getItem(WATCH_KEY);state.enabled=preference===null||preference==='1'}catch(_){state.enabled=false}",
        1,
        "Modem default-on preference",
    )
    data = _replace_count(
        data,
        b"if(value)w.sessionStorage.setItem(WATCH_KEY,'1');else w.sessionStorage.removeItem(WATCH_KEY);",
        b"w.sessionStorage.setItem(WATCH_KEY,value?'1':'0');",
        1,
        "Modem explicit opt-out preference",
    )
    data = _replace_count(
        data,
        b"['SIM',value.sim],['Registration',value.registration],['Radio',value.rat],['Operator',value.operator],['PDP',value.pdp],['Band',value.band],['RSRP',value.rsrp]",
        b"['SIM',value.sim],['Registration',value.registration],['Radio',value.rat],['Engineering mode',value.engineeringMode],['Signal level',value.signalLevel],['Operator',value.operator],['PDP',value.pdp],['Band',value.band],['RSRP',value.rsrp]",
        1,
        "Modem evidence rows",
    )
    data = _replace_count(
        data,
        b"var page=w.document.getElementById('mfCommunityR25Modem'),refresh=w.document.getElementById('mfModemRefresh'),copy=w.document.getElementById('mfModemCopy'),watch=w.document.getElementById('mfModemWatch');",
        b"var page=w.document.getElementById('mfCommunityR25Modem'),refresh=w.document.getElementById('mfModemRefresh'),copy=w.document.getElementById('mfModemCopy'),terms=w.document.getElementById('mfModemTerms'),termsPanel=w.document.getElementById('mfModemTermsPanel'),watch=w.document.getElementById('mfModemWatch');",
        1,
        "Modem terms controls",
    )
    data = _replace_count(
        data,
        b"function metric(label,value){var box=w.document.createElement('div'),key=w.document.createElement('span'),text=w.document.createElement('strong');box.className='mfModemMetric';key.className='mfModemMetricLabel';text.className='mfModemMetricValue';key.textContent=label;text.textContent=value;box.appendChild(key);box.appendChild(text);summary.appendChild(box)}",
        b"var TERMS={'SIM':'Subscriber Identity Module','PDP':'Packet Data Protocol session','RSRP':'Reference Signal Received Power','RSRQ':'Reference Signal Received Quality','SINR':'Signal-to-Interference-plus-Noise Ratio','RSSI':'Received Signal Strength Indicator','DL EARFCN':'Downlink E-UTRA Absolute Radio Frequency Channel Number','UL EARFCN':'Uplink E-UTRA Absolute Radio Frequency Channel Number','PCI':'Physical Cell Identity','DL bandwidth':'Downlink bandwidth; the displayed stock value is not converted without proof','CQI':'Channel Quality Indicator','Main RSRP':'Main-antenna Reference Signal Received Power','Diversity RSRP':'Diversity-antenna Reference Signal Received Power','Main RSRQ':'Main-antenna Reference Signal Received Quality','Diversity RSRQ':'Diversity-antenna Reference Signal Received Quality','UMTS PSC':'Universal Mobile Telecommunications System Primary Scrambling Code','UMTS ARFCN':'Universal Mobile Telecommunications System Absolute Radio Frequency Channel Number','RSCP':'Received Signal Code Power','Ec/N0':'Energy per chip to noise power spectral density ratio','UMTS Tx power':'Universal Mobile Telecommunications System transmit power','GSM ARFCN':'Global System for Mobile Communications Absolute Radio Frequency Channel Number','GPRS UL throughput':'General Packet Radio Service uplink throughput','GPRS DL throughput':'General Packet Radio Service downlink throughput'};\n"
        b"      function explainLabel(node,label){var term=TERMS[label];node.textContent=label;if(term){node.className+=' mfHasTerm';node.setAttribute('title',term);node.setAttribute('aria-label',label+' \\u2014 '+term)}}\n"
        b"      function metric(label,value){var box=w.document.createElement('div'),key=w.document.createElement('span'),text=w.document.createElement('strong');box.className='mfModemMetric';key.className='mfModemMetricLabel';text.className='mfModemMetricValue';explainLabel(key,label);text.textContent=value;box.appendChild(key);box.appendChild(text);summary.appendChild(box)}",
        1,
        "Modem term titles",
    )
    old_summary = (
        b"        summary.textContent='';var rows=[['SIM',value.sim],['Registration',value.registration],['Radio',value.rat],['Engineering mode',value.engineeringMode],['Signal level',value.signalLevel],['Operator',value.operator],['PDP',value.pdp],['Band',value.band],['RSRP',value.rsrp],['RSRQ',value.rsrq],['SINR',value.sinr],['Battery',value.battery==='Not returned'?value.battery:value.battery+'%'],['Uplink',value.wanProto],['Connection time',value.connectionTime]];\n"
        b"        var optional=[['DL EARFCN',value.earfcn],['UL EARFCN',value.ulEarfcn],['PCI',value.pci],['DL bandwidth',value.bandwidth],['CQI',value.cqi],['Main RSRP',value.mainRsrp],['Diversity RSRP',value.diversityRsrp],['Main RSRQ',value.mainRsrq],['Diversity RSRQ',value.diversityRsrq],['UMTS PSC',value.umtsPsc],['UMTS ARFCN',value.umtsArfcn],['RSCP',value.rscp],['Ec/N0',value.ecno],['UMTS Tx power',value.txPower],['GSM ARFCN',value.gsmArfcn],['GSM signal',value.gsmSignal],['GSM quality',value.gsmQuality],['GSM timing advance',value.timingAdvance],['GPRS UL throughput',value.gprsUl],['GPRS DL throughput',value.gprsDl]];\n"
        b"        for(var o=0;o<optional.length;o++)if(optional[o][1]!=='Not returned')rows.push(optional[o]);"
    )
    new_summary = (
        b"        summary.textContent='';var rows=[['SIM',value.sim],['Registration',value.registration],['Radio',value.rat],['Engineering mode',value.engineeringMode],['Signal level',value.signalLevel],['Operator',value.operator],['PDP',value.pdp],['Battery',value.battery==='Not returned'?value.battery:value.battery+'%'],['Uplink',value.wanProto],['Connection time',value.connectionTime]];\n"
        b"        var optional=[['Band',value.band],['RSRP',value.rsrp],['RSRQ',value.rsrq],['SINR',value.sinr],['RSSI',value.rssi],['DL EARFCN',value.earfcn],['UL EARFCN',value.ulEarfcn],['PCI',value.pci],['DL bandwidth',value.bandwidth],['CQI',value.cqi],['Main RSRP',value.mainRsrp],['Diversity RSRP',value.diversityRsrp],['Main RSRQ',value.mainRsrq],['Diversity RSRQ',value.diversityRsrq],['UMTS PSC',value.umtsPsc],['UMTS ARFCN',value.umtsArfcn],['RSCP',value.rscp],['Ec/N0',value.ecno],['UMTS Tx power',value.txPower],['GSM ARFCN',value.gsmArfcn],['GSM signal',value.gsmSignal],['GSM quality',value.gsmQuality],['GSM timing advance',value.timingAdvance],['GPRS UL throughput',value.gprsUl],['GPRS DL throughput',value.gprsDl]],returned=0;\n"
        b"        for(var o=0;o<optional.length;o++)if(optional[o][1]!=='Not returned'){rows.push(optional[o]);returned++}if(!returned)rows.push(['Detailed radio metrics','Not returned']);"
    )
    data = _replace_count(data, old_summary, new_summary, 1, "concise Modem radio rows")
    data = _replace_count(
        data,
        b"if(!valid.length){line.setAttribute('points','');signalNow.textContent='No samples';fallback.textContent='No valid RSRP samples yet.';return}",
        b"if(!valid.length){line.setAttribute('points','');signalNow.textContent='No RSRP samples';fallback.textContent=session.latest&&session.latest.signalLevel!=='Not returned'?'RSRP was not returned. Signal level: '+session.latest.signalLevel+'.':'No valid RSRP samples yet.';return}",
        1,
        "Modem RSRP fallback",
    )
    data = _replace_count(
        data,
        b"rsrp:value.rsrp,rsrq:value.rsrq,sinr:value.sinr,rssi:value.rssi,",
        b"engineeringMode:value.engineeringMode,signalIndex:value.signalIndex,signalBars:value.signalBars,rsrp:value.rsrp,rsrq:value.rsrq,sinr:value.sinr,rssi:value.rssi,",
        1,
        "Modem sample evidence",
    )
    data = _replace_count(
        data,
        b"else setStatus(session.enabled?'Watching \xc2\xb7 next read in 30 seconds.':'Modem status updated.');",
        b"else if((value.engineeringMode==='Disabled'||value.engineeringMode==='Enabled')&&value.rsrp==='Not returned')setStatus((session.enabled?'Watching \xc2\xb7 next read in 30 seconds. ':'')+'Engineering mode is '+value.engineeringMode+'; RSRP was not returned.');else setStatus(session.enabled?'Watching \xc2\xb7 next read in 30 seconds.':'Modem status updated.');",
        1,
        "Modem Engineering-mode explanation",
    )
    data = _replace_count(
        data,
        b"refresh.addEventListener('click',function(){run(false)});copy.addEventListener('click',copyTrace);watch.addEventListener('change',function(){",
        b"terms.addEventListener('click',function(){var open=termsPanel.hidden;termsPanel.hidden=!open;terms.setAttribute('aria-expanded',open?'true':'false')});refresh.addEventListener('click',function(){run(false)});copy.addEventListener('click',copyTrace);watch.addEventListener('change',function(){",
        1,
        "Modem terms toggle",
    )
    return data


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        parent_replacements, parent_additions, removals = r24.build_patch_set(records, root)
    except r24.CommunityR24Error as exc:
        raise CommunityR25Error(str(exc)) from exc
    parent_replacements = dict(parent_replacements)
    parent_additions = dict(parent_additions)
    removals = set(removals)

    new_paths = {
        AUTH_PATH, BOOT_PATH, CSS_PATH, SMS_JS_PATH, SMS_HTML_PATH,
        DIAGNOSTICS_JS_PATH, DIAGNOSTICS_HTML_PATH, MODEM_JS_PATH,
        MODEM_HTML_PATH, DASHBOARD_JS_PATH, DASHBOARD_HTML_PATH,
        UTILS_PATH, LAYOUT_PATH, MENU_PATH, ENTRY_PATH,
    }
    if any(path in records or path in parent_additions for path in new_paths):
        raise CommunityR25Error("R2.5 cache-safe asset path already exists")

    replacements = dict(parent_replacements)
    replacements["www\\index.html"] = _revise(
        parent_replacements["www\\index.html"], "canonical Community link"
    )
    replacements["www\\html\\adminApp.html"] = _patch_admin_app(
        parent_replacements["www\\html\\adminApp.html"]
    )

    additions = {
        AUTH_PATH: _revise(parent_additions[r24.AUTH_PATH], "auth"),
        BOOT_PATH: _revise(parent_additions[r24.BOOT_PATH], "bootstrap"),
        CSS_PATH: _patch_css(parent_additions[r24.CSS_PATH]),
        SMS_JS_PATH: _patch_sms(parent_additions[r24.SMS_JS_PATH]),
        SMS_HTML_PATH: _revise(parent_additions[r24.SMS_HTML_PATH], "SMS page"),
        DIAGNOSTICS_JS_PATH: _patch_diagnostics(parent_additions[r24.DIAGNOSTICS_JS_PATH]),
        DIAGNOSTICS_HTML_PATH: _patch_diagnostics_html(parent_additions[r24.DIAGNOSTICS_HTML_PATH]),
        MODEM_JS_PATH: _patch_modem(parent_additions[r24.MODEM_JS_PATH]),
        MODEM_HTML_PATH: _patch_modem_html(parent_additions[r24.MODEM_HTML_PATH]),
        DASHBOARD_JS_PATH: _revise(parent_additions[r24.DASHBOARD_JS_PATH], "dashboard controller"),
        DASHBOARD_HTML_PATH: _patch_dashboard(parent_additions[r24.DASHBOARD_HTML_PATH]),
        UTILS_PATH: _revise(parent_additions[r24.UTILS_PATH], "private utility controller"),
        LAYOUT_PATH: _revise(parent_additions[r24.LAYOUT_PATH], "private menu loader"),
        MENU_PATH: parent_additions[r24.MENU_PATH],
        ENTRY_PATH: _revise(parent_additions[r24.ENTRY_PATH], "Community entry"),
    }

    if set(replacements) != set(r24.OUTPUT_RECORDS):
        raise CommunityR25Error("R2.5 replacement path set changed")
    if set(additions) != new_paths:
        raise CommunityR25Error("R2.5 addition path set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR25Error("R2.5 removed-locale set changed")
    if MARKER not in additions[DASHBOARD_HTML_PATH]:
        raise CommunityR25Error("R2.5 marker is absent from the dashboard")

    legacy_index = replacements["www\\index.html"]
    if legacy_index.count(b'href="/r25.html"') != 1 or b"r24.html" in legacy_index:
        raise CommunityR25Error("canonical entry does not bind exactly one R2.5 link")
    header = replacements["www\\html\\adminApp.html"]
    if header.count(b'id="mfCommunityHeaderLink"') != 1 or header.count(PROFILE.encode()) != 1:
        raise CommunityR25Error("shared header does not contain one exact Community entry")
    if b'href="/r25.html"' not in header:
        raise CommunityR25Error("shared header Community route is absent")
    for route in (
        b"r25boot.js", b"r25auth.js", b"r25diag.js", b"r25modem.js",
        b"r25sms.js", b"r25dash.js", b"r25ui.css", b"r25utils.js", b"r25layout.js",
    ):
        if route in legacy_index:
            raise CommunityR25Error("canonical entry loads Community functionality")
        if additions[ENTRY_PATH].count(route) != 1:
            raise CommunityR25Error("R2.5 entry does not bind each cache-safe asset once")
    if b"r24" in additions[ENTRY_PATH].lower():
        raise CommunityR25Error("R2.5 entry retains an R2.4 cache path")

    joined = b"\n".join([*replacements.values(), *additions.values()])
    for forbidden in (
        b"canary_logs", b"RestoreFw", b"SEND_USSD", b"+CUSD",
        b"wlan_cli_scan", b"wan/wifi/psk",
    ):
        if forbidden.lower() in joined.lower():
            raise CommunityR25Error("R2.5 includes an unavailable or forbidden capability")
    modem = additions[MODEM_JS_PATH]
    if b"PostXML" in modem or b"method=set" in modem or b"setInterval" in modem:
        raise CommunityR25Error("R2.5 Modem monitor contains a write or interval path")
    if b"Engineering_mode>1" in joined or b"Engineering_mode',1" in joined:
        raise CommunityR25Error("R2.5 enables Engineering mode")
    return replacements, additions, removals


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR25Error("R2.5 derived output records are not pinned; offline build remains disabled")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR25Error("R2.5 output record gate is incomplete")
    if set(ADDITION_OUTPUT_RECORDS) != set(additions):
        raise CommunityR25Error("R2.5 addition provenance gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR25Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR25Error(str(exc)) from exc
    return replacements, additions, removals
