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


if __name__ == "__main__":
    unittest.main()
