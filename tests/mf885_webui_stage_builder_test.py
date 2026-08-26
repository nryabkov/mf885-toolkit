import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mf885_firmware_inspect as inspector  # noqa: E402
import mf885_webui_stage_builder as stage  # noqa: E402


LOCAL_GOLDEN = Path(os.environ.get("MF885_TEST_GOLDEN", ROOT / "input/MF885_golden.bin"))
LOCAL_IDENTITY = Path(os.environ.get("MF885_TEST_IDENTITY", ROOT / "input/mf885-base.xml"))


class WebuiStageBuilderTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
