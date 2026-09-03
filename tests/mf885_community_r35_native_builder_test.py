import json
import sys
import tempfile
import unittest
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mf885_community_r35_native_builder as builder  # noqa: E402
import mf885_firmware_inspect as inspector  # noqa: E402
import mf885_webi_builder as webi  # noqa: E402


GOLDEN = ROOT / ".runtime" / "private" / "MF885_golden_capture_a.bin"
IDENTITY = ROOT / ".runtime" / "private" / "mf885-base-identity-20260821.xml"
RETAINED = ROOT / ".runtime" / "private" / "r35-same-model-ttl-candidate-c"


@unittest.skipUnless(GOLDEN.is_file() and IDENTITY.is_file(), "exact private fixtures are optional in CI")
class CommunityR35NativeBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.identity = inspector.load_identity(IDENTITY)
        cls.golden = webi.require_reviewed_golden(GOLDEN, cls.identity)
        cls.first, cls.first_report = builder.build_candidate(cls.golden, cls.identity)
        cls.second, cls.second_report = builder.build_candidate(cls.golden, cls.identity)
        cls.verification = builder.verify_candidate(cls.golden, cls.first, cls.identity)

    def test_double_build_is_byte_and_report_deterministic(self):
        self.assertEqual(self.first, self.second)
        self.assertEqual(self.first_report, self.second_report)
        self.assertEqual(len(self.first), 8_323_644)

    def test_native_surface_is_same_model_and_preserves_sensitive_stock_paths(self):
        native = self.first_report["native"]
        ranges = {item["name"]: item for item in native["changed_ranges"]}
        self.assertEqual(native["state"]["address"], "0x06001430")
        self.assertEqual(native["transport"]["publisher_slot"], "post_get")
        self.assertEqual(native["transport"]["publisher_setter_calls"], 1)
        self.assertEqual(native["transport"]["read_model"], "diagnostic")
        self.assertEqual(native["transport"]["read_field"], "output")
        self.assertTrue(native["transport"]["same_model_publication"])
        self.assertFalse(native["transport"]["system_channel_bridge_used"])
        self.assertEqual(native["transport"]["set_response_setter_calls"], 0)
        self.assertFalse(native["engineering"]["wan_engineering_mode_changed"])
        self.assertFalse(native["engineering"]["debugon_row_changed"])
        self.assertFalse(native["engineering"]["debugon_callback_changed"])
        self.assertFalse(native["engineering"]["system_channel_row_changed"])
        self.assertFalse(native["engineering"]["system_channel_callback_changed"])
        self.assertTrue(all(item["passed"] for item in native["engineering"]["conditions"]))
        self.assertIn("diagnostic_post_get_pointer", ranges)
        self.assertIn("diagnostic_post_set_pointer", ranges)
        self.assertNotIn("diagnostic_pre_get_pointer", ranges)
        self.assertTrue(all(item["passed"] for item in self.first_report["native_allowed_ranges"]["conditions"]))

    def test_live_claims_remain_honestly_unqualified(self):
        native = self.first_report["native"]
        self.assertTrue(native["qualification"]["offline_machine_contract"])
        self.assertFalse(native["qualification"]["live_get"])
        self.assertFalse(native["qualification"]["live_set"])
        self.assertFalse(native["qualification"]["live_packet_path"])
        self.assertFalse(native["state"]["persistent"])

    def test_full_verifier_and_independent_container_are_green(self):
        self.assertEqual(self.verification["status"], "GREEN")
        self.assertTrue(all(item["passed"] for item in self.verification["conditions"]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / builder.ARTIFACT
            path.write_bytes(self.first)
            parsed = inspector.inspect_image(path, self.identity, include_records=True)
        self.assertEqual(parsed.report["verification"]["status"], "verified")

    def test_reports_are_complete_json(self):
        self.assertGreater(len(json.dumps(self.first_report, sort_keys=True)), 1_000)
        self.assertGreater(len(json.dumps(self.verification, sort_keys=True)), 1_000)

    def test_retained_delivery_artifact_and_report_match_fresh_build(self):
        artifact_path = RETAINED / builder.ARTIFACT
        report_path = RETAINED / "build-report.json"
        retained = artifact_path.read_bytes()
        report_bytes = report_path.read_bytes()
        report = json.loads(report_bytes)
        self.assertEqual(retained, self.first)
        expected = json.loads(
            json.dumps(
                builder.delivery_report(
                    source_name=GOLDEN.name,
                    artifact_name=builder.ARTIFACT,
                    golden_raw=self.golden,
                    artifact=self.first,
                    build=self.first_report,
                    verification=self.verification,
                    independent_container_status="verified",
                )
            )
        )
        self.assertEqual(report, expected)
        self.assertEqual(report_bytes, (json.dumps(expected, indent=2, sort_keys=True) + "\n").encode())
        self.assertEqual(report["artifact"]["sha256"], hashlib.sha256(self.first).hexdigest())
        additions = {
            item["path"]: (item["size"], item["sha256"])
            for item in report["build"]["webui"]["cafe"]["additions"]
        }
        self.assertEqual(
            additions["www\\js\\r35app.js"],
            (76_227, "97043bc4487c650e27213536b212f7835dd36acbd57614988873567eb0a75d11"),
        )


if __name__ == "__main__":
    unittest.main()
