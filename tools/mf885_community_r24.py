#!/usr/bin/env python3
"""Deterministic Community R2.4 patch set built on immutable R2.3.

R2.4 is re-derived from the exact reviewed golden through R2.3.  It keeps the
minimal canonical vendor login and moves every Community asset to a new cache-
safe path.  Its new Modem monitor is read-only; dormant stock WISP, USSD, TTL
and IMEI write paths are deliberately not activated.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r23 as r23


PROFILE = "0.2.4-community-r2"
MARKER = b"MF885 Community R2.4 Modem Monitor 0.2.4-community-r2"
REMOVED_RECORDS = r23.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r23.REMOVED_ARCHIVE_BYTES

AUTH_PATH = "www\\js\\r24auth.js"
BOOT_PATH = "www\\js\\r24boot.js"
CSS_PATH = "www\\css\\r24ui.css"
SMS_JS_PATH = "www\\js\\panel\\SMS\\r24sms.js"
SMS_HTML_PATH = "www\\html\\Community\\r24sms.html"
DIAGNOSTICS_JS_PATH = "www\\js\\r24diag.js"
DIAGNOSTICS_HTML_PATH = "www\\html\\Community\\r24diag.html"
MODEM_JS_PATH = "www\\js\\r24modem.js"
MODEM_HTML_PATH = "www\\html\\Community\\r24modem.html"
DASHBOARD_JS_PATH = "www\\js\\panel\\r24dash.js"
DASHBOARD_HTML_PATH = "www\\html\\Community\\r24dash.html"
UTILS_PATH = "www\\js\\r24utils.js"
LAYOUT_PATH = "www\\js\\r24layout.js"
MENU_PATH = "www\\xml\\r24ui.xml"
ENTRY_PATH = "www\\r24.html"

CUSTOM_FILES = {
    MODEM_HTML_PATH: (
        "firmware/community-r2.4/Modem.html",
        2_571,
        "58f027f4d540a9a2dd9de35142945a48b61a6cc958780939f64fd85044fb9b8b",
    ),
    MODEM_JS_PATH: (
        "firmware/community-r2.4/modem_monitor.js",
        25_164,
        "bed9c502dbd7c6c27549b3797e078214e8d9449abb424466e3ae3b9d4a5a8526",
    ),
}
CSS_ADDITION = (
    "firmware/community-r2.4/community_ui_additions.css",
    2_084,
    "c625f22962ae4d6acac64559cb7f82c9f84d1f89ec9bf85f38493f4c98ecd8e4",
)

OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_341, "7561d91c633b49038506394d167d1549ac26c1ab0367ebddb8045084cbfc3321"),
    "www\\index.html": (26_636, "d9d9c01f94da8732a2b1d8e25292b9fc953141885d0f6048d0c1b687c0e3df01"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    CSS_PATH: (12_927, "f51a01a46c420c5eba5d09cc4e3dd93502da94a79e01e16e46ce0717aae8c485", "derived R2.4 visual system plus pinned community_ui_additions.css c625f229…ecd8e4"),
    DASHBOARD_HTML_PATH: (10_241, "c3a80035683294f7bfa29b6b54c4fda0784bc98e97f4e990b25f22484008502b", "derived cache-safe R2.4 dashboard"),
    DIAGNOSTICS_HTML_PATH: (889, "de5f45243534756f0f0406c9a6f3af542d3e0ad8e1d4e08d66d409b744f9c0d4", "derived cache-safe Diagnostics page"),
    SMS_HTML_PATH: (2_014, "3abfc3139d92a133fc33239b91b279a679408aa7a217a10a4cc38a989dbbf04a", "derived cache-safe Messages page"),
    SMS_JS_PATH: (28_800, "f52abb2379e05ab112bc1dc64a3f16116b0b9a0358c9d643a63dd3d401e59450", "derived cache-safe SMS controller"),
    DASHBOARD_JS_PATH: (59_938, "31a9adc3e09310a224dad3e897cc25f09c743b877868590f6fa15d6deba32837", "derived cache-safe dashboard controller"),
    AUTH_PATH: (8_084, "0701e1c4b5411924da0544a05880676c7d67e27f87e58692cfc17c0d33b38637", "derived cache-safe tab authentication"),
    BOOT_PATH: (2_852, "de43aa5a8efe62db4ffa078b2971515bc98679cf0e7aad95d79f2fdb41d10f9f", "derived cache-safe labels and identity gate"),
    DIAGNOSTICS_JS_PATH: (16_696, "33e04129674d646243788c3d92c7a9aeb335383d00a8cbddd147635b6219c949", "derived cache-safe Diagnostics controller"),
    LAYOUT_PATH: (11_457, "f1eee0a11eda5cf29a1882c26c6af231210c39866b35641e0923f8056f5a346c", "derived private menu loader"),
    UTILS_PATH: (17_049, "89d341739d7483af45e7b0d3a058ca30b3c697d4d45675b818dc4efd48cf80e1", "derived private utility controller"),
    ENTRY_PATH: (26_969, "2884c7b899123a9075026dbdc0f614a42cd276d3a4cd6bb59283c5ab28ead52d", "derived cache-safe R2.4 entry document"),
    MENU_PATH: (3_002, "dacc4fc1efbf70085dcc115d354e3d77c06a07491402bf10d0e93c47d057478c", "derived private Community menu"),
}


class CommunityR24Error(Exception):
    pass


def _replace_count(data: bytes, old: bytes, new: bytes, count: int, label: str) -> bytes:
    if data.count(old) != count:
        raise CommunityR24Error(f"{label} anchor count changed")
    return data.replace(old, new)


def _load_exact(root: Path, source: str, size: int, digest: str) -> bytes:
    try:
        data = (root / source).read_bytes()
    except OSError as exc:
        raise CommunityR24Error(f"could not read exact Community R2.4 source {source}") from exc
    try:
        return r2.require_exact(data, size, digest, source)
    except r2.CommunityR2Error as exc:
        raise CommunityR24Error(str(exc)) from exc


def _load_custom(root: Path) -> tuple[dict[str, bytes], bytes]:
    custom = {
        target: _load_exact(root, source, size, digest)
        for target, (source, size, digest) in CUSTOM_FILES.items()
    }
    source, size, digest = CSS_ADDITION
    return custom, _load_exact(root, source, size, digest)


def _revise(data: bytes, label: str) -> bytes:
    """Move one R2.3 owned asset to its immutable R2.4 identity."""
    replacements = (
        (b"0.2.3-community-r2", b"0.2.4-community-r2"),
        (b"R2.3", b"R2.4"),
        (b"r23", b"r24"),
        (b"R23", b"R24"),
    )
    changed = 0
    for old, new in replacements:
        count = data.count(old)
        if count:
            data = data.replace(old, new)
            changed += count
    if not changed:
        raise CommunityR24Error(f"{label} has no R2.3 revision anchor")
    return data


def _patch_boot(data: bytes) -> bytes:
    data = _revise(data, "bootstrap")
    anchor = b"    jq.i18n.map.mDiagnostics='Diagnostics';\n"
    return _replace_count(
        data,
        anchor,
        anchor + b"    jq.i18n.map.mModemMonitor='Modem monitor';\n",
        1,
        "Modem menu label",
    )


def _patch_index(data: bytes) -> bytes:
    data = _revise(data, "Community entry")
    anchor = b'        <script type="text/javascript" src="js/r24diag.js" language="javascript"></script>\r\n'
    addition = anchor + b'        <script type="text/javascript" src="js/r24modem.js" language="javascript"></script>\r\n'
    return _replace_count(data, anchor, addition, 1, "Modem monitor loader")


def _patch_menu(data: bytes) -> bytes:
    anchor = b"\t\t\t<Menu id='mDiagnostics' implFunction='objDiagnostics' xmlName='status1' />\r\n"
    addition = anchor + b"\t\t\t<Menu id='mModemMonitor' implFunction='objModemMonitor' xmlName='status1' />\r\n"
    return _replace_count(data, anchor, addition, 1, "Modem monitor menu")


def _patch_sms(data: bytes) -> bytes:
    data = _revise(data, "SMS controller")
    anchor = b"    return state;\n  }\n\n  function opaqueRecordHash(value){"
    addition = (
        b"    return state;\n  }\n"
        b"  function modemReadBusy(){var state=w.MF885_COMMUNITY_R24_MODEM_SESSION;if(state&&state.document===w.document&&state.busy&&typeof state.releaseDetached==='function')state.releaseDetached();return !!(state&&state.document===w.document&&state.busy)}\n\n"
        b"  function opaqueRecordHash(value){"
    )
    data = _replace_count(data, anchor, addition, 1, "SMS Modem monitor gate")
    data = _replace_count(
        data,
        b"var writeBusy=busy||session.busy;",
        b"var writeBusy=busy||session.busy||modemReadBusy();",
        1,
        "SMS button serialization",
    )
    for old, new, count, label in (
        (
            b"if(busy||session.busy||session.locked||!identityMatched)return;",
            b"if(busy||session.busy||modemReadBusy()||session.locked||!identityMatched)return;",
            2,
            "SMS mutation submission serialization",
        ),
        (
            b"if(busy||session.busy||session.locked||!identityMatched||!profile.deletable||!historyComplete)return;",
            b"if(busy||session.busy||modemReadBusy()||session.locked||!identityMatched||!profile.deletable||!historyComplete)return;",
            1,
            "SMS Delete serialization",
        ),
        (
            b"if(busy||session.busy||session.locked||!identityMatched||composer.hidden)return;",
            b"if(busy||session.busy||modemReadBusy()||session.locked||!identityMatched||composer.hidden)return;",
            1,
            "SMS Send serialization",
        ),
    ):
        data = _replace_count(data, old, new, count, label)
    return data


def _patch_dashboard(data: bytes) -> bytes:
    data = _revise(data, "dashboard")
    data = _replace_count(
        data,
        b"MF885 Community R2.4 SMS Safe Diagnostics 0.2.4-community-r2",
        MARKER,
        1,
        "R2.4 dashboard marker",
    )
    anchor = b'<a href="#" onclick="dashboardOnClick(6,\'mDiagnostics\')">Diagnostics</a>'
    return _replace_count(
        data,
        anchor,
        anchor + b'<a href="#" onclick="dashboardOnClick(6,\'mModemMonitor\')">Modem monitor</a>',
        1,
        "dashboard Modem link",
    )


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        parent_replacements, parent_additions, removals = r23.build_patch_set(records, root)
    except r23.CommunityR23Error as exc:
        raise CommunityR24Error(str(exc)) from exc
    parent_replacements = dict(parent_replacements)
    parent_additions = dict(parent_additions)
    removals = set(removals)
    custom, css_addition = _load_custom(root)

    new_paths = {
        AUTH_PATH, BOOT_PATH, CSS_PATH, SMS_JS_PATH, SMS_HTML_PATH,
        DIAGNOSTICS_JS_PATH, DIAGNOSTICS_HTML_PATH, MODEM_JS_PATH,
        MODEM_HTML_PATH, DASHBOARD_JS_PATH, DASHBOARD_HTML_PATH,
        UTILS_PATH, LAYOUT_PATH, MENU_PATH, ENTRY_PATH,
    }
    if any(path in records or path in parent_additions for path in new_paths):
        raise CommunityR24Error("R2.4 cache-safe asset path already exists")

    replacements = dict(parent_replacements)
    replacements["www\\index.html"] = _revise(
        parent_replacements["www\\index.html"], "canonical Community link"
    )

    additions = {
        AUTH_PATH: _revise(parent_additions[r23.AUTH_PATH], "auth"),
        BOOT_PATH: _patch_boot(parent_additions[r23.BOOT_PATH]),
        CSS_PATH: _revise(parent_additions[r23.CSS_PATH], "visual system") + b"\n" + css_addition,
        SMS_JS_PATH: _patch_sms(parent_additions[r23.SMS_JS_PATH]),
        SMS_HTML_PATH: _revise(parent_additions[r23.SMS_HTML_PATH], "SMS page"),
        DIAGNOSTICS_JS_PATH: _revise(parent_additions[r23.DIAGNOSTICS_JS_PATH], "Diagnostics controller"),
        DIAGNOSTICS_HTML_PATH: _revise(parent_additions[r23.DIAGNOSTICS_HTML_PATH], "Diagnostics page"),
        MODEM_JS_PATH: custom[MODEM_JS_PATH],
        MODEM_HTML_PATH: custom[MODEM_HTML_PATH],
        DASHBOARD_JS_PATH: _revise(parent_additions[r23.DASHBOARD_JS_PATH], "dashboard controller"),
        DASHBOARD_HTML_PATH: _patch_dashboard(parent_additions[r23.DASHBOARD_HTML_PATH]),
        UTILS_PATH: _revise(parent_additions[r23.UTILS_PATH], "private utility controller"),
        LAYOUT_PATH: _revise(parent_additions[r23.LAYOUT_PATH], "private menu loader"),
        MENU_PATH: _patch_menu(parent_additions[r23.MENU_PATH]),
        ENTRY_PATH: _patch_index(parent_additions[r23.ENTRY_PATH]),
    }

    if set(replacements) != set(r23.OUTPUT_RECORDS):
        raise CommunityR24Error("R2.4 replacement path set changed")
    if set(additions) != new_paths:
        raise CommunityR24Error("R2.4 addition path set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR24Error("R2.4 removed-locale set changed")
    if MARKER not in additions[DASHBOARD_HTML_PATH]:
        raise CommunityR24Error("R2.4 marker is absent from the dashboard")

    legacy_index = replacements["www\\index.html"]
    if legacy_index.count(b'href="/r24.html"') != 1 or b"r23.html" in legacy_index:
        raise CommunityR24Error("canonical entry does not bind exactly one R2.4 link")
    for route in (
        b"r24boot.js", b"r24auth.js", b"r24diag.js", b"r24modem.js",
        b"r24sms.js", b"r24dash.js", b"r24ui.css", b"r24utils.js", b"r24layout.js",
    ):
        if route in legacy_index:
            raise CommunityR24Error("canonical entry loads Community functionality")
        if additions[ENTRY_PATH].count(route) != 1:
            raise CommunityR24Error("R2.4 entry does not bind each cache-safe asset once")
    if b"r23" in additions[ENTRY_PATH].lower():
        raise CommunityR24Error("R2.4 entry retains an R2.3 cache path")
    if additions[MENU_PATH].count(b"mModemMonitor") != 1:
        raise CommunityR24Error("R2.4 menu does not contain one Modem monitor")

    joined = b"\n".join([*replacements.values(), *additions.values()])
    for forbidden in (b"canary_logs", b"RestoreFw", b"SEND_USSD", b"+CUSD", b"wlan_cli_scan", b"wan/wifi/psk"):
        if forbidden.lower() in joined.lower():
            raise CommunityR24Error("R2.4 includes an unavailable or forbidden capability")
    modem = additions[MODEM_JS_PATH]
    if b"PostXML" in modem or b"method=set" in modem or b"setInterval" in modem:
        raise CommunityR24Error("R2.4 Modem monitor contains a write or interval path")
    return replacements, additions, removals


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR24Error("R2.4 derived output records are not pinned; offline build remains disabled")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR24Error("R2.4 output record gate is incomplete")
    derived_additions = set(additions) - set(CUSTOM_FILES)
    if set(ADDITION_OUTPUT_RECORDS) != derived_additions:
        raise CommunityR24Error("R2.4 addition provenance gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR24Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR24Error(str(exc)) from exc
    return replacements, additions, removals
