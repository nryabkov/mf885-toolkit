import lzma
import os
import struct
import sys
import unittest
import zlib
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
EXACT_OSLO_RAW = Path("/tmp/mf885-oslo.raw")
LOCAL_GOLDEN = Path(os.environ.get("MF885_TEST_GOLDEN", ROOT / "input/MF885_golden.bin"))
LOCAL_IDENTITY = Path(os.environ.get("MF885_TEST_IDENTITY", ROOT / "input/mf885-base.xml"))

import mf885_firmware_inspect as inspector  # noqa: E402
import mf885_webi_builder as builder  # noqa: E402


def cafe_payload(path: str, data: bytes, size: int = 4096) -> bytes:
    value = bytearray(20)
    struct.pack_into("<I", value, 0, 0xCAFECAFE)
    struct.pack_into("<I", value, 8, 0x00001019)
    header = bytearray(inspector.CAFE_RECORD_HEADER_SIZE)
    struct.pack_into("<I", header, 0, 0xCAFE1000)
    padding = (-len(data)) % 4
    stored = data + b"\xFF" * padding
    struct.pack_into("<I", header, 4, (padding << 24) | len(stored))
    encoded = path.encode("ascii")
    header[8 : 8 + len(encoded)] = encoded
    value.extend(header)
    value.extend(stored)
    sentinel = len(value)
    value.extend(struct.pack("<I", 0xDADADADA))
    value.extend(b"\xFF" * (size - len(value)))
    struct.pack_into("<I", value, 4, zlib.adler32(value[8:sentinel]) & 0xFFFFFFFF)
    return bytes(value)


class WebiBuilderTests(unittest.TestCase):
    def test_lzma_inspection_stops_at_the_uncompressed_size_limit(self):
        payload = lzma.compress(b"A" * 4096, format=lzma.FORMAT_ALONE)
        with mock.patch.object(inspector, "MAX_LZMA_UNCOMPRESSED_BYTES", 1024):
            report = inspector.inspect_lzma(payload)
        self.assertFalse(report["stream_complete"])
        self.assertEqual(report["error"], "uncompressed-size-limit")
        self.assertEqual(report["uncompressed_limit_bytes"], 1024)
        self.assertNotIn("uncompressed_sha256", report)

        with mock.patch.object(inspector, "MAX_LZMA_UNCOMPRESSED_BYTES", 8192):
            control = inspector.inspect_lzma(payload)
        self.assertTrue(control["stream_complete"])
        self.assertEqual(control["uncompressed_bytes"], 4096)

        with mock.patch.object(inspector, "MAX_LZMA_MEMORY_BYTES", 1024 * 1024):
            memory_limited = inspector.inspect_lzma(payload)
        self.assertFalse(memory_limited["stream_complete"])
        self.assertEqual(memory_limited["error"], "LZMAError")

    def test_canary_profiles_are_bound_to_exact_script_bytes(self):
        for profile, relative in (
            ("0.0-logs-r1", "firmware/webui-canary-logs/canary_logs.js"),
            ("0.0-logs-r2", "firmware/webui-canary-logs-r2/canary_logs.js"),
        ):
            with self.subTest(profile=profile):
                script = (ROOT / relative).read_bytes()
                self.assertEqual(
                    builder.require_exact_canary_script(script, profile),
                    builder.CANARY_PROFILES[profile]["marker"],
                )
                with self.assertRaises(builder.BuildError):
                    builder.require_exact_canary_script(script + b"\n", profile)

    def test_restorefw_gate_report_is_attached_only_to_a_complete_oslo_stream(self):
        payload = lzma.compress(b"small unknown OSLO", format=lzma.FORMAT_ALONE)
        oslo = inspector.inspect_lzma(payload, "OSLO")
        grbi = inspector.inspect_lzma(payload, "GRBI")

        self.assertTrue(oslo["stream_complete"])
        self.assertEqual(oslo["restorefw_system_gate"]["status"], "unrecognized")
        self.assertNotIn("restorefw_system_gate", grbi)

    def test_restorefw_gate_does_not_classify_an_unknown_oslo(self):
        report = inspector.inspect_restorefw_system_gate(b"not the reviewed OSLO")
        self.assertEqual(report["status"], "unrecognized")
        self.assertFalse(report["exact_build_match"])
        self.assertNotIn("required_system_type", report)

    def test_restorefw_gate_requires_minsys_before_the_multipart_parser(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        for _name, offset, expected in inspector.RESTOREFW_NATIVE_SIGNATURES:
            synthetic[offset : offset + len(expected)] = expected
        synthetic[0x1200:0x1260] = bytes.fromhex(
            "05 5a 4d 49 46 49 00 00 04 4e 4f 4e 45 00 00 00 "
            "00 4d 4d 49 46 49 00 00 00 00 00 00 01 4d 49 46 "
            "49 33 00 00 00 00 00 00 02 4d 49 46 49 34 00 00 "
            "00 00 00 00 03 4d 49 46 49 35 00 00 00 00 00 00 "
            "04 4d 49 4e 53 59 53 00 00 00 00 00 05 5a 4d 49 "
            "46 49 00 00 00 00 00 00 07 54 50 4c 49 4e 00 00"
        )
        synthetic_sha256 = inspector.sha256(synthetic)
        with mock.patch.object(inspector, "EXACT_OSLO_SHA256", synthetic_sha256):
            report = inspector.inspect_restorefw_system_gate(bytes(synthetic))

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["required_system_type"], {"value": 4, "name": "MINSYS"})
        self.assertEqual(
            report["compiled_initial_system_type"], {"value": 5, "name": "ZMIFI"}
        )
        self.assertFalse(report["compiled_initial_value_satisfies_gate"])
        self.assertTrue(report["rejection_precedes_multipart_and_firmware_bytes"])
        self.assertEqual(report["rejection_http_status"], 500)
        self.assertEqual(report["rejection_message"], "Not support the request")
        self.assertEqual(report["candidate_mode_diagnostic_action"], "GetSysType")
        self.assertFalse(report["candidate_mode_diagnostic_handler_purity_verified"])
        self.assertFalse(report["remote_mode_setter_identified_in_reviewed_static_analysis"])

    def test_restorefw_gate_fails_closed_on_a_fixed_offset_signature_mismatch(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        for _name, offset, expected in inspector.RESTOREFW_NATIVE_SIGNATURES:
            synthetic[offset : offset + len(expected)] = expected
        synthetic[0x1200:0x1260] = bytes.fromhex(
            "05 5a 4d 49 46 49 00 00 04 4e 4f 4e 45 00 00 00 "
            "00 4d 4d 49 46 49 00 00 00 00 00 00 01 4d 49 46 "
            "49 33 00 00 00 00 00 00 02 4d 49 46 49 34 00 00 "
            "00 00 00 00 03 4d 49 46 49 35 00 00 00 00 00 00 "
            "04 4d 49 4e 53 59 53 00 00 00 00 00 05 5a 4d 49 "
            "46 49 00 00 00 00 00 00 07 54 50 4c 49 4e 00 00"
        )
        synthetic[0x0A058A] = 5
        synthetic_sha256 = inspector.sha256(synthetic)
        with mock.patch.object(inspector, "EXACT_OSLO_SHA256", synthetic_sha256):
            report = inspector.inspect_restorefw_system_gate(bytes(synthetic))

        self.assertEqual(report["status"], "signature-mismatch")
        self.assertFalse(report["native_signatures_valid"])
        self.assertIn("MINSYS predicate", report["signature_mismatches"])
        self.assertNotIn("required_system_type", report)

    def test_fbf_update_report_proves_only_the_zmifi_signature_presence_branch(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        for _name, offset, expected in inspector.FBF_UPDATE_NATIVE_SIGNATURES:
            synthetic[offset : offset + len(expected)] = expected
        synthetic_sha256 = inspector.sha256(synthetic)
        with mock.patch.object(inspector, "EXACT_OSLO_SHA256", synthetic_sha256):
            report = inspector.inspect_fbf_update_path(bytes(synthetic))

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["normal_system_type"], {"value": 5, "name": "ZMIFI"})
        self.assertEqual(
            report["missing_rsai_fatal_system_type"], {"value": 7, "name": "TPLIN"}
        )
        self.assertTrue(report["missing_rsai_fatal_only_for_tplin"])
        self.assertTrue(report["zmifi_without_rsai_reaches_later_update_gates"])
        self.assertTrue(report["present_rsai_verification_required"])
        self.assertTrue(report["authenticated_session_gate"])
        self.assertFalse(report["exact_auth_wire_mechanism_proven"])
        self.assertTrue(report["normal_zmifi_upload_control_flow"])
        self.assertFalse(report["upload_command_value_required_proven"])
        self.assertTrue(report["writer_iterates_supplied_record_list"])
        self.assertFalse(report["fixed_full_partition_set_required_by_parser"])
        self.assertTrue(report["version_and_hardware_validation_precedes_write"])
        self.assertFalse(report["native_partition_whitelist_identified"])
        self.assertTrue(report["generic_start_address_deny_guard"])
        self.assertTrue(report["flash_guard_checks_start_address_only"])
        self.assertFalse(report["full_extent_end_bound_check_identified"])
        self.assertTrue(report["candidate_webi_starts_pass_every_reviewed_guard_profile"])
        self.assertEqual(len(report["candidate_webi_record_starts"]),14)
        self.assertFalse(report["version_gate_semantics"]["numeric_downgrade_compare_identified"])
        self.assertTrue(report["version_gate_semantics"]["reviewed_donor_passes_this_gate"])
        self.assertFalse(report["version_gate_semantics"]["full_live_acceptance_proven"])
        self.assertEqual(
            report["native_per_record_operation"],
            "erase-full-extent-then-write-stored-bytes",
        )
        self.assertFalse(report["native_write_readback_identified"])
        self.assertFalse(report["native_readback_verified"])
        self.assertEqual(report["maximum_content_length_bytes"], 9_961_472)
        self.assertEqual(report["native_new_upload_allowed_previous_causes"], [0, 7])
        self.assertEqual(report["upgrade_failure_causes"]["7"], "Socket Error!")
        self.assertEqual(report["success_retained_selector"]["value"], "MAXS")
        self.assertTrue(
            report["worker_minus_five_occurs_after_preflash_and_writer_attempt"]
        )
        self.assertTrue(report["worker_minus_five_may_follow_partial_record_writes"])
        self.assertFalse(report["worker_minus_five_is_qualified_mins_entry"])
        self.assertFalse(report["webi_only_live_acceptance_proven"])
        self.assertFalse(report["rollback_verified"])
        self.assertFalse(report["flash_qualified"])

    def test_early_loader_abi_is_exact_but_does_not_claim_a_selector_reader(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        profile = dict(inspector.EARLY_LOADER_ABI_BUILDS["2.5.94"])
        synthetic[0x1C0:0x1C4] = inspector.EARLY_LOADER_HEADER_PREFIX
        struct.pack_into("<I", synthetic, 0x1C4, profile["header_pointer"])
        synthetic[0x1C8:0x200] = inspector.EARLY_LOADER_HEADER_SUFFIX
        synthetic[profile["function_offset"] : profile["function_offset"] + 2] = b"\xf0\xb5"
        name = b"ReadBootloaderVersion\0"
        synthetic[profile["name_offset"] : profile["name_offset"] + len(name)] = name
        struct.pack_into("<I", synthetic, profile["literal_offset"], 0x07D7F00C)
        synthetic[profile["literal_refs"][0] : profile["literal_refs"][0] + 2] = bytes.fromhex(
            "8e 4c"
        )
        synthetic[profile["literal_refs"][1] : profile["literal_refs"][1] + 2] = bytes.fromhex(
            "76 4c"
        )
        profile["sha256"] = inspector.sha256(synthetic)

        with mock.patch.dict(
            inspector.EARLY_LOADER_ABI_BUILDS,
            {"2.5.94": profile},
        ):
            report = inspector.inspect_early_loader_abi(bytes(synthetic))

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["retained_page_base"], "0x07d7f000")
        self.assertEqual(report["bootloader_version_address"], "0x07d7f00c")
        self.assertEqual(report["mins_selector_address"], "0x07d7f040")
        self.assertTrue(
            report["bootloader_version_and_selector_addresses_share_page"]
        )
        self.assertFalse(report["selector_consumer_analysis_performed"])
        self.assertFalse(report["selector_read_by_early_loader_proven"])

    def test_early_loader_abi_fails_closed_on_a_literal_reference_mutation(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        profile = dict(inspector.EARLY_LOADER_ABI_BUILDS["2.5.94"])
        synthetic[0x1C0:0x1C4] = inspector.EARLY_LOADER_HEADER_PREFIX
        struct.pack_into("<I", synthetic, 0x1C4, profile["header_pointer"])
        synthetic[0x1C8:0x200] = inspector.EARLY_LOADER_HEADER_SUFFIX
        synthetic[profile["function_offset"] : profile["function_offset"] + 2] = b"\xf0\xb5"
        name = b"ReadBootloaderVersion\0"
        synthetic[profile["name_offset"] : profile["name_offset"] + len(name)] = name
        struct.pack_into("<I", synthetic, profile["literal_offset"], 0x07D7F00C)
        synthetic[profile["literal_refs"][0] : profile["literal_refs"][0] + 2] = bytes.fromhex(
            "8e 4c"
        )
        synthetic[profile["literal_refs"][1] : profile["literal_refs"][1] + 2] = bytes.fromhex(
            "77 4c"
        )
        profile["sha256"] = inspector.sha256(synthetic)

        with mock.patch.dict(
            inspector.EARLY_LOADER_ABI_BUILDS,
            {"2.5.94": profile},
        ):
            report = inspector.inspect_early_loader_abi(bytes(synthetic))

        self.assertEqual(report["status"], "signature-mismatch")
        self.assertIn(
            "bootloader-version literal references",
            report["signature_mismatches"],
        )
        self.assertNotIn("mins_selector_address", report)

    @unittest.skipUnless(
        EXACT_OSLO_RAW.is_file(),
        "exact private OSLO artifact is optional in CI",
    )
    def test_exact_private_oslo_matches_the_production_loader_abi_profile(self):
        report = inspector.inspect_early_loader_abi(EXACT_OSLO_RAW.read_bytes())

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["build"], "2.5.94")
        self.assertFalse(report["selector_read_by_early_loader_proven"])

    def test_fbf_update_report_fails_closed_on_an_unsigned_branch_mutation(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        for _name, offset, expected in inspector.FBF_UPDATE_NATIVE_SIGNATURES:
            synthetic[offset : offset + len(expected)] = expected
        synthetic[0x291128] ^= 1
        synthetic_sha256 = inspector.sha256(synthetic)
        with mock.patch.object(inspector, "EXACT_OSLO_SHA256", synthetic_sha256):
            report = inspector.inspect_fbf_update_path(bytes(synthetic))

        self.assertEqual(report["status"], "signature-mismatch")
        self.assertIn(
            "TPLIN-only missing-RSAI fatal branch", report["signature_mismatches"]
        )
        self.assertNotIn("normal_system_type", report)

    def test_fbf_update_report_fails_closed_on_retry_gate_mutation(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        for _name, offset, expected in inspector.FBF_UPDATE_NATIVE_SIGNATURES:
            synthetic[offset : offset + len(expected)] = expected
        synthetic[0x6E9558] ^= 1
        synthetic_sha256 = inspector.sha256(synthetic)
        with mock.patch.object(inspector, "EXACT_OSLO_SHA256", synthetic_sha256):
            report = inspector.inspect_fbf_update_path(bytes(synthetic))

        self.assertEqual(report["status"], "signature-mismatch")
        self.assertIn(
            "previous OTA result zero-or-socket-error gate",
            report["signature_mismatches"],
        )
        self.assertNotIn("native_new_upload_allowed_previous_causes", report)

    def test_fbf_update_report_fails_closed_on_flash_guard_mutation(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        for _name, offset, expected in inspector.FBF_UPDATE_NATIVE_SIGNATURES:
            synthetic[offset : offset + len(expected)] = expected
        synthetic[0x6BBD3A] ^= 1
        synthetic_sha256 = inspector.sha256(synthetic)
        with mock.patch.object(inspector, "EXACT_OSLO_SHA256", synthetic_sha256):
            report = inspector.inspect_fbf_update_path(bytes(synthetic))

        self.assertEqual(report["status"], "signature-mismatch")
        self.assertIn("generic flash start-address deny guard", report["signature_mismatches"])
        self.assertNotIn("candidate_webi_starts_pass_every_reviewed_guard_profile", report)

    def test_fbf_update_report_fails_closed_on_a_writer_target_mutation(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        for _name, offset, expected in inspector.FBF_UPDATE_NATIVE_SIGNATURES:
            synthetic[offset : offset + len(expected)] = expected
        synthetic[0x34AD2C] ^= 1
        synthetic_sha256 = inspector.sha256(synthetic)
        with mock.patch.object(inspector, "EXACT_OSLO_SHA256", synthetic_sha256):
            report = inspector.inspect_fbf_update_path(bytes(synthetic))

        self.assertEqual(report["status"], "signature-mismatch")
        self.assertIn("native record burn target", report["signature_mismatches"])
        self.assertNotIn("native_per_record_operation", report)

    def test_minsys_transition_report_keeps_physical_entry_as_unproved(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        for _name, offset, expected in inspector.MINSYS_TRANSITION_NATIVE_SIGNATURES:
            synthetic[offset : offset + len(expected)] = expected
        synthetic_sha256 = inspector.sha256(synthetic)
        with mock.patch.object(inspector, "EXACT_OSLO_SHA256", synthetic_sha256):
            report = inspector.inspect_minsys_transition_path(bytes(synthetic))

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["retained_selector_address"], "0x07d7f040")
        self.assertEqual(report["ota_message_actions"]["1"], "MINS")
        self.assertEqual(report["proved_normal_image_ota_producers"], [3])
        self.assertTrue(report["early_phase_fallback_writes_mins"])
        self.assertEqual(
            report["early_phase_path_kind"], "fatal-exception-ee-log-handler"
        )
        self.assertEqual(report["startup_minsys_predicate_address"], "0x060a0584")
        self.assertEqual(
            report["startup_minsys_recognition_action"], "log-current-system-type"
        )
        self.assertFalse(report["startup_minsys_recognition_is_entry_mechanism"])
        self.assertEqual(report["minimum_system_power_timer_guard_constant"], 0)
        self.assertFalse(
            report["minimum_system_power_timer_reachable_in_normal_build"]
        )
        self.assertFalse(report["ordinary_power_cycle_runs_early_phase_handler_proven"])
        self.assertFalse(report["cold_power_cycle_preserves_retained_selector_proven"])
        self.assertFalse(report["physical_reset_key_to_fallback_timing_proven"])
        self.assertFalse(report["debugmode_writes_selector"])
        self.assertTrue(report["registered_at_mins_setter_handler_identified"])
        at_transition = report["registered_at_mins_transition"]
        self.assertEqual(at_transition["status"], "verified")
        self.assertEqual(at_transition["dispatch_case"], 29)
        self.assertEqual(at_transition["second_argument_for_mins"], 0)
        self.assertEqual(
            at_transition["statically_derived_at_message"],
            {
                "display": "AT+LOG=29,0<CR>",
                "hex": "41542b4c4f473d32392c300d",
            },
        )
        self.assertEqual(
            at_transition["second_argument_range"],
            {
                "minimum": 0,
                "maximum": 65_536,
                "local_storage_initialized_to": 0,
            },
        )
        self.assertEqual(
            at_transition["usb_at_channel_strips_terminator_bytes"],
            ["0x0a", "0x0d"],
        )
        self.assertTrue(at_transition["line_feed_transport_framing_proven"])
        self.assertFalse(at_transition["terminator_required_proven"])
        self.assertFalse(at_transition["final_ok_before_reset_expected"])
        self.assertFalse(at_transition["watchdog_reset_returns"])
        self.assertTrue(at_transition["registered_handler_to_mins_write_and_reset_proven"])
        self.assertTrue(
            at_transition["static_usb_at_delivery_path_to_registry_proven"]
        )
        self.assertFalse(at_transition["external_usb_at_delivery_live_observed"])
        self.assertEqual(
            at_transition["usb_at_delivery_chain"]["bulk_out_endpoint"], "0x02"
        )
        self.assertEqual(
            at_transition["usb_at_delivery_chain"]["line_parser_address"],
            "0x0658d326",
        )
        self.assertFalse(
            at_transition["statically_resolvable_selector_reader_identified"]
        )
        self.assertFalse(at_transition["selector_reader_search_complete"])
        self.assertFalse(at_transition["post_reset_minsys_boot_observed"])
        self.assertFalse(at_transition["safe_to_execute"])
        self.assertFalse(report["reachable_remote_mins_setter_identified"])

    def test_registered_at_mins_transition_fails_closed_on_case_table_mutation(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        for _name, offset, expected in inspector.MINSYS_TRANSITION_NATIVE_SIGNATURES:
            synthetic[offset : offset + len(expected)] = expected
        synthetic[0x184683 + 29] ^= 1
        synthetic_sha256 = inspector.sha256(synthetic)
        with mock.patch.object(inspector, "EXACT_OSLO_SHA256", synthetic_sha256):
            report = inspector.inspect_registered_at_mins_transition(bytes(synthetic))

        self.assertEqual(report["status"], "signature-mismatch")
        self.assertIn("+LOG case-29 switch target", report["signature_mismatches"])
        self.assertNotIn("retained_selector_value", report)

    def test_minsys_transition_fails_closed_on_usb_at_chain_mutation(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        for _name, offset, expected in inspector.MINSYS_TRANSITION_NATIVE_SIGNATURES:
            synthetic[offset : offset + len(expected)] = expected
        synthetic[0x095740] ^= 1
        synthetic_sha256 = inspector.sha256(synthetic)
        with mock.patch.object(inspector, "EXACT_OSLO_SHA256", synthetic_sha256):
            report = inspector.inspect_minsys_transition_path(bytes(synthetic))

        self.assertEqual(report["status"], "signature-mismatch")
        self.assertIn(
            "AT channel CR-LF byte handling", report["signature_mismatches"]
        )
        self.assertNotIn("registered_at_mins_transition", report)

    def test_registered_at_transition_checks_every_usb_at_link(self):
        for link_name, offset, _expected in inspector.USB_AT_DELIVERY_LINK_SIGNATURES:
            with self.subTest(link=link_name):
                synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
                for _name, sig_offset, signature in (
                    inspector.MINSYS_TRANSITION_NATIVE_SIGNATURES
                ):
                    synthetic[sig_offset : sig_offset + len(signature)] = signature
                synthetic[offset] ^= 1
                synthetic_sha256 = inspector.sha256(synthetic)
                with mock.patch.object(
                    inspector, "EXACT_OSLO_SHA256", synthetic_sha256
                ):
                    report = inspector.inspect_registered_at_mins_transition(
                        bytes(synthetic)
                    )

                self.assertEqual(report["status"], "signature-mismatch")
                self.assertIn(link_name, report["signature_mismatches"])

    def test_registered_at_transition_checks_arguments_and_watchdog_tail(self):
        profile = inspector.REGISTERED_AT_MINS_TRANSITION_BUILDS["2.5.94"]
        cases = (
            (profile["argument_setup_offset"], "+LOG numeric argument setup"),
            (profile["numeric_parser_offset"], "+LOG inclusive numeric parser"),
            (profile["watchdog_tail_offset"], "watchdog non-returning tail"),
        )
        for offset, mismatch in cases:
            with self.subTest(mismatch=mismatch):
                synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
                for _name, sig_offset, signature in (
                    inspector.MINSYS_TRANSITION_NATIVE_SIGNATURES
                ):
                    synthetic[sig_offset : sig_offset + len(signature)] = signature
                synthetic[offset] ^= 1
                synthetic_sha256 = inspector.sha256(synthetic)
                with mock.patch.object(
                    inspector, "EXACT_OSLO_SHA256", synthetic_sha256
                ):
                    report = inspector.inspect_registered_at_mins_transition(
                        bytes(synthetic)
                    )

                self.assertEqual(report["status"], "signature-mismatch")
                self.assertIn(mismatch, report["signature_mismatches"])

    def test_engineering_usb_profile_is_composite_but_not_a_mins_entry(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        for _name, offset, expected in inspector.ENGINEERING_USB_NATIVE_SIGNATURES:
            synthetic[offset : offset + len(expected)] = expected
        synthetic_sha256 = inspector.sha256(synthetic)
        with mock.patch.object(inspector, "EXACT_OSLO_SHA256", synthetic_sha256):
            report = inspector.inspect_engineering_usb_profile(bytes(synthetic))

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["usb_mode"], 8)
        self.assertEqual(report["descriptor_selector"], "0x1e")
        self.assertEqual(report["device"]["vendor_id"], "0x1286")
        self.assertEqual(report["device"]["product_id"], "0x4e31")
        self.assertEqual(report["model_registry"]["callback_phase"], "post_get")
        self.assertEqual(
            report["model_registry"]["callback_pointer_raw"], "0x06266e05"
        )
        self.assertEqual(
            report["model_registry"]["callback_code_address"], "0x06266e04"
        )
        self.assertTrue(report["model_registry"]["other_callback_slots_null"])
        self.assertEqual(
            report["callback_semantics"]["result_literals"], ["success", "failed"]
        )
        self.assertFalse(report["callback_semantics"]["empty_openmode_is_activation"])
        self.assertFalse(
            report["callback_semantics"]["external_activation_request_proven"]
        )
        self.assertFalse(
            report["callback_semantics"]["external_off_callback_identified"]
        )
        self.assertFalse(report["system_type_change"])
        self.assertFalse(report["retained_mins_selector_written"])
        self.assertFalse(report["service_loader_protocol_identified"])
        self.assertFalse(report["service_interface_to_mins_transition_proven"])
        self.assertTrue(report["engineering_descriptor_interfaces_present_in_image"])

        without_storage, with_storage = report["configurations"]
        self.assertEqual(without_storage["total_length"], 121)
        self.assertEqual(without_storage["declared_interface_count"], 4)
        self.assertEqual(
            [item["number"] for item in without_storage["interfaces"]],
            [0, 1, 2, 4],
        )
        self.assertEqual(with_storage["total_length"], 144)
        self.assertEqual(with_storage["declared_interface_count"], 5)
        self.assertEqual(
            [item["number"] for item in with_storage["interfaces"]],
            [0, 1, 2, 4, 5],
        )
        self.assertEqual(with_storage["interfaces"][2]["role"], "diagnostic")
        self.assertEqual(with_storage["interfaces"][3]["role"], "at-command")
        self.assertEqual(with_storage["interfaces"][4]["role"], "mass-storage")
        self.assertEqual(
            with_storage["interfaces"][2]["role_confidence"],
            "native-string-registration-proven",
        )
        self.assertEqual(
            [endpoint["address"] for endpoint in with_storage["interfaces"][2]["endpoints"]],
            [0x86, 0x05],
        )
        self.assertEqual(
            [endpoint["address"] for endpoint in with_storage["interfaces"][3]["endpoints"]],
            [0x83, 0x02],
        )
        strings = {item["index"]: item for item in report["string_descriptors"]}
        self.assertEqual(strings[8]["text"], "Mobile Diag Interface")
        self.assertEqual(strings[11]["text"], "Mobile AT Interface")
        self.assertTrue(strings[3]["runtime_override_possible"])

    def test_engineering_usb_profile_fails_closed_on_selector_mutation(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        for _name, offset, expected in inspector.ENGINEERING_USB_NATIVE_SIGNATURES:
            synthetic[offset : offset + len(expected)] = expected
        synthetic[0x0A906E] ^= 1
        synthetic_sha256 = inspector.sha256(synthetic)
        with mock.patch.object(inspector, "EXACT_OSLO_SHA256", synthetic_sha256):
            report = inspector.inspect_engineering_usb_profile(bytes(synthetic))

        self.assertEqual(report["status"], "signature-mismatch")
        self.assertIn("debugmode USB mode-8 selector", report["signature_mismatches"])
        self.assertNotIn("device", report)

    def test_engineering_usb_profile_fails_closed_on_model_callback_mutation(self):
        synthetic = bytearray(inspector.EXACT_OSLO_SIZE)
        for _name, offset, expected in inspector.ENGINEERING_USB_NATIVE_SIGNATURES:
            synthetic[offset : offset + len(expected)] = expected
        synthetic[0x9007CC] ^= 1
        synthetic_sha256 = inspector.sha256(synthetic)
        with mock.patch.object(inspector, "EXACT_OSLO_SHA256", synthetic_sha256):
            report = inspector.inspect_engineering_usb_profile(bytes(synthetic))

        self.assertEqual(report["status"], "signature-mismatch")
        self.assertIn("debugon model registry row", report["signature_mismatches"])
        self.assertNotIn("callback_semantics", report)

    def test_logs_canary_is_known_but_not_restorable(self):
        artifact = inspector.KNOWN_ARTIFACTS[
            "65e5f5b507b9fcf49609a6fd1f010daa6f18111dc6a829d5655fa6bd30553517"
        ]
        self.assertEqual(artifact["id"], "mf885-community-0.0-canary-logs-r1")
        self.assertEqual(
            artifact["structural_status"],
            "quarantined-invalid-cafe-padding-live-confirmed",
        )
        self.assertFalse(artifact["restorable"])
        self.assertTrue(inspector.known_is_quarantined({"known_artifact": artifact}))

        logs_r2 = inspector.KNOWN_ARTIFACTS[
            "0cc9eb514d9a821a39b32d7c3f1b7b73f1358e3d79374bdd6b6c7340c308c1f1"
        ]
        self.assertEqual(logs_r2["id"], "mf885-community-0.0-canary-logs-r2")
        self.assertEqual(logs_r2["structural_status"], "quarantined-invalid-cafe-padding")
        self.assertFalse(logs_r2["restorable"])
        self.assertTrue(inspector.known_is_quarantined({"known_artifact": logs_r2}))

        sms_r1 = inspector.KNOWN_ARTIFACTS[
            "f1f5f7fc51dc4bd6a094071cd82958b141f9525ba401bbf92024864e28f271a6"
        ]
        self.assertEqual(sms_r1["id"], "mf885-community-0.0-sms-r1")
        self.assertEqual(sms_r1["role"], "webui-sms-canary")
        self.assertEqual(
            sms_r1["structural_status"],
            "quarantined-noncanonical-cafe-alignment",
        )
        self.assertFalse(sms_r1["restorable"])
        self.assertTrue(inspector.known_is_quarantined({"known_artifact": sms_r1}))

        corrected = {
            "a1d970c68bde7534519b942bd73a57c6805d321860dead6b437392b0319fe922",
            "aeaceb9cd193a44100bd33c3f14dc48ede6d2e163d7a214a87411d7875adf07f",
            "c27b5f7989ac4e4ac6ff1ebdd603685f6f1fe777918458059b620b1c36ec73ce",
        }
        for digest in corrected:
            item = inspector.KNOWN_ARTIFACTS[digest]
            self.assertEqual(item["structural_status"], "verified-not-flash-qualified")
            self.assertFalse(item["restorable"])
            self.assertFalse(inspector.known_is_quarantined({"known_artifact": item}))

        for digest in {
            "a9a284c5e5d2c8d0a18a55b0e324693b5a4a9f099eed814c3d20cd66a9cb642a",
            "444252fe98c231e2411c82656b1f03cd418e0ad0b4be3feafbc3ba2860270758",
            "de17be0290edb4d3192cf95d4dfca620550a0bf7a9adfbd3d22a15e5b14a518b",
            "d18f87991caf7f8fe173da221d6317e47f9803c0e8b9c22fade4b8aa3ea6459f",
            "c77b66eb9ad817018c597b77d87caef9ab59ee3c14d2e2a6f134b9412dca7431",
            "1dc8f2e006b1ef32f0ffb99c358cc412e5e6b00fa676e024a81cf95a60b7bed1",
            "8d5e9731615180ce09035ee969505fe6afe28d667143cfbed40030c580c5cd5d",
            "ecb494b46875866dbe4274f5275cfef0a00607229291fdf96ebedcca56df6cf8",
            "fde992e34885b0d21167f8333758e577fc1b692430505f35791f3f75de0ec6af",
            "5bfe13360711dc0204de8fdb690095fdcce4b0bb0b1160c58304d0d99f6d875c",
        }:
            self.assertTrue(
                inspector.known_is_quarantined(
                    {"known_artifact": inspector.KNOWN_ARTIFACTS[digest]}
                )
            )

        old_canary = inspector.KNOWN_ARTIFACTS[
            "f2ee088574634d822d5feed8210578a62788c8837fabc80129c6ce51ddfb429c"
        ]
        self.assertTrue(inspector.known_is_quarantined({"known_artifact": old_canary}))

    def test_fixed_size_loader_uses_reviewed_pre_body_slot(self):
        stock = b"<html><body>stock" + (b" " * len(builder.INDEX_LOADER)) + b"</body></html>"
        patched = builder.patch_index_loader(stock)
        self.assertEqual(len(patched), len(stock))
        self.assertIn(builder.INDEX_LOADER, patched)

    def test_cafe_logical_lengths_round_trip_with_canonical_padding(self):
        for remainder in range(4):
            logical = b"x" * (8 + remainder)
            stored, padding, flags = builder.encode_cafe_data(logical)
            self.assertEqual(padding, (-len(logical)) % 4)
            self.assertEqual(len(stored) % 4, 0)
            self.assertEqual(flags & 0x00FFFFFF, len(stored))
            self.assertEqual(flags >> 24, padding)
            self.assertEqual(stored[: len(logical)], logical)
            self.assertEqual(stored[len(logical) :], b"\xFF" * padding)

    def test_inspector_rejects_claimed_padding_that_contains_real_bytes(self):
        logical = b"real-data-12"
        payload = bytearray(cafe_payload(builder.SCRIPT_PATH, logical))
        record_offset = inspector.CAFE_HEADER_SIZE
        stored_size = inspector.u32(payload, record_offset + 4) & 0x00FFFFFF
        struct.pack_into("<I", payload, record_offset + 4, 0x03000000 | stored_size)
        sentinel = record_offset + inspector.CAFE_RECORD_HEADER_SIZE + stored_size
        struct.pack_into("<I", payload, 4, zlib.adler32(payload[8:sentinel]) & 0xFFFFFFFF)
        report, records = inspector.parse_cafe(bytes(payload), include_records=True)
        self.assertFalse(report["record_padding_valid"])
        self.assertEqual(report["invalid_padding_paths"], [builder.SCRIPT_PATH])
        self.assertEqual(records[0].padding_bytes, 3)
        self.assertEqual(records[0].logical_size, stored_size - 3)
        self.assertFalse(records[0].padding_valid)

    def test_builder_rejects_unaligned_source_record(self):
        logical = b"12345"
        payload = bytearray(1024)
        struct.pack_into("<I", payload, 0, 0xCAFECAFE)
        struct.pack_into("<I", payload, 8, 0x00001019)
        record_offset = inspector.CAFE_HEADER_SIZE
        struct.pack_into("<I", payload, record_offset, 0xCAFE1000)
        struct.pack_into("<I", payload, record_offset + 4, len(logical))
        path = builder.INDEX_PATH.encode("ascii")
        payload[record_offset + 8 : record_offset + 8 + len(path)] = path
        data_start = record_offset + inspector.CAFE_RECORD_HEADER_SIZE
        payload[data_start : data_start + len(logical)] = logical
        sentinel = data_start + len(logical)
        struct.pack_into("<I", payload, sentinel, 0xDADADADA)
        payload[sentinel + 4 :] = b"\xFF" * (len(payload) - sentinel - 4)
        struct.pack_into("<I", payload, 4, zlib.adler32(payload[8:sentinel]) & 0xFFFFFFFF)
        report, _ = inspector.parse_cafe(bytes(payload), include_records=False)
        self.assertFalse(report["stored_sizes_aligned_4"])
        self.assertEqual(report["unaligned_stored_paths"], [builder.INDEX_PATH])
        with self.assertRaises(builder.BuildError):
            builder.parse_cafe_source(bytes(payload))

    def test_rebuild_preserves_record_and_appends_script_in_padding(self):
        stock_index = b"<html><body>stock" + (b" " * len(builder.INDEX_LOADER)) + b"</body></html>"
        payload = cafe_payload(builder.INDEX_PATH, stock_index)
        patched_index = builder.patch_index_loader(stock_index)
        script = b"window.marker='MF885 Community Canary Logs 0.0-logs-r1';"
        first, report = builder.rebuild_cafe(
            payload,
            {builder.INDEX_PATH: patched_index},
            {builder.SCRIPT_PATH: script},
        )
        second, _ = builder.rebuild_cafe(
            payload,
            {builder.INDEX_PATH: patched_index},
            {builder.SCRIPT_PATH: script},
        )
        parsed, records = inspector.parse_cafe(first, include_records=True)
        self.assertEqual(first, second)
        self.assertTrue(parsed["adler32_valid"])
        self.assertTrue(parsed["padding_all_ff"])
        self.assertEqual([record.path for record in records], [builder.INDEX_PATH, builder.SCRIPT_PATH])
        self.assertEqual(report["changes"][0]["size_before"], report["changes"][0]["size_after"])
        self.assertEqual(report["additions"][0]["path"], builder.SCRIPT_PATH)
        added = next(record for record in records if record.path == builder.SCRIPT_PATH)
        self.assertTrue(added.padding_valid)
        self.assertEqual(added.logical_sha256, inspector.sha256(script))

    @unittest.skipUnless(
        LOCAL_GOLDEN.is_file() and LOCAL_IDENTITY.is_file(),
        "exact local golden and identity are optional in CI",
    )
    def test_private_logs_profiles_have_exact_logical_bytes_and_valid_padding(self):
        raw = LOCAL_GOLDEN.read_bytes()
        identity = inspector.load_identity(LOCAL_IDENTITY)
        expected = {
            "0.0-logs-r1": (
                0x03003114,
                12_561,
                3,
                "a1d970c68bde7534519b942bd73a57c6805d321860dead6b437392b0319fe922",
            ),
            "0.0-logs-r2": (
                0x0200345C,
                13_402,
                2,
                "aeaceb9cd193a44100bd33c3f14dc48ede6d2e163d7a214a87411d7875adf07f",
            ),
        }
        for profile, relative in (
            ("0.0-logs-r1", "firmware/webui-canary-logs/canary_logs.js"),
            ("0.0-logs-r2", "firmware/webui-canary-logs-r2/canary_logs.js"),
        ):
            with self.subTest(profile=profile):
                script = (ROOT / relative).read_bytes()
                candidate, _ = builder.build_image(raw, identity, script, profile)
                header = inspector.decrypt_header(candidate, identity)
                partitions, errors = inspector.parse_partitions(header, len(candidate))
                self.assertEqual(errors, [])
                webi = next(part for part in partitions if part.name == "WEBI")
                report, records = inspector.parse_cafe(
                    candidate[webi.offset : webi.offset + webi.length],
                    include_records=True,
                )
                record = next(item for item in records if item.path == builder.SCRIPT_PATH)
                size_flags, logical_size, padding, artifact_sha256 = expected[profile]
                self.assertEqual(inspector.sha256(candidate), artifact_sha256)
                self.assertTrue(report["record_padding_valid"])
                self.assertEqual(record.size_flags, size_flags)
                self.assertEqual(record.logical_size, logical_size)
                self.assertEqual(record.padding_bytes, padding)
                self.assertEqual(record.logical_sha256, inspector.sha256(script))

    def test_builder_rejects_duplicate_or_oversized_additions(self):
        stock_index = b"<html><body>stock" + (b" " * len(builder.INDEX_LOADER)) + b"</body></html>"
        payload = cafe_payload(builder.INDEX_PATH, stock_index, size=1024)
        with self.assertRaises(builder.BuildError):
            builder.rebuild_cafe(payload, {}, {builder.INDEX_PATH: b"duplicate"})
        with self.assertRaises(builder.BuildError):
            builder.rebuild_cafe(payload, {}, {builder.SCRIPT_PATH: b"x" * 2000})


if __name__ == "__main__":
    unittest.main()
