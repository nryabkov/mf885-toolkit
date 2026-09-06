#!/usr/bin/env python3
"""Offline ARMv5/Thumb1 TTL control component. Never a flashable image.

Read current request fields, update one RAM byte, and publish sampled state
with a generation counter. Historical firmware sources and pins are untouched.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path
import mf885_thumb_llvm_build as thumb
import mf885_ttl_native_payload as stock
import mf885_ttl_native_payload_r45 as r45
import mf885_ttl_phase3_context_abi as context_abi

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'firmware/community-r4.6/native'
TARGET = dict(target_triple=b'thumbv5te-none-eabi', target_cpu=b'arm926ej-s',
              target_features=b'+thumb-mode,-thumb2,-neon,-vfp2,+strict-align')
STATE_OFFSET, STATE_BYTES = 0x14A0, 0x60
STATE_RUNTIME = stock.OSLO_RUNTIME_BASE + STATE_OFFSET
ENTRY_STUB = r45.ENTRY_STUB
HOOK = r45.IP_FORWARD_HOOK
# (source bytes, source SHA, output bytes, mapped code bytes, output SHA, address)
SPECS = {
 'ttl_forward_configurable_armv5': (3474,'e947204e19eebd763e703d172333531f883f1dcc74b64dce8a1166565de1a0b7',140,128,'390cd21b3879f37319b1c3c30b4c0de357ccb6890520ceb1028e4d01fd77216d',0x12A8),
 'ttl_request_post_set_armv5': (5872,'21feae55b3048b62f1f0f8f63b425e0aa633c879ef8b8740f01ff9cffa6c34ea',224,212,'e244ab69be661b9e448a5e3d8425043f18ef9904e1957b095642e21dd3e9a834',0x1340),
 'ttl_state_pre_get_armv5': (2356,'6cc1fb8cfe02438562826e00f1d01432ed0594ce4c8bd2f183327030a61b6088',128,112,'48f5d1f7114d8d5a64396e94314ad9b6962e1c3aff05dee5e3e0f641964fd6f4',0x1520),
}
class TtlR46PayloadError(RuntimeError): pass

def sha256(raw): return hashlib.sha256(raw).hexdigest()
def check(ok, why):
    if not ok: raise TtlR46PayloadError(why)

def data_blob():
    data=bytearray(STATE_BYTES);data[0]=64
    data[8:16]=b'command\0';data[16:20]=b'arg\0';data[20:27]=b'output\0'
    data[28:45]=b'0123456789abcdef\0'
    return bytes(data)

def source_inputs():
    expected=dict(target_triple=b'thumbv5te-none-eabi',target_cpu=b'arm926ej-s',
                  target_features=b'+thumb-mode,-thumb2,-neon,-vfp2,+strict-align')
    check(TARGET==expected,'R46 architecture profile changed before compilation')
    sources={}
    # Check every new native unit before compiling the first unit.
    for name,(size,pin,*_) in SPECS.items():
        raw=(DIRECTORY/(name+'.ll')).read_bytes()
        check(len(raw)==size and sha256(raw)==pin,'R46 source pin: '+name)
        for marker in (b'target triple = "thumbv5te-none-eabi"',b'"target-cpu"="arm926ej-s"',
                       b'"target-features"="+thumb-mode,-thumb2,-neon,-vfp2,+strict-align"'):
            check(raw.count(marker)==1,'R46 source architecture: '+name)
        check(not any(v in raw for v in (b'thumbv7',b'cortex-a9',b'+thumb2')),'R46 incompatible target')
        sources[name]=raw
    return sources

def compile_components():
    sources=source_inputs();components={};reports={}
    for name,raw in sources.items():
        spec=SPECS[name];obj=thumb._emit_object(raw,**TARGET)
        layout=thumb.extract_text_layout(obj);body=bytes(layout['raw'])
        check(obj[:6]==b'\x7fELF\x01\x01' and struct.unpack_from('<H',obj,18)[0]==40,'R46 object machine')
        check(struct.unpack_from('<I',obj,36)[0]==0x05000000,'R46 object EABI/float flags')
        check(len(body)==spec[2] and sha256(body)==spec[4],'R46 emitted code pin: '+name)
        ranges=[{'kind':'thumb','offset':0,'bytes':spec[3]},
                {'kind':'data','offset':spec[3],'bytes':spec[2]-spec[3]}]
        check(layout['ranges']==ranges,'R46 code/data boundaries: '+name)
        check(layout['functions']==[{'name':name,'offset':0,'thumb':True,'bytes':spec[2]}],'R46 function symbol: '+name)
        components[name]=body
        reports[name]={'source_sha256':sha256(raw),'bytes':len(body),'sha256':sha256(body),
                       'object_sha256':sha256(obj),'mapping_ranges':ranges,'runtime':hex(stock.OSLO_RUNTIME_BASE+spec[5])}
    check(len(ENTRY_STUB)+len(components['ttl_forward_configurable_armv5'])<=0x1340-0x12A0,'R46 forward reservation')
    check(0x1340+len(components['ttl_request_post_set_armv5'])<=STATE_OFFSET,'R46 SET reservation')
    check(STATE_OFFSET+STATE_BYTES<=0x1500,'R46 data reservation')
    check(0x1520+len(components['ttl_state_pre_get_armv5'])<=0x1600,'R46 GET reservation')
    return components,reports

def inspect_exact_oslo(oslo):
    check(len(oslo)==stock.OSLO_BYTES and sha256(oslo)==stock.OSLO_SHA256,'R46 exact stock OSLO required')
    check(oslo[0x12A0:0x1500]==bytes(0x260) and oslo[0x1520:0x1600]==bytes(0xE0),'R46 original zero reservations')
    check(oslo[stock.IP_FORWARD_HOOK_OFFSET:stock.IP_FORWARD_HOOK_OFFSET+12]==stock.IP_FORWARD_ORIGINAL,'R46 original forwarding hook')
    for ptr in (stock.DUSTER_PRE_SET_POINTER,stock.DUSTER_POST_SET_POINTER,stock.DUSTER_PRE_GET_POINTER,stock.DUSTER_POST_GET_POINTER):
        check(struct.unpack_from('<I',oslo,ptr)[0]==0,'R46 original diagnostic callback slot')
    abi=context_abi.inspect_exact_oslo(oslo)
    check(abi['status']=='GREEN' and all(c['passed'] for c in abi['conditions']),'R46 current request/stock callback ABI')
    return abi

def build_payload(oslo):
    abi=inspect_exact_oslo(oslo);parts,compiled=compile_components()
    patches=[('forward',0x12A0,ENTRY_STUB+parts['ttl_forward_configurable_armv5']),
             ('post_set',0x1340,parts['ttl_request_post_set_armv5']),
             ('ram_state_and_names',STATE_OFFSET,data_blob()),
             ('pre_get',0x1520,parts['ttl_state_pre_get_armv5']),
             ('ip_forward_hook',stock.IP_FORWARD_HOOK_OFFSET,HOOK),
             ('diagnostic_post_set',stock.DUSTER_POST_SET_POINTER,struct.pack('<I',0x06001341)),
             ('diagnostic_pre_get',stock.DUSTER_PRE_GET_POINTER,struct.pack('<I',0x06001521))]
    patches.sort(key=lambda x:x[1]);candidate=bytearray(oslo);cursor=0
    for name,offset,raw in patches:
        check(offset>=cursor and offset+len(raw)<=len(oslo),'R46 overlapping/outside patch')
        candidate[offset:offset+len(raw)]=raw;cursor=offset+len(raw)
    result=bytes(candidate);cursor=0
    for _,offset,raw in patches:
        check(result[cursor:offset]==oslo[cursor:offset],'R46 untouched span changed')
        cursor=offset+len(raw)
    check(result[cursor:]==oslo[cursor:],'R46 untouched tail changed')
    report={'schema':'mf885-r46-ttl-control-native-component/v1','status':'GREEN',
            'source':{'bytes':len(oslo),'sha256':sha256(oslo)},
            'architecture':{k:v.decode() for k,v in TARGET.items()},'components':compiled,
            'stock_abi':abi,'changed_ranges':[{'name':n,'offset':o,'bytes':len(b)} for n,o,b in patches],
            'artifact':{'kind':'decompressed_oslo_component','flashable':False,'bytes':len(result),'sha256':sha256(result)},
            'contract':{'state_runtime':hex(STATE_RUNTIME),'initial_value':64,'off_value':0,'numeric_range':[1,255],
                        'set_source':'current request tree, exact ttl and canonical off|1..255',
                        'readback':'r46:GGGGGGGG:TT; hex32 generation and hex8 TTL; freshness must advance',
                        'storage':'one RAM byte plus aligned generation32; no persistence added',
                        'output_api':'diagnostic.output via phase4 pre_get and synchronous stock setter',
                        'callback_errors_do_not_set_http_status':True,'packet_access':'byte-only IPv4 header; inherited eligibility and output ABI',
                        'off_behavior':'no packet writes; original output callback once',
                        'state_snapshot_per_packet':1,'generation_counter_serialization':'not independently qualified; client rejects stale/nonadvancing generation'},
            'qualification':{'live_callbacks':False,'live_dynamic_ttl':False,'state_memory_writability':False,
                             'cold_boot':False,'persistence':False,'full_firmware_container_built':False},
            'live_actions':{'http':0,'firmware_posts':0,'usb':0,'network_changes':0,'service_changes':0}}
    return result,report

def verify_payload(oslo,candidate):
    expected,report=build_payload(oslo)
    return {'schema':'mf885-r46-ttl-control-native-verification/v1','status':'GREEN' if candidate==expected else 'REJECTED',
            'candidate_matches':candidate==expected,'build':report}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('oslo',type=Path);p.add_argument('--output',type=Path);p.add_argument('--report',type=Path)
    a=p.parse_args(argv)
    try:
        candidate,report=build_payload(a.oslo.read_bytes())
        if a.output:
            with a.output.open('xb') as f:f.write(candidate)
        if a.report:
            with a.report.open('x') as f:json.dump(report,f,indent=2,sort_keys=True);f.write('\n')
        print(json.dumps({'status':report['status'],'artifact':report['artifact']}));return 0
    except (OSError,ValueError,TtlR46PayloadError,thumb.NativeBuildError,context_abi.Phase3ContextAbiError) as e:
        print(json.dumps({'status':'REJECTED','reason':str(e)}));return 2
if __name__=='__main__':raise SystemExit(main())
