#!/usr/bin/env python3
"""Deterministic Community R2.3 patch set built on immutable R2.2.

R2.3 is always re-derived from the reviewed 2.5.94 / Ver.D golden through the
exact R2.2 transformer.  R2.2 records, sources and live-delivery helpers remain
untouched.  Until the final derived record pins are filled after an independent
offline build review, ``build_patch_set`` fails closed.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r21 as r21
import mf885_community_r22 as r22


PROFILE = "0.2.3-community-r2"
MARKER = b"MF885 Community R2.3 SMS Safe Diagnostics 0.2.3-community-r2"
REMOVED_RECORDS = r22.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r22.REMOVED_ARCHIVE_BYTES

AUTH_PATH = "www\\js\\r23auth.js"
BOOT_PATH = "www\\js\\r23boot.js"
CSS_PATH = "www\\css\\r23ui.css"
SMS_JS_PATH = "www\\js\\panel\\SMS\\r23sms.js"
SMS_HTML_PATH = "www\\html\\Community\\r23sms.html"
DIAGNOSTICS_JS_PATH = "www\\js\\r23diag.js"
DIAGNOSTICS_HTML_PATH = "www\\html\\Community\\r23diag.html"
DASHBOARD_JS_PATH = "www\\js\\panel\\r23dash.js"
DASHBOARD_HTML_PATH = "www\\html\\Community\\r23dash.html"
UTILS_PATH = "www\\js\\r23utils.js"
LAYOUT_PATH = "www\\js\\r23layout.js"
MENU_PATH = "www\\xml\\r23ui.xml"
ENTRY_PATH = "www\\r23.html"

CUSTOM_FILES = {
    BOOT_PATH: (
        "firmware/community-r2.3/community_bootstrap.js",
        2_805,
        "4ae296f1594f2d1545311fbc03f67158698890eb23b5231bf37efce833479830",
    ),
    CSS_PATH: (
        "firmware/community-r2.3/community_ui.css",
        10_842,
        "c2a4d6e16653806ff05e586ff34f94869586f1f1d339ad35855c0d2dbe41beaf",
    ),
    SMS_HTML_PATH: (
        "firmware/community-r2.3/SMS.html",
        2_014,
        "a285be74f10b5db7e0bf58bcacac2c7f4df4f3de667daca0272bcbfdd867d144",
    ),
    SMS_JS_PATH: (
        "firmware/community-r2.3/SMS.js",
        28_466,
        "4136c2c3a8dca19c9fd206d588526fd7d00f2021ed031e4d4d83a65ba8ae17ef",
    ),
    DIAGNOSTICS_HTML_PATH: (
        "firmware/community-r2.3/Diagnostics.html",
        889,
        "a4a7a778efeb5088cd85b21d42c36713b93261a1b9acf26121cf262ba9091add",
    ),
}

# Exact outputs derived from the immutable R2.2 patch set and reviewed golden
# anchors.  Direct R2.3 sources remain separately pinned in CUSTOM_FILES.
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\adminApp.html": (4_341, "7561d91c633b49038506394d167d1549ac26c1ab0367ebddb8045084cbfc3321"),
    "www\\index.html": (26_636, "5b34426bf905fc6ad386245cedbebeff4efb1d44d793756ffdfb4c3bdc366f84"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (16_873, "5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
}
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    "www\\html\\Community\\r23dash.html": (10_173, "5e50b5d90eb36a8b7703fc05fb305abc7bfed5ea4a7daa282b7722144e735818", "derived R2.3 dashboard copy"),
    "www\\js\\panel\\r23dash.js": (59_938, "684d7e0d874251ac8c6aa9f6ca934fa2220414b2a3234202e4ee9605ea0d2b34", "derived cache-safe dashboard controller"),
    "www\\js\\r23auth.js": (8_084, "2a5e1e521b701d22ad46f9e3ab12880206e06676581125e71a7f1f9897619b27", "derived cache-safe tab authentication"),
    "www\\js\\r23diag.js": (16_696, "c59f82de793db764c9f0e860867d2fe7a1cadd339f95d67c5004687c3173924f", "derived cache-safe Diagnostics controller"),
    "www\\js\\r23layout.js": (11_457, "bc863d890683c36d3551aec00ee0427a1dc7937353153f0a3245f88caf9ea457", "derived private menu loader"),
    "www\\js\\r23utils.js": (17_049, "17b4d58708d36e9b55c4cb4e533466c40d55e55f21b7475750350dade2076a19", "derived private utility controller"),
    "www\\r23.html": (26_876, "c3b41dcfe7a74c0aee7870f3a5391f05b2187252a58ad3365aa2e36674cbd645", "derived cache-safe R2.3 entry document"),
    "www\\xml\\r23ui.xml": (2_921, "c8d54dca3fda4b9c4f9b9b470c680d1d354f69673c257aa2d024f4fb93403d23", "derived private Community menu"),
}


class CommunityR23Error(Exception):
    pass


def _replace_count(data: bytes, old: bytes, new: bytes, count: int, label: str) -> bytes:
    if data.count(old) != count:
        raise CommunityR23Error(f"{label} anchor count changed")
    return data.replace(old, new)


def _load_exact(root: Path, source: str, size: int, digest: str) -> bytes:
    try:
        data = (root / source).read_bytes()
    except OSError as exc:
        raise CommunityR23Error(f"could not read exact Community R2.3 source {source}") from exc
    try:
        return r2.require_exact(data, size, digest, source)
    except r2.CommunityR2Error as exc:
        raise CommunityR23Error(str(exc)) from exc


def _load_custom(root: Path) -> dict[str, bytes]:
    return {
        target: _load_exact(root, source, size, digest)
        for target, (source, size, digest) in CUSTOM_FILES.items()
    }


def _derive_auth(data: bytes) -> bytes:
    data = _replace_count(data, b"Community R2.2", b"Community R2.3", 1, "auth revision")
    data = _replace_count(data, b"0.2.2-community-r2", b"0.2.3-community-r2", 2, "auth identity")
    return _replace_count(data, b"MF885CommunityR22", b"MF885CommunityR23", 3, "auth identity helper")


def _derive_diagnostics(data: bytes) -> bytes:
    data = _replace_count(data, b"Community R2.2", b"Community R2.3", 1, "Diagnostics revision")
    data = _replace_count(data, b"0.2.2-community-r2", b"0.2.3-community-r2", 2, "Diagnostics identity")
    data = _replace_count(data, b"MF885CommunityR22", b"MF885CommunityR23", 2, "Diagnostics identity helper")
    data = _replace_count(data, b"html/Community/r22diag.html", b"html/Community/r23diag.html", 1, "Diagnostics HTML route")
    return _replace_count(
        data,
        b"root.innerHTML=w.callProductHTML('html/Community/r23diag.html');",
        b"root.innerHTML=w.callProductHTML('html/Community/r23diag.html');if(w.MF885CommunityR23&&typeof w.MF885CommunityR23.markRoot==='function')w.MF885CommunityR23.markRoot();",
        1,
        "Diagnostics visual root",
    )


def _derive_dashboard_script(data: bytes) -> bytes:
    return _replace_count(data, b"html/Community/r22dash.html", b"html/Community/r23dash.html", 1, "dashboard HTML route")


def _patch_modern_utils(data: bytes) -> bytes:
    return _replace_count(
        data,
        b'window.location="index.html";',
        b'window.location="/r23.html";',
        1,
        "cache-safe logout and timeout landing",
    )


def _derive_layout(data: bytes) -> bytes:
    return _replace_count(
        data,
        b'callXML("xml/ui_" + g_platformName + ".xml",parseXml);',
        b'callXML("xml/r23ui.xml",parseXml);',
        1,
        "R2.3 private menu route",
    )


def _patch_legacy_utils(data: bytes) -> bytes:
    data = r2.replace_region(
        data,
        b"    if(getCookie('locale')=='')\r\n",
        b'    var host = window.location.protocol + "//" + window.location.host + "/";',
        b'    htmlFilename = "help_en.html";\r\n',
        "legacy context Help locale",
    )
    return r2.replace_region(
        data,
        b"    if (getCookie('locale') == '')\r\n",
        b'    var host = window.location.protocol + "//" + window.location.host + "/";',
        b'    htmlFilename = "help_en.html?name=" + _temp[0] + "&version=" + _temp[1];\r\n',
        "legacy main Help locale",
    )


def _patch_legacy_index(data: bytes) -> bytes:
    data = r2.replace_region(
        data,
        b"            function setLocale(value){",
        b"\t\t\tfunction Indexstatusshow(){",
        b'''            function setLocale(value){\r
                setCookie("locale","en",365);\r
                setLocalization("en");\r
                zmlb="images/logo_blue_en.png";\r
                zml="images/logo_en.png";\r
                $("#zlogoblue").attr("src",zmlb);\r
                displayControls();\r
                document.getElementById("tbarouter_password").focus();\r
                document.getElementById("btnSignIn").disabled = false;\r
            }\r
''',
        "legacy English locale function",
    )
    data = r2.replace_region(
        data,
        b'\t\t\t\tif(sim_status == "1"){',
        b'\t\t\t\telse if (NW_register_status == "2"){',
        b'''\t\t\t\tif(sim_status == "1"){\r
                    document.getElementById("iindexstatusimg").src = "images/nosimc_en.png";\r
                }\r
''',
        "legacy English no-SIM image",
    )
    data = r2.replace_region(
        data,
        b'          var xml = callProductXML("locale");',
        b'         $("#zlogoblue").attr("src",zmlb);',
        b'''          var xml = callProductXML("locale");\r
         var zhard_ver = $(xml).find("hardware_version").text();\r
         zmlb="images/logo_blue_en.png";\r
         zml="images/logo_en.png";\r
         setLocalization("en");\r
         setCookie("locale", "en", 365);\r
''',
        "legacy English init locale",
    )
    lines = data.splitlines(keepends=True)
    switch_count = 0
    for index, line in enumerate(lines):
        token = b'document.getElementById("langswitch").innerHTML='
        if token in line:
            newline = b"\r\n" if line.endswith(b"\r\n") else b"\n"
            indent = line[: len(line) - len(line.lstrip())]
            lines[index] = indent + token + b'"English";' + newline
            switch_count += 1
    if switch_count != 4:
        raise CommunityR23Error("legacy language-switch branch count changed")
    data = b"".join(lines)
    button_anchor = (
        b'                    <input name="" type="button" class="button" '
        b'id="btnSignIn" value="\xe7\x99\xbb\xe5\xbd\x95" onclick=\'Login()\' disabled=""/>'
    )
    replacement = (
        b'                    <input name="" type="button" class="button" '
        b'id="btnSignIn" value="Sign In" onclick=\'Login()\' disabled=""/>\r\n'
        b'                    <a id="mfFreshUiLink" href="/r23.html" '
        b'style="display:block;margin:10px 0 0;text-align:center">Open updated interface</a>'
    )
    data = _replace_count(data, button_anchor, replacement, 1, "legacy modern-interface link")
    return _replace_count(data, b">\xe8\xae\xbf\xe9\x97\xae\xe5\xae\x98\xe7\xbd\x91</a>", b">Official website</a>", 1, "legacy English home link")


def _patch_index(data: bytes) -> bytes:
    data = _replace_count(
        data,
        b'        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">\r\n',
        b'        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">\r\n'
        b'        <meta name="viewport" content="width=device-width, initial-scale=1">\r\n'
        b'        <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">\r\n'
        b'        <meta http-equiv="Pragma" content="no-cache">\r\n'
        b'        <meta http-equiv="Expires" content="0">\r\n',
        1,
        "responsive cache-safe document metadata",
    )
    routes = (
        (b"js/r22boot.js", b"js/r23boot.js", "bootstrap route"),
        (b"js/r22auth.js", b"js/r23auth.js", "auth route"),
        (b"js/r22diag.js", b"js/r23diag.js", "Diagnostics route"),
        (b"js/panel/SMS/r22sms.js", b"js/panel/SMS/r23sms.js", "SMS route"),
        (b"js/panel/r22dash.js", b"js/panel/r23dash.js", "dashboard route"),
        (b"css/r22ui.css", b"css/r23ui.css", "stylesheet route"),
    )
    for old, new, label in routes:
        data = _replace_count(data, old, new, 1, label)
    data = _replace_count(data, b'src="js/base/utils.js"', b'src="js/r23utils.js"', 1, "private utility route")
    data = _replace_count(data, b'src="js/base/layout_manager.js"', b'src="js/r23layout.js"', 1, "private menu loader route")
    old_remember = b'''                    <label class="mfRememberRow" for="mfRememberTab"><input type="checkbox" id="mfRememberTab" /> <span>Remember me in this tab</span></label>\r
                    <small class="mfRememberHelp">Refreshes will sign in automatically. This tab stores a password-equivalent Digest key, not the password itself. Ten minutes without keyboard, touch or mouse activity clears it; signing out or closing the tab normally clears it. Scripts loaded by this page can read it, so use this only on a trusted device.</small>\r
'''
    new_remember = b'''                    <label class="mfRememberRow" for="mfRememberTab"><input type="checkbox" id="mfRememberTab" />Remember this tab</label>\r
                    <small class="mfRememberHelp">Keeps refreshes signed in with a password-equivalent key. Sign out or close the tab to clear it.</small>\r
                    <a id="mfFreshUiLink" class="mfFreshUiLink" href="/r23.html">Open updated interface</a>\r
'''
    data = _replace_count(data, old_remember, new_remember, 1, "compact Remember markup")
    return _replace_count(data, b"MF885CommunityR22.seedLabels();", b"MF885CommunityR23.seedLabels();", 2, "R2.3 label seed")


def _patch_dashboard(data: bytes) -> bytes:
    old = b'''            <!-- MF885 Community R2.2 SMS Safe Diagnostics 0.2.2-community-r2 -->\r
            <div id="mfCommunityDashboard">\r
              <span class="mfCommunityBuild">Community R2.2</span>\r
              <span class="mfCommunityBase">base 2.5.94</span>\r
              <span class="mfCommunityDashboardActions"><a href="#" onclick="dashboardOnClick(5,'mDeviceInbox')">Messages</a><a href="#" onclick="dashboardOnClick(6,'mDiagnostics')">Diagnostics</a></span>\r
            </div>\r
'''
    new = b'''            <!-- MF885 Community R2.3 SMS Safe Diagnostics 0.2.3-community-r2 -->\r
            <div id="mfCommunityDashboard">\r
              <span class="mfCommunityBuild">Community UI</span>\r
              <span class="mfCommunityBase">base 2.5.94</span>\r
              <span class="mfCommunityDashboardActions"><a href="#" onclick="dashboardOnClick(5,'mDeviceInbox')">Messages</a><a href="#" onclick="dashboardOnClick(6,'mDiagnostics')">Diagnostics</a></span>\r
            </div>\r
'''
    return _replace_count(data, old, new, 1, "R2.3 dashboard badge")


def _derive_unpinned_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        modern_replacements, parent_additions, removals = r22.build_patch_set(records, root)
    except r22.CommunityR22Error as exc:
        raise CommunityR23Error(str(exc)) from exc
    modern_replacements = dict(modern_replacements)
    parent_additions = dict(parent_additions)
    removals = set(removals)
    custom = _load_custom(root)

    new_paths = {
        AUTH_PATH, BOOT_PATH, CSS_PATH, SMS_JS_PATH, SMS_HTML_PATH,
        DIAGNOSTICS_JS_PATH, DIAGNOSTICS_HTML_PATH, DASHBOARD_JS_PATH,
        DASHBOARD_HTML_PATH, UTILS_PATH, LAYOUT_PATH, MENU_PATH, ENTRY_PATH,
    }
    if any(path in records or path in parent_additions for path in new_paths):
        raise CommunityR23Error("R2.3 cache-safe asset path already exists")

    parent_auth = parent_additions[r22.AUTH_PATH]
    parent_diagnostics = parent_additions[r22.DIAGNOSTICS_JS_PATH]
    parent_dashboard_script = parent_additions[r22.DASHBOARD_JS_PATH]
    modern_index = _patch_index(modern_replacements["www\\index.html"])
    modern_utils = _patch_modern_utils(modern_replacements["www\\js\\base\\utils.js"])
    modern_dashboard = _patch_dashboard(modern_replacements["www\\html\\dashboard.html"])

    # The canonical vendor entry remains deliberately plain.  Its only new
    # product link opens the versioned Community entry; the other replacements
    # are the minimum English-only fallbacks/copy fixes required after removing
    # the three unused locale packs.
    replacements = {
        "www\\index.html": _patch_legacy_index(records["www\\index.html"]),
        "www\\js\\base\\utils.js": _patch_legacy_utils(records["www\\js\\base\\utils.js"]),
        "www\\js\\base\\ajax_calls.js": r2.patch_ajax(records["www\\js\\base\\ajax_calls.js"]),
        "www\\html\\adminApp.html": r2.patch_admin_app(records["www\\html\\adminApp.html"]),
        "www\\properties\\Messages_en.properties": r2.patch_properties(records["www\\properties\\Messages_en.properties"]),
        "www\\help_en.html": r2.patch_help(records["www\\help_en.html"]),
    }
    additions: dict[str, bytes] = {}
    additions[AUTH_PATH] = _derive_auth(parent_auth)
    additions[BOOT_PATH] = custom[BOOT_PATH]
    additions[CSS_PATH] = custom[CSS_PATH]
    additions[SMS_JS_PATH] = custom[SMS_JS_PATH]
    additions[SMS_HTML_PATH] = custom[SMS_HTML_PATH]
    additions[DIAGNOSTICS_JS_PATH] = _derive_diagnostics(parent_diagnostics)
    additions[DIAGNOSTICS_HTML_PATH] = custom[DIAGNOSTICS_HTML_PATH]
    additions[DASHBOARD_JS_PATH] = _derive_dashboard_script(parent_dashboard_script)
    additions[DASHBOARD_HTML_PATH] = modern_dashboard
    additions[UTILS_PATH] = modern_utils
    additions[LAYOUT_PATH] = _derive_layout(records["www\\js\\base\\layout_manager.js"])
    additions[MENU_PATH] = modern_replacements["www\\xml\\ui_mifi.xml"]
    additions[ENTRY_PATH] = modern_index

    expected_replacements = {
        "www\\index.html", "www\\js\\base\\utils.js",
        "www\\js\\base\\ajax_calls.js", "www\\html\\adminApp.html",
        "www\\properties\\Messages_en.properties", "www\\help_en.html",
    }
    if set(replacements) != expected_replacements:
        raise CommunityR23Error("R2.3 replacement path set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR23Error("R2.3 removed-locale set changed")
    if set(additions) != new_paths:
        raise CommunityR23Error("R2.3 addition path set changed")
    if MARKER not in additions[DASHBOARD_HTML_PATH]:
        raise CommunityR23Error("R2.3 marker is absent from the dashboard")

    joined = b"\n".join([*replacements.values(), *additions.values()])
    # The reviewed stock menu still contains its historical detailed_log
    # route.  R2.3 neither loads nor extends it; owned-source tests enforce
    # that boundary.  Keep truly new/active unsafe capabilities out here.
    for forbidden in (b"canary_logs", b"RestoreFw", b"SEND_USSD", b"+CUSD"):
        if forbidden.lower() in joined.lower():
            raise CommunityR23Error("R2.3 includes an unavailable or forbidden capability")
    legacy_index = replacements["www\\index.html"]
    if legacy_index.count(b'href="/r23.html"') != 1:
        raise CommunityR23Error("legacy entry must expose exactly one Community link")
    for route in (b"r23boot.js", b"r23auth.js", b"r23diag.js", b"r23sms.js", b"r23dash.js", b"r23ui.css", b"r23utils.js", b"r23layout.js"):
        if route in legacy_index:
            raise CommunityR23Error("legacy entry loads Community functionality")
    index = additions[ENTRY_PATH]
    for route in (b"r23boot.js", b"r23auth.js", b"r23diag.js", b"r23sms.js", b"r23dash.js", b"r23ui.css", b"r23utils.js", b"r23layout.js"):
        if index.count(route) != 1:
            raise CommunityR23Error("R2.3 index does not bind each cache-safe asset once")
    if any(route in index for route in (b"r22boot.js", b"r22auth.js", b"r22diag.js", b"r22sms.js", b"r22dash.js", b"r22ui.css")):
        raise CommunityR23Error("R2.3 index still binds an R2.2 cache-safe asset")
    return replacements, additions, removals


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    replacements, additions, removals = _derive_unpinned_patch_set(records, root)
    if not OUTPUT_RECORDS or not ADDITION_OUTPUT_RECORDS:
        raise CommunityR23Error("R2.3 derived output records are not pinned; offline build remains disabled")
    if set(OUTPUT_RECORDS) != set(replacements):
        raise CommunityR23Error("R2.3 output record gate is incomplete")
    derived_additions = set(additions) - set(CUSTOM_FILES)
    if set(ADDITION_OUTPUT_RECORDS) != derived_additions:
        raise CommunityR23Error("R2.3 addition provenance gate is incomplete")
    for path, (size, digest) in OUTPUT_RECORDS.items():
        try:
            r2.require_exact(replacements[path], size, digest, f"derived {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR23Error(str(exc)) from exc
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR23Error(str(exc)) from exc
    return replacements, additions, removals
