#!/usr/bin/env python3
"""Deterministic source-only patch set for MF885 Community R2.

The operator supplies the reviewed 2.5.94 / Ver.D backup.  This module verifies
every stock record it touches or removes before deriving the replacement bytes;
it does not redistribute the stock WebUI files.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


PROFILE = "0.2-community-r2"
MARKER = b"MF885 Community R2 English SMS 0.2-community-r2"
AUTH_PATH = "www\\js\\community_auth.js"
REMOVED_ARCHIVE_BYTES = 263_312

BASE_RECORDS = {
    "www\\index.html": (29_777, "24b996abd8e9609aa8ce4c93229da4918aa9d1ae0ea3f8de3536fd779d1a9c71"),
    "www\\js\\base\\utils.js": (17_140, "6f51c05b83290ef89d9d9d2a1eb517d56cdcfc223d1cbaa61f959c11aefdd0a5"),
    "www\\js\\base\\ajax_calls.js": (21_537, "5447f2f6ba6a76c52b4c8acd841a21a7b29161cf6c51fd3b79a3df1bee05ce30"),
    "www\\xml\\ui_mifi.xml": (2_403, "a072d8641d7c33d2d65d378ae1ea57c4ad85125ba0436248b04dc009c22cc16e"),
    "www\\html\\adminApp.html": (4_337, "b3331c4476e378ac41aff8ec113315ff5e38dae2f262a56de3c8450eae3d115c"),
    "www\\html\\dashboard.html": (9_677, "15ebc743ddd471583f39e525d4e983e01d4f051db8ef62690e08e3043b1e5650"),
    "www\\properties\\Messages_en.properties": (47_003, "e7032368c2979b5cf8b90b30b14baae96a956706fa264fd7b2ccf256426464ea"),
    "www\\help_en.html": (21_375, "c3c2876a2a8781bfe5a18dc08daa638d94d45f092ca950977df3c8f04c5bc58d"),
}

REMOVED_RECORDS = {
    "www\\help_cn.html": (15_880, "ed70a489ac8179a764aabdce4c2564448c139302a2ce4899a338f6ce9a9702b6"),
    "www\\help_hk.html": (15_834, "53141ed5dc309c7987e53db39488f93021451bcd973faad7b7e2bcffbb64f3f3"),
    "www\\help_jp.html": (21_134, "9b9a803d587e1220069ee762d941793faa427dcef09ca054f052436e173ad297"),
    "www\\properties\\Messages_cn.properties": (44_163, "e6f14e7ef0786c1619381ef830eb3e95f3281446c48ca0841ba9f34bf1228baa"),
    "www\\properties\\Messages_hk.properties": (46_448, "0e17bb3940db50aa3d64bc8724cdf246119aeda64fba91edcbcb463299362c5b"),
    "www\\properties\\Messages_jp.properties": (57_680, "25c675156648b4b5ffcd50e3754572cf7e69840f8c04a8cdf06345808fb60d95"),
    "www\\images\\logo_blue_cn.png": (4_264, "5812394f659457fc5e612280452ae33b042af588f26f91ecc11e8383891f4497"),
    "www\\images\\logo_blue_hk.png": (5_951, "118eb62f5fd03da3cdd2502a28c9e17d496dd063c183c729d1ddee4ead6483cd"),
    "www\\images\\logo_blue_jp.png": (6_015, "48625674bc83e0dc72a20c6cc29d86b5702597aa9eec6df08dcbe9ba5864fa25"),
    "www\\images\\logo_cn.png": (5_440, "7259d8fbffe385df1ce888d92e39d3e86029f9be6246294d3966174226cad621"),
    "www\\images\\logo_hk.png": (6_140, "06852906c3456562da5bd3c708a8503191b243081235c65a638ecd5ce84632c6"),
    "www\\images\\logo_jp.png": (5_966, "a382ce60df11340448b18bd753c7a79e57bf99f58724d35eab0708f8daa53b21"),
    "www\\images\\nosimc_cn.png": (4_492, "c5f60cdfdd59879eab1057bdf6e001effcaca2df697b03575ef78d3fc09d0e4c"),
    "www\\images\\nosimc_hk.png": (4_511, "fcba929dde23b9033f4868e1d96e6840ff195f60aee57792d9f521e3aeb5e728"),
    "www\\images\\nosimc_jp.png": (4_639, "a5aae4ea6f9154dd0428430a6872d277b950859dde93b99601f09e8d64d23a07"),
    "www\\images\\pinlock_cn.png": (4_076, "c075710edba05cd1582e6415d58012bcc467427b1dbb1fddb43724138468f91a"),
    "www\\images\\pinlock_hk.png": (4_136, "9d5363c94642a83c8c897ebc07584ee191e18a5cff3b9424d6d5e6cee024f7cf"),
    "www\\images\\pinlock_jp.png": (4_081, "1e9160be5ab08002faa6e59c7a62bbdc398f5f61e386aef16d302c8672467d71"),
}

CUSTOM_FILES = {
    "www\\html\\SMS\\SMS.html": (
        "firmware/community-r1/SMS.html",
        601,
        "64b5dc600ff4aff228439168b4cad5b1a429ca055a11622bb03b3f418ca834a9",
    ),
    "www\\js\\panel\\SMS\\SMS.js": (
        "firmware/community-r1/SMS.js",
        11_822,
        "5102a7c29ff325d3d9481ceaa0069b273849986b9ef2c8fe9dcc6bff0a99b679",
    ),
    AUTH_PATH: (
        "firmware/community-r2/community_auth.js",
        8_141,
        "253bee3ceac1ab1b3e64982400653a25082278accb03324e8b0609ba4a416a65",
    ),
}

# Filled with independently derived output bytes.  Keeping these separate from
# the stock gates makes every future source edit an explicit profile revision.
OUTPUT_RECORDS: dict[str, tuple[int, str]] = {
    "www\\help_en.html": (21_381, "00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2"),
    "www\\html\\SMS\\SMS.html": (601, "64b5dc600ff4aff228439168b4cad5b1a429ca055a11622bb03b3f418ca834a9"),
    "www\\html\\adminApp.html": (4_341, "7561d91c633b49038506394d167d1549ac26c1ab0367ebddb8045084cbfc3321"),
    "www\\html\\dashboard.html": (10_038, "e8d644af47b2a0cf5407b85aaf9cb31ebc6daaedc9b945c02a346ec90aeb4355"),
    "www\\index.html": (26_472, "397dce6a6a1b57f9dbf9624916d38e156c1fabade0faf9d9aba72f5f4169f715"),
    "www\\js\\base\\ajax_calls.js": (21_467, "f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127"),
    "www\\js\\base\\utils.js": (17_050, "67c335b9626deb7e9ec5c3c789814415dd6759fac12700bb41e22d9a7abe6756"),
    "www\\js\\panel\\SMS\\SMS.js": (11_822, "5102a7c29ff325d3d9481ceaa0069b273849986b9ef2c8fe9dcc6bff0a99b679"),
    "www\\properties\\Messages_en.properties": (46_943, "2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c"),
    "www\\xml\\ui_mifi.xml": (2_756, "006944623b03221efebb5af185c64d190f40b9a60cd330e5690ca44123566254"),
}


class CommunityR2Error(Exception):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_exact(data: bytes, size: int, digest: str, label: str) -> bytes:
    if len(data) != size or sha256(data) != digest:
        raise CommunityR2Error(f"{label} does not match the reviewed byte sequence")
    return data


def replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    if data.count(old) != 1:
        raise CommunityR2Error(f"{label} anchor count changed")
    return data.replace(old, new, 1)


def replace_region(data: bytes, start: bytes, end: bytes, replacement: bytes, label: str) -> bytes:
    if data.count(start) != 1:
        raise CommunityR2Error(f"{label} region anchors changed")
    left = data.index(start)
    try:
        right = data.index(end, left + len(start))
    except ValueError as exc:
        raise CommunityR2Error(f"{label} end anchor changed") from exc
    return data[:left] + replacement + data[right:]


def patch_index(data: bytes) -> bytes:
    script_anchor = (
        b'        <script type="text/javascript" src="js/base/utils.js" '
        b'language="javascript"></script>\r\n'
    )
    data = replace_once(
        data,
        script_anchor,
        script_anchor
        + b'        <script type="text/javascript" src="js/community_auth.js" '
        + b'language="javascript"></script>\r\n',
        "Community auth loader",
    )

    data = replace_region(
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
        "English locale function",
    )

    data = replace_region(
        data,
        b'\t\t\t\tif(sim_status == "1"){',
        b'\t\t\t\telse if (NW_register_status == "2"){',
        b'''\t\t\t\tif(sim_status == "1"){\r
                    document.getElementById("iindexstatusimg").src = "images/nosimc_en.png";\r
                }\r
''',
        "English no-SIM image",
    )

    data = replace_region(
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
        "English init locale",
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
        raise CommunityR2Error("language-switch branch count changed")
    data = b"".join(lines)

    data = replace_region(
        data,
        b"\t    if(login_done == 1){",
        b"        }\r\n        function checkEnter(e)",
        b'''\t    if(login_done == 1 && MF885CommunityAuth.afterManualLogin(\r
                    document.getElementById("mfRememberTab").checked)){\r
                MF885CommunityAuth.openAdmin();\r
                return;\r
            }\r
            if(login_done == 0){\r
                document.getElementById('lloginfailed').style.display = 'block';\r
                document.getElementById("lloginfailed").innerHTML = jQuery.i18n.prop("lloginfailed");\r
            } else {\r
                document.getElementById('lloginfailed').style.display = 'block';\r
                document.getElementById("lloginfailed").innerHTML = jQuery.i18n.prop("lnoconn");\r
            }\r
''',
        "manual login handoff",
    )

    init_anchor = (
        b'         document.getElementById("btnSignIn").disabled = false;\r\n\r\n    }'
    )
    init_replacement = b'''         document.getElementById("btnSignIn").disabled = false;\r
         if(!MF885CommunityAuth.supported())\r
             document.getElementById("mfRememberTab").disabled = true;\r
         else if(MF885CommunityAuth.resume())\r
             MF885CommunityAuth.openAdmin();\r
\r
    }'''
    data = replace_once(data, init_anchor, init_replacement, "single resume attempt")

    button_anchor = (
        b'                    <input name="" type="button" class="button" '
        b'id="btnSignIn" value="\xe7\x99\xbb\xe5\xbd\x95" onclick=\'Login()\' disabled=""/>'
    )
    remember = b'''                    <label style="display:block;margin:8px 0 3px 0;text-align:left"><input type="checkbox" id="mfRememberTab" /> Remember me in this tab</label>\r
                    <small style="display:block;text-align:left;line-height:1.25;color:#555">Refreshes will sign in automatically. This tab stores a password-equivalent Digest key, not the password itself. Ten minutes without keyboard, touch or mouse activity clears it; signing out or closing the tab normally clears it. Scripts loaded by this page can read it, so use this only on a trusted device.</small>\r
'''
    english_button = (
        b'                    <input name="" type="button" class="button" '
        b'id="btnSignIn" value="Sign In" onclick=\'Login()\' disabled=""/>'
    )
    data = replace_once(data, button_anchor, remember + english_button, "remember-tab controls")
    data = replace_once(data, b">\xe8\xae\xbf\xe9\x97\xae\xe5\xae\x98\xe7\xbd\x91</a>", b">Official website</a>", "English home link")
    return data


def patch_utils(data: bytes) -> bytes:
    first = b'HA1 = hex_md5(username+ ":" + Authrealm + ":" + passwd);'
    second = b'HA1 = hex_md5(username + ":" + Authrealm + ":" + passwd);'
    replacement_first = (
        b'HA1 = (window.MF885CommunityAuth && MF885CommunityAuth.ha1()) || '
        b'hex_md5(username+ ":" + Authrealm + ":" + passwd);'
    )
    replacement_second = (
        b'HA1 = (window.MF885CommunityAuth && MF885CommunityAuth.ha1()) || '
        b'hex_md5(username + ":" + Authrealm + ":" + passwd);'
    )
    if data.count(first) != 2 or data.count(second) != 1:
        raise CommunityR2Error("Digest HA1 call sites changed")
    data = data.replace(first, replacement_first)
    data = data.replace(second, replacement_second)
    data = replace_region(
        data,
        b"    if(getCookie('locale')=='')\r\n",
        b"    var host = window.location.protocol + \"//\" + window.location.host + \"/\";",
        b'    htmlFilename = "help_en.html";\r\n',
        "context Help locale",
    )
    data = replace_region(
        data,
        b"    if (getCookie('locale') == '')\r\n",
        b"    var host = window.location.protocol + \"//\" + window.location.host + \"/\";",
        b'    htmlFilename = "help_en.html?name=" + _temp[0] + "&version=" + _temp[1];\r\n',
        "main Help locale",
    )
    return data


def patch_ajax(data: bytes) -> bytes:
    return replace_region(
        data,
        b"function setLocalization(locale) {",
        b"    try {\r\n",
        b'''function setLocalization(locale) {\r
    locale = "en";\r
\r
''',
        "English localization fallback",
    )


def patch_menu(data: bytes) -> bytes:
    block = b'''\r
\t<Tab Name='tSms' type='submenupresent'>\r
\t\t<Menues>\r
\t\t\t<Menu id='mDeviceInbox' implFunction='objSms' xmlName='message' />\r
\t\t\t<Menu id='mDeviceOutbox' implFunction='objSms' xmlName='message' />\r
\t\t\t<Menu id='mSimSms' implFunction='objSms' xmlName='message' />\r
\t\t\t<Menu id='mDrafts' implFunction='objSms' xmlName='message' />\r
\t\t</Menues>\r
\t</Tab>\r
'''
    return replace_once(data, b"\r\n</Ui>", block + b"\r\n</Ui>", "SMS menu")


def patch_dashboard(data: bytes) -> bytes:
    anchor = b'''\t\t    <label id="lHardVersion"></label>\r
\t\t    </a>\r
        </h3>'''
    replacement = b'''\t\t    <label id="lHardVersion"></label>\r
\t\t    </a><br /><br />\r
            <!-- MF885 Community R2 English SMS 0.2-community-r2 -->\r
            <strong>Community Build:</strong><br />\r
            <label>Community R2 &middot; base 2.5.94</label><br /><br />\r
            <a href="#" onclick="dashboardOnClick(5,'mDeviceInbox')"><strong>Messages</strong><br />\r
            <label>Open Device Inbox</label></a>\r
        </h3>'''
    return replace_once(data, anchor, replacement, "dashboard build badge")


def patch_admin_app(data: bytes) -> bytes:
    return replace_once(
        data,
        b">\xe8\xae\xbf\xe9\x97\xae\xe5\xae\x98\xe7\xbd\x91</a>",
        b">Official website</a>",
        "English admin home link",
    )


PROPERTY_FIXES = {
    b"lAuthUnAuth": (b"UnAuthorized,please login again", b"Unauthorized, please log in again."),
    b"lAuthTimeout": (b"UnAuthorized,please login again", b"Unauthorized, please log in again."),
    b"lloginfailed": (b"Incorrect password.Please try again.", b"Incorrect password. Please try again."),
    b"lDisableWifiAutoOff": (b"I want to disable wifi atuo off function.", b"I want to disable Wi-Fi auto-off."),
    b"lspecialTFTname": (b"Should not have special charactors in TFT rule name", b"Should not have special characters in TFT rule name"),
    b"lManualPromte": (b"&nbsp; &nbsp; It will take more than one minute to manual scan network.Please waiting...", b"&nbsp; &nbsp; A manual network scan can take more than one minute. Please wait..."),
    b"dropdown30sec": (b"30 secondes", b"30 seconds"),
    b"waitScanNetwork": (b"Searching network,please waiting...", b"Searching network, please wait..."),
    b"selectEmptyNetworkTypeErrorTip": (b"Seleced network can't be empty.", b"Selected network cannot be empty."),
    b"lIdle": (b"Unchargeg", b"Uncharged"),
    b"lCharging_error": (b"Chargeing srror", b"Charging error"),
    b"mPinPuk": (b"PIN Managment", b"PIN Management"),
    b"lAtleastOne": (b"Please provide atleast one of the source IP address, source ports, destination IP address and destination ports.", b"Please provide at least one source IP address, source port, destination IP address or destination port."),
    b"h1CustomPWRule": (b"Port Forwording Rule", b"Port Forwarding Rule"),
    b"lPWAtleastOne": (b"Please provide atleast one of IP address, port range.", b"Please provide at least one IP address or port range."),
    b"lSaveAcatDumplogSetting": (b"Save Acatlog to SD Settings", b"Save ACAT Log to SD Settings"),
    b"lt_SmsSet_stcLargest": (b"Maxinum", b"Maximum"),
    b"lt_sms_readedSms": (b"Readed SMS", b"Read SMS"),
    b"lt_sms_stcmeusavenumber": (b"SaveNumber", b"Save Number"),
    b"lt_sms_stcmeuclearall": (b"ClearAll", b"Clear All"),
    b"lSMSCenterModificationWarning": (b"You modified smscenter number ,maybe it will casue send SMS failed!!!", b"Changing the SMS center number may cause SMS sending to fail."),
    b"lt_sms_stcSmsLenghtError": (b"Most send 640 english or 280 chinese characters", b"Up to 640 English or 280 Chinese characters"),
    b"lTriggerPortIncomplete": (b"Trigger port number is imcomplete,please check", b"The trigger port number is incomplete. Please check it."),
    b"lResponsePortIncomplete": (b"Response port number is imcomplete,please check", b"The response port number is incomplete. Please check it."),
    b"lBtnSave": (b"Save", b"Save"),
    b"lMaxBlockStatusTip": (b"Most blocked 8 clients\xa3\xacplease unblock another client if you want block the client.", b"At most 8 clients can be blocked; unblock another client before blocking this one."),
    b"lt_trafficSet_stcMonthAvailableTraffic": (b"Month Avalible Traffic", b"Month Available Traffic"),
    b"lt_trafficSet_stcPeriodAvalibleTraffic": (b"Period Avalible Traffic", b"Period Available Traffic"),
    b"MonthAvalibleTrafficSetting": (b"Month Avalible Traffic Setting", b"Month Available Traffic Setting"),
    b"MonthAvalibleTraffic": (b"Month Avalible Traffic", b"Month Available Traffic"),
    b"PeriodAvalibleTrafficSetting": (b"Period Avalible Traffic Setting", b"Period Available Traffic Setting"),
    b"PeriodAvalibleTraffic": (b"Period Avalible Traffic", b"Period Available Traffic"),
    b"lt_trafficSet_stcUnlimitPeriodAvailableTraffic": (b"Unlimit Avalible Upper Traffic", b"Unlimited Available Traffic"),
    b"DailyAvalibleTrafficSetting": (b"Daily Avalible Traffic Setting", b"Daily Available Traffic Setting"),
    b"DailyAvalibleTraffic": (b"Daily Avalible Traffic", b"Daily Available Traffic"),
    b"lt_trafficSet_stcDailyAvailableTraffic": (b"Daily Avalible Traffic", b"Daily Available Traffic"),
}


def patch_properties(data: bytes) -> bytes:
    lines = data.splitlines(keepends=True)
    seen: set[bytes] = set()
    output: list[bytes] = []
    for line in lines:
        newline = b"\r\n" if line.endswith(b"\r\n") else b"\n" if line.endswith(b"\n") else b""
        raw = line[: -len(newline)] if newline else line
        key = raw.split(b"=", 1)[0].strip() if b"=" in raw else raw.split(b"\t", 1)[0].strip()
        if key in PROPERTY_FIXES:
            old_value, new_value = PROPERTY_FIXES[key]
            if b"=" in raw:
                current_value = raw.split(b"=", 1)[1].strip()
            else:
                current_value = raw[len(key) :].strip()
            if current_value == old_value:
                if key in seen:
                    raise CommunityR2Error(f"duplicate English typo property {key.decode('ascii')}")
                output.append(key + b" = " + new_value + newline)
                seen.add(key)
            else:
                output.append(line)
        else:
            output.append(line)
    missing = sorted(set(PROPERTY_FIXES) - seen)
    if missing:
        raise CommunityR2Error("English property keys changed: " + ", ".join(x.decode() for x in missing))
    return b"".join(output)


def patch_help(data: bytes) -> bytes:
    fixes = (
        (b"ThePIN Managment", b"The PIN Management", 1),
        (b"PIN Managment", b"PIN Management", 3),
        (b"Passowrd", b"Password", 1),
        (b"triggle", b"trigger", 1),
        (b"inteval", b"interval", 2),
        (b"801.11", b"802.11", 1),
        (b"fileters", b"filters", 1),
    )
    for old, new, expected in fixes:
        if data.count(old) != expected:
            raise CommunityR2Error(f"English Help typo anchor changed: {old!r}")
        data = data.replace(old, new)
    return data


def build_patch_set(records: dict[str, bytes], root: Path) -> tuple[dict[str, bytes], dict[str, bytes], set[str]]:
    for path, (size, digest) in {**BASE_RECORDS, **REMOVED_RECORDS}.items():
        if path not in records:
            raise CommunityR2Error(f"reviewed stock record is missing: {path}")
        require_exact(records[path], size, digest, path)

    custom: dict[str, bytes] = {}
    for target, (source, size, digest) in CUSTOM_FILES.items():
        try:
            data = (root / source).read_bytes()
        except OSError as exc:
            raise CommunityR2Error(f"could not read exact Community source {source}") from exc
        custom[target] = require_exact(data, size, digest, source)

    replacements = {
        "www\\index.html": patch_index(records["www\\index.html"]),
        "www\\js\\base\\utils.js": patch_utils(records["www\\js\\base\\utils.js"]),
        "www\\js\\base\\ajax_calls.js": patch_ajax(records["www\\js\\base\\ajax_calls.js"]),
        "www\\xml\\ui_mifi.xml": patch_menu(records["www\\xml\\ui_mifi.xml"]),
        "www\\html\\adminApp.html": patch_admin_app(records["www\\html\\adminApp.html"]),
        "www\\html\\dashboard.html": patch_dashboard(records["www\\html\\dashboard.html"]),
        "www\\properties\\Messages_en.properties": patch_properties(
            records["www\\properties\\Messages_en.properties"]
        ),
        "www\\help_en.html": patch_help(records["www\\help_en.html"]),
        "www\\html\\SMS\\SMS.html": custom["www\\html\\SMS\\SMS.html"],
        "www\\js\\panel\\SMS\\SMS.js": custom["www\\js\\panel\\SMS\\SMS.js"],
    }
    for path, expected in OUTPUT_RECORDS.items():
        require_exact(replacements[path], expected[0], expected[1], f"derived {path}")

    retained = {path: data for path, data in records.items() if path not in REMOVED_RECORDS}
    retained.update(replacements)
    retained[AUTH_PATH] = custom[AUTH_PATH]
    forbidden_references = tuple(
        path.rsplit("\\", 1)[-1].encode("ascii") for path in REMOVED_RECORDS
    )
    leaks = sorted(
        path
        for path, data in retained.items()
        if any(name.lower() in data.lower() for name in forbidden_references)
    )
    if leaks:
        raise CommunityR2Error(
            "retained WEBI files still reference removed language assets: " + ", ".join(leaks)
        )
    return replacements, {AUTH_PATH: custom[AUTH_PATH]}, set(REMOVED_RECORDS)
