#!/usr/bin/env python3
"""Deterministic Community R2.1 patch set built on immutable Community R2.

R2.1 is always derived from the same strictly reviewed 2.5.94 / Ver.D golden
image as R2.  The existing R2 transformer remains unchanged; this module first
derives its exact bytes and then applies the separately pinned R2.1 delta.
"""

from __future__ import annotations

from pathlib import Path

import mf885_community_r2 as r2


PROFILE = "0.2.1-community-r2"
MARKER = b"MF885 Community R2.1 SMS Safe Diagnostics 0.2.1-community-r2"
AUTH_PATH = r2.AUTH_PATH
DIAGNOSTICS_HTML_PATH = "www\\html\\Diagnostics\\Diagnostics.html"
DIAGNOSTICS_JS_PATH = "www\\js\\community_diagnostics.js"
REMOVED_RECORDS = r2.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES = r2.REMOVED_ARCHIVE_BYTES

CUSTOM_FILES = {
    "www\\html\\SMS\\SMS.html": (
        "firmware/community-r2.1/SMS.html",
        2_272,
        "4f7b215ff00e0001bc83ddae9a9d4c4f15224a997a514a7e6d6bee8e92ca769e",
    ),
    "www\\js\\panel\\SMS\\SMS.js": (
        "firmware/community-r2.1/SMS.js",
        19_450,
        "8ce3f06d2fd1620d74bd9efe2b19ca4143ab349941ec5637b90d7738723327cd",
    ),
    AUTH_PATH: r2.CUSTOM_FILES[AUTH_PATH],
    DIAGNOSTICS_HTML_PATH: (
        "firmware/community-r2.1/Diagnostics.html",
        1_066,
        "343ffc5d6e01235e273f4ae9d31aec2de956c8e54e7c2c5192e09944dd1d86bb",
    ),
    DIAGNOSTICS_JS_PATH: (
        "firmware/community-r2.1/community_diagnostics.js",
        16_514,
        "fa208b9032afe623636d422f0e9affc7fae59c57b40ed5cd2edce7567780421a",
    ),
}

# Filled after independently deriving the final records from the reviewed
# golden.  Keeping this gate explicit makes every future byte change a new
# profile revision rather than a silent rebuild of R2.1.
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\SMS\\SMS.html": (2_272, "4f7b215ff00e0001bc83ddae9a9d4c4f15224a997a514a7e6d6bee8e92ca769e"),
    "www\\html\\adminApp.html": (4_341, "7561d91c633b49038506394d167d1549ac26c1ab0367ebddb8045084cbfc3321"),
    "www\\html\\dashboard.html": (10_224, "c83a1a3b22337587588c396c12a4db180271ebe98cbd82eb98078bf5a38453a7"),
    "www\\index.html": (26_578, "10c076cbc10926ec9fa2a85f3167695f5b650c24d3db29287c078844dea756ca"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (17_050, "67c335b9626deb7e9ec5c3c789814415dd6759fac12700bb41e22d9a7abe6756"),
    "www\\js\\panel\\SMS\\SMS.js": (19_450, "8ce3f06d2fd1620d74bd9efe2b19ca4143ab349941ec5637b90d7738723327cd"),
    "www\\properties\\Messages_en.properties": (47_001, "5f6426f6d50c0e3a6a602990b0d7d70643043b98169db3b8f4cd5af5e8e31f8f"),
    "www\\xml\\ui_mifi.xml": (2_921, "c8d54dca3fda4b9c4f9b9b470c680d1d354f69673c257aa2d024f4fb93403d23"),
}


class CommunityR21Error(Exception):
    pass


def _replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    if data.count(old) != 1:
        raise CommunityR21Error(f"{label} anchor count changed")
    return data.replace(old, new, 1)


def _load_custom(root: Path) -> dict[str, bytes]:
    values: dict[str, bytes] = {}
    for target, (source, size, digest) in CUSTOM_FILES.items():
        try:
            data = (root / source).read_bytes()
        except OSError as exc:
            raise CommunityR21Error(f"could not read exact Community R2.1 source {source}") from exc
        try:
            values[target] = r2.require_exact(data, size, digest, source)
        except r2.CommunityR2Error as exc:
            raise CommunityR21Error(str(exc)) from exc
    return values


def _patch_index(data: bytes) -> bytes:
    auth = (
        b'        <script type="text/javascript" src="js/community_auth.js" '
        b'language="javascript"></script>\r\n'
    )
    diagnostics = (
        b'        <script type="text/javascript" src="js/community_diagnostics.js" '
        b'language="javascript"></script>\r\n'
    )
    return _replace_once(data, auth, auth + diagnostics, "Safe Diagnostics loader")


def _patch_menu(data: bytes) -> bytes:
    block = b'''\r
\t<Tab Name='tDiagnostics' type='submenupresent'>\r
\t\t<Menues>\r
\t\t\t<Menu id='mDiagnostics' implFunction='objDiagnostics' xmlName='status1' />\r
\t\t</Menues>\r
\t</Tab>\r
'''
    return _replace_once(data, b"\r\n</Ui>", block + b"\r\n</Ui>", "Diagnostics menu")


def _patch_dashboard(data: bytes) -> bytes:
    old = b'''            <!-- MF885 Community R2 English SMS 0.2-community-r2 -->\r
            <strong>Community Build:</strong><br />\r
            <label>Community R2 &middot; base 2.5.94</label><br /><br />\r
            <a href="#" onclick="dashboardOnClick(5,'mDeviceInbox')"><strong>Messages</strong><br />\r
            <label>Open Device Inbox</label></a>\r
'''
    new = b'''            <!-- MF885 Community R2.1 SMS Safe Diagnostics 0.2.1-community-r2 -->\r
            <strong>Community Build:</strong><br />\r
            <label>Community R2.1 &middot; base 2.5.94</label><br /><br />\r
            <a href="#" onclick="dashboardOnClick(5,'mDeviceInbox')"><strong>Messages</strong><br />\r
            <label>Open Device Inbox</label></a><br /><br />\r
            <a href="#" onclick="dashboardOnClick(6,'mDiagnostics')"><strong>Diagnostics</strong><br />\r
            <label>Open Safe Diagnostics</label></a>\r
'''
    return _replace_once(data, old, new, "R2.1 dashboard links and badge")


def _patch_properties(data: bytes) -> bytes:
    addition = b"tDiagnostics = Diagnostics\r\nmDiagnostics = Diagnostics\r\n"
    if b"tDiagnostics" in data or b"mDiagnostics" in data:
        raise CommunityR21Error("Diagnostics property keys already exist")
    final_line = b"lt_trafficSet_btnChangeDailyTotalTraffic  =  Change"
    if not data.endswith(final_line) or data.count(final_line) != 1:
        raise CommunityR21Error("English property tail changed")
    return data + b"\r\n" + addition


def build_patch_set(
    records: dict[str, bytes], root: Path
) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    try:
        replacements, additions, removals = r2.build_patch_set(records, root)
    except r2.CommunityR2Error as exc:
        raise CommunityR21Error(str(exc)) from exc

    replacements = dict(replacements)
    additions = dict(additions)
    removals = set(removals)
    custom = _load_custom(root)

    replacements["www\\index.html"] = _patch_index(replacements["www\\index.html"])
    replacements["www\\xml\\ui_mifi.xml"] = _patch_menu(
        replacements["www\\xml\\ui_mifi.xml"]
    )
    replacements["www\\html\\dashboard.html"] = _patch_dashboard(
        replacements["www\\html\\dashboard.html"]
    )
    replacements["www\\properties\\Messages_en.properties"] = _patch_properties(
        replacements["www\\properties\\Messages_en.properties"]
    )
    replacements["www\\html\\SMS\\SMS.html"] = custom["www\\html\\SMS\\SMS.html"]
    replacements["www\\js\\panel\\SMS\\SMS.js"] = custom[
        "www\\js\\panel\\SMS\\SMS.js"
    ]
    additions[AUTH_PATH] = custom[AUTH_PATH]
    additions[DIAGNOSTICS_HTML_PATH] = custom[DIAGNOSTICS_HTML_PATH]
    additions[DIAGNOSTICS_JS_PATH] = custom[DIAGNOSTICS_JS_PATH]

    if set(replacements) != set(r2.OUTPUT_RECORDS):
        raise CommunityR21Error("R2.1 replacement path set changed")
    if removals != set(REMOVED_RECORDS):
        raise CommunityR21Error("R2.1 removed-locale set changed")
    if set(additions) != {AUTH_PATH, DIAGNOSTICS_HTML_PATH, DIAGNOSTICS_JS_PATH}:
        raise CommunityR21Error("R2.1 addition path set changed")

    if OUTPUT_RECORDS:
        if set(OUTPUT_RECORDS) != set(replacements):
            raise CommunityR21Error("R2.1 output record gate is incomplete")
        for path, expected in OUTPUT_RECORDS.items():
            try:
                r2.require_exact(replacements[path], expected[0], expected[1], f"derived {path}")
            except r2.CommunityR2Error as exc:
                raise CommunityR21Error(str(exc)) from exc

    retained = {path: data for path, data in records.items() if path not in REMOVED_RECORDS}
    retained.update(replacements)
    retained.update(additions)
    forbidden = tuple(path.rsplit("\\", 1)[-1].encode("ascii") for path in REMOVED_RECORDS)
    leaks = sorted(
        path
        for path, data in retained.items()
        if any(name.lower() in data.lower() for name in forbidden)
    )
    if leaks:
        raise CommunityR21Error(
            "retained R2.1 WEBI files still reference removed language assets: "
            + ", ".join(leaks)
        )
    if MARKER not in replacements["www\\html\\dashboard.html"]:
        raise CommunityR21Error("R2.1 marker is absent from the dashboard")
    return replacements, additions, removals
