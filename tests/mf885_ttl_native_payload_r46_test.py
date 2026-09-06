"""Actual ARMv5 instruction tests, independent checksum and request oracles."""
import hashlib,os,struct,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import mf885_ttl_native_payload_r46 as native
import mf885_thumb1_chain_model as base
from mf885_ttl_r46_machine import CallbackMachine,ForwardMachine,STATE,FIELD,TEXT,PUBLISH

class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.parts,cls.reports=native.compile_components();cls.data=native.data_blob()
    def setter(self,argument,**kw):
        m=CallbackMachine('set',self.parts['ttl_request_post_set_armv5'],self.data,argument=argument,**kw);state=m.run();return m,state
    def getter(self,**kw):
        m=CallbackMachine('get',self.parts['ttl_state_pre_get_armv5'],self.data,**kw);state=m.run();return m,state
    def test_all_numeric_values_and_off_use_current_request(self):
        reached=set()
        for text,want in [(str(x).encode(),x) for x in range(1,256)]+[(b'off',0)]:
            m,state=self.setter(text,target=(want+1)%256);self.assertEqual(state[0],want);reached.update(m.trace)
            self.assertEqual([(a,n) for a,n,k in m.writes if k!='stack'],[(STATE,1)])
            self.assertEqual([x[0] for x in m.calls],[FIELD,TEXT,FIELD,TEXT])
            self.assertEqual(state[1:],self.data[1:])
        self.assertIn(0x6001410,reached)
    def test_invalid_input_never_writes_state(self):
        bad=[b'',b'0',b'00',b'01',b'064',b'256',b'999',b'1000',b'-1',b'+64',b'64.0',b'0x40',b' 64',b'64 ',b'OFF',b'offx',b'of',b'o',b'64\n',b'6a',b'6/',b'6:',b'12a',b'12/',b'12:']
        for raw in bad:
            m,state=self.setter(raw);self.assertEqual(state,self.data,raw)
            self.assertEqual([(a,n) for a,n,k in m.writes if k!='stack'],[],raw)
        for cmd in (b'',b't',b'tt',b'TTL',b'ttL',b'ttlx',b'foo'):
            m,state=self.setter(b'65',command=cmd);self.assertEqual(state,self.data)
        for kwargs in ({'command':None},{'argument':None},{'missing':'command_text'},{'missing':'arg_text'},{'missing':'command_value'},{'missing':'arg_value'}):
            arg=kwargs.pop('argument',b'65');m,state=self.setter(arg,**kwargs);self.assertEqual(state,self.data)
    def test_callback_guards_skip_request_and_state(self):
        for phase in (0,1,2,4,5,0xffffffff):
            m,state=self.setter(b'65',phase=phase);self.assertEqual(state,self.data);self.assertFalse(m.calls)
            self.assertFalse(any(k=='context' for _,_,k in m.reads))
        for kwargs in ({'context_present':False},{'context_type':0},{'context_type':2},{'tree_present':False}):
            m,state=self.setter(b'65',**kwargs);self.assertEqual(state,self.data);self.assertFalse(m.calls)
        for phase in (0,1,2,3,5,0xffffffff):
            m,state=self.getter(phase=phase);self.assertEqual(state,self.data);self.assertFalse(m.calls)
    def test_generation_and_sampled_state_readback(self):
        reached=set()
        for value in range(256):
            for generation in (0,1,0xfffffffe,0xffffffff,0x1234abcd):
                m,state=self.getter(target=value,generation=generation);reached.update(m.trace)
                new=(generation+1)&0xffffffff
                self.assertEqual(m.published,('r46:%08x:%02x'%(new,value)).encode())
                self.assertEqual(state[0],value);self.assertEqual(struct.unpack_from('<I',state,4)[0],new)
                self.assertEqual([(a,n) for a,n,k in m.writes if k!='stack'],[(STATE+4,4)])
                self.assertEqual(len(m.calls),1);self.assertEqual(m.calls[0][0],PUBLISH)
        self.assertEqual(reached,set(range(0x6001520,0x6001590,2)))
    def test_failed_publication_does_not_change_ttl(self):
        m,state=self.getter(target=65,generation=8,publish_failure=True)
        self.assertIsNone(m.published);self.assertEqual(state[0],65);self.assertEqual(struct.unpack_from('<I',state,4)[0],9)
    def forward(self,target,ttl,alignment=0,ihl=5,proto=17,arm=False,total=None,contiguous=None):
        packet=base.sample(ttl,ihl,proto);total=len(packet) if total is None else total;contiguous=len(packet) if contiguous is None else contiguous
        m=ForwardMachine(self.parts['ttl_forward_configurable_armv5'],packet,target=target,alignment=alignment,arm_output=arm,total=total,contiguous=contiguous)
        actual,writes=m.run();expected=bytearray(packet)
        changed=target!=0 and ttl>=2 and target!=ttl and min(total,contiguous)>=ihl*4
        if changed:expected[8]=target;expected[10:12]=b'\0\0';expected[10:12]=base.checksum(bytes(expected[:ihl*4])).to_bytes(2,'big')
        self.assertEqual(actual,bytes(expected));self.assertEqual(writes,[(m.packet_address+a,n) for a,n in ((10,1),(11,1),(8,1))] if changed else [])
        self.assertEqual(sum(1 for a,n,k in m.reads if k=='state'),1)
        self.assertEqual(base.checksum(actual[:ihl*4]),0)
        return m
    def test_configured_forwarding_all_targets_and_all_old_ttls(self):
        reached=set()
        for target in range(256):
            for ttl in (0,1,2,32,63,64,65,96,254,255):
                for alignment in range(4):reached.update(self.forward(target,ttl,alignment).trace)
        for target in (0,1,2,32,64,65,96,255):
            for ttl in range(256):reached.update(self.forward(target,ttl,alignment=ttl%4,ihl=(5,6,15)[ttl%3],proto=(1,6,17)[ttl%3],arm=bool(ttl%2)).trace)
        self.assertTrue(set(range(base.BODY,base.BODY+126,2))<=reached)
    def test_length_guards_off_and_packet_single_snapshot(self):
        for target in (0,1,64,255):
            for alignment in range(4):
                for ihl in (5,6,15):
                    for total,contiguous in ((0,60),(60,0),(ihl*4-1,60),(60,ihl*4-1),(ihl*4,ihl*4)):
                        self.forward(target,96,alignment,ihl,total=total,contiguous=contiguous)
        helper=self.parts['ttl_forward_configurable_armv5']
        for value in (0,65):
            m=ForwardMachine(helper,base.sample(96,5,17),target=value)
            original=m.read
            def read(address,width):
                result=original(address,width)
                if address==STATE:
                    _,data,_,_=m.region(STATE,1);data[0]=255
                return result
            m.read=read;packet,_=m.run();self.assertEqual(packet[8],96 if value==0 else value)
    def test_all_version_ihl_bytes_and_minimal_packet_mappings(self):
        helper=self.parts['ttl_forward_configurable_armv5']
        for target in (0,1,64,255):
            for alignment in range(4):
                for first in range(256):
                    packet=bytearray(base.sample(96,15,17));packet[0]=first
                    eligible=first>>4==4 and first&15>=5;ihl=first&15
                    if eligible:
                        packet[10:12]=b'\0\0';packet[10:12]=base.checksum(bytes(packet[:ihl*4])).to_bytes(2,'big')
                    m=ForwardMachine(helper,bytes(packet),target=target,alignment=alignment)
                    actual,writes=m.run();expected=packet.copy()
                    if eligible and target:
                        expected[8]=target;expected[10:12]=b'\0\0';expected[10:12]=base.checksum(bytes(expected[:ihl*4])).to_bytes(2,'big')
                    self.assertEqual(actual,bytes(expected))
                    offsets=[a-m.packet_address for a,n,k in m.reads if k=='packet']
                    self.assertEqual(offsets,[] if target==0 else [0,8,9,10,11] if eligible else [0])
                for first in (0x44,0x65,0x45):
                    packet=bytes([first]);m=ForwardMachine(helper,packet,target=target,alignment=alignment,total=1,contiguous=1)
                    self.assertEqual(m.run(),(packet,[]))
    def test_checksum_zero_carry_edges_and_fragment_headers(self):
        helper=self.parts['ttl_forward_configurable_armv5']
        for target in (1,2,64,65,96,255):
            for ttl in (2,32,63,65,96,255):
                for alignment in range(4):
                    packet=bytearray(base.sample(ttl,5,17));packet[4:6]=b'\0\0';packet[10:12]=b'\0\0';packet[8]=target
                    packet[4:6]=base.checksum(bytes(packet[:20])).to_bytes(2,'big')
                    packet[8]=ttl;packet[10:12]=base.checksum(bytes(packet[:20])).to_bytes(2,'big')
                    actual,_=ForwardMachine(helper,bytes(packet),target=target,alignment=alignment).run()
                    self.assertEqual(actual[10:12],b'\0\0');self.assertEqual(actual[8],target);self.assertEqual(base.checksum(actual[:20]),0)
        for fragment in (0,0x2000,0x0001,0x2010,0x1fff):
            packet=bytearray(base.sample(96,5,17));packet[6:8]=fragment.to_bytes(2,'big');packet[10:12]=b'\0\0';packet[10:12]=base.checksum(bytes(packet[:20])).to_bytes(2,'big')
            actual,_=ForwardMachine(helper,bytes(packet),target=65,alignment=3).run()
            self.assertEqual(actual[6:8],packet[6:8]);self.assertEqual(actual[8],65);self.assertEqual(base.checksum(actual[:20]),0)
    def test_architecture_and_sources_rejected_before_compilation(self):
        with patch.object(native,'TARGET',{**native.TARGET,'target_cpu':b'cortex-a9'}),patch.object(native.thumb,'_emit_object') as emit:
            with self.assertRaises(native.TtlR46PayloadError):native.compile_components()
            emit.assert_not_called()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for p in native.DIRECTORY.glob('*.ll'):(root/p.name).write_bytes(p.read_bytes())
            last=root/'ttl_state_pre_get_armv5.ll';last.write_bytes(last.read_bytes().replace(b'thumbv5te',b'thumbv7'))
            with patch.object(native,'DIRECTORY',root),patch.object(native.thumb,'_emit_object') as emit:
                with self.assertRaises(native.TtlR46PayloadError):native.compile_components()
                emit.assert_not_called()
    def test_thumb2_and_literal_execution_rejected(self):
        bad=bytes.fromhex('10f0')+self.parts['ttl_state_pre_get_armv5'][2:]
        with self.assertRaises(AssertionError):CallbackMachine('get',bad,self.data).run()
        m,_=self.getter();m.r[15]=0x6001590
        with self.assertRaises(AssertionError):m.step()
        bad=bytes.fromhex('10f0')+self.parts['ttl_forward_configurable_armv5'][2:]
        with self.assertRaises(AssertionError):ForwardMachine(bad,base.sample(96,5,17),target=64).run()

if __name__=='__main__':unittest.main()
