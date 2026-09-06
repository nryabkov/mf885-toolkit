"""Fail-closed regressions for the independent model; no live I/O."""
import unittest
from unittest.mock import patch
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import mf885_thumb1_chain_model as proof
import mf885_ttl_native_payload_r44 as native
import mf885_ttl_native_payload_r43 as historical
import hashlib
import tempfile
import os


class NegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.helper=native.compile_forward()[0][len(native.ENTRY_STUB):]

    def test_wrong_stub_branch_skips_prologue_rejected(self):
        with patch.object(proof,'STUB',bytes.fromhex('28003100220000e0')):
            with self.assertRaises(AssertionError):
                proof.Machine(self.helper,proof.sample(96,5,17)).run()

    def test_return_branch_into_literal_rejected(self):
        bad=bytearray(proof.HOOK);bad[4:6]=bytes.fromhex('00e0')
        with patch.object(proof,'HOOK',bytes(bad)):
            with self.assertRaisesRegex(AssertionError,'literal/outside execution'):
                proof.Machine(self.helper,proof.sample(96,5,17)).run()

    def test_arm_entry_literal_rejected(self):
        bad=bytearray(proof.HOOK);bad[6]&=0xfe
        with patch.object(proof,'HOOK',bytes(bad)):
            with self.assertRaisesRegex(AssertionError,'unexpected ARM execution'):
                proof.Machine(self.helper,proof.sample(96,5,17)).run()

    def test_corrupt_output_offset_rejected(self):
        bad=bytearray(self.helper);bad[4:6]=bytes.fromhex('546d') # LDR r4,[r2,#0x54]
        with self.assertRaisesRegex(AssertionError,'unmapped memory'):
            proof.Machine(bytes(bad),proof.sample(96,5,17)).run()

    def test_extra_packet_write_rejected(self):
        bad=bytearray(self.helper);bad[130:132]=bytes.fromhex('c260') # STR r2,[r0,#12]
        with self.assertRaises(AssertionError):
            proof.Machine(bytes(bad),proof.sample(96,5,17)).run()

    def test_unknown_thumb2_halfword_rejected(self):
        bad=bytearray(self.helper);bad[:2]=bytes.fromhex('10f0')
        with self.assertRaisesRegex(AssertionError,'not supported Thumb1'):
            proof.Machine(bytes(bad),proof.sample(96,5,17)).run()

    def test_historical_thumb2_hook_is_rejected(self):
        with patch.object(proof, 'HOOK', historical.IP_FORWARD_HOOK):
            machine = proof.Machine(self.helper, proof.sample(96,5,17))
            # The historical hook has 12 code bytes, not the new inline literal.
            machine.code = ((proof.A, proof.A+12),) + machine.code[1:]
            with self.assertRaisesRegex(AssertionError, 'not supported Thumb1'):
                machine.run()

    def test_condition_flags_signed_unsigned(self):
        m=proof.Machine(self.helper,proof.sample(96,5,17))
        self.assertEqual(m.sub(0,1),0xffffffff);self.assertFalse(m.C);self.assertTrue(m.N);self.assertFalse(m.V)
        self.assertEqual(m.sub(0x80000000,1),0x7fffffff);self.assertTrue(m.C);self.assertTrue(m.V)
        self.assertEqual(m.add(0x7fffffff,1),0x80000000);self.assertFalse(m.C);self.assertTrue(m.V)
        self.assertEqual(m.add(0xffffffff,1),0);self.assertTrue(m.C);self.assertTrue(m.Z)


class R44ChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forward, cls.conditions = native.compile_forward()
        cls.helper = cls.forward[len(native.ENTRY_STUB):]

    def test_full_emitted_chain_and_checksum_matrix(self):
        reached = set()
        with patch.object(proof, 'HOOK', native.IP_FORWARD_HOOK), patch.object(proof, 'STUB', native.ENTRY_STUB):
            for ttl in range(256):
                for ihl in (5, 6, 15):
                    for proto in (1, 6, 17):
                        for arm in (False, True):
                            packet = proof.sample(ttl, ihl, proto)
                            m = proof.Machine(self.helper, packet, arm_output=arm)
                            actual, writes = m.run()
                            want, write = proof.expected(packet, 0, len(packet), len(packet))
                            self.assertEqual(actual, want)
                            self.assertEqual(bool(writes), write)
                            reached.update(m.trace)
        self.assertTrue(set(range(proof.BODY, proof.BODY+140, 2)) <= reached)

    def test_invalid_headers_are_forwarded_unchanged(self):
        for arm in (False, True):
            for kw in ({'alignment':1}, {'alignment':2}, {'alignment':3}, {'total':19}, {'contiguous':19}):
                packet = proof.sample(96,5,17)
                self.assertEqual(proof.Machine(self.helper, packet, arm_output=arm, **kw).run(), (packet, []))
            for version_ihl in (0x65, 0x44):
                packet=bytearray(proof.sample(96,5,17));packet[0]=version_ihl
                self.assertEqual(proof.Machine(self.helper, bytes(packet), arm_output=arm).run(), (bytes(packet), []))

    def test_architecture_and_combined_patch_are_pinned(self):
        self.assertTrue(all(c['passed'] for c in self.conditions))
        self.assertEqual(len(self.forward), 156)
        self.assertEqual(hashlib.sha256(self.forward).hexdigest(), native.FORWARD_SHA256)
        self.assertEqual(native.IP_FORWARD_HOOK, proof.HOOK)
        self.assertEqual(native.ENTRY_STUB, proof.STUB)
        self.assertEqual(native.TARGET['target_triple'], b'thumbv5te-none-eabi')
        self.assertEqual(native.TARGET['target_cpu'], b'arm926ej-s')
        self.assertIn(b'-thumb2', native.TARGET['target_features'])
        with patch.object(native.thumb, 'compile_ir_layout', wraps=native.thumb.compile_ir_layout) as compile:
            native.compile_forward()
            self.assertEqual(compile.call_args.kwargs, native.TARGET)

    def test_changed_source_and_wrong_emission_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.ll';path.write_bytes(native.SOURCE.read_bytes().replace(b'arm926ej-s',b'cortex-a9'))
            with patch.object(native,'SOURCE',path), self.assertRaises(native.TtlR44PayloadError):
                native.compile_forward()
        layout=native.thumb.compile_ir_layout(native.SOURCE.read_bytes(), **native.TARGET)
        layout['raw']=bytes.fromhex('02bf')+layout['raw'][2:]
        with patch.object(native.thumb,'compile_ir_layout',return_value=layout), self.assertRaises(native.TtlR44PayloadError):
            native.compile_forward()

    def test_historical_emission_remains_reproducible(self):
        raw, conditions = historical.compile_forward()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), historical.FORWARD_SHA256)
        self.assertTrue(all(c['passed'] for c in conditions))

    def test_checksum_positive_zero_is_preserved(self):
        packet=bytearray(proof.sample(96,5,17));packet[4:6]=b'\0\0';packet[10:12]=b'\0\0';packet[8]=64
        packet[4:6]=proof.checksum(bytes(packet[:20])).to_bytes(2,'big')
        packet[8]=96;packet[10:12]=proof.checksum(bytes(packet[:20])).to_bytes(2,'big')
        for arm in (False,True):
            actual,_=proof.Machine(self.helper,bytes(packet),arm_output=arm).run()
            self.assertEqual(actual[10:12], b'\0\0')
            self.assertEqual(proof.checksum(actual[:20]),0)


if __name__=='__main__':unittest.main()
