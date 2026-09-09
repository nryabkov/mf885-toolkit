#!/usr/bin/env python3
"""Inspect a synthetic linked USSD probe; no firmware placement qualification."""
import hashlib
import re
import struct
import subprocess
from pathlib import Path
import mf885_thumb_disasm as dis
from mf885_ussd_native_abi_v1 import branch, require

BASE = 0x01000000  # Synthetic address, not a proposed MF885 code cave.


def load(path, *, base=BASE, allocator_profile="raw-v1"):
    require(allocator_profile in ("raw-v1", "ci-v4", "pool-v5"), "unknown allocator profile")
    require(base in (0x01000000, 0x06000200), "unsupported offline probe base")
    raw = path.read_bytes()
    require(len(raw) >= 52 and raw[:7] == b'\x7fELF\x01\x01\x01', 'ELF32 LE')
    require(struct.unpack_from('<HH', raw, 16) == (2, 40), 'ARM executable ELF')
    require(struct.unpack_from('<I', raw, 36)[0] in (0x5000000, 0x5000200), 'EABI5 soft-float flags')
    off = struct.unpack_from('<I', raw, 32)[0]
    size, count, names = struct.unpack_from('<HHH', raw, 46)
    require(size == 40 and count > 0 and names < count and off+size*count <= len(raw), 'section bounds')
    sh = [struct.unpack_from('<10I',raw,off+i*size) for i in range(count)]
    def contents(s):
        require(s[4]+s[5] <= len(raw), 'section content bounds')
        return raw[s[4]:s[4]+s[5]]
    def cstr(blob, p):
        end=blob.find(b'\0',p)
        require(0 <= p < len(blob) and end >= p, 'string bounds')
        return blob[p:end].decode('ascii')
    names_blob = contents(sh[names])
    sections={cstr(names_blob,s[0]):(i,s,contents(s)) for i,s in enumerate(sh)}
    require(not any(s[1] in (4,9) and s[5] for s in sh), 'unresolved relocations')
    require(not any(s[2]&1 and s[5] for s in sh), 'writable section')
    require({name for name,(_,s,_) in sections.items() if s[2]&2 and s[5]} == {'.text','.rodata'}, 'unexpected allocated section')
    ti,ts,text = sections['.text']; _,rs,rodata=sections['.rodata']
    require(ts[3] == base and ts[2] == 6 and rs[2] in (2, 0x32) and rs[3] == base+len(text), 'synthetic section layout')
    mappings=[]; symbols={}; funcs=[]
    for s in sh:
        if s[1] != 2: continue
        require(s[9] == 16 and s[5]%16 == 0 and s[6]<len(sh), 'symbol table')
        strings=contents(sh[s[6]])
        for p in range(0,s[5],16):
            name,value,n,info,_,idx=struct.unpack_from('<IIIBBH',contents(s),p)
            name=cstr(strings,name)
            require(not (idx == 0 and name), 'undefined symbol '+name)
            if name and info&15 in (1,2):
                require(name not in symbols, 'duplicate object/function')
                symbols[name]=value
            if idx != ti: continue
            if re.fullmatch(r'\$[tda](?:\.[0-9]+)?',name): mappings.append((value,name[1]))
            if info&15 == 2:
                require(value&1 and n and base <= (value&~1) < base+len(text), 'Thumb function entry')
                funcs.append({'name':name,'address':value,'bytes':n})
    mappings.sort(); require(mappings and mappings[0] == (base,'t'), 'mapping start')
    rows=[]; decoded=[]; previous=dis.TRIPLE
    try:
        dis.TRIPLE=b'thumbv5te-none-eabi'
        for i,(start,kind) in enumerate(mappings):
            end=mappings[i+1][0] if i+1<len(mappings) else base+len(text)
            require(base <= start < end <= base+len(text) and kind in ('t','d'), 'mapping bounds/state')
            blob=text[start-base:end-base]
            rows.append({'address':start,'bytes':len(blob),'kind':kind,'sha256':hashlib.sha256(blob).hexdigest()})
            if kind=='t': decoded.extend(dis.disassemble(blob,start))
    finally: dis.TRIPLE=previous
    entries={r['address'] for r in decoded}; direct=[]; indirect=[]
    for row in decoded:
        a=row['address']; b=bytes.fromhex(row['bytes']); h=int.from_bytes(b[:2],'little')
        if len(b)==4 or h&0xf800==0xe000 or h&0xf000==0xd000:
            require(h&0xff00 not in (0xde00,0xdf00),'trap instruction')
            edge=branch(b,a)
            require(edge['state']=='thumb' and edge['target'] in entries,'branch boundary/state')
            direct.append({'address':a,**edge})
        elif h&0xf800==0x4800:
            target=((a+4)&~3)+4*(h&255)
            require(any(r['kind']=='d' and r['address']<=target and target+4<=r['address']+r['bytes'] for r in rows),'literal boundary')
        elif h&0xff00==0x4700:
            require(h==0x4770 or h&0x87==0x80,'unexpected indirect branch')
            if h!=0x4770: indirect.append({'address':a,'instruction':row['instruction']})
        require(not re.search(r'\b(?:it|itt|ite|cbz|cbnz|movw|movt|bxj|ldrex|strex|v\w+)\b',row['instruction']),'unsupported ISA')
    require(all((f['address']&~1) in entries for f in funcs),'function boundary')
    expected_rodata=struct.pack('<4I',symbols['allocate'],symbols['stock_init'],0x06426160,0x06426178)
    require(rodata[:16]==expected_rodata,'bound ops/state bits')
    strings=[]
    if 'uo_native_http_read' in symbols: strings += [b'ussd_v1',b'0123456789abcdef']
    if 'uo_native_http_submit' in symbols: strings += [b'*100#']
    tail=rodata[16:]
    require((not tail and not strings) or
            (tail.endswith(b'\0') and sorted(tail[:-1].split(b'\0'))==sorted(strings)),
            'exact read-only strings')
    bindings={'raw-v1':[0x0641b0e8], 'ci-v4':[0x06367290],
              'pool-v5':[0x4559,0x06c08680,0x0694a1a2,0x06426160]}
    selected=bindings[allocator_profile]
    others={v[0] for k,v in bindings.items() if k!=allocator_profile}
    for other in others:
        require(not any(r['kind']=='d' and struct.pack('<I',other) in text[r['address']-base:r['address']-base+r['bytes']] for r in rows), 'mixed allocator binding')
    for target in (*selected,0x0625c7dd,0x0694aa5c,0x06e9db18):
        require(any(r['kind']=='d' and struct.pack('<I',target) in text[r['address']-base:r['address']-base+r['bytes']] for r in rows),'missing stock binding '+hex(target))
    if allocator_profile == 'pool-v5':
        # Pinned Clang derives leave = enter +24 instead of a second literal.
        start=symbols['allocate']&~1;offset=start-base
        h=int.from_bytes(text[offset+8:offset+10],'little')
        require(h&0xff00==0x4d00,'allocator enter literal register')
        literal=((start+12)&~3)+4*(h&255)
        require(struct.unpack_from('<I',text,literal-base)[0]==0x06426160,'allocator enter address')
        require(text[offset+18:offset+24]==bytes.fromhex('18352000a847'),'derived leave enter+24, original mask argument')
    attrs=subprocess.check_output(['readelf','-A',str(path)],text=True)
    for item in ('Tag_CPU_arch: v5TE\n','Tag_THUMB_ISA_use: Thumb-1','Tag_CPU_unaligned_access: None'):
        require(item in attrs,'architecture '+item)
    require('Tag_ABI_VFP_args' not in attrs,'VFP ABI')
    require(struct.unpack_from('<I',raw,24)[0] == symbols['uo_native_init'],'entry point')
    report={'schema':'mf885-ussd-linked-probe/v1','accepted':True,'elf_sha256':hashlib.sha256(raw).hexdigest(),
        'allocator_profile':allocator_profile,'synthetic_base':base,'runtime_qualified':False,'flash_candidate':False,
        'text_bytes':len(text),'readonly_bytes':len(rodata),'payload_sha256':hashlib.sha256(text+rodata).hexdigest(),
        'instructions':len(decoded),'functions':funcs,'ranges':rows,'direct_edges':direct,'indirect_calls':indirect,
        'undefined_symbols':0,'relocations':0,'writable_sections':0,'attributes':attrs.splitlines(),
        'limits':['Synthetic link address is not an available code/RAM location.',
                  'Indirect call execution checked separately; not full hook coverage or hardware qualification.']}
    return report,symbols,text+rodata
