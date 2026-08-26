#!/usr/bin/env python3
"""Deterministic Community R2.2 patch set built on immutable R2.1.

R2.2 is rebuilt directly from the reviewed 2.5.94 / Ver.D golden.  The R2.1
transformer is used only as an exact, pinned parent derivation; this module
then adds cache-safe asset names, the strict live status1 identity gate and a
small legacy-browser visual system.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2
import mf885_community_r21 as r21


PROFILE = "0.2.2-community-r2"
MARKER = b"MF885 Community R2.2 SMS Safe Diagnostics 0.2.2-community-r2"
PARENT_AUTH_PATH = r21.AUTH_PATH
AUTH_PATH = "www\\js\\r22auth.js"
REMOVED_RECORDS = r21.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r21.REMOVED_ARCHIVE_BYTES

BOOT_PATH = "www\\js\\r22boot.js"
CSS_PATH = "www\\css\\r22ui.css"
SMS_JS_PATH = "www\\js\\panel\\SMS\\r22sms.js"
SMS_HTML_PATH = "www\\html\\Community\\r22sms.html"
DIAGNOSTICS_JS_PATH = "www\\js\\r22diag.js"
DIAGNOSTICS_HTML_PATH = "www\\html\\Community\\r22diag.html"
DASHBOARD_JS_PATH = "www\\js\\panel\\r22dash.js"
DASHBOARD_HTML_PATH = "www\\html\\Community\\r22dash.html"

CUSTOM_FILES = {
    BOOT_PATH: (
        "firmware/community-r2.2/community_bootstrap.js",
        2_327,
        "8a868f139ed052ddffc60b1ba3782480c6d631d1fd008b3825ac0c023fb8c05d",
    ),
    CSS_PATH: (
        "firmware/community-r2.2/community_ui.css",
        3_950,
        "6bceff4ee6bf23716611741d09760afd161d092e7601a811a03b5173e70cc2c0",
    ),
    SMS_HTML_PATH: (
        "firmware/community-r2.2/SMS.html",
        1_976,
        "4830cfb2ddb36b97f86c9b84f8f219930ad9d9120321ac2be99ed8a49490d1aa",
    ),
    DIAGNOSTICS_HTML_PATH: (
        "firmware/community-r2.2/Diagnostics.html",
        955,
        "3a7bf999f3aa4dd9f1c610e67f41db65251d8bf431d2c71fe583b08e680f831d",
    ),
}

# Exact derived replacements.  Additions are pinned by their source or by the
# exact parent-source transformation above.
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\SMS\\SMS.html": (2_272, "4f7b215ff00e0001bc83ddae9a9d4c4f15224a997a514a7e6d6bee8e92ca769e"),
    "www\\html\\adminApp.html": (4_341, "7561d91c633b49038506394d167d1549ac26c1ab0367ebddb8045084cbfc3321"),
    "www\\html\\dashboard.html": (10_175, "1e4ac14a8feaa47c2fea1b43b18ac6550aead9e211f842f2db9ebb1de979f3dc"),
    "www\\index.html": (26_739, "cff247f939effcc1b854c9169750d4ec4574997c0165b005beb125df6da334e9"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (17_050, "67c335b9626deb7e9ec5c3c789814415dd6759fac12700bb41e22d9a7abe6756"),
    "www\\js\\panel\\SMS\\SMS.js": (19_450, "8ce3f06d2fd1620d74bd9efe2b19ca4143ab349941ec5637b90d7738723327cd"),
    "www\\properties\\Messages_en.properties": (47_001, "5f6426f6d50c0e3a6a602990b0d7d70643043b98169db3b8f4cd5af5e8e31f8f"),
    "www\\xml\\ui_mifi.xml": (2_921, "c8d54dca3fda4b9c4f9b9b470c680d1d354f69673c257aa2d024f4fb93403d23"),
}

# Final bytes for additions that are inherited from R2.1 or derived from its
# exact reviewed sources.  CUSTOM_FILES already covers the four direct R2.2
# source additions; this map makes the remaining five additions explicit in
# both the build gate and the private provenance report.
ADDITION_OUTPUT_RECORDS: dict[str, tuple[int, str, str]] = {
    AUTH_PATH: (
        8_084,
        "4a820b497262c53d0e30ce11bf81125bd2532edeb80507d2a8262113ca2af01f",
        "derived from exact reviewed Community R2 auth source anchors",
    ),
    r21.DIAGNOSTICS_HTML_PATH: (
        r21.CUSTOM_FILES[r21.DIAGNOSTICS_HTML_PATH][1],
        r21.CUSTOM_FILES[r21.DIAGNOSTICS_HTML_PATH][2],
        r21.CUSTOM_FILES[r21.DIAGNOSTICS_HTML_PATH][0],
    ),
    r21.DIAGNOSTICS_JS_PATH: (
        r21.CUSTOM_FILES[r21.DIAGNOSTICS_JS_PATH][1],
        r21.CUSTOM_FILES[r21.DIAGNOSTICS_JS_PATH][2],
        r21.CUSTOM_FILES[r21.DIAGNOSTICS_JS_PATH][0],
    ),
    SMS_JS_PATH: (
        19_148,
        "601c01239346fe02e051cc19e8b67c3a4cd3baa48eebf0b8c95dd0e8c777b599",
        "derived from exact reviewed Community R2.1 SMS source anchors",
    ),
    DIAGNOSTICS_JS_PATH: (
        16_592,
        "ecca26d09a4ac2b00a1aa209043760df0df1d2dd4d7cfd8215bdd74f0ca066ff",
        "derived from exact reviewed Community R2.1 Diagnostics source anchors",
    ),
    DASHBOARD_HTML_PATH: (
        10_175,
        "1e4ac14a8feaa47c2fea1b43b18ac6550aead9e211f842f2db9ebb1de979f3dc",
        "derived from exact reviewed golden dashboard anchors",
    ),
    DASHBOARD_JS_PATH: (
        59_938,
        "a49ea2480acf2e05edfb40096a49b59c9d0fa59ec9431624cb6c119d4c1f02a9",
        "derived from exact reviewed golden dashboard controller",
    ),
}


class CommunityR22Error(Exception):
    pass


def _replace_count(data: bytes, old: bytes, new: bytes, count: int, label: str) -> bytes:
    if data.count(old) != count:
        raise CommunityR22Error(f"{label} anchor count changed")
    return data.replace(old, new)


def _load_exact(root: Path, source: str, size: int, digest: str) -> bytes:
    try:
        data = (root / source).read_bytes()
    except OSError as exc:
        raise CommunityR22Error(f"could not read exact Community R2.2 source {source}") from exc
    try:
        return r2.require_exact(data, size, digest, source)
    except r2.CommunityR2Error as exc:
        raise CommunityR22Error(str(exc)) from exc


def _load_custom(root: Path) -> dict[str, bytes]:
    return {
        target: _load_exact(root, source, size, digest)
        for target, (source, size, digest) in CUSTOM_FILES.items()
    }


def _load_parent_source(root: Path, target: str) -> bytes:
    source, size, digest = r21.CUSTOM_FILES[target]
    return _load_exact(root, source, size, digest)


def _derive_auth(root: Path) -> bytes:
    data = _load_parent_source(root, PARENT_AUTH_PATH)
    data = _replace_count(
        data,
        b"Community R2 tab-scoped Digest session 0.2-community-r2",
        b"Community R2.2 tab-scoped Digest session 0.2.2-community-r2",
        1,
        "auth revision",
    )
    data = _replace_count(
        data,
        b'id: "0.2-community-r2"',
        b'id: "0.2.2-community-r2"',
        1,
        "auth component identity",
    )
    old_gate = b'''    if (!xml || !xml.documentElement ||\n        String(xml.documentElement.nodeName).toUpperCase() !== "RGW") return false;\n    if (w.jQuery(xml).find("login_status").text()) return false;\n    return w.jQuery(xml).find("sysinfo hardware_version").text() === "MF96 Ver.D" &&\n      w.jQuery(xml).find("sysinfo version_num").text() ===\n        "2.5.94_release_MF855_NZ_CP_2.129.003";\n'''
    new_gate = b'''    if (!xml || !w.MF885CommunityR22 ||\n        typeof w.MF885CommunityR22.exactStatus1Identity !== "function") return false;\n    if (w.jQuery(xml).find("login_status").text()) return false;\n    try {\n      return w.MF885CommunityR22.exactStatus1Identity(xml) === true;\n    } catch (error) {\n      return false;\n    }\n'''
    return _replace_count(data, old_gate, new_gate, 1, "strict auth identity gate")


def _derive_sms(root: Path) -> bytes:
    data = _load_parent_source(root, "www\\js\\panel\\SMS\\SMS.js")
    data = _replace_count(data, b"R2.1", b"R2.2", 1, "SMS revision")
    data = _replace_count(data, b"R21", b"R22", 4, "SMS runtime namespace")
    data = _replace_count(
        data,
        b"0.2.1-community-r2",
        b"0.2.2-community-r2",
        3,
        "SMS component identity",
    )
    data = _replace_count(
        data,
        b"html/SMS/SMS.html",
        b"html/Community/r22sms.html",
        1,
        "SMS cache-safe HTML path",
    )
    old_identity = b"""      function checkIdentity(){\n        try{\n          var doc=asDocument(w.callProductXML('status1')),model=text(doc,'model'),version=text(doc,'version_num');\n          var hardware=typeof w.getHardware_Version==='function'?String(w.getHardware_Version()||''):'';\n          identityMatched=/^(?:LV01|MF885)$/i.test(model)&&/^2\\.5\\.94(?:_|$)/.test(version)&&/(?:^|\\s)Ver\\.?\\s*D(?:$|\\s)/i.test(hardware);\n        }catch(_){identityMatched=false}\n        if(!identityMatched)setStatus('Read-only mode: exact MF885 / Ver.D / 2.5.94 identity was not proven.',true);\n        updateButtons();return identityMatched;\n      }\n"""
    new_identity = b"""      function checkIdentity(){\n        try{identityMatched=!!(w.MF885CommunityR22&&w.MF885CommunityR22.exactStatus1Identity(w.callProductXML('status1')))}catch(_){identityMatched=false}\n        if(!identityMatched)setStatus('Read-only mode: exact MF885 / Ver.D / 2.5.94 identity was not proven.',true);\n        updateButtons();return identityMatched;\n      }\n"""
    data = _replace_count(data, old_identity, new_identity, 1, "strict SMS identity gate")
    style_replacements = (
        (b"card.style.cssText='border:1px solid #d0d5dd;border-radius:10px;padding:10px;margin:8px 0'", b"card.className='mfCommunityMessage'", "SMS card class"),
        (b"summary.style.cursor='pointer'", b"summary.className='mfCommunityMessageSummary'", "SMS summary class"),
        (b"received.style.cssText='font-size:12px;color:#667085;margin-left:8px'", b"received.className='mfCommunityMessageDate'", "SMS date class"),
        (b"content.style.cssText='white-space:pre-wrap;margin-top:10px'", b"content.className='mfCommunityMessageBody'", "SMS content class"),
        (b"del.style.marginTop='10px'", b"del.className='mfCommunityButton mfCommunityButtonDanger'", "SMS delete class"),
    )
    for old, new, label in style_replacements:
        data = _replace_count(data, old, new, 1, label)
    return data


def _derive_diagnostics(root: Path) -> bytes:
    data = _load_parent_source(root, r21.DIAGNOSTICS_JS_PATH)
    data = _replace_count(data, b"R2.1", b"R2.2", 1, "Diagnostics revision")
    data = _replace_count(
        data,
        b"0.2.1-community-r2",
        b"0.2.2-community-r2",
        2,
        "Diagnostics component identity",
    )
    data = _replace_count(
        data,
        b"html/Diagnostics/Diagnostics.html",
        b"html/Community/r22diag.html",
        1,
        "Diagnostics cache-safe HTML path",
    )
    data = _replace_count(
        data,
        b"done(null,extract(name,xml))",
        b"done(null,extract(name,xml),name==='status1'&&!!(w.MF885CommunityR22&&w.MF885CommunityR22.exactStatus1Identity(xml)))",
        1,
        "Diagnostics shared identity proof",
    )
    data = _replace_count(
        data,
        b"var models={},values={},endpointStates={},busy=false,hasSuccess=false,xmlName='status1';",
        b"var models={},values={},endpointStates={},busy=false,hasSuccess=false,identityProof=false,xmlName='status1';",
        1,
        "Diagnostics identity state",
    )
    data = _replace_count(
        data,
        b"var failed=Object.keys(failures).length,identity=exactIdentity(values);renderValues();",
        b"var failed=Object.keys(failures).length,identity=identityProof;renderValues();",
        1,
        "Diagnostics strict identity result",
    )
    data = _replace_count(
        data,
        b"fallback.hidden=true;models={};endpointStates={};var failures={},index=0;",
        b"fallback.hidden=true;models={};endpointStates={};identityProof=false;var failures={},index=0;",
        1,
        "Diagnostics identity reset",
    )
    data = _replace_count(
        data,
        b"requestModel($,name,function(error,data){endpointStates[name]=error||'ok';if(error)failures[name]=error;else models[name]=data;next()})",
        b"requestModel($,name,function(error,data,proof){endpointStates[name]=error||'ok';if(error)failures[name]=error;else{models[name]=data;if(name==='status1')identityProof=proof===true}next()})",
        1,
        "Diagnostics identity callback",
    )
    old_style = b"row.style.cssText='border-bottom:1px solid #eaecf0;padding:5px 0;min-width:0';title.style.cssText='display:block;color:#667085;font-size:12px';"
    new_style = b"row.className='mfCommunityValue';title.className='mfCommunityValueLabel';"
    data = _replace_count(data, old_style, new_style, 1, "Diagnostics value classes")
    data = _replace_count(
        data,
        b"value.style.cssText='display:block;overflow-wrap:anywhere'",
        b"value.className='mfCommunityValueText'",
        1,
        "Diagnostics text class",
    )
    return data


def _derive_dashboard_script(records: dict[str, bytes]) -> bytes:
    return _replace_count(
        records["www\\js\\panel\\dashboard.js"],
        b"html/dashboard.html",
        b"html/Community/r22dash.html",
        1,
        "R2.2 cache-safe dashboard HTML path",
    )


def _patch_index(data: bytes) -> bytes:
    old_auth = (
        b'        <script type="text/javascript" src="js/community_auth.js" '
        b'language="javascript"></script>\r\n'
    )
    new_auth = (
        b'        <script type="text/javascript" src="js/r22boot.js" language="javascript"></script>\r\n'
        b'        <script type="text/javascript" src="js/r22auth.js" language="javascript"></script>\r\n'
    )
    old_diagnostics = (
        b'        <script type="text/javascript" src="js/community_diagnostics.js" '
        b'language="javascript"></script>\r\n'
    )
    new_diagnostics = (
        b'        <script type="text/javascript" src="js/r22diag.js" language="javascript"></script>\r\n'
    )
    data = _replace_count(data, old_auth, new_auth, 1, "R2.2 cache-safe auth loader")
    data = _replace_count(data, old_diagnostics, new_diagnostics, 1, "R2.2 cache-safe diagnostics loaders")
    data = _replace_count(
        data,
        b'src="js/panel/SMS/SMS.js"',
        b'src="js/panel/SMS/r22sms.js"',
        1,
        "R2.2 cache-safe SMS loader",
    )
    data = _replace_count(
        data,
        b'src="js/panel/dashboard.js"',
        b'src="js/panel/r22dash.js"',
        1,
        "R2.2 cache-safe dashboard loader",
    )
    data = _replace_count(
        data,
        b'        <link rel="stylesheet" type="text/css" href="css/modaldbox.css">\r\n',
        b'        <link rel="stylesheet" type="text/css" href="css/modaldbox.css">\r\n'
        b'        <link rel="stylesheet" type="text/css" href="css/r22ui.css">\r\n',
        1,
        "R2.2 visual stylesheet",
    )
    old_remember = b'''                    <label style="display:block;margin:8px 0 3px 0;text-align:left"><input type="checkbox" id="mfRememberTab" /> Remember me in this tab</label>\r
                    <small style="display:block;text-align:left;line-height:1.25;color:#555">Refreshes will sign in automatically. This tab stores a password-equivalent Digest key, not the password itself. Ten minutes without keyboard, touch or mouse activity clears it; signing out or closing the tab normally clears it. Scripts loaded by this page can read it, so use this only on a trusted device.</small>\r
'''
    new_remember = b'''                    <label class="mfRememberRow" for="mfRememberTab"><input type="checkbox" id="mfRememberTab" /> <span>Remember me in this tab</span></label>\r
                    <small class="mfRememberHelp">Refreshes will sign in automatically. This tab stores a password-equivalent Digest key, not the password itself. Ten minutes without keyboard, touch or mouse activity clears it; signing out or closing the tab normally clears it. Scripts loaded by this page can read it, so use this only on a trusted device.</small>\r
'''
    data = _replace_count(data, old_remember, new_remember, 1, "Remember visual markup")
    data = _replace_count(
        data,
        b"createMenuFromXML();",
        b"MF885CommunityR22.seedLabels(); createMenuFromXML();",
        2,
        "cache-safe Diagnostics labels",
    )
    return data


def _patch_dashboard(data: bytes) -> bytes:
    old = b'''            <!-- MF885 Community R2.1 SMS Safe Diagnostics 0.2.1-community-r2 -->\r
            <strong>Community Build:</strong><br />\r
            <label>Community R2.1 &middot; base 2.5.94</label><br /><br />\r
            <a href="#" onclick="dashboardOnClick(5,'mDeviceInbox')"><strong>Messages</strong><br />\r
            <label>Open Device Inbox</label></a><br /><br />\r
            <a href="#" onclick="dashboardOnClick(6,'mDiagnostics')"><strong>Diagnostics</strong><br />\r
            <label>Open Safe Diagnostics</label></a>\r
'''
    new = b'''            <!-- MF885 Community R2.2 SMS Safe Diagnostics 0.2.2-community-r2 -->\r
            <div id="mfCommunityDashboard">\r
              <span class="mfCommunityBuild">Community R2.2</span>\r
              <span class="mfCommunityBase">base 2.5.94</span>\r
              <span class="mfCommunityDashboardActions"><a href="#" onclick="dashboardOnClick(5,'mDeviceInbox')">Messages</a><a href="#" onclick="dashboardOnClick(6,'mDiagnostics')">Diagnostics</a></span>\r
            </div>\r
'''
    return _replace_count(data, old, new, 1, "R2.2 dashboard badge and actions")


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        replacements, additions, removals = r21.build_patch_set(records, root)
    except r21.CommunityR21Error as exc:
        raise CommunityR22Error(str(exc)) from exc
    replacements = dict(replacements)
    additions = dict(additions)
    removals = set(removals)
    custom = _load_custom(root)

    new_paths = {
        AUTH_PATH,
        BOOT_PATH,
        CSS_PATH,
        SMS_JS_PATH,
        SMS_HTML_PATH,
        DIAGNOSTICS_JS_PATH,
        DIAGNOSTICS_HTML_PATH,
        DASHBOARD_JS_PATH,
        DASHBOARD_HTML_PATH,
    }
    if any(path in records or path in additions for path in new_paths):
        raise CommunityR22Error("R2.2 cache-safe asset path already exists")

    replacements["www\\index.html"] = _patch_index(replacements["www\\index.html"])
    replacements["www\\html\\dashboard.html"] = _patch_dashboard(
        replacements["www\\html\\dashboard.html"]
    )
    additions.pop(PARENT_AUTH_PATH, None)
    additions[AUTH_PATH] = _derive_auth(root)
    additions[BOOT_PATH] = custom[BOOT_PATH]
    additions[CSS_PATH] = custom[CSS_PATH]
    additions[SMS_HTML_PATH] = custom[SMS_HTML_PATH]
    additions[DIAGNOSTICS_HTML_PATH] = custom[DIAGNOSTICS_HTML_PATH]
    additions[SMS_JS_PATH] = _derive_sms(root)
    additions[DIAGNOSTICS_JS_PATH] = _derive_diagnostics(root)
    additions[DASHBOARD_HTML_PATH] = replacements["www\\html\\dashboard.html"]
    additions[DASHBOARD_JS_PATH] = _derive_dashboard_script(records)

    if set(replacements) != set(r21.OUTPUT_RECORDS):
        raise CommunityR22Error("R2.2 replacement path set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR22Error("R2.2 removed-locale set changed")
    expected_additions = {
        r21.DIAGNOSTICS_HTML_PATH,
        r21.DIAGNOSTICS_JS_PATH,
        *new_paths,
    }
    if set(additions) != expected_additions:
        raise CommunityR22Error("R2.2 addition path set changed")

    if set(CUSTOM_FILES) | set(ADDITION_OUTPUT_RECORDS) != expected_additions:
        raise CommunityR22Error("R2.2 addition provenance gate is incomplete")
    for path, (size, digest, _source) in ADDITION_OUTPUT_RECORDS.items():
        try:
            r2.require_exact(additions[path], size, digest, f"added {path}")
        except r2.CommunityR2Error as exc:
            raise CommunityR22Error(str(exc)) from exc

    if OUTPUT_RECORDS:
        if set(OUTPUT_RECORDS) != set(replacements):
            raise CommunityR22Error("R2.2 output record gate is incomplete")
        for path, (size, digest) in OUTPUT_RECORDS.items():
            try:
                r2.require_exact(replacements[path], size, digest, f"derived {path}")
            except r2.CommunityR2Error as exc:
                raise CommunityR22Error(str(exc)) from exc

    index = replacements["www\\index.html"]
    for route in (
        b"js/r22boot.js",
        b"js/r22auth.js",
        b"js/r22diag.js",
        b"js/panel/SMS/r22sms.js",
        b"js/panel/r22dash.js",
        b"css/r22ui.css",
    ):
        if index.count(route) != 1:
            raise CommunityR22Error("R2.2 index does not bind each cache-safe asset exactly once")
    if (
        b"js/community_auth.js" in index
        or b"js/community_diagnostics.js" in index
        or b"js/panel/SMS/SMS.js" in index
        or b"js/panel/dashboard.js" in index
    ):
        raise CommunityR22Error("R2.2 index still loads a cache-prone Community script")
    if MARKER not in replacements["www\\html\\dashboard.html"]:
        raise CommunityR22Error("R2.2 marker is absent from the dashboard")
    return replacements, additions, removals
