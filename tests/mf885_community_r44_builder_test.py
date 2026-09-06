import hashlib
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mf885_build_variant as wrapper
import mf885_community_r43 as previous
import mf885_community_r44 as release
import mf885_community_r44_native_builder as builder
import mf885_firmware_inspect as inspector
import mf885_webi_builder as webi
import mf885_webui_stage_builder as stage


GOLDEN = Path(os.environ.get("MF885_TEST_GOLDEN", str(ROOT / "input/MF885_golden.bin")))
IDENTITY = Path(os.environ.get("MF885_TEST_IDENTITY", str(ROOT / "input/mf885-base.xml")))
ARTIFACT_SHA256 = "f6b4ce3eb99d75c86a329e77e791c65b1095cf50247004faaa6017d5b08d9316"


class R44SourceTests(unittest.TestCase):
    def test_profile_has_distinct_marker_and_truthful_fixed64_limits(self):
        profile = stage.STAGE_PROFILES[release.PROFILE]
        self.assertEqual(profile["marker"], b"MF885 Community R4.4 extension 0.4.4-community-r2")
        self.assertEqual(profile["patcher"], "community-r4.4")
        safety = profile["safety"]
        self.assertEqual(safety["ttlFixedValue"], 64)
        self.assertEqual(safety["ttlMode"], "fixed-64")
        self.assertEqual(safety["ttlScope"], "eligible-forwarded-ipv4-both-directions")
        self.assertTrue(safety["ttlForwardingHookIncludedInFullImage"])
        self.assertFalse(any(key.startswith("diagnosticNative") for key in safety))
        for key in ("ttlBrowserGetRequests", "ttlBrowserPostRequests", "diagnosticBrowserRequests", "diagnosticGetCallbacks"):
            self.assertEqual(safety[key], 0, key)
        for key in ("ttlAvailable", "ttlRuntimeOffAvailable", "ttlDirectionFilter", "ttlPacketPathQualified"):
            self.assertFalse(safety[key], key)
        # The prior context-read profile remains unchanged.
        self.assertEqual(stage.STAGE_PROFILES[previous.PROFILE]["safety"]["ttlFixedValue"], 64)
        self.assertFalse(builder.QUALIFICATION["live_forward_hook_execution"])
        self.assertFalse(builder.QUALIFICATION["live_packet_ttl_verified"])
        self.assertFalse(builder.QUALIFICATION["flash_qualified"])

    def test_wrapper_delegates_only_to_offline_r44_builder(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(builder, "main", return_value=17) as run:
            result = wrapper.main(["--variant", "community-r4.4", "--output-dir", tmp, "--acknowledge-brick-risk"])
            self.assertEqual(result, 17)
            args = run.call_args.args[0]
            self.assertIn(builder.CONFIRMATION_FLAG, args)
            self.assertIn(str(Path(tmp) / builder.ARTIFACT), args)

    def test_existing_output_and_missing_ack_fail_before_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / builder.ARTIFACT
            report = Path(tmp) / "report.json"
            args = ["--golden", str(GOLDEN), "--identity-xml", str(IDENTITY), "--output", str(output), "--report", str(report)]
            with mock.patch.object(builder.comparator, "build_candidate") as build:
                self.assertEqual(builder.main(args), 2)
                output.write_bytes(b"keep")
                self.assertEqual(builder.main(args + [builder.CONFIRMATION_FLAG]), 2)
                build.assert_not_called()
            self.assertEqual(output.read_bytes(), b"keep")
            self.assertFalse(report.exists())


@unittest.skipUnless(GOLDEN.is_file(), "optional exact stock backup")
class R44AssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = GOLDEN.read_bytes()
        _, records, _ = webi.parse_cafe_source(raw[0x52023C:0x52023C + 0x1C0000])
        cls.records = {r.path: r.logical_data for r in records}
        cls.replacements, cls.additions, cls.removals = release.build_patch_set(cls.records, ROOT)

    def test_exact_version_surface_and_old_paths_are_absent(self):
        self.assertEqual(set(self.additions), {release.ENTRY_PATH, release.APP_PATH, release.CSS_PATH})
        self.assertIn(b'href="/r44.html"', self.replacements["www\\index.html"])
        self.assertIn(b'href="/r44.html"', self.replacements["www\\html\\adminApp.html"])
        joined = b"\n".join(self.additions.values())
        for expected in (release.MARKER, b'src="js/r44app.js"', b'href="css/r44ui.css"', b"Fixed TTL 64", b"There is no On/Off switch", b"A measurement on this router is still required"):
            self.assertTrue(expected in joined, expected)
        for forbidden in (b"modelGet('diagnostic'", b"file=diagnostic", b"file=ttl_set", b"<command>ttl</command>", b"setInterval", b"/r43.html", b"js/r43app.js"):
            self.assertNotIn(forbidden, joined)
        for path, (size, digest, _description) in release.ADDITION_OUTPUT_RECORDS.items():
            self.assertEqual((len(self.additions[path]), hashlib.sha256(self.additions[path]).hexdigest()), (size, digest))

    def test_controller_and_css_preserve_previous_behaviour(self):
        _, prior, removed = previous.build_patch_set(self.records, ROOT)
        self.assertEqual(self.additions[release.APP_PATH], release._revise(prior[previous.APP_PATH], "test controller"))
        self.assertEqual(self.additions[release.CSS_PATH], prior[previous.CSS_PATH])
        self.assertEqual(self.removals, removed)

    def test_modified_panel_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            panel = root / release.FRAGMENT_FILE
            panel.parent.mkdir(parents=True)
            panel.write_bytes((ROOT / release.FRAGMENT_FILE).read_bytes() + b" ")
            with self.assertRaises(release.CommunityR44Error):
                release._fragment(root)


@unittest.skipUnless(GOLDEN.is_file() and IDENTITY.is_file(), "optional exact stock backup and local identity")
class R44ContainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.identity = inspector.load_identity(IDENTITY)
        cls.golden = webi.require_reviewed_golden(GOLDEN, cls.identity)
        cls.image, cls.report = builder.build_candidate(cls.golden, cls.identity)
        cls.verification = builder.verify_candidate(cls.golden, cls.image, cls.identity)

    def test_rebuild_matches_retained_image_and_all_native_bytes(self):
        self.assertEqual(len(self.image), 8_323_644)
        # Raw encrypted headers are unit-bound; this reference raw hash applies
        # only to the original reference backup, not another owner's key.
        if hashlib.sha256(self.golden).hexdigest() == "2b5880fc26805918bb574d07341ea9b863f8261be34c3bf9766fac0929204531":
            self.assertEqual(hashlib.sha256(self.image).hexdigest(), ARTIFACT_SHA256)
        header = inspector.decrypt_header(self.image, self.identity)
        self.assertEqual(hashlib.sha256(bytes(header) + self.image[inspector.HEADER_SIZE:]).hexdigest(), "02048911c1a556074a2b1e7773dd2c24d3dad9a84487f467e03e11c12e09c2c2")
        self.assertEqual(self.verification["status"], "GREEN")
        self.assertTrue(all(c["passed"] for c in self.verification["conditions"]))
        native = self.report["native"]
        self.assertEqual(native["artifact"]["sha256"], "a9cbc51a48decc11cb7aee393034f1996a35a6d4a19107346d76f36c45e022d8")
        self.assertEqual(native["component"]["sha256"], "c04dc80c7f37309d1e9304257211ba84cf2ab51fbe55d7e9e79e62bb49750c6d")
        self.assertEqual(native["packet_contract"]["fixed_ttl"], 64)
        self.assertFalse(native["packet_contract"]["diagnostic_callbacks_installed"])
        self.assertFalse(native["qualification"]["live_forward_hook_execution"])

    def test_independent_inspector_and_other_partition_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / builder.ARTIFACT
            path.write_bytes(self.image)
            result = inspector.inspect_image(path, self.identity, include_records=True)
        self.assertEqual(result.report["verification"]["status"], "verified")
        _, partitions = builder.shared._partition_map(self.golden, self.identity)
        for partition in partitions:
            if partition.name not in ("OSLO", "WEBI"):
                a, b = partition.offset, partition.offset + partition.length
                self.assertEqual(self.image[a:b], self.golden[a:b], partition.name)

    def test_changed_payload_is_rejected_by_full_verifier(self):
        changed = bytearray(self.image)
        # A stable non-OSLO/WEBI partition is not part of the experiment.
        _, partitions = builder.shared._partition_map(self.golden, self.identity)
        partition = next(p for p in partitions if p.name not in ("OSLO", "WEBI"))
        changed[partition.offset] ^= 1
        with self.assertRaises((builder.CommunityR44NativeError, inspector.InspectionError)):
            builder.verify_candidate(self.golden, bytes(changed), self.identity)

    def test_short_or_wrong_header_image_is_rejected(self):
        for image in (self.image[:100], bytes(1024)):
            with self.subTest(length=len(image)), self.assertRaises((builder.CommunityR44NativeError, builder.shared.CommunityR30NativeError, inspector.InspectionError, ValueError, struct.error)):
                builder.verify_candidate(self.golden, image, self.identity)


if __name__ == "__main__":
    unittest.main()
