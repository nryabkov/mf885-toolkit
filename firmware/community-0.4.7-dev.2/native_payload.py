"""Private 0.4.7-dev.2 native TTL repair. Offline qualification only."""
import hashlib,json,struct
from pathlib import Path
import mf885_thumb_llvm_build as thumb
import mf885_thumb_disasm as dis
import mf885_ttl_native_payload as stock
import mf885_ttl_native_payload_r45 as fixed
import mf885_ttl_native_payload_r46 as old
import memory_layout
HERE=Path(__file__).resolve().parent
TARGET=dict(target_triple=b'thumbv5te-none-eabi',target_cpu=b'arm926ej-s',target_features=b'+thumb-mode,-thumb2,-neon,-vfp2,+strict-align')
OFFSETS={'ttl_forward_configurable_armv5':0x12a8,'ttl_request_post_set_armv5':0x1340,'ttl_state_pre_get_armv5':0x1520}
class Error(ValueError):pass
def check(ok,why):
 if not ok:raise Error(why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def architecture_inputs():
 check(TARGET==old.TARGET==fixed.TARGET,'target profile drift')
 check(TARGET==dict(target_triple=b'thumbv5te-none-eabi',target_cpu=b'arm926ej-s',target_features=b'+thumb-mode,-thumb2,-neon,-vfp2,+strict-align'),'required target')
 check(fixed.ENTRY_STUB==bytes.fromhex('280031002200ffe7') and fixed.IP_FORWARD_HOOK==bytes.fromhex('014b984702e0a1120006c046'),'hook and entry architecture/ABI')
 pins=json.loads((HERE/'native/source-pins.json').read_bytes());check(set(pins)==set(OFFSETS),'native source set')
 result={}
 for name in OFFSETS:
  raw=(HERE/'native'/(name+'.ll')).read_bytes();check(pins[name]=={'bytes':len(raw),'sha256':sha(raw)},'source pin '+name)
  for s in (b'target triple = "thumbv5te-none-eabi"',b'"target-cpu"="arm926ej-s"',b'"target-features"="+thumb-mode,-thumb2,-neon,-vfp2,+strict-align"'):check(raw.count(s)==1,'source architecture '+name)
  check(b'118149684' in raw and not any(x in raw for x in (b'thumbv7',b'cortex-a9',b'+thumb2',b'100668576')),'state/ISA profile '+name)
  result[name]=raw
 return result

def compile_components():
 sources=architecture_inputs();pins=json.loads((HERE/'native/emitted-pins.json').read_bytes());parts={};reports={};dis.TRIPLE=TARGET['target_triple']
 for name,source in sources.items():
  obj=thumb._emit_object(source,**TARGET);layout=thumb.extract_text_layout(obj);body=bytes(layout['raw'])
  check(obj[:6]==b'\x7fELF\x01\x01' and struct.unpack_from('<H',obj,18)[0]==40 and struct.unpack_from('<I',obj,36)[0]==0x05000000,'object ISA/endianness/EABI/float')
  actual={'bytes':len(body),'sha256':sha(body),'ranges':layout['ranges'],'functions':layout['functions']};check(actual==pins[name],'emitted pin '+name)
  rows=[]
  for r in layout['ranges']:
   check(r['kind'] in ('thumb','data'),'instruction state')
   if r['kind']=='thumb':rows+=dis.disassemble(body[r['offset']:r['offset']+r['bytes']],0x06000000+OFFSETS[name]+r['offset'])
  check(all(x['size']==2 for x in rows),'only Thumb1 short instructions, register BLX for externals')
  parts[name]=body;reports[name]={**actual,'source_sha256':sha(source),'object_sha256':sha(obj),'instructions':rows,'runtime':0x06000000+OFFSETS[name]}
 check(0x12a8+len(parts['ttl_forward_configurable_armv5'])<=0x1340,'forward/SET overlap')
 check(0x1340+len(parts['ttl_request_post_set_armv5'])<=0x14a0,'SET/names overlap')
 check(0x1520+len(parts['ttl_state_pre_get_armv5'])<=0x1600,'GET/stock overlap')
 return parts,reports

def data_blob():
 data=bytearray(old.data_blob());data[:8]=bytes(8);return bytes(data)
def build_payload(oslo):
 architecture_inputs();memory,allocation=memory_layout.reserve(oslo);abi=old.inspect_exact_oslo(oslo);parts,reports=compile_components()
 patches=[('forward_entry_and_body',0x12a0,fixed.ENTRY_STUB+parts['ttl_forward_configurable_armv5']),('post_set',0x1340,parts['ttl_request_post_set_armv5']),('read_only_names',0x14a0,data_blob()),('pre_get',0x1520,parts['ttl_state_pre_get_armv5']),('bss_end_plus_four',memory_layout.END_LITERAL,struct.pack('<I',memory_layout.STATE+4)),('ip_forward_hook',stock.IP_FORWARD_HOOK_OFFSET,fixed.IP_FORWARD_HOOK),('diagnostic_post_set',stock.DUSTER_POST_SET_POINTER,struct.pack('<I',0x06001341)),('diagnostic_pre_get',stock.DUSTER_PRE_GET_POINTER,struct.pack('<I',0x06001521))]
 out=bytearray(oslo);at=0
 for name,o,raw in sorted(patches,key=lambda x:x[1]):
  check(o>=at,'patch overlap');out[o:o+len(raw)]=raw;at=o+len(raw)
 at=0
 for name,o,raw in sorted(patches,key=lambda x:x[1]):check(out[at:o]==oslo[at:o],'unowned bytes changed');at=o+len(raw)
 check(out[at:]==oslo[at:],'unowned tail changed')
 check(out[memory_layout.STACK_SOURCE:memory_layout.STACK_SOURCE+4]==oslo[memory_layout.STACK_SOURCE:memory_layout.STACK_SOURCE+4],'stock stack source changed')
 result=bytes(out)
 return result,{'schema':'mf885-047d2-native-repair/v1','source':{'bytes':len(oslo),'sha256':sha(oslo)},'artifact':{'bytes':len(result),'sha256':sha(result),'flashable':False},'architecture':{k:v.decode() for k,v in TARGET.items()},'components':reports,'memory_reservation':allocation,'stock_abi':abi,'changed_ranges':[{'name':n,'offset':o,'bytes':len(v)} for n,o,v in sorted(patches,key=lambda x:x[1])],'contract':{'state_runtime':memory_layout.STATE,'state_bytes':4,'boot_word':0,'boot_ttl':64,'off_target':0,'numeric_range':[1,255],'set_callback':True,'set_global_stores':1,'get_global_stores':0,'forward_global_stores':0,'state_reads_per_packet':1,'word_layout':'revision24 high bits; target8 low bits; all-zero means boot default64','readback':'r47:00RRRRRR:TT; hex revision24 and target8','revision_freshness':False,'concurrent_write_uniqueness':False,'revision_notes':'Advances for serialized valid SETs, wraps to1; concurrent SETs can share revision. No CAS or multi-client transaction guarantee. GET does not advance revision.','persistence_across_reboot':False,'browser_ttl_requests':0,'live_qualified':False}}
