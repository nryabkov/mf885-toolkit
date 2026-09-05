"""Execute compiled R43 bytes; checksum oracle does not use payload helpers."""
import hashlib
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import mf885_thumb_disasm as disasm
import mf885_thumb_subset_emulator as emulator
import mf885_ttl_native_payload as stock
import mf885_ttl_native_payload_r43 as probe


def checksum(raw):
    """Independent complete Internet checksum, including IPv4 options."""
    if len(raw)&1:raw+=b'\0'
    value=sum(int.from_bytes(raw[i:i+2],'big') for i in range(0,len(raw),2))
    while value>>16:value=(value&0xffff)+(value>>16)
    return (~value)&0xffff


def header(ttl,protocol=17,ihl=5,ident=0xa55a):
    raw=bytearray(ihl*4);raw[0]=0x40|ihl;raw[1]=0x2e
    struct.pack_into('>HHH',raw,2,ihl*4+113,ident,0x4000)
    raw[8]=ttl;raw[9]=protocol
    raw[12:20]=bytes.fromhex('c0000201c6336402')
    # NOP options give a valid variable-length header without parser side effects.
    raw[20:]=b'\x01'*(len(raw)-20)
    struct.pack_into('>H',raw,10,checksum(bytes(raw)))
    return bytes(raw)


def expected_fixed64(raw):
    value=bytearray(raw)
    if value[8]>=2:
        value[8]=64;value[10:12]=b'\0\0'
        struct.pack_into('>H',value,10,checksum(bytes(value)))
    return bytes(value)


class RecordingMachine(emulator.ThumbMachine):
    def __init__(self,*args,**kwargs):
        self.read_log=[]
        super().__init__(*args,**kwargs)
    def bytes(self,address,length):
        self.read_log.append((address,length))
        return super().bytes(address,length)


class R43MachineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw,cls.conditions=probe.compile_forward()
        cls.program=emulator.ThumbProgram(cls.raw,probe.FORWARD_RUNTIME,probe.FORWARD_CODE_BYTES)

    def run_packet(self,raw,*,address=0x21000000,total=None,contiguous=None):
        pbuf_addr=0x21001000;outnetif=0x22000000;output_addr=0x23000001
        # Map only stock fields at +8/+10; no other pbuf layout is assumed.
        lengths=struct.pack('<HH',len(raw) if total is None else total,len(raw) if contiguous is None else contiguous)
        calls=[];output_header=[]
        def output(machine,args):
            self.assertEqual(args[:3],(outnetif,pbuf_addr,0x0702c14c))
            self.assertEqual(machine.regs['sp']&7,0)
            calls.append(args)
            output_header.append(emulator.ThumbMachine.bytes(machine,address,len(raw)))
            # An output callee may clobber caller-saved registers. Preserve LR.
            for index in (1,2,3,12):machine.regs[f'r{index}']=0xeeee0000+index
            return 0x13579bdf
        preserved={f'r{i}':0xc9000000+i for i in range(4,12)}
        machine=RecordingMachine(self.program,registers={'r0':address,'r1':pbuf_addr,'r2':outnetif,'r3':output_addr,**preserved},blobs=((address,raw),(pbuf_addr+8,lengths)),callbacks={output_addr:output})
        initial_sp=machine.regs['sp']
        # State 0x06001430, callbacks, netif storage and destination storage stay
        # unmapped. Only packet, length fields, emitted literals and stack exist.
        self.assertEqual(machine.run(),0x13579bdf)
        self.assertEqual(len(calls),1);self.assertEqual(len(machine.call_log),1)
        self.assertEqual(machine.regs['sp'],initial_sp)
        for reg,value in preserved.items():self.assertEqual(machine.regs[reg],value,reg)
        def contained(addr,width,start,size):return start<=addr and addr+width<=start+size
        for addr,width in machine.read_log:
            self.assertTrue(any(contained(addr,width,start,size) for start,size in ((address,len(raw)),(pbuf_addr+8,4),(probe.FORWARD_RUNTIME,len(self.raw)),(initial_sp-128,128))),hex(addr))
        packet_writes=[]
        for addr,width,value in machine.write_log:
            if initial_sp-128<=addr and addr+width<=initial_sp:continue
            self.assertEqual((addr,width),(address+8,4),'one atomic IPv4 TTL/protocol/checksum word store')
            packet_writes.append((addr,width,value))
        actual=emulator.ThumbMachine.bytes(machine,address,len(raw))
        self.assertEqual(output_header,[actual], 'rewrite must precede original output call')
        self.assertEqual(emulator.ThumbMachine.bytes(machine,pbuf_addr+8,4),lengths)
        return actual,packet_writes,machine

    def test_exact_machine_pin_disassembly_hook_target_and_no_overlap(self):
        self.assertTrue(self.conditions);self.assertTrue(all(c['passed'] for c in self.conditions))
        self.assertEqual(len(self.raw),probe.FORWARD_BYTES)
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),probe.FORWARD_SHA256)
        records=disasm.disassemble(self.raw[:probe.FORWARD_CODE_BYTES],probe.FORWARD_RUNTIME)
        self.assertEqual(sum(v['size'] for v in records),probe.FORWARD_CODE_BYTES)
        self.assertFalse(any('udf' in v['instruction'] for v in records))
        self.assertEqual(probe.FORWARD_OFFSET,0x12a0)
        self.assertEqual(probe.FORWARD_RUNTIME,probe.OSLO_RUNTIME_BASE+probe.FORWARD_OFFSET)
        self.assertLessEqual(probe.FORWARD_OFFSET+len(self.raw),0x1340)
        self.assertEqual(probe.IP_FORWARD_HOOK_OFFSET,0x8ed1ca)
        self.assertEqual(probe.IP_FORWARD_ORIGINAL.hex(),'c44aa36d3100203220009847')
        self.assertEqual(probe.IP_FORWARD_HOOK[:8].hex(),'280031002200a36d')
        self.assertEqual(stock.thumb_bl_target(probe.IP_FORWARD_HOOK[8:12],probe.OSLO_RUNTIME_BASE+probe.IP_FORWARD_HOOK_OFFSET+8),probe.FORWARD_RUNTIME)
        self.assertEqual(len(probe.IP_FORWARD_HOOK),len(probe.IP_FORWARD_ORIGINAL))

    def test_actual_trampoline_argument_setup_and_exact_branch_target(self):
        # The subset emulator supports BLX but not direct BL. Execute all four
        # actual register/setup instructions, then separately decode the BL.
        # Appended BX LR is a test stop, not part of the installed trampoline.
        setup=emulator.ThumbProgram(probe.IP_FORWARD_HOOK[:8]+bytes.fromhex('7047'),probe.OSLO_RUNTIME_BASE+probe.IP_FORWARD_HOOK_OFFSET,10)
        machine=setup.machine(registers={'r4':0x22000000,'r5':0x21000000,'r6':0x21001000},blobs=((0x22000058,struct.pack('<I',0x23000001)),),callbacks={})
        machine.run()
        self.assertEqual(tuple(machine.regs[f'r{i}'] for i in range(4)),(0x21000000,0x21001000,0x22000000,0x23000001))
        self.assertEqual(machine.write_log,[]);self.assertEqual(machine.call_log,[])
        self.assertEqual(stock.thumb_bl_target(probe.IP_FORWARD_HOOK[8:12],probe.OSLO_RUNTIME_BASE+probe.IP_FORWARD_HOOK_OFFSET+8),probe.FORWARD_RUNTIME)

    def test_options_and_payload_preserved_while_header_checksum_is_valid(self):
        payload=bytes(range(113))
        for ihl in (5,6,15):
            original_header=header(128,17,ihl)
            original=original_header+payload
            actual,writes,_=self.run_packet(original)
            self.assertEqual(actual,expected_fixed64(original_header)+payload)
            self.assertEqual(checksum(actual[:ihl*4]),0)
            self.assertEqual(actual[20:ihl*4],original[20:ihl*4])
            self.assertEqual(actual[ihl*4:],payload)
            self.assertEqual([(a,w) for a,w,_ in writes],[(0x21000008,4)])

    def test_all_ttls_all_ihls_representative_protocols_have_valid_full_checksum(self):
        for ttl in range(256):
            for ihl in range(5,16):
                for protocol in (1,6,17):
                    with self.subTest(ttl=ttl,ihl=ihl,protocol=protocol):
                        original=header(ttl,protocol,ihl)
                        actual,writes,_=self.run_packet(original)
                        self.assertEqual(actual,expected_fixed64(original))
                        self.assertEqual(checksum(actual),0)
                        self.assertEqual(actual[9],protocol)
                        self.assertEqual(actual[:8]+actual[12:],original[:8]+original[12:])
                        self.assertEqual(len(writes),0 if ttl in (0,1,64) else 1)

    def test_bad_version_ihl_lengths_and_alignment_never_modify_packet(self):
        base=header(128)
        bad=[]
        for version_ihl in (0x05,0x35,0x44,0x65,0xff):
            changed=bytearray(base);changed[0]=version_ihl
            bad.append((bytes(changed),0x21000000,None,None))
        for offset in (1,2,3):bad.append((base,0x21000000+offset,None,None))
        for length in range(20):
            bad.extend(((base,0x21000000,length,20),(base,0x21000000,20,length)))
        extended=header(128,17,15)
        bad.extend(((extended,0x21000000,59,60),(extended,0x21000000,60,59)))
        # A first byte is readable at this stock callsite. Short mapped buffers
        # still must not read TTL/checksum beyond the declared contiguous length.
        for length in range(1,20):bad.append((base[:length],0x21000000,length,length))
        for original,address,total,contiguous in bad:
            with self.subTest(size=len(original),address=address,total=total,contiguous=contiguous,first=original[0]):
                actual,writes,_=self.run_packet(original,address=address,total=total,contiguous=contiguous)
                self.assertEqual(actual,original);self.assertEqual(writes,[])

    def test_incremental_checksum_handles_dual_zero_and_carry_edges(self):
        # Pick actual valid headers spanning checksum 0x0000/0xffff neighbors,
        # rather than reusing the implementation's incremental formula oracle.
        seeds={}
        for ident in range(65536):
            original=header(255,17,5,ident)
            value=int.from_bytes(original[10:12],'big')
            if value in (0,1,0x7fff,0xfffe,0xffff):seeds[value]=original
            if len(seeds)==5:break
        self.assertTrue({0,1,0x7fff,0xfffe}.issubset(seeds))
        for original in seeds.values():
            actual,_,_=self.run_packet(original)
            self.assertEqual(actual,expected_fixed64(original));self.assertEqual(checksum(actual),0)

    def test_rewritten_checksum_zero_is_positive_zero_not_ffff(self):
        # Full-checksum oracle selects a valid header whose fixed64 checksum is
        # exactly zero, the RFC1624 dual-zero boundary.
        original=header(255,17,5,ident=0x4e03)
        expected=header(64,17,5,ident=0x4e03)
        self.assertEqual(expected[10:12],b'\0\0')
        actual,writes,_=self.run_packet(original)
        self.assertEqual(actual,expected)
        self.assertEqual(checksum(actual),0)
        self.assertEqual(len(writes),1)

    def test_changed_source_and_invalid_stock_rejected_before_build(self):
        with tempfile.TemporaryDirectory() as d:
            changed=Path(d)/'changed.ll';changed.write_bytes(probe.SOURCE.read_bytes()+b'\n; source drift\n')
            with mock.patch.object(probe,'SOURCE',changed):
                with self.assertRaises((RuntimeError,ValueError)):probe.compile_forward()
        with mock.patch.object(probe,'compile_forward') as compile_forward:
            with self.assertRaises((RuntimeError,ValueError)):probe.build_payload(b'not exact stock OSLO')
            compile_forward.assert_not_called()


OSLO_INPUT=os.environ.get('MF885_R43_TEST_OSLO')
@unittest.skipUnless(OSLO_INPUT,'optional exact stock OSLO via MF885_R43_TEST_OSLO')
class R43ExactStockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oslo=Path(OSLO_INPUT).read_bytes()
        cls.candidate,cls.report=probe.build_payload(cls.oslo)
        cls.raw,_=probe.compile_forward()

    def test_exact_two_patches_full_preservation_and_no_callbacks_or_state(self):
        expected=bytearray(self.oslo)
        expected[probe.FORWARD_OFFSET:probe.FORWARD_OFFSET+len(self.raw)]=self.raw
        o=probe.IP_FORWARD_HOOK_OFFSET
        expected[o:o+len(probe.IP_FORWARD_HOOK)]=probe.IP_FORWARD_HOOK
        self.assertEqual(self.candidate,bytes(expected))
        self.assertEqual(self.report['status'],'GREEN')
        self.assertFalse(self.report['artifact']['flashable'])
        self.assertFalse(self.report['qualification']['full_firmware_container_built'])
        self.assertFalse(self.report['qualification']['live_forward_hook_execution'])
        self.assertFalse(self.report['qualification']['live_packet_ttl_verified'])
        self.assertFalse(self.report['packet_contract']['runtime_off_available'])
        self.assertIsNone(self.report['packet_contract']['direction_filter'])
        self.assertEqual(self.report['packet_contract']['custom_state_accesses'],0)
        self.assertFalse(self.report['packet_contract']['diagnostic_callbacks_installed'])
        self.assertEqual(probe.verify_payload(self.oslo,self.candidate)['status'],'GREEN')
        self.assertEqual({(r['offset'],r['bytes']) for r in probe.CHANGED_RANGES},{(probe.FORWARD_OFFSET,len(self.raw)),(o,len(probe.IP_FORWARD_HOOK))})
        for offset in (0x9003fc,0x900404,0x90040c,0x900414):
            self.assertEqual(self.candidate[offset:offset+4],b'\0'*4)
        self.assertEqual(self.candidate[0x1340:0x1600],self.oslo[0x1340:0x1600])

    def test_candidate_mutation_inside_outside_patch_and_truncation_rejected(self):
        for offset in (0,probe.FORWARD_OFFSET,probe.FORWARD_OFFSET+len(self.raw)-1,probe.FORWARD_OFFSET+len(self.raw),0x1430,0x900404,probe.IP_FORWARD_HOOK_OFFSET,len(self.candidate)-1):
            changed=bytearray(self.candidate);changed[offset]^=1
            with self.subTest(offset=offset):self.assertEqual(probe.verify_payload(self.oslo,bytes(changed))['status'],'REJECTED')
        for changed in (b'',self.candidate[:probe.FORWARD_OFFSET],self.candidate[:-1],self.candidate+b'\0'):
            self.assertEqual(probe.verify_payload(self.oslo,changed)['status'],'REJECTED')

    def test_same_size_stock_drift_is_rejected_without_compilation(self):
        changed=bytearray(self.oslo);changed[-1]^=1
        with mock.patch.object(probe,'compile_forward') as compile_forward:
            with self.assertRaises((RuntimeError,ValueError)):probe.build_payload(bytes(changed))
            compile_forward.assert_not_called()

if __name__=='__main__':unittest.main()
