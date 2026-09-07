"""Execute emitted Thumb1 bytes with guarded memory and independent oracles."""
import hashlib,json,struct,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];HERE=ROOT/'firmware/community-0.4.7-dev.2'
sys.path[:0]=[str(HERE),str(ROOT/'tools'),str(ROOT/'tests')]
import native_payload as native
import memory_layout
import machine
import mf885_thumb1_chain_model as base
PARTS=None

def parts():
 global PARTS
 if PARTS is None:
  # Preserve the disassembler profile of unrelated historical test modules.
  with patch.object(native.dis, 'TRIPLE', native.dis.TRIPLE):
   PARTS=native.compile_components()[0]
 return PARTS

def updated(old,target):
 revision=((old>>8)+1)%16777216 or 1
 return revision*256+target

class CallbackTests(unittest.TestCase):
 def make(self,kind,**kw):return machine.CallbackMachine(kind,parts()['ttl_request_post_set_armv5' if kind=='set' else 'ttl_state_pre_get_armv5'],native.data_blob(),**kw)
 def test_all_values_off_and_revision_wrap_commit_one_word(self):
  for old in (0,0x141,0xfffffe40,0xffffffff):
   for target in range(256):
    m=self.make('set',word=old,argument=b'off' if target==0 else str(target).encode());self.assertEqual(m.run(),updated(old,target))
    self.assertEqual([(a,n) for a,n,k in m.writes if k!='stack'],[(machine.RAM,4)])
    self.assertEqual([(a,n) for a,n,k in m.reads if k=='state'],[(machine.RAM,4)])
    self.assertEqual([x[0] for x in m.calls],[machine.FIELD,machine.TEXT,machine.FIELD,machine.TEXT])
 def test_invalid_inputs_and_missing_borrowed_values_do_not_touch_state(self):
  invalid=[b'',b'0',b'00',b'01',b'064',b'256',b'999',b'1000',b'-1',b'+64',b'64.0',b'0x40',b' 64',b'64 ',b'OFF',b'offx',b'of',b'o',b'64\n',b'6a',b'6/',b'6:',b'12a',b'12/',b'12:']
  cases=[{'argument':x} for x in invalid]+[{'command':x} for x in (b'',b't',b'tt',b'TTL',b'ttL',b'ttlx',b'foo',None)]+[{'argument':None}]+[{'missing':x} for x in ('command_text','arg_text','command_value','arg_value')]
  for kw in cases:
   m=self.make('set',word=0x234100,**kw);self.assertEqual(m.run(),0x234100,kw);self.assertFalse(any(k=='state' for _,_,k in m.reads+m.writes))
 def test_phase_context_guards(self):
  for kind,phase in (('set',3),('get',4)):
   for other in range(7):
    if other==phase:continue
    m=self.make(kind,word=0x12341,phase=other);self.assertEqual(m.run(),0x12341);self.assertFalse(m.calls);self.assertFalse(any(k=='state' for _,_,k in m.reads+m.writes))
  for kw in ({'context_present':False},{'context_type':0},{'context_type':2},{'tree_present':False}):
   m=self.make('set',**kw);self.assertEqual(m.run(),0);self.assertFalse(m.calls)
 def test_get_snapshot_all_targets_and_revisions_has_no_global_store(self):
  for revision in (0,1,0x123456,0xffffff):
   for target in range(256):
    word=revision*256+target;m=self.make('get',word=word)
    self.assertEqual(m.run(),word);self.assertEqual(m.published,('r47:%08x:%02x'%(revision,64 if word==0 else target)).encode())
    self.assertTrue(all(k=='stack' for _,_,k in m.writes));self.assertEqual([(a,n) for a,n,k in m.reads if k=='state'],[(machine.RAM,4)])
 def test_get_failure_and_concurrent_mutation_preserve_one_snapshot(self):
  m=self.make('get',word=0x345640,publish_failure=True);self.assertEqual(m.run(),0x345640);self.assertIsNone(m.published);self.assertTrue(all(k=='stack' for _,_,k in m.writes))
  m=self.make('get',word=0x123400);original=m.read
  def read(a,n):
   value=original(a,n)
   if a==machine.RAM:
    _,raw,_,_=m.region(machine.RAM,4);raw[:]=struct.pack('<I',0x987641)
   return value
  m.read=read;self.assertEqual(m.run(),0x987641);self.assertEqual(m.published,b'r47:00001234:00')
 def test_two_writers_can_share_revision_but_never_split_value_and_revision(self):
  a=self.make('set',word=0x1240,argument=b'65');b=self.make('set',word=0x1240,argument=b'off')
  shared=a.region(machine.RAM,4)[1]
  b.regions=[(start,shared if label=='state' else raw,w,label) for start,raw,w,label in b.regions]
  for m in (a,b):
   for _ in range(600):
    m.step()
    if any(label=='state' for _,_,label in m.reads):break
   else:self.fail('state load not reached')
  self.assertEqual(a.run(),0x1341);self.assertEqual(b.run(),0x1300)
  self.assertEqual(int.from_bytes(shared,'little'),0x1300)
 def test_numeric_orr_flags_and_forbidden_instruction(self):
  m=self.make('set');m.r[15]=0x6001422;m.r[2]=0x80000100;m.r[0]=0x41;m.C=True;m.V=True;m.step()
  self.assertEqual(m.r[2],0x80000141);self.assertTrue(m.N and m.C and m.V);self.assertFalse(m.Z)
  for kind in ('set','get'):
   m=self.make(kind);start,raw,_,_=m.region(m.entry,2);raw[:2]=bytes.fromhex('10f0')
   with self.assertRaises(AssertionError):m.run()
 def test_architecture_drift_rejected_before_emission(self):
  with patch.dict(native.TARGET,{'target_cpu':b'cortex-a9'}),patch.object(native.thumb,'_emit_object') as emit:
   with self.assertRaises(native.Error):native.compile_components()
   emit.assert_not_called()

class ReservationTests(unittest.TestCase):
 def test_exact_stock_reservation_adds_only_gap_and_preserves_stacks(self):
  source=ROOT/'input/stock-oslo.bin'
  if not source.is_file(): self.skipTest('exact local stock OSLO not supplied')
  stock=source.read_bytes();candidate,report=memory_layout.reserve(stock)
  self.assertEqual([i for i,(a,b) in enumerate(zip(stock,candidate)) if a!=b],[0x4b5b90])
  self.assertEqual(candidate[0x4b5b90:0x4b5b94],bytes.fromhex('38d20a07'))
  self.assertEqual(report['initial_stacks'],[[0x70ad238,0x70ad620],[0x70ad620,0x70ada08],[0x70ada08,0x70addf0]])
  self.assertEqual(report['new_zero_length']-report['old_zero_length'],4)
  for o in (0x4b5b90,0x8e5914,0x7ed660,0x44e2a8):
   altered=bytearray(stock);altered[o]^=1
   with self.assertRaises(memory_layout.Error):memory_layout.reserve(bytes(altered))

class ForwardMachine(machine.ForwardMachine):
 def __init__(self,helper,packet,*,target,**kw):super().__init__(helper,packet,word=0x100|target,**kw)
STATE=machine.RAM
class ForwardTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.parts=parts()
 def test_boot_default64_and_off_are_distinct(self):
  packet=base.sample(96,5,17)
  for word,want in ((0,64),(0x100,96),(0xffffff00,96),(0x141,65)):
   m=machine.ForwardMachine(parts()['ttl_forward_configurable_armv5'],packet,word=word);actual,writes=m.run();self.assertEqual(actual[8],want);self.assertEqual(base.checksum(actual[:20]),0);self.assertEqual(sum(k=='state' for a,n,k in m.reads),1)
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
     m=machine.ForwardMachine(self.parts['ttl_forward_configurable_armv5'],base.sample(96,5,17),word=0);m.run();reached.update(m.trace)
     self.assertTrue(set(range(base.BODY,base.BODY+138,2))<=reached)
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

if __name__=='__main__':unittest.main(verbosity=2)
