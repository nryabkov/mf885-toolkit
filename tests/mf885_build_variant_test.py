import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import mf885_build_variant as wrapper


class BuildVariantTests(unittest.TestCase):
    def test_registry_is_public_and_structural_only(self):
        self.assertEqual(
            tuple(wrapper.VARIANTS),
            ("community-r2", "community-r1", "logs-r1", "logs-r2", "sms-r1"),
        )
        for item in wrapper.describe_variants():
            self.assertIn("structural-only", item["qualification"])

    def test_missing_acknowledgement_performs_no_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.logs_builder, "main") as logs_main:
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    result = wrapper.main(
                        ["--variant", "logs-r1", "--output-dir", temporary]
                    )
                self.assertEqual(result, 2)
                logs_main.assert_not_called()
                self.assertIn("permanently brick", stderr.getvalue())

    def test_logs_variant_delegates_exact_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.logs_builder, "main", return_value=0) as main:
                result = wrapper.main(
                    [
                        "--variant",
                        "logs-r2",
                        "--golden",
                        "golden.bin",
                        "--identity-xml",
                        "base.xml",
                        "--output-dir",
                        temporary,
                        "--acknowledge-brick-risk",
                    ]
                )
                self.assertEqual(result, 0)
                arguments = main.call_args.args[0]
                self.assertEqual(arguments[arguments.index("--profile") + 1], "0.0-logs-r2")
                self.assertEqual(
                    Path(arguments[arguments.index("--output") + 1]).name,
                    "MF885_Community_0.0-logs-r2-auth-r4-cafe-r2.bin",
                )

    def test_sms_variant_uses_stage_builder(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.stage_builder, "main", return_value=0) as main:
                result = wrapper.main(
                    [
                        "--variant",
                        "sms-r1",
                        "--output-dir",
                        temporary,
                        "--acknowledge-brick-risk",
                    ]
                )
                self.assertEqual(result, 0)
                arguments = main.call_args.args[0]
                self.assertEqual(arguments[arguments.index("--profile") + 1], "0.0-sms-r1")

    def test_community_variant_uses_exact_new_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.stage_builder, "main", return_value=0) as main:
                result = wrapper.main(
                    [
                        "--variant",
                        "community-r1",
                        "--output-dir",
                        temporary,
                        "--acknowledge-brick-risk",
                    ]
                )
                self.assertEqual(result, 0)
                arguments = main.call_args.args[0]
                self.assertEqual(
                    arguments[arguments.index("--profile") + 1],
                    "0.1-community-r1",
                )
                self.assertEqual(
                    Path(arguments[arguments.index("--output") + 1]).name,
                    "MF885_Community_0.1-community-r1-cafe-r2.bin",
                )

    def test_community_r2_uses_exact_english_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.stage_builder, "main", return_value=0) as main:
                result = wrapper.main(
                    [
                        "--variant",
                        "community-r2",
                        "--output-dir",
                        temporary,
                        "--acknowledge-brick-risk",
                    ]
                )
                self.assertEqual(result, 0)
                arguments = main.call_args.args[0]
                self.assertEqual(
                    arguments[arguments.index("--profile") + 1],
                    "0.2-community-r2",
                )
                self.assertEqual(
                    Path(arguments[arguments.index("--output") + 1]).name,
                    "MF885_Community_0.2-community-r2-cafe-r2.bin",
                )


if __name__ == "__main__":
    unittest.main()
