"""Execute actual R45 Thumb-1 bytes against independent packet/ABI oracles."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import mf885_thumb1_chain_model as proof
import mf885_ttl_native_payload_r44 as previous
import mf885_ttl_native_payload_r45 as native


class BytePacketMachine(proof.Machine):
    # Independently reviewed machine layout, not imported from the builder.
    BODY_BYTES = 124
    EXECUTABLE_BYTES = 114  # The following two bytes are unreachable alignment padding.
    OUTPUT_RETURN_OFFSET = 112
    PACKET_WRITE_PLAN = ((10, 1), (11, 1), (8, 1))

    def read(self, address, width):
        if self.region(address, width)[3] == 'packet':
            assert width == 1, ('wide packet read', address, width)
        return super().read(address, width)

    def write(self, address, width, value):
        if self.region(address, width)[3] == 'packet':
            assert width == 1, ('wide packet write', address, width)
        return super().write(address, width, value)


class R45ChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forward, cls.conditions = native.compile_forward()
        cls.helper = cls.forward[8:]

    def check_packet(self, packet, *, alignment=0, arm_output=False, total=None, contiguous=None):
        total = len(packet) if total is None else total
        contiguous = len(packet) if contiguous is None else contiguous
        machine = BytePacketMachine(self.helper, packet, alignment=alignment,
                                    arm_output=arm_output, total=total, contiguous=contiguous)
        actual, writes = machine.run()
        # The oracle recomputes the complete checksum, rather than reproducing
        # the helper's incremental formula; R45 has no alignment eligibility gate.
        want, changed = proof.expected(packet, 0, total, contiguous)
        self.assertEqual(actual, want)
        plan = [(machine.packet_address+offset, width) for offset,width in ((10,1),(11,1),(8,1))]
        self.assertEqual(writes, plan if changed else [])
        expected_reads = [0]
        if packet[0]>>4 == 4 and (packet[0]&15) >= 5 and min(total,contiguous) >= (packet[0]&15)*4:
            expected_reads += [8]
            if changed:
                expected_reads += [9,10,11]
        self.assertEqual([(a-machine.packet_address,n) for a,n,name in machine.reads if name=='packet'],
                         [(offset,1) for offset in expected_reads])
        self.assertEqual(actual[9], packet[9])
        if changed:
            self.assertEqual(proof.checksum(actual[:(actual[0]&15)*4]), 0)
        return machine

    def test_all_alignments_full_emitted_chain_checksum_and_abi(self):
        reached = set()
        for alignment in range(4):
            for ttl in range(256):
                for ihl in (5,6,15):
                    for proto in (1,6,17):
                        for arm in (False,True):
                            machine = self.check_packet(proof.sample(ttl,ihl,proto), alignment=alignment, arm_output=arm)
                            reached.update(machine.trace)
        # 18,432 complete chains; every reachable instruction, excluding NOP padding.
        self.assertTrue(set(range(proof.BODY, proof.BODY+114, 2)) <= reached)
        self.assertNotIn(proof.BODY+114, reached)

    def test_r44_alignment_regression_is_fixed(self):
        old = previous.compile_forward()[0][8:]
        packet = proof.sample(96,5,17)
        for alignment in (1,2,3):
            self.assertEqual(proof.Machine(old,packet,alignment=alignment).run(), (packet,[]))
            machine = self.check_packet(packet,alignment=alignment)
            self.assertEqual(machine.packet()[8],64)

    def test_header_length_boundaries_and_all_version_ihl_values(self):
        for alignment in range(4):
            for ihl in (5,6,15):
                packet = proof.sample(96,ihl,17)
                for total in (0,ihl*4-1,ihl*4,len(packet)):
                    for contiguous in (0,ihl*4-1,ihl*4,len(packet)):
                        for arm in (False,True):
                            self.check_packet(packet,alignment=alignment,arm_output=arm,total=total,contiguous=contiguous)
            for first in range(256):
                packet=bytearray(proof.sample(96,15,17));packet[0]=first
                # Valid-version headers need a checksum consistent with their IHL.
                if first>>4==4 and first&15>=5:
                    packet[10:12]=b'\0\0';packet[10:12]=proof.checksum(bytes(packet[:(first&15)*4])).to_bytes(2,'big')
                self.check_packet(bytes(packet),alignment=alignment)

    def test_short_mapping_is_not_read_past_guard(self):
        for alignment in range(4):
            for first in (0x44,0x65,0x45):
                packet=bytes((first,))
                machine=BytePacketMachine(self.helper,packet,alignment=alignment,total=1,contiguous=1)
                self.assertEqual(machine.run(),(packet,[]))
                self.assertEqual([(a-machine.packet_address,n) for a,n,name in machine.reads if name=='packet'],[(0,1)])

    def test_checksum_zero_and_carry_edges(self):
        for ttl in (2,32,63,65,96,255):
            for alignment in range(4):
                packet=bytearray(proof.sample(ttl,5,17));packet[4:6]=b'\0\0';packet[10:12]=b'\0\0';packet[8]=64
                packet[4:6]=proof.checksum(bytes(packet[:20])).to_bytes(2,'big')
                packet[8]=ttl;packet[10:12]=proof.checksum(bytes(packet[:20])).to_bytes(2,'big')
                machine=self.check_packet(bytes(packet),alignment=alignment)
                self.assertEqual(machine.packet()[10:12],b'\0\0')

    def test_wide_packet_access_and_wrong_store_address_rejected(self):
        for before,after in ((bytes.fromhex('027a'),bytes.fromhex('8268')),
                             (bytes.fromhex('8572'),bytes.fromhex('8562')),
                             (bytes.fromhex('8572'),bytes.fromhex('4572'))):
            self.assertEqual(self.helper.count(before),1)
            bad=self.helper.replace(before,after,1)
            with self.assertRaises(AssertionError):
                BytePacketMachine(bad,proof.sample(96,5,17),alignment=2).run()

    def test_hook_literal_padding_and_thumb2_execution_rejected(self):
        bad_hook=bytearray(proof.HOOK);bad_hook[4:6]=bytes.fromhex('00e0')
        with patch.object(proof,'HOOK',bytes(bad_hook)),self.assertRaises(AssertionError):
            BytePacketMachine(self.helper,proof.sample(96,5,17)).run()
        bad_hook=bytearray(proof.HOOK);bad_hook[6]&=0xfe
        with patch.object(proof,'HOOK',bytes(bad_hook)),self.assertRaises(AssertionError):
            BytePacketMachine(self.helper,proof.sample(96,5,17)).run()
        with self.assertRaises(AssertionError):
            BytePacketMachine(bytes.fromhex('10f0')+self.helper[2:],proof.sample(96,5,17)).run()
        machine=BytePacketMachine(self.helper,proof.sample(96,5,17));machine.r[15]=proof.BODY+114
        with self.assertRaises(AssertionError):machine.step()

    def test_architecture_source_layout_and_hook_pins(self):
        self.assertTrue(all(c['passed'] for c in self.conditions))
        self.assertEqual(len(self.forward),132)
        self.assertEqual(self.helper[114:116],bytes.fromhex('c046'))
        self.assertEqual(native.ENTRY_STUB,proof.STUB)
        self.assertEqual(native.IP_FORWARD_HOOK,proof.HOOK)
        self.assertLessEqual(len(self.forward),native.RESERVATION_END-native.FORWARD_OFFSET)
        self.assertEqual(native.TARGET,dict(target_triple=b'thumbv5te-none-eabi',target_cpu=b'arm926ej-s',
                         target_features=b'+thumb-mode,-thumb2,-neon,-vfp2,+strict-align'))
        with patch.object(native.thumb,'compile_ir_layout',wraps=native.thumb.compile_ir_layout) as compiler:
            native.compile_forward();self.assertEqual(compiler.call_args.kwargs,native.TARGET)

    def test_wrong_architecture_fails_before_llvm(self):
        with patch.object(native,'TARGET',{**native.TARGET,'target_cpu':b'cortex-a9'}), \
             patch.object(native.thumb,'compile_ir_layout') as compiler:
            with self.assertRaises(native.TtlR45PayloadError):native.compile_forward()
            compiler.assert_not_called()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.ll';path.write_bytes(native.SOURCE.read_bytes().replace(b'arm926ej-s',b'cortex-a9'))
            with patch.object(native,'SOURCE',path),patch.object(native.thumb,'compile_ir_layout') as compiler:
                with self.assertRaises(native.TtlR45PayloadError):native.compile_forward()
                compiler.assert_not_called()

    def test_changed_machine_bytes_are_rejected(self):
        layout=native.thumb.compile_ir_layout(native.SOURCE.read_bytes(),**native.TARGET)
        layout['raw']=bytes.fromhex('10f0')+layout['raw'][2:]
        with patch.object(native.thumb,'compile_ir_layout',return_value=layout),self.assertRaises(native.TtlR45PayloadError):
            native.compile_forward()


if __name__ == '__main__':unittest.main()
