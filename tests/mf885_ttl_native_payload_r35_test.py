import lzma
import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mf885_thumb_disasm as disasm  # noqa: E402
import mf885_thumb_subset_emulator as thumb_exec  # noqa: E402
import mf885_ttl_native_payload_r35 as ttl  # noqa: E402


GOLDEN = ROOT / ".runtime" / "private" / "MF885_golden_capture_a.bin"
SETTER = 0x064073DB
GETTER = 0x06407493
FREE = 0x0644F00F


def exact_oslo() -> bytes:
    raw = GOLDEN.read_bytes()
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE, memlimit=64 * 1024 * 1024)
    return decoder.decompress(raw[0x23C:0x23C + 0x460000], max_length=32 * 1024 * 1024)


class R35MachineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiled, cls.conditions = ttl.compile_components()
        cls.post_get = thumb_exec.ThumbProgram(
            cls.compiled["ttl_post_get"], ttl.TTL_POST_GET_RUNTIME, 156
        )
        cls.post_set = thumb_exec.ThumbProgram(
            cls.compiled["ttl_post_set"], ttl.TTL_POST_SET_RUNTIME, 192
        )

    def test_components_fit_exact_caves_and_readback_has_one_call(self):
        self.assertTrue(all(item["passed"] for item in self.conditions))
        self.assertEqual(
            {name: len(raw) for name, raw in self.compiled.items()},
            {"ttl_forward": 152, "ttl_post_set": 208, "ttl_post_get": 168},
        )
        self.assertLessEqual(ttl.TTL_POST_SET_OFFSET + 208, ttl.TTL_DATA_OFFSET)
        self.assertLessEqual(ttl.TTL_DATA_END, 0x1500)
        self.assertLessEqual(ttl.TTL_POST_GET_OFFSET + 168, 0x1600)
        instructions = [
            item["instruction"]
            for item in disasm.disassemble(
                self.compiled["ttl_post_get"][:156], ttl.TTL_POST_GET_RUNTIME
            )
        ]
        self.assertEqual(sum(value.startswith("blx\t") for value in instructions), 1)
        self.assertFalse(any("udf" in value for value in instructions))

    def test_data_contains_only_same_model_read_and_isolated_write_names(self):
        blob = ttl.data_blob()
        self.assertEqual(len(blob), 0x30)
        self.assertEqual(blob[0], 0)
        self.assertEqual(blob[0x04:0x10], b"\0" * 12)
        self.assertEqual(blob[0x10:0x18], b"command\0")
        self.assertEqual(blob[0x18:0x1C], b"arg\0")
        self.assertEqual(blob[0x1C:0x23], b"output\0")
        self.assertEqual(blob[0x28:0x2C], b"off\0")
        for forbidden in (b"SystemChannelName", b"PRODUCT_CHANNEL", b"debugon", b"Engineering"):
            self.assertNotIn(forbidden, blob)

    def _run_post_get(self, state: int, phase: int = 4, setter_result: int = 0):
        data = bytearray(ttl.data_blob())
        data[0] = state
        published = []

        def setter(machine, arguments):
            published.append((*arguments, machine.read_c_string(arguments[3])))
            return setter_result

        preserved = {f"r{index}": 0xA5000000 + index for index in range(4, 11)}
        machine = self.post_get.machine(
            registers={"r0": phase, "r1": 0xDEADBEEF, **preserved},
            blobs=((ttl.TTL_DATA_RUNTIME, bytes(data)),),
            callbacks={SETTER: setter},
        )
        before = machine.bytes(ttl.TTL_DATA_RUNTIME, ttl.TTL_DATA_BYTES)
        initial_sp = machine.regs["sp"]
        result = machine.run()
        after = machine.bytes(ttl.TTL_DATA_RUNTIME, ttl.TTL_DATA_BYTES)
        return result, before, after, published, machine, initial_sp, preserved

    def test_post_get_publishes_all_states_once_on_diagnostic_output(self):
        for state in range(256):
            with self.subTest(state=state):
                result, before, after, published, machine, initial_sp, preserved = self._run_post_get(state)
                self.assertEqual(result, 0)
                self.assertEqual(before, after)
                self.assertEqual(machine.regs["sp"], initial_sp)
                self.assertEqual(len(published), 1)
                self.assertEqual(
                    published[0][:3],
                    (ttl.STOCK_DIAGNOSTIC_MODEL_RUNTIME, 0, ttl.TTL_DATA_RUNTIME + 0x1C),
                )
                self.assertEqual(published[0][4], b"off" if state == 0 else str(state).encode())
                for register, value in preserved.items():
                    self.assertEqual(machine.regs[register], value, register)
        result, _before, _after, published, _machine, _sp, _preserved = self._run_post_get(
            64, setter_result=0x13579BDF
        )
        self.assertEqual(result, 0x13579BDF)
        self.assertEqual(len(published), 1)
        result, before, after, published, machine, initial_sp, preserved = self._run_post_get(64, phase=3)
        self.assertEqual((result, after, published), (0, before, []))
        self.assertEqual(machine.call_log, [])
        self.assertEqual(machine.regs["sp"], initial_sp)
        for register, value in preserved.items():
            self.assertEqual(machine.regs[register], value)

    def _run_post_set(self, command, argument, initial=173, phase=3):
        command_address = 0x21002000
        argument_address = 0x21002100
        data = bytearray(ttl.data_blob())
        data[0] = initial
        blobs = [(ttl.TTL_DATA_RUNTIME, bytes(data))]
        if command is not None:
            blobs.append((command_address, command + b"\0"))
        if argument is not None:
            blobs.append((argument_address, argument + b"\0"))
        freed = []

        def getter(_machine, arguments):
            self.assertEqual(arguments[:2], (ttl.STOCK_DIAGNOSTIC_MODEL_RUNTIME, 0))
            if arguments[2] == ttl.TTL_DATA_RUNTIME + 0x10:
                return 0 if command is None else command_address
            if arguments[2] == ttl.TTL_DATA_RUNTIME + 0x18:
                return 0 if argument is None else argument_address
            self.fail(f"unexpected getter field 0x{arguments[2]:08x}")

        def free(_machine, arguments):
            freed.append(arguments[0])
            return 0

        preserved = {f"r{index}": 0xB6000000 + index for index in range(4, 11)}
        machine = self.post_set.machine(
            registers={"r0": phase, "r1": 0xDEADBEEF, **preserved},
            blobs=blobs,
            callbacks={GETTER: getter, FREE: free},
        )
        initial_sp = machine.regs["sp"]
        result = machine.run()
        writes = [
            item
            for item in machine.write_log
            if ttl.TTL_DATA_RUNTIME <= item[0] < ttl.TTL_DATA_RUNTIME + ttl.TTL_DATA_BYTES
        ]
        self.assertEqual(machine.regs["sp"], initial_sp)
        for register, value in preserved.items():
            self.assertEqual(machine.regs[register], value, register)
        setter_calls = [item for item in machine.call_log if item["target"] == (SETTER & ~1)]
        return result, machine.read8(ttl.TTL_DATA_RUNTIME), writes, freed, setter_calls

    def test_post_set_accepts_only_off_or_canonical_1_to_255(self):
        for state in range(256):
            value = b"off" if state == 0 else str(state).encode()
            result, actual, writes, freed, setter_calls = self._run_post_set(b"ttl", value)
            self.assertEqual((result, actual), (0, state))
            self.assertEqual(writes, [(ttl.TTL_DATA_RUNTIME, 1, state)])
            self.assertEqual(freed, [0x21002000, 0x21002100])
            self.assertEqual(setter_calls, [])
        invalid = (b"", b"0", b"00", b"01", b"256", b"999", b"1234", b"-1", b"+1", b" 64", b"64 ", b"OFF", b"\xff")
        for value in invalid:
            with self.subTest(value=value):
                result, actual, writes, freed, setter_calls = self._run_post_set(b"ttl", value)
                self.assertEqual((result, actual, writes), (0, 173, []))
                self.assertEqual(freed, [0x21002000, 0x21002100])
                self.assertEqual(setter_calls, [])


@unittest.skipUnless(GOLDEN.is_file(), "exact private golden is optional in CI")
class R35ExactGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oslo = exact_oslo()

    def test_stock_and_candidate_use_same_setter_without_system_bridge(self):
        source = ttl.inspect_exact_oslo(self.oslo)
        self.assertEqual(source["status"], "GREEN")
        candidate, report = ttl.build_payload(self.oslo, "full")
        verification = ttl.verify_payload(self.oslo, candidate, "full")
        self.assertEqual(verification["status"], "GREEN")
        self.assertEqual(report["transport"]["trigger_model"], "diagnostic")
        self.assertEqual(report["transport"]["read_model"], "diagnostic")
        self.assertEqual(report["transport"]["read_field"], "output")
        self.assertEqual(report["transport"]["publisher_slot"], "post_get")
        self.assertEqual(report["transport"]["publisher_setter_calls"], 1)
        self.assertTrue(report["transport"]["same_model_publication"])
        self.assertFalse(report["transport"]["system_channel_bridge_used"])
        self.assertEqual(struct.unpack_from("<I", candidate, ttl.DUSTER_PRE_GET_POINTER)[0], 0)
        self.assertEqual(
            struct.unpack_from("<I", candidate, ttl.DUSTER_POST_GET_POINTER)[0],
            ttl.TTL_POST_GET_RUNTIME | 1,
        )
        self.assertTrue(all(item["passed"] for item in report["engineering"]["conditions"]))

    def test_full_and_observer_modes_differ_only_at_forward_hook(self):
        observer, observer_report = ttl.build_payload(self.oslo, "observer")
        full, full_report = ttl.build_payload(self.oslo, "full")
        start = ttl.IP_FORWARD_HOOK_OFFSET
        end = start + len(ttl.IP_FORWARD_HOOK)
        self.assertEqual(observer[start:end], ttl.IP_FORWARD_ORIGINAL)
        self.assertEqual(full[start:end], ttl.IP_FORWARD_HOOK)
        self.assertEqual(observer[:start] + observer[end:], full[:start] + full[end:])
        self.assertFalse(observer_report["hook"]["installed"])
        self.assertTrue(full_report["hook"]["installed"])


if __name__ == "__main__":
    unittest.main()
