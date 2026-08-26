import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mf885_firmware_inspect as inspector  # noqa: E402
import mf885_community_r2 as community_r2  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
