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
            ("community-0.4.7-dev.4", "community-r4.6", "community-r4.5", "community-r4.4", "community-r4.3", "community-r4.2", "community-r3.5", "community-r2.9", "community-r2.8", "community-r2.7", "community-r2.6", "community-r2.5", "community-r2.4", "community-r2.3", "community-r2.2", "community-r2.1", "community-r2", "community-r1", "logs-r1", "logs-r2", "sms-r1"),
        )
        for item in wrapper.describe_variants():
            self.assertIn("structural-only", item["qualification"])

    def test_dev4_uses_isolated_offline_process_and_preserves_failure(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(wrapper.subprocess, "run") as run:
            run.return_value.returncode = 2
            result = wrapper.main(["--variant", "community-0.4.7-dev.4", "--output-dir", temporary, "--acknowledge-brick-risk"])
            self.assertEqual(result, 2)
            args = run.call_args.args[0]
            self.assertEqual(Path(args[2]).name, "mf885_build_047d4.py")
            self.assertIn("--acknowledge-brick-risk", args)
            self.assertEqual(Path(args[args.index("--output") + 1]).name, "MF885-Community-0.4.7-dev.4-base-2.5.94.bin")
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(wrapper.subprocess, "run") as run, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(wrapper.main(["--variant", "community-0.4.7-dev.4", "--output-dir", temporary]), 2)
            run.assert_not_called()

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

    def test_community_r21_uses_new_immutable_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.stage_builder, "main", return_value=0) as main:
                result = wrapper.main(
                    [
                        "--variant",
                        "community-r2.1",
                        "--output-dir",
                        temporary,
                        "--acknowledge-brick-risk",
                    ]
                )
                self.assertEqual(result, 0)
                arguments = main.call_args.args[0]
                self.assertEqual(
                    arguments[arguments.index("--profile") + 1],
                    "0.2.1-community-r2",
                )
                self.assertEqual(
                    Path(arguments[arguments.index("--output") + 1]).name,
                    "MF885_Community_0.2.1-community-r2-cafe-r2.bin",
                )

    def test_community_r22_uses_new_immutable_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.stage_builder, "main", return_value=0) as main:
                result = wrapper.main(
                    [
                        "--variant",
                        "community-r2.2",
                        "--output-dir",
                        temporary,
                        "--acknowledge-brick-risk",
                    ]
                )
                self.assertEqual(result, 0)
                arguments = main.call_args.args[0]
                self.assertEqual(
                    arguments[arguments.index("--profile") + 1],
                    "0.2.2-community-r2",
                )
                self.assertEqual(
                    Path(arguments[arguments.index("--output") + 1]).name,
                    "MF885_Community_0.2.2-community-r2-cafe-r2.bin",
                )

    def test_community_r23_uses_new_immutable_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.stage_builder, "main", return_value=0) as main:
                result = wrapper.main(
                    [
                        "--variant",
                        "community-r2.3",
                        "--output-dir",
                        temporary,
                        "--acknowledge-brick-risk",
                    ]
                )
                self.assertEqual(result, 0)
                arguments = main.call_args.args[0]
                self.assertEqual(
                    arguments[arguments.index("--profile") + 1],
                    "0.2.3-community-r2",
                )
                self.assertEqual(
                    Path(arguments[arguments.index("--output") + 1]).name,
                    "MF885_Community_0.2.3-community-r2-cafe-r2.bin",
                )

    def test_community_r24_uses_new_immutable_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.stage_builder, "main", return_value=0) as main:
                result = wrapper.main(
                    [
                        "--variant",
                        "community-r2.4",
                        "--output-dir",
                        temporary,
                        "--acknowledge-brick-risk",
                    ]
                )
                self.assertEqual(result, 0)
                arguments = main.call_args.args[0]
                self.assertEqual(
                    arguments[arguments.index("--profile") + 1],
                    "0.2.4-community-r2",
                )
                self.assertEqual(
                    Path(arguments[arguments.index("--output") + 1]).name,
                    "MF885_Community_0.2.4-community-r2-cafe-r2.bin",
                )

    def test_community_r25_uses_new_immutable_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.stage_builder, "main", return_value=0) as main:
                result = wrapper.main(
                    [
                        "--variant",
                        "community-r2.5",
                        "--output-dir",
                        temporary,
                        "--acknowledge-brick-risk",
                    ]
                )
                self.assertEqual(result, 0)
                arguments = main.call_args.args[0]
                self.assertEqual(
                    arguments[arguments.index("--profile") + 1],
                    "0.2.5-community-r2",
                )
                self.assertEqual(
                    Path(arguments[arguments.index("--output") + 1]).name,
                    "MF885_Community_0.2.5-community-r2-cafe-r2.bin",
                )

    def test_community_r26_uses_new_non_blocking_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.stage_builder, "main", return_value=0) as main:
                result = wrapper.main(
                    [
                        "--variant",
                        "community-r2.6",
                        "--output-dir",
                        temporary,
                        "--acknowledge-brick-risk",
                    ]
                )
                self.assertEqual(result, 0)
                arguments = main.call_args.args[0]
                self.assertEqual(arguments[arguments.index("--profile") + 1], "0.2.6-community-r2")
                self.assertEqual(
                    Path(arguments[arguments.index("--output") + 1]).name,
                    "MF885_Community_0.2.6-community-r2-cafe-r2.bin",
                )

    def test_community_r27_uses_extension_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.stage_builder, "main", return_value=0) as main:
                result = wrapper.main(
                    [
                        "--variant",
                        "community-r2.7",
                        "--output-dir",
                        temporary,
                        "--acknowledge-brick-risk",
                    ]
                )
                self.assertEqual(result, 0)
                arguments = main.call_args.args[0]
                self.assertEqual(arguments[arguments.index("--profile") + 1], "0.2.7-community-r2")
                self.assertEqual(
                    Path(arguments[arguments.index("--output") + 1]).name,
                    "MF885_Community_0.2.7-community-r2-cafe-r2.bin",
                )

    def test_community_r28_uses_in_interface_modem_lab_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.stage_builder, "main", return_value=0) as main:
                result = wrapper.main(
                    [
                        "--variant",
                        "community-r2.8",
                        "--output-dir",
                        temporary,
                        "--acknowledge-brick-risk",
                    ]
                )
                self.assertEqual(result, 0)
                arguments = main.call_args.args[0]
                self.assertEqual(arguments[arguments.index("--profile") + 1], "0.2.8-community-r2")
                self.assertEqual(
                    Path(arguments[arguments.index("--output") + 1]).name,
                    "MF885_Community_0.2.8-community-r2-cafe-r2.bin",
                )

    def test_community_r29_uses_universal_refresh_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.stage_builder, "main", return_value=0) as main:
                result = wrapper.main(
                    [
                        "--variant",
                        "community-r2.9",
                        "--output-dir",
                        temporary,
                        "--acknowledge-brick-risk",
                    ]
                )
                self.assertEqual(result, 0)
                arguments = main.call_args.args[0]
                self.assertEqual(arguments[arguments.index("--profile") + 1], "0.2.9-community-r2")
                self.assertEqual(
                    Path(arguments[arguments.index("--output") + 1]).name,
                    "MF885_Community_0.2.9-community-r2-cafe-r2.bin",
                )

    def test_quarantined_target_profiles_do_not_read_inputs_or_invoke_builders(self):
        for name, module in (("community-r3.5", wrapper.r35_native_builder),
                             ("community-r4.2", wrapper.r42_native_builder),
                             ("community-r4.3", wrapper.r43_native_builder)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                with mock.patch.object(module, "main") as main, \
                     mock.patch.object(Path, "read_bytes", side_effect=AssertionError("input opened")), \
                     contextlib.redirect_stderr(io.StringIO()) as stderr:
                    result = wrapper.main(["--variant", name, "--output-dir", temporary,
                                           "--acknowledge-brick-risk"])
                self.assertEqual(result, 2)
                main.assert_not_called()
                self.assertEqual(list(Path(temporary).iterdir()), [])
                self.assertIn("quarantined", stderr.getvalue())
                self.assertIn("ARMv5TE/Thumb-1", stderr.getvalue())

    def test_r46_hardware_failure_blocks_even_with_risk_acknowledgement(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(wrapper.r46_native_builder, "main") as main, \
                 mock.patch.object(Path, "read_bytes", side_effect=AssertionError("input opened")), \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                result = wrapper.main(["--variant", "community-r4.6", "--output-dir", temporary,
                                       "--acknowledge-brick-risk"])
            self.assertEqual(result, 2)
            main.assert_not_called()
            self.assertEqual(list(Path(temporary).iterdir()), [])
            self.assertIn("first native TTL GET", stderr.getvalue())
        item = next(x for x in wrapper.describe_variants() if x["name"] == "community-r4.6")
        self.assertFalse(item["build_allowed"])
        self.assertEqual(item["status"], "quarantined-hardware-test-failed")

    def test_list_exposes_quarantine_without_hiding_history(self):
        variants = {item["name"]: item for item in wrapper.describe_variants()}
        for name in ("community-r3.5", "community-r4.2", "community-r4.3"):
            self.assertFalse(variants[name]["build_allowed"])
            self.assertEqual(variants[name]["status"], "quarantined-target-mismatch")
        for name in ("community-r4.4", "community-r4.5"):
            self.assertTrue(variants[name]["build_allowed"])
            self.assertIn("never flash-qualified", variants[name]["qualification"])


if __name__ == "__main__":
    unittest.main()
