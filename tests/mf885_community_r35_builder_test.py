import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mf885_community_r35 as release  # noqa: E402
import mf885_firmware_inspect as inspector  # noqa: E402
import mf885_webi_builder as webi  # noqa: E402
import mf885_webui_stage_builder as stage  # noqa: E402


GOLDEN = ROOT / ".runtime" / "private" / "MF885_golden_capture_a.bin"
IDENTITY = ROOT / ".runtime" / "private" / "mf885-base-identity-20260821.xml"


class CommunityR35SourceTests(unittest.TestCase):
    def test_profile_exposes_same_model_ttl_and_preserves_engineering(self):
        profile = stage.STAGE_PROFILES[release.PROFILE]
        safety = profile["safety"]
        self.assertEqual(profile["patcher"], "community-r3.5")
        self.assertEqual(profile["marker"], release.MARKER)
        self.assertTrue(safety["ttlAvailable"])
        self.assertEqual(safety["ttlReadSetterCalls"], 1)
        self.assertEqual(safety["ttlSetResponseSetterCalls"], 0)
        self.assertIn("diagnostic.output", safety["ttlReadPublicationLifecycle"])
        self.assertIn("fresh strict diagnostic.output GET", safety["ttlMutationGate"])
        self.assertFalse(safety["systemChannelBridgeUsed"])
        self.assertFalse(safety["engineeringWanRowChanged"])
        self.assertFalse(safety["engineeringDebugonRowChanged"])
        self.assertFalse(safety["engineeringDebugonCallbackChanged"])
        self.assertEqual(safety["automaticMutationRetries"], 0)
        self.assertTrue(safety["buildPinned"])

    @unittest.skipUnless(GOLDEN.is_file(), "exact private golden is optional in CI")
    def test_outputs_and_read_write_templates_are_exact_and_isolated(self):
        raw = GOLDEN.read_bytes()
        webi_payload = raw[0x52023C:0x52023C + 0x1C0000]
        _header, records, _sentinel = webi.parse_cafe_source(webi_payload)
        source = {item.path: item.logical_data for item in records}
        replacements, additions, removals = release.build_patch_set(source, ROOT)
        self.assertEqual(set(replacements), set(release.OUTPUT_RECORDS))
        self.assertEqual(set(additions), set(release.ADDITION_OUTPUT_RECORDS))
        self.assertEqual(removals, set(release.REMOVED_RECORDS))
        for path, (size, digest) in release.OUTPUT_RECORDS.items():
            self.assertEqual((len(replacements[path]), hashlib.sha256(replacements[path]).hexdigest()), (size, digest))
        for path, (size, digest, _source) in release.ADDITION_OUTPUT_RECORDS.items():
            self.assertEqual((len(additions[path]), hashlib.sha256(additions[path]).hexdigest()), (size, digest))
        read_template = replacements[release.DIAGNOSTIC_PATH]
        set_template = additions[release.TTL_SET_PATH]
        self.assertIn(b"<diagnostic>", read_template)
        self.assertIn(b"<output />", read_template)
        self.assertNotIn(b"<command", read_template)
        self.assertNotIn(b"<arg", read_template)
        self.assertNotIn(b"SystemChannelName", read_template)
        self.assertIn(b"<command>", set_template)
        self.assertIn(b"<arg>", set_template)
        self.assertNotIn(b"<output", set_template)
        self.assertNotIn(b"SystemChannelName", set_template)
        app = additions[release.APP_PATH]
        self.assertEqual(app.count(b"file=ttl_set"), 1)
        self.assertEqual(app.count(b"modelGet('diagnostic'"), 1)
        for exact_guard in (
            b"rootTag==='RGW'",
            b"rootAttrCount===0",
            b"rootElementCount===1",
            b"!rootSignificantText",
            b"modelAttrCount===0",
            b"modelElementCount===1",
            b"!modelSignificantText",
            b"outputAttrCount===0",
            b"outputElementCount===0",
            b"String(outputNode.textContent||''):null",
        ):
            self.assertIn(exact_guard, app)
        self.assertNotIn(b"SystemChannelName", app)
        self.assertNotIn(b"PRODUCT_CHANNEL", app)
        self.assertNotIn(b"debugmodeon", app)

    @unittest.skipUnless(GOLDEN.is_file() and IDENTITY.is_file(), "exact private fixtures are optional in CI")
    def test_exact_golden_web_stage_is_deterministic(self):
        identity = inspector.load_identity(IDENTITY)
        raw = webi.require_reviewed_golden(GOLDEN, identity)
        first, first_report = stage.build_stage_image(raw, identity, release.PROFILE)
        second, second_report = stage.build_stage_image(raw, identity, release.PROFILE)
        self.assertEqual(first, second)
        self.assertEqual(first_report, second_report)
        self.assertEqual(len(first), 8_323_644)
        self.assertEqual(first_report["profile_delta"]["added_paths"], sorted(release.ADDITION_OUTPUT_RECORDS))
        self.assertEqual(first_report["profile_delta"]["replaced_paths"], sorted(release.OUTPUT_RECORDS))


if __name__ == "__main__":
    unittest.main()
