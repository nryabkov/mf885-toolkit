import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mf885_firmware_inspect as inspector  # noqa: E402
import mf885_community_r2 as community_r2  # noqa: E402
import mf885_community_r21 as community_r21  # noqa: E402
import mf885_community_r22 as community_r22  # noqa: E402
import mf885_community_r23 as community_r23  # noqa: E402
import mf885_community_r24 as community_r24  # noqa: E402
import mf885_webui_stage_builder as stage  # noqa: E402


LOCAL_GOLDEN = Path(os.environ.get("MF885_TEST_GOLDEN", ROOT / "input/MF885_golden.bin"))
LOCAL_IDENTITY = Path(os.environ.get("MF885_TEST_IDENTITY", ROOT / "input/mf885-base.xml"))


class WebuiStageBuilderTests(unittest.TestCase):
    def test_exclusive_outputs_stay_private_under_a_permissive_umask(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "private-report.json"
            previous = os.umask(0)
            try:
                stage.write_exclusive(output, b"private")
            finally:
                os.umask(previous)
            self.assertEqual(output.read_bytes(), b"private")
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with self.assertRaisesRegex(stage.StageBuildError, "overwrite"):
                stage.write_exclusive(output, b"replacement")

    def test_community_r2_is_a_derived_english_only_profile(self):
        specification = stage.STAGE_PROFILES["0.2-community-r2"]
        self.assertEqual(specification["marker"], community_r2.MARKER)
        self.assertEqual(specification["patcher"], "community-r2")
        self.assertEqual(specification["safety"]["languages"], ["en"])
        self.assertTrue(specification["safety"]["tabAuthStoresPasswordEquivalentHA1"])
        self.assertFalse(specification["safety"]["tabAuthStoresPlaintextPassword"])
        self.assertEqual(len(community_r2.REMOVED_RECORDS), 18)
        self.assertEqual(community_r2.REMOVED_ARCHIVE_BYTES, 263_312)
        with self.assertRaisesRegex(stage.StageBuildError, "reviewed golden"):
            stage.load_profile_sources("0.2-community-r2")

    def test_community_r21_is_a_separate_derived_safe_diagnostics_profile(self):
        specification = stage.STAGE_PROFILES["0.2.1-community-r2"]
        self.assertEqual(specification["marker"], community_r21.MARKER)
        self.assertEqual(specification["patcher"], "community-r2.1")
        self.assertEqual(specification["safety"]["languages"], ["en"])
        self.assertFalse(specification["safety"]["nativeDetailedLog"])
        self.assertFalse(specification["safety"]["backgroundDiagnosticsPolling"])
        self.assertEqual(len(community_r21.REMOVED_RECORDS), 18)
        with self.assertRaisesRegex(stage.StageBuildError, "reviewed golden"):
            stage.load_profile_sources("0.2.1-community-r2")

    def test_community_r22_is_a_separate_cache_safe_exact_identity_profile(self):
        specification = stage.STAGE_PROFILES["0.2.2-community-r2"]
        self.assertEqual(specification["marker"], community_r22.MARKER)
        self.assertEqual(specification["patcher"], "community-r2.2")
        self.assertEqual(specification["safety"]["languages"], ["en"])
        self.assertTrue(specification["safety"]["cacheSafeCommunityAssets"])
        self.assertTrue(specification["safety"]["exactStatus1MutationGate"])
        self.assertTrue(specification["safety"]["exactStatus1AuthGate"])
        self.assertFalse(specification["safety"]["nativeDetailedLog"])
        self.assertEqual(len(community_r22.REMOVED_RECORDS), 18)
        self.assertEqual(
            set(community_r22.CUSTOM_FILES)
            | set(community_r22.ADDITION_OUTPUT_RECORDS),
            {
                community_r22.AUTH_PATH,
                community_r21.DIAGNOSTICS_HTML_PATH,
                community_r21.DIAGNOSTICS_JS_PATH,
                community_r22.BOOT_PATH,
                community_r22.CSS_PATH,
                community_r22.SMS_JS_PATH,
                community_r22.SMS_HTML_PATH,
                community_r22.DIAGNOSTICS_JS_PATH,
                community_r22.DIAGNOSTICS_HTML_PATH,
                community_r22.DASHBOARD_JS_PATH,
                community_r22.DASHBOARD_HTML_PATH,
            },
        )
        provenance = stage.derived_source_records(community_r22)
        self.assertEqual(
            {item["target"] for item in provenance},
            set(community_r22.OUTPUT_RECORDS)
            | set(community_r22.CUSTOM_FILES)
            | set(community_r22.ADDITION_OUTPUT_RECORDS),
        )
        self.assertEqual(len(provenance), 21)
        with self.assertRaisesRegex(stage.StageBuildError, "reviewed golden"):
            stage.load_profile_sources("0.2.2-community-r2")

    def test_community_r23_is_registered_and_every_output_is_pinned(self):
        specification = stage.STAGE_PROFILES["0.2.3-community-r2"]
        self.assertEqual(specification["marker"], community_r23.MARKER)
        self.assertEqual(specification["patcher"], "community-r2.3")
        self.assertEqual(specification["safety"]["languages"], ["en"])
        self.assertEqual(specification["safety"]["displayPaginationPageSize"], 10)
        self.assertFalse(specification["safety"]["ussdTransportProven"])
        self.assertFalse(specification["safety"]["smsPollingDefaultEnabled"])
        self.assertEqual(specification["safety"]["smsPollingMinimumSeconds"], 60)
        self.assertFalse(specification["safety"]["smsPollingStoresMessageData"])
        self.assertFalse(specification["safety"]["canonicalVendorUiLoadsCommunityCode"])
        pinned = bool(community_r23.OUTPUT_RECORDS and community_r23.ADDITION_OUTPUT_RECORDS)
        self.assertEqual(specification["safety"]["buildPinned"], pinned)
        self.assertEqual(len(community_r23.REMOVED_RECORDS), 18)
        self.assertTrue(pinned)
        provenance = stage.derived_source_records(community_r23)
        self.assertEqual(
            {item["target"] for item in provenance},
            set(community_r23.OUTPUT_RECORDS)
            | set(community_r23.CUSTOM_FILES)
            | set(community_r23.ADDITION_OUTPUT_RECORDS),
        )
        self.assertEqual(len(provenance), 19)
        manifest = json.loads((ROOT / "firmware/community-r2.3/manifest.json").read_text())
        self.assertEqual(
            {item["target"]: (item["size"], item["sha256"]) for item in manifest["sources"]},
            {
                target: (size, digest)
                for target, (_source, size, digest) in community_r23.CUSTOM_FILES.items()
            },
        )
        self.assertEqual(
            {item["target"]: (item["size"], item["sha256"]) for item in manifest["derived_outputs"]},
            {
                target: (size, digest)
                for target, (size, digest, _source) in community_r23.ADDITION_OUTPUT_RECORDS.items()
            },
        )
        self.assertEqual(manifest["logical_change_counts"], {"replaced": 6, "added": 13, "removed": 18})
        self.assertEqual(manifest["artifact"]["sha256"], "06d79b9e51d54e87e4065ceabac63d70b4d34b72b21bfa096a1132d1b45af86b")
        self.assertEqual(manifest["artifact"]["portable_plaintext_sha256"], "6cac69f41874f3b559183a4539e0bd0fa5de89b085e663df337375fa505b2887")
        self.assertEqual(manifest["webi_padding_bytes_remaining"], 80_392)
        with self.assertRaisesRegex(stage.StageBuildError, "reviewed golden"):
            stage.load_profile_sources("0.2.3-community-r2")

    def test_community_r24_is_registered_read_only_and_every_output_is_pinned(self):
        specification = stage.STAGE_PROFILES["0.2.4-community-r2"]
        safety = specification["safety"]
        self.assertEqual(specification["marker"], community_r24.MARKER)
        self.assertEqual(specification["patcher"], "community-r2.4")
        self.assertEqual(safety["modemMonitorEndpoints"], ["status1", "wan", "Engineer_parameter"])
        self.assertTrue(safety["modemMonitorReadOnly"])
        self.assertFalse(safety["modemMonitorPollingDefaultEnabled"])
        self.assertEqual(safety["modemMonitorPollingMinimumSeconds"], 30)
        self.assertFalse(safety["safeDiagnosticsBackgroundPolling"])
        self.assertFalse(safety["wispScanOrConnectEnabled"])
        self.assertFalse(safety["ussdTransportProven"])
        self.assertFalse(safety["ttlMutationEnabled"])
        self.assertFalse(safety["imeiMutationEnabled"])
        pinned = bool(community_r24.OUTPUT_RECORDS and community_r24.ADDITION_OUTPUT_RECORDS)
        self.assertEqual(safety["buildPinned"], pinned)
        self.assertTrue(pinned)
        provenance = stage.derived_source_records(community_r24)
        self.assertEqual(
            {item["target"] for item in provenance},
            set(community_r24.OUTPUT_RECORDS)
            | set(community_r24.CUSTOM_FILES)
            | set(community_r24.ADDITION_OUTPUT_RECORDS),
        )
        self.assertEqual(len(provenance), 21)
        manifest = json.loads((ROOT / "firmware/community-r2.4/manifest.json").read_text())
        direct = {item["file"]: (item["size"], item["sha256"]) for item in manifest["sources"]}
        self.assertEqual(
            direct,
            {
                "Modem.html": (2_571, "58f027f4d540a9a2dd9de35142945a48b61a6cc958780939f64fd85044fb9b8b"),
                "modem_monitor.js": (25_164, "bed9c502dbd7c6c27549b3797e078214e8d9449abb424466e3ae3b9d4a5a8526"),
                "community_ui_additions.css": (2_084, "c625f22962ae4d6acac64559cb7f82c9f84d1f89ec9bf85f38493f4c98ecd8e4"),
            },
        )
        self.assertEqual(
            {item["target"]: (item["size"], item["sha256"]) for item in manifest["derived_outputs"]},
            {
                target: (size, digest)
                for target, (size, digest, _source) in community_r24.ADDITION_OUTPUT_RECORDS.items()
            },
        )
        self.assertEqual(manifest["logical_change_counts"], {"replaced": 6, "added": 15, "removed": 18})
        self.assertEqual(manifest["artifact"]["sha256"], "5bc408710afa5e78836c49da91656a8f94d804ee4fe64c53f6ef7d53786fd7db")
        self.assertEqual(manifest["artifact"]["portable_plaintext_sha256"], "e33038e8a80838db6d91d347c4fc0c06480e365f577627edbf7a3cdf95e0bdc1")
        self.assertEqual(manifest["webi_padding_bytes_remaining"], 49_680)
        with self.assertRaisesRegex(stage.StageBuildError, "reviewed golden"):
            stage.load_profile_sources("0.2.4-community-r2")

    def test_community_profile_is_bound_to_safe_exact_sources(self):
        replacements = stage.load_profile_sources("0.1-community-r1")
        specification = stage.STAGE_PROFILES["0.1-community-r1"]
        self.assertEqual(set(replacements), set(specification["files"]))
        joined = b"\n".join(replacements.values())
        self.assertIn(specification["marker"], joined)
        for forbidden in (b"SEND_SMS", b"detailed_log", b"canary_logs", b"mfSmsLog"):
            self.assertNotIn(forbidden.lower(), joined.lower())
        for target, data in replacements.items():
            with self.subTest(target=target):
                source = specification["files"][target]
                self.assertEqual(len(data), source["size"])
                self.assertEqual(inspector.sha256(data), source["sha256"])

    def test_sms_profile_is_bound_to_every_exact_source(self):
        replacements = stage.load_profile_sources("0.0-sms-r1")
        specification = stage.STAGE_PROFILES["0.0-sms-r1"]
        self.assertEqual(set(replacements), set(specification["files"]))
        for target, data in replacements.items():
            with self.subTest(target=target):
                source = specification["files"][target]
                self.assertEqual(len(data), source["size"])
                self.assertEqual(inspector.sha256(data), source["sha256"])
                with self.assertRaises(stage.StageBuildError):
                    stage.validate_profile_source(data + b"\n", source)

    def test_unresolved_ussd_profile_is_not_buildable(self):
        with self.assertRaisesRegex(stage.StageBuildError, "unbuildable"):
            stage.load_profile_sources("0.0-ussd-r1")
        with self.assertRaisesRegex(stage.StageBuildError, "unbuildable"):
            stage.build_stage_image(b"", None, "0.0-ussd-r1")

    @unittest.skipUnless(
        LOCAL_GOLDEN.is_file() and LOCAL_IDENTITY.is_file(),
        "exact local golden and identity are optional in CI",
    )
    def test_private_sms_stage_is_deterministic_and_changes_only_reviewed_webi_records(self):
        raw = LOCAL_GOLDEN.read_bytes()
        identity = inspector.load_identity(LOCAL_IDENTITY)
        first, first_report = stage.build_stage_image(raw, identity, "0.0-sms-r1")
        second, second_report = stage.build_stage_image(raw, identity, "0.0-sms-r1")
        self.assertEqual(first, second)
        self.assertEqual(first_report, second_report)
        self.assertEqual(len(first), 8_323_644)
        self.assertEqual(
            inspector.sha256(first),
            "c27b5f7989ac4e4ac6ff1ebdd603685f6f1fe777918458059b620b1c36ec73ce",
        )
        self.assertEqual(
            [item["path"] for item in first_report["cafe"]["changes"]],
            [
                "www\\html\\SMS\\SMS.html",
                "www\\js\\panel\\SMS\\SMS.js",
            ],
        )
        self.assertEqual(first_report["cafe"]["additions"], [])
        self.assertGreater(first_report["cafe"]["padding_after"], 40_000)

    @unittest.skipUnless(
        LOCAL_GOLDEN.is_file() and LOCAL_IDENTITY.is_file(),
        "exact local golden and identity are optional in CI",
    )
    def test_private_community_r1_is_deterministic_and_exactly_scoped(self):
        raw = LOCAL_GOLDEN.read_bytes()
        identity = inspector.load_identity(LOCAL_IDENTITY)
        first, first_report = stage.build_stage_image(raw, identity, "0.1-community-r1")
        second, second_report = stage.build_stage_image(raw, identity, "0.1-community-r1")
        self.assertEqual(first, second)
        self.assertEqual(first_report, second_report)
        self.assertEqual(len(first), 8_323_644)
        self.assertEqual(
            inspector.sha256(first),
            "d42a912e31aafed4e57c6c98d94932444a0b2cf1fe0f8e223c95b3df22dae676",
        )
        self.assertEqual(
            [item["path"] for item in first_report["cafe"]["changes"]],
            [
                "www\\html\\SMS\\SMS.html",
                "www\\js\\panel\\SMS\\SMS.js",
            ],
        )
        self.assertEqual(first_report["cafe"]["additions"], [])
        self.assertEqual(first_report["cafe"]["padding_after"], 48_472)

    @unittest.skipUnless(
        LOCAL_GOLDEN.is_file() and LOCAL_IDENTITY.is_file(),
        "exact local golden and identity are optional in CI",
    )
    def test_private_community_r2_is_deterministic_english_only_and_exactly_scoped(self):
        raw = LOCAL_GOLDEN.read_bytes()
        identity = inspector.load_identity(LOCAL_IDENTITY)
        first, first_report = stage.build_stage_image(raw, identity, "0.2-community-r2")
        second, second_report = stage.build_stage_image(raw, identity, "0.2-community-r2")
        self.assertEqual(first, second)
        self.assertEqual(first_report, second_report)
        self.assertEqual(len(first), 8_323_644)
        self.assertEqual(
            inspector.sha256(first),
            "aebc751d87d8a007fc50cfb6b0788a6168127ca8988d989176de902986a487ee",
        )
        self.assertEqual(
            stage.base.portable_plaintext_sha256(first, identity),
            "022b36407d6f9e38da6b45d21a86461501398bb3e142b9048df8414594413a9f",
        )
        delta = first_report["profile_delta"]
        self.assertEqual(len(delta["replaced_paths"]), 10)
        self.assertEqual(delta["added_paths"], [community_r2.AUTH_PATH])
        self.assertEqual(delta["removed_paths"], sorted(community_r2.REMOVED_RECORDS))
        self.assertEqual(
            sum(item["stored_size"] + 136 for item in first_report["cafe"]["removals"]),
            community_r2.REMOVED_ARCHIVE_BYTES,
        )
        self.assertEqual(first_report["cafe"]["padding_after"], 306_308)

    @unittest.skipUnless(
        LOCAL_GOLDEN.is_file() and LOCAL_IDENTITY.is_file(),
        "exact local golden and identity are optional in CI",
    )
    def test_private_community_r21_is_deterministic_and_exactly_scoped(self):
        raw = LOCAL_GOLDEN.read_bytes()
        identity = inspector.load_identity(LOCAL_IDENTITY)
        first, first_report = stage.build_stage_image(raw, identity, "0.2.1-community-r2")
        second, second_report = stage.build_stage_image(raw, identity, "0.2.1-community-r2")
        self.assertEqual(first, second)
        self.assertEqual(first_report, second_report)
        self.assertEqual(len(first), 8_323_644)
        self.assertEqual(
            inspector.sha256(first),
            "51bd396c69e9c8db96249455092634b6b54552f64f5c4daee6f710b644759c95",
        )
        self.assertEqual(
            stage.base.portable_plaintext_sha256(first, identity),
            "9b7312ae365f3a381a060b4d28a0de719e64aaffe29893dcb2601987e9dfcd2a",
        )
        delta = first_report["profile_delta"]
        self.assertEqual(len(delta["replaced_paths"]), 10)
        self.assertEqual(
            delta["added_paths"],
            sorted(
                [
                    community_r21.AUTH_PATH,
                    community_r21.DIAGNOSTICS_HTML_PATH,
                    community_r21.DIAGNOSTICS_JS_PATH,
                ]
            ),
        )
        self.assertEqual(delta["removed_paths"], sorted(community_r21.REMOVED_RECORDS))
        self.assertEqual(first_report["cafe"]["padding_after"], 278_636)

        header = inspector.decrypt_header(first, identity)
        partitions, layout_errors = inspector.parse_partitions(header, len(first))
        self.assertEqual(layout_errors, [])
        webi = next(item for item in partitions if item.name == "WEBI")
        _, records, _ = stage.base.parse_cafe_source(
            first[webi.offset : webi.offset + webi.length]
        )
        logical = {record.path: record.logical_data for record in records}
        menu = logical["www\\xml\\ui_mifi.xml"]
        dashboard = logical["www\\html\\dashboard.html"]
        index = logical["www\\index.html"]
        self.assertEqual(menu.count(b"<Tab Name='tDiagnostics'"), 1)
        self.assertEqual(menu.count(b"implFunction='objDiagnostics'"), 1)
        self.assertLess(menu.index(b"<Tab Name='tSetting'"), menu.index(b"<Tab Name='tSms'"))
        self.assertLess(menu.index(b"<Tab Name='tSms'"), menu.index(b"<Tab Name='tDiagnostics'"))
        self.assertEqual(dashboard.count(b"dashboardOnClick(5,'mDeviceInbox')"), 1)
        self.assertEqual(dashboard.count(b"dashboardOnClick(6,'mDiagnostics')"), 1)
        self.assertEqual(index.count(b"js/community_diagnostics.js"), 1)

    @unittest.skipUnless(
        LOCAL_GOLDEN.is_file() and LOCAL_IDENTITY.is_file(),
        "exact local golden and identity are optional in CI",
    )
    def test_private_community_r22_is_deterministic_cache_safe_and_exactly_scoped(self):
        raw = LOCAL_GOLDEN.read_bytes()
        identity = inspector.load_identity(LOCAL_IDENTITY)
        first, first_report = stage.build_stage_image(raw, identity, "0.2.2-community-r2")
        second, second_report = stage.build_stage_image(raw, identity, "0.2.2-community-r2")
        self.assertEqual(first, second)
        self.assertEqual(first_report, second_report)
        self.assertEqual(len(first), 8_323_644)
        self.assertEqual(
            inspector.sha256(first),
            "80e94750bf820e1fdbf6f51b8b2462cad633e28d19571610ce744bac7e6e04d5",
        )
        self.assertEqual(
            stage.base.portable_plaintext_sha256(first, identity),
            "c712f4774d8d4dc05e1a70ddd34cb8f508e705705b9cb16e3174bbb991d612ec",
        )
        delta = first_report["profile_delta"]
        self.assertEqual(len(delta["replaced_paths"]), 10)
        self.assertEqual(
            delta["added_paths"],
            sorted(
                [
                    community_r22.AUTH_PATH,
                    community_r21.DIAGNOSTICS_HTML_PATH,
                    community_r21.DIAGNOSTICS_JS_PATH,
                    community_r22.BOOT_PATH,
                    community_r22.CSS_PATH,
                    community_r22.SMS_JS_PATH,
                    community_r22.SMS_HTML_PATH,
                    community_r22.DIAGNOSTICS_JS_PATH,
                    community_r22.DIAGNOSTICS_HTML_PATH,
                    community_r22.DASHBOARD_JS_PATH,
                    community_r22.DASHBOARD_HTML_PATH,
                ]
            ),
        )
        self.assertEqual(delta["removed_paths"], sorted(community_r22.REMOVED_RECORDS))
        self.assertEqual(first_report["cafe"]["padding_after"], 162_428)

        header = inspector.decrypt_header(first, identity)
        partitions, layout_errors = inspector.parse_partitions(header, len(first))
        self.assertEqual(layout_errors, [])
        webi = next(item for item in partitions if item.name == "WEBI")
        _, records, _ = stage.base.parse_cafe_source(
            first[webi.offset : webi.offset + webi.length]
        )
        logical = {record.path: record.logical_data for record in records}
        index = logical["www\\index.html"]
        dashboard = logical["www\\html\\dashboard.html"]
        self.assertEqual(index.count(b"js/r22boot.js"), 1)
        self.assertEqual(index.count(b"js/r22auth.js"), 1)
        self.assertEqual(index.count(b"js/r22diag.js"), 1)
        self.assertLess(index.index(b"js/r22boot.js"), index.index(b"js/r22auth.js"))
        self.assertLess(index.index(b"js/r22auth.js"), index.index(b"js/r22diag.js"))
        self.assertEqual(index.count(b"js/panel/SMS/r22sms.js"), 1)
        self.assertEqual(index.count(b"js/panel/r22dash.js"), 1)
        self.assertEqual(index.count(b"css/r22ui.css"), 1)
        self.assertNotIn(b"src=\"js/community_diagnostics.js\"", index)
        self.assertNotIn(b"src=\"js/community_auth.js\"", index)
        self.assertNotIn(b"src=\"js/panel/SMS/SMS.js\"", index)
        self.assertNotIn(b"src=\"js/panel/dashboard.js\"", index)
        self.assertEqual(index.count(b"MF885CommunityR22.seedLabels()"), 2)
        self.assertIn(community_r22.MARKER, dashboard)
        self.assertNotIn(community_r21.AUTH_PATH, logical)
        self.assertIn(b"width:16px !important", logical[community_r22.CSS_PATH])
        self.assertEqual(inspector.sha256(logical[community_r22.SMS_JS_PATH]), "601c01239346fe02e051cc19e8b67c3a4cd3baa48eebf0b8c95dd0e8c777b599")
        self.assertEqual(inspector.sha256(logical[community_r22.AUTH_PATH]), "4a820b497262c53d0e30ce11bf81125bd2532edeb80507d2a8262113ca2af01f")
        self.assertEqual(inspector.sha256(logical[community_r22.DIAGNOSTICS_JS_PATH]), "ecca26d09a4ac2b00a1aa209043760df0df1d2dd4d7cfd8215bdd74f0ca066ff")
        self.assertEqual(logical[community_r22.DASHBOARD_HTML_PATH], dashboard)
        self.assertEqual(inspector.sha256(logical[community_r22.DASHBOARD_JS_PATH]), "a49ea2480acf2e05edfb40096a49b59c9d0fa59ec9431624cb6c119d4c1f02a9")

    @unittest.skipUnless(
        LOCAL_GOLDEN.is_file() and LOCAL_IDENTITY.is_file(),
        "exact local golden and identity are optional in CI",
    )
    def test_private_community_r23_is_deterministic_responsive_and_exactly_scoped(self):
        raw = LOCAL_GOLDEN.read_bytes()
        identity = inspector.load_identity(LOCAL_IDENTITY)
        first, first_report = stage.build_stage_image(raw, identity, "0.2.3-community-r2")
        second, second_report = stage.build_stage_image(raw, identity, "0.2.3-community-r2")
        self.assertEqual(first, second)
        self.assertEqual(first_report, second_report)
        self.assertEqual(len(first), 8_323_644)
        self.assertEqual(inspector.sha256(first), "06d79b9e51d54e87e4065ceabac63d70b4d34b72b21bfa096a1132d1b45af86b")
        self.assertEqual(stage.base.portable_plaintext_sha256(first, identity), "6cac69f41874f3b559183a4539e0bd0fa5de89b085e663df337375fa505b2887")
        delta = first_report["profile_delta"]
        self.assertEqual(len(delta["replaced_paths"]), 6)
        self.assertEqual(len(delta["added_paths"]), 13)
        self.assertEqual(delta["removed_paths"], sorted(community_r23.REMOVED_RECORDS))
        self.assertEqual(first_report["cafe"]["padding_after"], 80_392)

        header = inspector.decrypt_header(first, identity)
        partitions, layout_errors = inspector.parse_partitions(header, len(first))
        self.assertEqual(layout_errors, [])
        webi = next(item for item in partitions if item.name == "WEBI")
        _, records, _ = stage.base.parse_cafe_source(first[webi.offset : webi.offset + webi.length])
        logical = {record.path: record.logical_data for record in records}
        _, golden_records, _ = stage.base.parse_cafe_source(raw[webi.offset : webi.offset + webi.length])
        golden_logical = {record.path: record.logical_data for record in golden_records}
        legacy_index = logical["www\\index.html"]
        modern_index = logical[community_r23.ENTRY_PATH]
        self.assertNotEqual(legacy_index, modern_index)
        self.assertEqual(legacy_index.count(b'href="/r23.html"'), 1)
        for route in (b"r23boot.js", b"r23auth.js", b"r23diag.js", b"r23sms.js", b"r23dash.js", b"r23ui.css", b"r23utils.js", b"r23layout.js"):
            self.assertNotIn(route, legacy_index)
            self.assertEqual(modern_index.count(route), 1)
        self.assertIn(b'name="viewport" content="width=device-width, initial-scale=1"', modern_index)
        self.assertNotIn(b"r22boot.js", modern_index)
        self.assertIn(community_r23.MARKER, logical[community_r23.DASHBOARD_HTML_PATH])
        for stock_path in (
            "www\\xml\\ui_mifi.xml", "www\\html\\dashboard.html",
            "www\\html\\SMS\\SMS.html", "www\\js\\panel\\SMS\\SMS.js",
        ):
            self.assertEqual(logical[stock_path], golden_logical[stock_path])
        self.assertEqual(len(stage.derived_source_records(community_r23)), 19)

    @unittest.skipUnless(
        LOCAL_GOLDEN.is_file() and LOCAL_IDENTITY.is_file(),
        "exact local golden and identity are optional in CI",
    )
    def test_private_community_r24_is_deterministic_read_only_and_exactly_scoped(self):
        raw = LOCAL_GOLDEN.read_bytes()
        identity = inspector.load_identity(LOCAL_IDENTITY)
        first, first_report = stage.build_stage_image(raw, identity, "0.2.4-community-r2")
        second, second_report = stage.build_stage_image(raw, identity, "0.2.4-community-r2")
        self.assertEqual(first, second)
        self.assertEqual(first_report, second_report)
        self.assertEqual(len(first), 8_323_644)
        self.assertEqual(inspector.sha256(first), "5bc408710afa5e78836c49da91656a8f94d804ee4fe64c53f6ef7d53786fd7db")
        self.assertEqual(stage.base.portable_plaintext_sha256(first, identity), "e33038e8a80838db6d91d347c4fc0c06480e365f577627edbf7a3cdf95e0bdc1")
        delta = first_report["profile_delta"]
        self.assertEqual(len(delta["replaced_paths"]), 6)
        self.assertEqual(len(delta["added_paths"]), 15)
        self.assertEqual(delta["removed_paths"], sorted(community_r24.REMOVED_RECORDS))
        self.assertEqual(first_report["cafe"]["padding_after"], 49_680)

        header = inspector.decrypt_header(first, identity)
        partitions, layout_errors = inspector.parse_partitions(header, len(first))
        self.assertEqual(layout_errors, [])
        for partition in partitions:
            if partition.name != "WEBI":
                start, end = partition.offset, partition.offset + partition.length
                self.assertEqual(first[start:end], raw[start:end], partition.name)
        webi = next(item for item in partitions if item.name == "WEBI")
        _, records, _ = stage.base.parse_cafe_source(first[webi.offset : webi.offset + webi.length])
        logical = {record.path: record.logical_data for record in records}
        _, golden_records, _ = stage.base.parse_cafe_source(raw[webi.offset : webi.offset + webi.length])
        golden_logical = {record.path: record.logical_data for record in golden_records}
        legacy_index = logical["www\\index.html"]
        modern_index = logical[community_r24.ENTRY_PATH]
        self.assertEqual(legacy_index.count(b'href="/r24.html"'), 1)
        for route in (b"r24boot.js", b"r24auth.js", b"r24diag.js", b"r24modem.js", b"r24sms.js", b"r24dash.js", b"r24ui.css", b"r24utils.js", b"r24layout.js"):
            self.assertNotIn(route, legacy_index)
            self.assertEqual(modern_index.count(route), 1)
        for stock_path in (
            "www\\xml\\ui_mifi.xml", "www\\html\\dashboard.html",
            "www\\html\\SMS\\SMS.html", "www\\js\\panel\\SMS\\SMS.js",
        ):
            self.assertEqual(logical[stock_path], golden_logical[stock_path])
        modem = logical[community_r24.MODEM_JS_PATH]
        sms = logical[community_r24.SMS_JS_PATH]
        self.assertEqual(modem, (ROOT / "firmware/community-r2.4/modem_monitor.js").read_bytes())
        self.assertEqual(sms.count(b"modemReadBusy()"), 6)
        self.assertIn(b"var writeBusy=busy||session.busy||modemReadBusy();", sms)
        self.assertNotIn(b"PostXML", modem)
        self.assertNotIn(b"method=set", modem)
        self.assertNotIn(b"wlan_cli_scan", modem)


if __name__ == "__main__":
    unittest.main()
