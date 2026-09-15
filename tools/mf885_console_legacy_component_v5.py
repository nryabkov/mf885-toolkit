#!/usr/bin/env python3
"""Build an UNQUALIFIED offline OSLO component with real Thumb1 hook bytes.

Never a flash image: early-page ownership and real heap/boot behavior remain open.
The accepted TTL component is reconstructed from exact golden, never used as input.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from mf885_console_legacy_build_v5 import build as build_link, STOCK_SHA, REPO
from mf885_ussd_linked_object_v1 import load
from mf885_ussd_native_abi_v1 import branch

PAGE=0x06000200
END=0x06001200
BASE=0x06000000
ACCEPTED_NATIVE='686a5d3138cd6ee930d43d22704463b15c78dbcd3eb993ccd78dc29a45f663b7'

def digest(b):return hashlib.sha256(b).hexdigest()
def thumb_call(site,target):
    if site&1 or not target&1:raise ValueError('Thumb call alignment/state')
    displacement=(target&~1)-(site+4)
    if not -(1<<22)<=displacement<(1<<22) or displacement&1:raise ValueError('Thumb1 BL reach')
    raw=struct.pack('<HH',0xf000|((displacement>>12)&0x7ff),0xf800|((displacement>>1)&0x7ff))
    if branch(raw,site)!={'target':target&~1,'state':'thumb'}:raise ValueError('independent branch decoding')
    return raw

def build(root,stock_path,out,*,allocator_profile="raw-v1", lifecycle=False, service_exit_fix=False, phase_snapshot_fix=False, bounded_queue=False, message_memory=False, service_adapter=False, compact_code=False, lto_code=False, http_read=False, http_send=False, http_control=False, http_session=False, http_consume=False):
    assert not http_consume or http_session
    assert not http_session or http_control
    assert not http_control or http_send
    assert not http_send or http_read
    assert not http_read or lto_code
    assert not lto_code or compact_code
    assert not compact_code or service_adapter
    assert not service_adapter or message_memory
    assert not message_memory or bounded_queue
    assert not bounded_queue or phase_snapshot_fix
    assert not phase_snapshot_fix or service_exit_fix
    assert not service_exit_fix or (lifecycle and allocator_profile == "pool-v5")
    raw=stock_path.read_bytes();assert digest(raw)==STOCK_SHA
    assert not out.exists();out.mkdir(parents=True)
    build_link(root,stock_path,out/'synthetic',allocator_profile=allocator_profile,lifecycle=lifecycle,bounded_queue=bounded_queue,message_memory=message_memory,service_adapter=service_adapter,compact_code=compact_code,lto_code=lto_code,http_read=http_read,http_send=http_send,http_control=http_control,http_session=http_session,http_consume=http_consume)
    script=(REPO/'research/console-native-v7/synthetic.ld').read_text().replace('0x01000000','0x06000200')
    script='/* UNQUALIFIED placement experiment; no hardware write authority. */\n'+script
    extra_flags=[]
    if lto_code:
        from mf885_ussd_lto_v13 import link_flags,linker_script,inspect_backend
        script=linker_script(script).replace('*(.text .text.*) }','*(.text .text.*) . = ALIGN(4); }');extra_flags=link_flags()+(['--undefined=uo_native_http_read'] if http_read else [])+(['--undefined=uo_native_http_submit'] if http_send else [])+(['--undefined=uo_native_http_post'] if http_control else [])
    (out/'page.ld').write_text(script)
    env=os.environ.copy();env['LD_LIBRARY_PATH']=str(root/'usr/lib/x86_64-linux-gnu')
    elf=out/'page.elf'
    subprocess.run([str(root/'usr/bin/ld.lld-18'),'--threads=1',*extra_flags,'--no-undefined','-T',str(out/'page.ld'),
        *[str(out/'synthetic'/(c+'.o')) for c in (['observer','port','native'] + (['lifecycle'] if lifecycle else []) + (['queue'] if bounded_queue else []) + (['message'] if message_memory else []) + (['service'] if service_adapter else []) + (['http','producer'] if http_read else []))],'-o',str(elf)],env=env,check=True)
    if lto_code: (out/'LTO.json').write_text(json.dumps(inspect_backend(elf),indent=2)+'\n')
    audit,symbols,payload=load(elf,base=PAGE,allocator_profile=allocator_profile)
    assert PAGE+len(payload)<=END and raw[PAGE-BASE:END-BASE]==bytes(END-PAGE)
    sys.path.insert(0,str(REPO/'firmware/community-0.4.7-dev.2'))
    import native_payload
    native_payload.architecture_inputs()  # Verify all three accepted TTL helpers before compiling.
    accepted,ttl=native_payload.build_payload(raw)
    assert digest(accepted)==ACCEPTED_NATIVE,'cumulative native baseline mismatch'
    (out/'TTL-BASELINE.json').write_text(json.dumps(ttl,indent=2)+'\n')
    pins=[(0x1d72ee,bytes.fromhex('c360')),(0x1d730c,bytes.fromhex('85f066fa')),(0x1d8276,bytes.fromhex('aaf07ff9'))]
    for o,b in pins:assert accepted[o:o+len(b)]==b
    assert accepted[PAGE-BASE:END-BASE]==raw[PAGE-BASE:END-BASE]
    patches=[('page-payload',PAGE-BASE,payload),('defer-context-publication',0x1d72ee,bytes.fromhex('c046')),
             ('stock-init-call',0x1d730c,thumb_call(0x061d730c,symbols['uo_native_init'])),
             ('event-dispatch-call',0x1d8276,thumb_call(0x061d8276,symbols['uo_native_dispatch']))]
    if http_control:
        off=0x9003fc
        assert raw[off:off+4] == accepted[off:off+4] == bytes(4)
        patches.append(('diagnostic-pre-set-ussd-v16',off,struct.pack('<I',symbols['uo_native_http_post'])))
    if lifecycle:
        from mf885_ussd_lifecycle_patch_v6 import patches as lifecycle_patches
        extra, lifecycle_report = lifecycle_patches(raw,symbols)
        patches.extend(extra)
        # Cover calls through computed aliases at the allocator's actual entry,
        # not only the nine known direct edges. Preserve 8-byte call alignment.
        entry=0x061da17a
        original=bytes.fromhex('a14a1178c81df930491c11707047')
        assert raw[entry-BASE:entry-BASE+14] == original
        assert struct.unpack_from('<I',raw,0x061da400-BASE)[0] == 0x0694aa50
        detour=bytes.fromhex('02b5')+thumb_call(entry+2,symbols['uo_native_allocate_id'])+bytes.fromhex('02bd')+bytes.fromhex('c046')*3
        assert len(detour)==len(original)
        patches.append(('allocator-global-entry-v20',entry-BASE,detour))
        lifecycle_report['global_allocator_entry']={'address':entry,'before':original.hex(),'after':detour.hex(),'counter':0x0694aa50}
        lifecycle_report['schema']='mf885-ussd-lifecycle-patch/v20'
        lifecycle_report.pop('coverage_enabled')
        lifecycle_report['association_enable']='atomic null-slot test at arena publication; otherwise fallback or raw-only'
        lifecycle_report['limits']=['All callers entering the original allocator entry are intercepted; middle-of-function entry is not an ABI.', 'Full system boot, scheduler and hardware behavior remain unqualified.', 'Association disables on foreign context, nested interval, invalid event or ID reuse.']
        (out/'LIFECYCLE.json').write_text(json.dumps(lifecycle_report,indent=2)+'\n')
    if service_exit_fix:
        # Both NULL paths share1518;151a is also the normal shared epilogue.
        # Redirect only1518 to the existing release/return1 exit, leaving151a intact.
        site=0x066e1518;data=bytes.fromhex('22e0')
        assert raw[0x6e1518:0x6e151e]==bytes.fromhex('012007b0f0bd')
        assert accepted[0x6e1518:0x6e151e]==raw[0x6e1518:0x6e151e]
        assert raw[0x6e1560:0x6e156e]==bytes.fromhex('27480021006846f536ec0298d5e7')
        assert branch(data,site)=={'target':0x066e1560,'state':'thumb'}
        patches.append(('service-null-release-v7',site-BASE,data))
    if phase_snapshot_fix:
        from mf885_ussd_phase_snapshot_v8 import patches as phase_patches
        extra, phase_report = phase_patches(raw)
        patches.extend(extra)
        (out/'PHASE.json').write_text(json.dumps(phase_report,indent=2)+'\n')
    if service_adapter:
        from mf885_ussd_service_patch_v11 import patches as service_patches
        extra, service_report = service_patches(raw,symbols)
        patches.extend(extra)
        (out/'SERVICE.json').write_text(json.dumps(service_report,indent=2)+'\n')
    if http_read:
        site=0x900414
        assert raw[site:site+4]==accepted[site:site+4]==bytes(4)
        patches.append(('diagnostic-post-get-ussd-v14',site,struct.pack('<I',symbols['uo_native_http_read'])))
    patched=bytearray(accepted);previous=0;rows=[]
    for name,o,data in sorted(patches,key=lambda p:p[1]):
        assert previous<=o and o+len(data)<=len(patched)
        assert patched[previous:o]==accepted[previous:o]
        patched[o:o+len(data)]=data;previous=o+len(data)
        rows.append({'name':name,'offset':o,'bytes':len(data),'before_sha256':digest(accepted[o:o+len(data)]),'after_sha256':digest(data),
                     **({'encoding':data.hex()} if len(data)<=4 else {})})
    assert patched[previous:]==accepted[previous:] and len(patched)==len(raw)
    # Verify every unowned span after all writes, including the entire accepted TTL area.
    previous=0
    for _,o,data in sorted(patches,key=lambda p:p[1]):assert patched[previous:o]==accepted[previous:o];previous=o+len(data)
    assert patched[previous:]==accepted[previous:]
    assert patched[0x12a0:0x1600]==accepted[0x12a0:0x1600]
    (out/'unqualified-oslo.component.bin').write_bytes(patched)
    (out/'OBJECT.json').write_text(json.dumps(audit,indent=2)+'\n')
    report={'schema':'mf885-ussd-page-component/v3','offline_patch_verified':True,'flashable':False,'candidate_ready':False,
        'http_consume_v18':http_consume,'http_session_v17':http_session,'http_control_v16':http_control,'http_send_v15':http_send,'http_read_v14':http_read,'lto_code_v13':lto_code,'compact_code_v12':compact_code,'service_adapter_v11':service_adapter,'message_memory_v10':message_memory,'bounded_queue_v9':bounded_queue,'queue_entry_wired':service_adapter,'phase_snapshot_fix_v8':phase_snapshot_fix,'service_exit_fix_v7':service_exit_fix,'lifecycle_v6':lifecycle,'allocator_profile':allocator_profile,'stock_sha256':STOCK_SHA,'accepted_native_sha256':ACCEPTED_NATIVE,'component_sha256':digest(patched),
        'elf_sha256':digest(elf.read_bytes()),'page':[PAGE,END],'payload_bytes':len(payload),
        'spare_page_bytes':END-PAGE-len(payload),'patches':rows,
        'thumb_calls':[{'site':site,**branch(patched[site-BASE:site-BASE+4],site)} for site in (0x061d730c,0x061d8276)],
        'ttl_preserved':True,'unowned_spans_preserved':True,'original_header_copy':{'from':0x06000004,'to':0x07949310,'bytes':0x1fc,'end_exclusive':PAGE,'source_function':0x064e0150},
        'limits':['Early page ownership/executable mapping/external boot writes not qualified.','Real allocator and SS boot/task/preemption contracts remain unproved.','Offline component only, no container, version bump, flash or carrier send.'],
        'device_actions':0}
    (out/'COMPONENT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'offline_patch_verified':True,'payload_bytes':len(payload),'spare_page_bytes':report['spare_page_bytes'],'candidate_ready':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--toolchain-root',type=Path,required=True)
    p.add_argument('--stock',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--allocator-profile',choices=['raw-v1','ci-v4','pool-v5'],default='raw-v1');p.add_argument('--lifecycle-v6',action='store_true');p.add_argument('--service-exit-fix-v7',action='store_true');p.add_argument('--phase-snapshot-fix-v8',action='store_true');p.add_argument('--bounded-queue-v9',action='store_true');p.add_argument('--message-memory-v10',action='store_true');p.add_argument('--service-adapter-v11',action='store_true');p.add_argument('--compact-code-v12',action='store_true');p.add_argument('--lto-code-v13',action='store_true');p.add_argument('--http-read-v14',action='store_true');p.add_argument('--http-send-v15',action='store_true');p.add_argument('--http-control-v16',action='store_true');p.add_argument('--http-session-v17',action='store_true');p.add_argument('--http-consume-v18',action='store_true');a=p.parse_args()
    build(a.toolchain_root.resolve(),a.stock.resolve(),a.output_dir.resolve(),allocator_profile=a.allocator_profile,lifecycle=a.lifecycle_v6,service_exit_fix=a.service_exit_fix_v7,phase_snapshot_fix=a.phase_snapshot_fix_v8,bounded_queue=a.bounded_queue_v9,message_memory=a.message_memory_v10,service_adapter=a.service_adapter_v11,compact_code=a.compact_code_v12,lto_code=a.lto_code_v13,http_read=a.http_read_v14,http_send=a.http_send_v15,http_control=a.http_control_v16,http_session=a.http_session_v17,http_consume=a.http_consume_v18)
