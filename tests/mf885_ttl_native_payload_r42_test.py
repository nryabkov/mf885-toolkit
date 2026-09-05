import copy
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mf885_thumb_disasm as disasm
import mf885_thumb_subset_emulator as emulator
import mf885_ttl_native_payload_r42 as probe


class ReadRecordingMachine(emulator.ThumbMachine):
    """Observe actual emitted-code memory accesses, including failed reads."""

    def __init__(self, *args, **kwargs):
        self.read_log = []
        super().__init__(*args, **kwargs)

    def bytes(self, address, length):
        self.read_log.append((address, length))
        return super().bytes(address, length)


class R42MachineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw, cls.conditions = probe.compile_callback()
        cls.program = emulator.ThumbProgram(cls.raw, probe.CALLBACK_RUNTIME, len(cls.raw))

    def machine(self, phase, context, value=None):
        preserved = {f"r{i}": 0xA5000000 + i for i in range(2, 13)}
        registers = {"r0": phase, "r1": context, **preserved}
        blobs = [] if value is None else [(context, struct.pack("<H", value))]
        machine = ReadRecordingMachine(self.program, registers=registers, blobs=blobs, callbacks={})
        initial = dict(machine.regs)
        return machine, initial

    def assert_no_side_effects(self, machine, initial):
        self.assertEqual(machine.call_log, [])
        self.assertEqual(machine.write_log, [])
        for reg in [f"r{i}" for i in range(1, 13)] + ["sp", "lr"]:
            self.assertEqual(machine.regs[reg], initial[reg], reg)

    def test_exact_code_has_only_guarded_halfword_read_and_return(self):
        self.assertTrue(all(c["passed"] for c in self.conditions))
        self.assertEqual(probe.CALLBACK_RUNTIME | 1, 0x06001341)
        self.assertEqual(probe.DUSTER_POST_SET_POINTER, 0x900404)
        self.assertEqual(self.raw.hex(), "032801d101b1088800207047")
        self.assertEqual([r["instruction"] for r in disasm.disassemble(self.raw, probe.CALLBACK_RUNTIME)], [
            "cmp\tr0, #0x3", "bne\t#0x2", "cbz\tr1, #0x0",
            "ldrh\tr0, [r1]", "movs\tr0, #0x0", "bx\tlr",
        ])

    def test_wrong_phase_never_reads_even_non_null_unmapped_pointer(self):
        for phase in (0, 1, 2, 4, 0xFFFFFFFF):
            for context in (0, 0x21000000, 0xFFFFFFFE):
                with self.subTest(phase=phase, context=context):
                    machine, initial = self.machine(phase, context)
                    self.assertEqual(machine.run(), 0)
                    self.assertEqual(machine.read_log, [])
                    self.assert_no_side_effects(machine, initial)

    def test_phase_three_null_context_never_reads(self):
        machine, initial = self.machine(3, 0)
        self.assertEqual(machine.run(), 0)
        self.assertEqual(machine.read_log, [])
        self.assert_no_side_effects(machine, initial)

    def test_phase_three_reads_exactly_two_bytes_and_discards_value(self):
        # Only two bytes are mapped: tree offset 12 and stack are unavailable.
        for context in (0x21000000, 0x21000002):
            for value in (0, 1, 2, 0x1234, 0xFFFF):
                with self.subTest(context=context, value=value):
                    machine, initial = self.machine(3, context, value)
                    before = dict(machine.memory)
                    self.assertEqual(machine.run(), 0)
                    self.assertEqual(machine.read_log, [(context, 2)])
                    self.assertEqual(machine.memory, before)
                    self.assert_no_side_effects(machine, initial)

    def test_non_null_is_not_a_memory_validity_check(self):
        machine, _initial = self.machine(3, 0x21000000)
        with self.assertRaisesRegex(emulator.ThumbExecutionError, "unmapped read"):
            machine.run()
        self.assertEqual(machine.read_log, [(0x21000000, 2)])

    def test_load_requires_second_byte(self):
        machine, _initial = self.machine(3, 0x21000000)
        machine.load(0x21000000, b"\x01")
        with self.assertRaisesRegex(emulator.ThumbExecutionError, "0x21000001"):
            machine.run()
        self.assertEqual(machine.read_log, [(0x21000000, 2)])

    def test_source_drift_is_rejected_before_compiler(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "changed.ll"
            path.write_bytes(probe.SOURCE.read_bytes().replace(b"volatile", b"        "))
            with mock.patch.object(probe, "SOURCE", path), mock.patch.object(probe.thumb, "compile_ir_layout") as compile_ir:
                with self.assertRaises(probe.TtlR42PayloadError):
                    probe.compile_callback()
                compile_ir.assert_not_called()

    def test_emitted_code_or_mapping_drift_is_rejected(self):
        layout = probe.thumb.compile_ir_layout(probe.SOURCE.read_bytes())
        changes = [
            ("raw", bytes.fromhex("00207047")),
            ("ranges", [{"kind": "data", "offset": 0, "bytes": 12}]),
            ("functions", [{"name": probe.FUNCTION, "offset": 0, "thumb": False, "bytes": 12}]),
        ]
        for field, value in changes:
            changed = copy.deepcopy(layout)
            changed[field] = value
            with self.subTest(field=field), mock.patch.object(probe.thumb, "compile_ir_layout", return_value=changed):
                with self.assertRaises(probe.TtlR42PayloadError):
                    probe.compile_callback()

    def test_wrong_stock_input_rejected_before_compilation(self):
        with mock.patch.object(probe, "compile_callback") as compile_callback:
            with self.assertRaises(probe.TtlR42PayloadError):
                probe.build_payload(b"not the pinned stock OSLO")
            compile_callback.assert_not_called()


OSLO_INPUT = os.environ.get("MF885_R42_TEST_OSLO")


@unittest.skipUnless(OSLO_INPUT, "optional exact stock OSLO supplied via MF885_R42_TEST_OSLO")
class R42ExactStockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oslo = Path(OSLO_INPUT).read_bytes()
        cls.candidate, cls.report = probe.build_payload(cls.oslo)

    def test_exact_two_patches_preserve_entire_remaining_oslo(self):
        expected = bytearray(self.oslo)
        expected[0x1340:0x134C] = bytes.fromhex("032801d101b1088800207047")
        struct.pack_into("<I", expected, 0x900404, 0x06001341)
        self.assertEqual(self.candidate, bytes(expected))
        self.assertEqual(probe.verify_payload(self.oslo, self.candidate)["status"], "GREEN")
        self.assertFalse(self.report["artifact"]["flashable"])
        self.assertFalse(self.report["qualification"]["live_load_execution_proven"])
        self.assertEqual(self.report["transport"]["executed_loads_min"], 0)

    def test_candidate_drift_in_all_regions_or_size_is_rejected(self):
        for offset in (0, 0x1340, 0x134C, 0x1430, 0x900404, len(self.candidate) - 1):
            changed = bytearray(self.candidate)
            changed[offset] ^= 1
            with self.subTest(offset=offset):
                self.assertEqual(probe.verify_payload(self.oslo, bytes(changed))["status"], "REJECTED")
        for changed in (b"", self.candidate[:-1], self.candidate + b"\0"):
            self.assertEqual(probe.verify_payload(self.oslo, changed)["status"], "REJECTED")

    def test_same_size_stock_drift_is_rejected(self):
        changed = bytearray(self.oslo)
        changed[-1] ^= 1
        with self.assertRaises(probe.TtlR42PayloadError):
            probe.build_payload(bytes(changed))


if __name__ == "__main__":
    unittest.main()
