import hashlib
import lzma
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mf885_fbf as fbf  # noqa: E402
import mf885_fbf_sim as fbf_sim  # noqa: E402
import mf885_firmware_inspect as inspector  # noqa: E402


OFFICIAL_2589 = Path("/tmp/MF96-ROUTER-C2_2.5.89_official.bin")
OFFICIAL_2596 = Path("/tmp/MF96-ROUTER_2.5.96_official.bin")
LOCAL_CANARY = ROOT / "build" / "MF885_Community_0.0-logs-r1-cafe-r2.bin"


def synthetic_fbf(record_count: int = 1) -> bytes:
    table_end = fbf.FBF_RECORD_TABLE_OFFSET + record_count * fbf.FBF_RECORD_SIZE
    if table_end > fbf.FBF_BLOCK_SIZE:
        raise AssertionError("synthetic table exceeds its header block")
    value = bytearray(fbf.FBF_BLOCK_SIZE * (record_count + 2))
    value[: len(fbf.FBF_MAGIC)] = fbf.FBF_MAGIC
    value[0x0C:0x18] = b"020589ABCD-2"
    struct.pack_into("<I", value, 0x20, fbf.FBF_FORMAT_WORD)
    struct.pack_into("<I", value, 0x34, 1)
    struct.pack_into("<I", value, 0x38, 1)
    struct.pack_into("<I", value, 0x3C, fbf.FBF_DEVICE_OFFSET)
    struct.pack_into(
        "<I",
        value,
        0x40,
        fbf.FBF_RECORD_TABLE_OFFSET + (record_count - 1) * fbf.FBF_RECORD_SIZE,
    )
    struct.pack_into("<I", value, fbf.FBF_RECORD_COUNT_OFFSET, record_count)
    total = 0
    for index in range(record_count):
        offset = fbf.FBF_RECORD_TABLE_OFFSET + index * fbf.FBF_RECORD_SIZE
        data_offset = fbf.FBF_BLOCK_SIZE * (index + 1)
        payload = struct.pack("<II", 0x11223344 + index, 0x55667788 + index)
        value[offset : offset + 4] = b"IBEW"
        struct.pack_into("<I", value, offset + 0x0C, fbf.WEBI_CHUNK_BYTES)
        struct.pack_into("<I", value, offset + 0x10, 3)
        struct.pack_into("<I", value, offset + 0x14, data_offset // fbf.FBF_BLOCK_SIZE)
        struct.pack_into("<I", value, offset + 0x18, len(payload))
        struct.pack_into(
            "<I",
            value,
            offset + 0x1C,
            fbf.WEBI_FLASH_ADDRESS + index * fbf.WEBI_CHUNK_BYTES,
        )
        struct.pack_into("<I", value, offset + 0x30, fbf.xor32(payload))
        value[data_offset : data_offset + len(payload)] = payload
        total += len(payload)
    for offset in (0x24, 0x28, 0x2C):
        struct.pack_into("<I", value, offset, total)
    return bytes(value)


def synthetic_webi_candidate() -> bytes:
    donor = fbf.parse_fbf(synthetic_fbf(14))
    meaningful = fbf.CUSTOM_WEBI_SENTINEL + 4
    webi = bytearray(b"\xFF" * fbf.WEBI_FLASH_BYTES)
    for offset in range(meaningful):
        webi[offset] = (offset * 17 + 3) & 0xFF
    return fbf._assemble_webi_only_fbf(donor, bytes(webi), meaningful)


class FbfTests(unittest.TestCase):
    def test_parser_validates_header_ranges_totals_and_xor32(self):
        raw = synthetic_fbf()
        parsed = fbf.parse_fbf(raw, include_records=True)

        self.assertTrue(parsed.report["verification"]["structurally_verified"])
        self.assertEqual(parsed.report["header"]["version"], "020589ABCD-2")
        self.assertEqual(parsed.report["images_by_type"], {"WEBI": 1})
        self.assertFalse(parsed.report["rsa"]["record_present"])
        self.assertFalse(parsed.report["verification"]["flash_qualified"])
        self.assertEqual(
            parsed.report["layout"]["uncovered_by_records"],
            [
                {
                    "start": "0x00000000",
                    "end": "0x00ac0000",
                    "bytes": fbf.WEBI_FLASH_ADDRESS,
                },
                {
                    "start": "0x00ae0000",
                    "end": "0x02000000",
                    "bytes": fbf.FBF_FLASH_LIMIT
                    - fbf.WEBI_FLASH_ADDRESS
                    - fbf.WEBI_CHUNK_BYTES,
                },
            ],
        )
        rebuilt = fbf.reconstruct_partition(
            parsed, "WEBI", fbf.WEBI_FLASH_ADDRESS, fbf.WEBI_CHUNK_BYTES
        )
        self.assertEqual(rebuilt[:8], raw[fbf.FBF_BLOCK_SIZE : fbf.FBF_BLOCK_SIZE + 8])
        self.assertEqual(rebuilt[8:], b"\xFF" * (len(rebuilt) - 8))

    def test_parser_fails_closed_on_checksum_and_master_total_mutations(self):
        checksum = bytearray(synthetic_fbf())
        checksum[fbf.FBF_BLOCK_SIZE] ^= 1
        parsed = fbf.parse_fbf(bytes(checksum))
        self.assertFalse(parsed.report["verification"]["structurally_verified"])
        self.assertTrue(
            any("XOR32" in error for error in parsed.report["verification"]["errors"])
        )

        total = bytearray(synthetic_fbf())
        struct.pack_into("<I", total, 0x24, 9)
        parsed = fbf.parse_fbf(bytes(total))
        self.assertFalse(parsed.report["verification"]["structurally_verified"])
        self.assertTrue(
            any("totals disagree" in error for error in parsed.report["verification"]["errors"])
        )

    def test_webi_only_assembler_round_trips_all_fourteen_flash_chunks(self):
        candidate = synthetic_webi_candidate()
        parsed = fbf.parse_fbf(candidate)
        webi = fbf.reconstruct_partition(
            parsed, "WEBI", fbf.WEBI_FLASH_ADDRESS, fbf.WEBI_FLASH_BYTES
        )
        plan = fbf.webi_only_write_plan(parsed)

        self.assertTrue(parsed.report["verification"]["structurally_verified"])
        self.assertEqual(parsed.report["images_by_type"], {"WEBI": 14})
        self.assertFalse(parsed.report["rsa"]["record_present"])
        self.assertEqual(len(webi), fbf.WEBI_FLASH_BYTES)
        self.assertEqual(len(plan), 14)
        self.assertEqual(plan[0]["flash_address"], "0x00c60000")
        self.assertEqual(plan[-1]["flash_address"], "0x00ac0000")
        self.assertEqual(sum(item["erase_bytes"] for item in plan), 0x1C0000)
        self.assertEqual(sum(item["write_bytes"] for item in plan), 0x1BF968)

    def test_strict_webi_profile_fails_closed_on_write_plan_mutations(self):
        candidate = synthetic_webi_candidate()
        record0 = fbf.FBF_RECORD_TABLE_OFFSET
        record1 = record0 + fbf.FBF_RECORD_SIZE

        mutations: dict[str, bytes] = {}
        for name, offset, value in (
            ("tag", record0, b"OLSO"),
            ("extent", record0 + 0x0C, struct.pack("<I", fbf.WEBI_CHUNK_BYTES // 2)),
            ("flags", record0 + 0x10, struct.pack("<I", 2)),
            (
                "write-length",
                record0 + 0x18,
                struct.pack("<I", fbf.WEBI_CHUNK_BYTES),
            ),
            ("address", record0 + 0x1C, struct.pack("<I", fbf.WEBI_FLASH_ADDRESS)),
        ):
            mutated = bytearray(candidate)
            mutated[offset : offset + len(value)] = value
            mutations[name] = bytes(mutated)

        reordered = bytearray(candidate)
        first = bytes(reordered[record0 : record0 + fbf.FBF_RECORD_SIZE])
        second = bytes(reordered[record1 : record1 + fbf.FBF_RECORD_SIZE])
        reordered[record0 : record0 + fbf.FBF_RECORD_SIZE] = second
        reordered[record1 : record1 + fbf.FBF_RECORD_SIZE] = first
        mutations["record-order"] = bytes(reordered)

        checksum = bytearray(candidate)
        checksum[fbf.FBF_BLOCK_SIZE] ^= 1
        mutations["checksum"] = bytes(checksum)

        total = bytearray(candidate)
        struct.pack_into("<I", total, 0x24, struct.unpack_from("<I", total, 0x24)[0] + 4)
        mutations["master-total"] = bytes(total)

        count = bytearray(candidate)
        struct.pack_into("<I", count, fbf.FBF_RECORD_COUNT_OFFSET, 13)
        mutations["record-count"] = bytes(count)

        data_overlap = bytearray(candidate)
        struct.pack_into(
            "<I",
            data_overlap,
            record1 + 0x14,
            struct.unpack_from("<I", data_overlap, record0 + 0x14)[0],
        )
        mutations["data-overlap"] = bytes(data_overlap)

        version = bytearray(candidate)
        version[0x0C:0x18] = b"020596ABCD-2"
        mutations["version"] = bytes(version)
        mutations["trailing-data"] = candidate + b"\0"

        for name, raw in mutations.items():
            with self.subTest(name=name), self.assertRaises(fbf.FbfError):
                fbf.webi_only_write_plan(fbf.parse_fbf(raw))

    def test_webi_assembler_rejects_non_erased_omitted_source_bytes(self):
        donor = fbf.parse_fbf(synthetic_fbf(14))
        meaningful = fbf.CUSTOM_WEBI_SENTINEL + 4
        webi = bytearray(b"\xFF" * fbf.WEBI_FLASH_BYTES)
        webi[meaningful] = 0

        with self.assertRaises(fbf.FbfError):
            fbf._assemble_webi_only_fbf(donor, bytes(webi), meaningful)

    def test_builder_rejects_any_unreviewed_source_bytes(self):
        with self.assertRaises(fbf.FbfError):
            fbf.build_webi_noflash(synthetic_fbf(), b"not the reviewed ZIMI")

    def test_publish_requires_an_explicit_noflash_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(fbf.FbfError):
                fbf.publish_pair(root / "candidate.fbf", b"x", root / "report.json", b"{}")

    def test_noflash_simulator_models_success_deterministically_in_memory(self):
        candidate = synthetic_webi_candidate()
        parsed = fbf.parse_fbf(candidate)
        initial = b"\xA5" * fbf.WEBI_FLASH_BYTES
        first = fbf_sim.simulate_native_webi(parsed, initial)
        second = fbf_sim.simulate_native_webi(parsed, initial)
        expected = fbf.reconstruct_partition(
            parsed, "WEBI", fbf.WEBI_FLASH_ADDRESS, fbf.WEBI_FLASH_BYTES
        )

        self.assertEqual(first, second)
        self.assertEqual(first["model"]["completed_records"], 14)
        self.assertEqual(first["model"]["native_would_erase_bytes"], 0x1C0000)
        self.assertEqual(first["model"]["native_would_write_bytes"], 0x1BF968)
        self.assertEqual(
            first["model"]["modeled_final_partition_sha256"],
            hashlib.sha256(expected).hexdigest(),
        )
        self.assertEqual(
            [event.get("value") for event in first["model"]["events"] if event["phase"] == "retained-selector"],
            ["MAXS"],
        )
        self.assertEqual(initial, b"\xA5" * fbf.WEBI_FLASH_BYTES)
        self.assertEqual(first["safety"]["filesystem_writes_attempted"], 0)
        self.assertEqual(first["safety"]["router_requests_attempted"], 0)
        self.assertEqual(first["safety"]["firmware_posts_attempted"], 0)
        self.assertEqual(first["safety"]["flash_bytes_actually_written"], 0)
        self.assertFalse(first["safety"]["reset_attempted"])
        self.assertFalse(first["safety"]["flash_qualified"])
        event_by_phase = {event["phase"]: event for event in first["model"]["events"]}
        self.assertEqual(event_by_phase["strict-profile"]["result"], "pass")
        self.assertEqual(event_by_phase["version-hardware-gate"]["result"], "not-evaluated")
        self.assertEqual(event_by_phase["battery-gate"]["result"], "not-evaluated")
        self.assertEqual(event_by_phase["pre-flash-hook"]["result"], "would-call")

    def test_noflash_simulator_keeps_failed_record_state_unknown(self):
        parsed = fbf.parse_fbf(synthetic_webi_candidate())
        initial = b"\xA5" * fbf.WEBI_FLASH_BYTES
        result = fbf_sim.simulate_native_webi(
            parsed,
            initial,
            scenario="worker-return-minus-five",
            fail_record=3,
        )
        expected = bytearray(initial)
        for record in parsed.records[:3]:
            start = record.flash_address - fbf.WEBI_FLASH_ADDRESS
            expected[start : start + record.extent_bytes] = b"\xFF" * record.extent_bytes
            payload = parsed.raw[
                record.data_offset : record.data_offset + record.stored_bytes
            ]
            expected[start : start + record.stored_bytes] = payload

        self.assertEqual(result["model"]["completed_records"], 3)
        self.assertEqual(result["model"]["failed_record"], 3)
        self.assertEqual(result["model"]["failed_record_and_remainder_state"], "unknown")
        self.assertIsNone(result["model"]["modeled_final_partition_sha256"])
        self.assertEqual(
            result["model"]["known_prefix_state_sha256"],
            hashlib.sha256(expected).hexdigest(),
        )
        self.assertEqual(len(result["model"]["steps"]), 3)
        self.assertIn(
            {"phase": "retained-selector", "value": "MINS", "planned_only": True},
            result["model"]["events"],
        )
        self.assertFalse(result["limitations"]["qualified_mins_entry"])

    def test_noflash_simulator_rejects_ambiguous_scenarios_and_sizes(self):
        parsed = fbf.parse_fbf(synthetic_webi_candidate())
        initial = b"\xFF" * fbf.WEBI_FLASH_BYTES
        with self.assertRaises(fbf_sim.SimulationError):
            fbf_sim.simulate_native_webi(parsed, initial[:-1])
        with self.assertRaises(fbf_sim.SimulationError):
            fbf_sim.simulate_native_webi(parsed, initial, scenario="unknown")
        with self.assertRaises(fbf_sim.SimulationError):
            fbf_sim.simulate_native_webi(parsed, initial, fail_record=0)
        for value in (None, True, -1, 14):
            with self.subTest(fail_record=value), self.assertRaises(fbf_sim.SimulationError):
                fbf_sim.simulate_native_webi(
                    parsed,
                    initial,
                    scenario="worker-return-minus-five",
                    fail_record=value,
                )

    @unittest.skipUnless(
        OFFICIAL_2589.is_file() and OFFICIAL_2596.is_file(),
        "exact official FBF artifacts are optional in CI",
    )
    def test_nearby_official_packages_leave_the_same_candidate_system_gap(self):
        expected = {
            "start": "0x00500000",
            "end": "0x00940000",
            "bytes": 0x00440000,
        }
        for artifact in (OFFICIAL_2589, OFFICIAL_2596):
            report = fbf.parse_fbf(artifact.read_bytes()).report
            self.assertTrue(report["verification"]["structurally_verified"])
            self.assertIn(expected, report["layout"]["uncovered_by_records"])

    @unittest.skipUnless(
        OFFICIAL_2589.is_file() and OFFICIAL_2596.is_file(),
        "exact official FBF artifacts are optional in CI",
    )
    def test_nearby_official_builds_keep_the_registered_at_mins_transition(self):
        for version, artifact in (
            ("2.5.89", OFFICIAL_2589),
            ("2.5.96", OFFICIAL_2596),
        ):
            parsed = fbf.parse_fbf(artifact.read_bytes())
            packed = fbf.reconstruct_partition(parsed, "OSLO", 0x000A0000, 0x00460000)
            unpacked = lzma.decompress(packed, format=lzma.FORMAT_ALONE)
            report = inspector.inspect_registered_at_mins_transition(unpacked)
            self.assertEqual(report["status"], "verified")
            self.assertEqual(report["build"], version)
            self.assertEqual(report["dispatch_case"], 29)
            self.assertEqual(report["second_argument_for_mins"], 0)
            self.assertTrue(report["registered_handler_to_mins_write_and_reset_proven"])
            loader_abi = inspector.inspect_early_loader_abi(unpacked)
            self.assertEqual(loader_abi["status"], "verified")
            self.assertEqual(loader_abi["build"], version)
            self.assertFalse(loader_abi["selector_consumer_analysis_performed"])

    @unittest.skipUnless(
        OFFICIAL_2589.is_file() and LOCAL_CANARY.is_file(),
        "private/public exact local artifacts are optional in CI",
    )
    def test_exact_official_donor_build_is_deterministic_and_byte_exact(self):
        donor = OFFICIAL_2589.read_bytes()
        source = LOCAL_CANARY.read_bytes()
        first, report = fbf.build_webi_noflash(donor, source)
        second, _ = fbf.build_webi_noflash(donor, source)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 1_843_200)
        self.assertEqual(
            hashlib.sha256(first).hexdigest(),
            "63e040d385b29d2732c06cabee81e3f85d6fd000e8661b22eb049627e91460a7",
        )
        self.assertEqual(report["fbf"]["image_types"], {"WEBI": 14})
        self.assertTrue(report["donor"]["stock_webi_matches_target_2_5_94"])
        self.assertFalse(report["safety"]["flash_qualified"])
        self.assertEqual(report["safety"]["firmware_posts_attempted"], 0)


if __name__ == "__main__":
    unittest.main()
