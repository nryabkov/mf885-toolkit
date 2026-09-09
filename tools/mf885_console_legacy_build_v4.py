#!/usr/bin/env python3
"""Build a private synthetic ARM USSD link probe, never a flashable image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from mf885_ussd_linked_object_v1 import load

REPO=Path(__file__).resolve().parents[1]
STOCK_SHA='d51fb378d8ccf68662174f39d6b8c4f6be5571280790bc3a4dc4a9e8a967078c'
TOOLS={
 'usr/bin/clang-18':'8ef402d453d1ba4902e4ee0f0f847f6cfa01400c95aa43c24e97818b9c0e3f45',
 'usr/bin/ld.lld-18':'7ad9a0e8fe6d0e79b71172d731e33872c0274e49fceb7b516d774876d5a58ade'
}
FLAGS=['--target=thumbv5te-none-eabi','-mcpu=arm926ej-s','-mthumb',
 '-mfloat-abi=soft','-mfpu=none','-mno-unaligned-access',
 '-std=c11','-ffreestanding','-fno-builtin','-fno-stack-protector',
 '-fno-unwind-tables','-fno-asynchronous-unwind-tables',
 '-Os','-Wall','-Wextra','-Werror','-fstack-usage']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(root,stock,out,*,allocator_profile="raw-v1", lifecycle=False, bounded_queue=False, message_memory=False, service_adapter=False, compact_code=False, lto_code=False, http_read=False, http_send=False, http_control=False, http_session=False, http_consume=False):
    assert allocator_profile in ("raw-v1", "ci-v4", "pool-v5")
    assert not lifecycle or allocator_profile == "pool-v5"
    assert not http_consume or http_session
    assert not http_session or http_control
    assert not http_control or http_send
    assert not http_send or http_read
    assert not http_read or lto_code
    assert not lto_code or compact_code
    assert not compact_code or service_adapter
    assert not service_adapter or message_memory
    assert not message_memory or bounded_queue
    assert not bounded_queue or (lifecycle and allocator_profile == "pool-v5")
    assert sha(stock)==STOCK_SHA,'exact stock prerequisite'
    for name,pin in TOOLS.items():assert sha(root/name)==pin,'tool pin '+name
    assert not out.exists(),'immutable output directory must be new'
    env=os.environ.copy();env['LD_LIBRARY_PATH']=str(root/'usr/lib/x86_64-linux-gnu')
    cc=str(root/'usr/bin/clang-18');ld=str(root/'usr/bin/ld.lld-18')
    macros=subprocess.check_output([cc,*FLAGS[:6],'-dM','-E','-x','c','/dev/null'],env=env,text=True)
    for line in ['#define __ARM_ARCH 5','#define __ARM_ARCH_5TEJ__ 1',
                 '#define __thumb__ 1','#define __SOFTFP__ 1','#define __ARM_EABI__ 1',
                 '#define __BYTE_ORDER__ __ORDER_LITTLE_ENDIAN__','#define __SIZEOF_POINTER__ 4']:
        assert line in macros,'target preflight '+line
    assert '#define __thumb2__' not in macros and '#define __ARM_PCS_VFP' not in macros
    out.mkdir(parents=True)
    objects=[]; components=[]
    for name in ['observer','port','native'] + (['lifecycle'] if lifecycle else []) + (['queue'] if bounded_queue else []) + (['message'] if message_memory else []) + (['service'] if service_adapter else []) + (['http','producer'] if http_read else []):
        source=Path('research/console-native-v6')/(name+'.c');obj=out/(name+'.o')
        defines={'raw-v1':[], 'ci-v4':['-DMF885_CI_ALLOCATOR_V4'], 'pool-v5':['-DMF885_POOL_ALLOCATOR_V5']}
        component_flags=FLAGS+(defines[allocator_profile] if name=='native' else [])
        if http_consume: component_flags += ['-DMF885_HTTP_CONSUME_V18']
        if http_session: component_flags += ['-DMF885_HTTP_SESSION_V17']
        if http_control: component_flags += ['-DMF885_HTTP_CONTROL_V16']
        if lifecycle: component_flags += ['-DMF885_LIFECYCLE_V6', '-fno-jump-tables']
        # Preserve the separately pinned native allocator marshal exactly.
        if compact_code and name != 'native': component_flags += ['-Oz']
        if http_read and name in ('message','http'): component_flags += ['-DMF885_HTTP_READ_V14']
        if http_send: component_flags += ['-DMF885_HTTP_SEND_V15']
        bitcode = lto_code and name != 'native'
        if bitcode: component_flags += ['-flto','-fomit-frame-pointer']
        subprocess.run([cc,*component_flags,'-c',str(source),'-o',str(obj)],cwd=REPO,env=env,check=True)
        if bitcode:
            from mf885_ussd_lto_v13 import inspect_bitcode
            attrs=json.dumps(inspect_bitcode(obj),sort_keys=True)
        else:
            attrs=subprocess.check_output(['readelf','-A',str(obj)],text=True)
            assert 'Tag_CPU_arch: v5TE\n' in attrs and 'Tag_THUMB_ISA_use: Thumb-1' in attrs
            assert 'Tag_ABI_VFP_args' not in attrs
        components.append({'flags':component_flags,'source':str(source),'source_sha256':sha(REPO/source),'object_sha256':sha(obj),
                           'attributes':attrs.splitlines(),'stack_usage':[] if bitcode else obj.with_suffix('.su').read_text().splitlines(),'bitcode':bitcode})
        objects.append(str(obj))
    script=REPO/'research/console-native-v6/synthetic.ld'
    extra_flags=[]
    if lto_code:
        from mf885_ussd_lto_v13 import link_flags,linker_script,inspect_backend
        text=linker_script(script.read_text());text=text.replace('*(.text .text.*) }', '*(.text .text.*) . = ALIGN(4); }');script=out/'synthetic.ld';script.write_text(text)
        extra_flags=link_flags()+(['--undefined=uo_native_http_read'] if http_read else [])+(['--undefined=uo_native_http_submit'] if http_send else [])+(['--undefined=uo_native_http_post'] if http_control else [])
    elf=out/'synthetic.elf'
    subprocess.run([ld,'--threads=1',*extra_flags,'--no-undefined','-T',str(script),*objects,'-o',str(elf)],env=env,check=True)
    if lto_code: (out/'LTO.json').write_text(json.dumps(inspect_backend(elf),indent=2)+'\n')
    audit,_,_=load(elf,allocator_profile=allocator_profile)
    (out/'OBJECT.json').write_text(json.dumps(audit,indent=2)+'\n')
    report={'schema':'mf885-ussd-native-link-build/v1','stock_sha256':STOCK_SHA,
       'http_consume_v18':http_consume,'http_session_v17':http_session,'http_control_v16':http_control,'http_send_v15':http_send,'http_read_v14':http_read,'lto_code_v13':lto_code,'compact_code_v12':compact_code,'service_adapter_v11':service_adapter,'message_memory_v10':message_memory,'bounded_queue_v9':bounded_queue,'lifecycle_v6':lifecycle,'allocator_profile':allocator_profile,'tool_sha256':TOOLS,'flags':FLAGS,'linker_script_sha256':sha(script),
       'sources':{str(p.relative_to(REPO)):sha(p) for p in sorted((REPO/'research/console-native-v6').glob('*')) if p.suffix in ('.h','.c','.ld')},
       'components':components,'elf_sha256':sha(elf),'synthetic_base':audit['synthetic_base'],
       'target':'ARMv5TE/Thumb1 LE ARM EABI5 soft-float; ARM926 is a compatibility profile, not a CPUID observation',
       'architecture_evidence':'firmware/community-0.4.7-dev.2/README.md and pinned exact-stock USSD ARM/Thumb ABI audits; no inferred CPU change',
       'link_threads':1,'flash_images':0,'device_actions':0,'runtime_qualified':False}
    (out/'BUILD.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'accepted':True,'text_bytes':audit['text_bytes'],'readonly_bytes':audit['readonly_bytes'],'flash_images':0}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--toolchain-root',type=Path,required=True)
    p.add_argument('--stock',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--allocator-profile',choices=['raw-v1','ci-v4','pool-v5'],default='raw-v1')
    p.add_argument('--lifecycle-v6',action='store_true')
    p.add_argument('--bounded-queue-v9',action='store_true')
    p.add_argument('--message-memory-v10',action='store_true')
    p.add_argument('--service-adapter-v11',action='store_true')
    p.add_argument('--compact-code-v12',action='store_true')
    p.add_argument('--lto-code-v13',action='store_true')
    p.add_argument('--http-read-v14',action='store_true')
    p.add_argument('--http-send-v15',action='store_true');p.add_argument('--http-control-v16',action='store_true');p.add_argument('--http-session-v17',action='store_true');p.add_argument('--http-consume-v18',action='store_true')
    a=p.parse_args();build(a.toolchain_root.resolve(),a.stock.resolve(),a.output_dir.resolve(),allocator_profile=a.allocator_profile,lifecycle=a.lifecycle_v6,bounded_queue=a.bounded_queue_v9,message_memory=a.message_memory_v10,service_adapter=a.service_adapter_v11,compact_code=a.compact_code_v12,lto_code=a.lto_code_v13,http_read=a.http_read_v14,http_send=a.http_send_v15,http_control=a.http_control_v16,http_session=a.http_session_v17,http_consume=a.http_consume_v18)
