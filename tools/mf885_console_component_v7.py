#!/usr/bin/env python3
"""Build the private console v7 component: v6 console plus native CPU sampling.

Strict mixed ARM/Thumb inspection, pinned stock hash, an explicit patch
allowlist and an 8192-byte code window. This is an offline unqualified
component; native compilation and emitted-stub verification remain
reviewer-owned. No container, device, network, service or credential action.
"""
import argparse, hashlib, json, os, re, struct, subprocess
from pathlib import Path
from mf885_console_legacy_component_v5 import build as legacy_build, thumb_call
from mf885_console_legacy_build_v5 import TOOLS, FLAGS, STOCK_SHA, REPO
from mf885_ussd_linked_object_v1 import load
from mf885_ussd_native_abi_v1 import branch
import mf885_thumb_disasm as dis
BASE = 0x06000000
START = 0x06918ff0
END = 0x0691aff0
V6_SOURCE = REPO / 'research/console-native-v6'
V7_SOURCE = REPO / 'research/console-native-v7'
# Exact full instruction pins from the hash-checked stock image.
HOOKS = {
    'cpu-idle-begin': (0x067e1b9c, 'a0221fe5'),
    'cpu-idle-end': (0x067e1bc4, '01f02fe1'),
    'cpu-irq-exit': (0x067e2054, '058ce2fb'),
}
# The three patches are the ONLY additional vector/code patches v7 may make.
EXTRA_PATCH_ALLOWLIST = ('cpu-idle-begin', 'cpu-idle-end', 'cpu-irq-exit')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def derive_report():
    """Every v7 file must be a byte copy of its v6 namesake except the declared
    derivations. Fails closed if a v6 behavior file silently drifted."""
    derived = {'port.h', 'port.c', 'console.c', 'README.md'}
    v7_only = {'cpu.h', 'cpu.c', 'cpu_hooks.S', 'cpu_native_test.c'}
    rows = {}
    for path in sorted(V7_SOURCE.iterdir()):
        if path.suffix not in ('.c', '.h', '.S', '.ld', '.mjs', '.md'):
            continue
        v6 = V6_SOURCE / path.name
        same = v6.is_file() and sha(v6.read_bytes()) == sha(path.read_bytes())
        rows[path.name] = {'v6_sha256': sha(v6.read_bytes()) if v6.is_file() else None,
                           'v7_sha256': sha(path.read_bytes()), 'unchanged': same}
        if path.name in v7_only:
            assert not v6.is_file(), 'v7-only file shadows a v6 name: ' + path.name
            continue
        if not same and path.name not in derived:
            raise AssertionError('undeclared v7 source drift: ' + path.name)
    for name in derived:
        assert name in rows and not rows[name]['unchanged'], 'declared derivation not changed: ' + name
    for name in v7_only:
        assert name in rows and rows[name]['v6_sha256'] is None, 'v7-only file missing: ' + name
    return rows


def inspect(elf):
    raw = elf.read_bytes()
    assert raw[:7] == b'\x7fELF\x01\x01\x01'
    assert struct.unpack_from('<HH', raw, 16) == (2, 40)
    assert struct.unpack_from('<I', raw, 36)[0] in (0x5000000, 0x5000200)
    off = struct.unpack_from('<I', raw, 32)[0]
    size, count, names = struct.unpack_from('<HHH', raw, 46)
    assert size == 40 and off + size * count <= len(raw)
    sh = [struct.unpack_from('<10I', raw, off + i * size) for i in range(count)]

    def data(s):
        assert s[4] + s[5] <= len(raw)
        return raw[s[4]:s[4] + s[5]]

    def string(blob, n):
        return blob[n:blob.index(b'\0', n)].decode('ascii')

    sn = data(sh[names])
    sects = {string(sn, s[0]): s for s in sh}
    assert not any(s[1] in (4, 9) and s[5] for s in sh), 'unresolved relocation'
    assert not any(s[2] & 1 and s[5] for s in sh), 'writable allocated section'
    assert {n for n, s in sects.items() if s[2] & 2 and s[5]} == {'.text', '.rodata'}, 'unexpected allocated section'
    ts, rs = sects['.text'], sects['.rodata']
    assert ts[3] == START and rs[3] == START + ts[5], 'code window'
    payload = data(ts) + data(rs)
    assert START + len(payload) <= END, 'code window 8192 exceeded'
    # Mixed ARM($a)/Thumb($t) mapping symbols partition the text exactly.
    mapping = []
    symbols = {}
    for s in sh:
        if s[1] != 2:
            continue
        strs = data(sh[s[6]])
        for at in range(0, s[5], 16):
            n, v, z, info, _, idx = struct.unpack_from('<IIIBBH', data(s), at)
            name = string(strs, n)
            assert not (idx == 0 and name), name
            if name and info & 15 == 2:
                entry = v - 1 if v & 1 else v
                assert z and START <= entry < START + ts[5], 'function entry'
                symbols[name] = v
            if 0 < idx < len(sh) and sh[idx] == ts and re.fullmatch(r'\$[tda](?:\.[0-9]+)?', name):
                mapping.append((v, name[1]))
    mapping.sort()
    assert mapping and all(START <= a < START + ts[5] for a, _ in mapping), 'mapping bounds'
    # Both instruction states must be present and every range decoded with the
    # matching triple; no range may be silently skipped.
    kinds = {k for _, k in mapping}
    assert kinds == {'a', 't', 'd'}, 'v7 requires mixed ARM/Thumb mapping'
    decoded = []
    ranges = []
    for i, (a, k) in enumerate(mapping):
        e = mapping[i + 1][0] if i + 1 < len(mapping) else START + ts[5]
        assert a < e <= START + ts[5] and k in ('t', 'a', 'd')
        ranges.append({'address': a, 'end': e, 'kind': k})
        if k == 'd':
            continue
        old = dis.TRIPLE
        try:
            dis.TRIPLE = b'thumbv5te-none-eabi' if k == 't' else b'armv5te-none-eabi'
            decoded.extend(dict(row,state=k) for row in dis.disassemble(payload[a - START:e - START], a))
        finally:
            dis.TRIPLE = old
    entries = {x['address'] for x in decoded}
    for row in decoded:
        b = bytes.fromhex(row['bytes'])
        h = int.from_bytes(b[:2], 'little')
        a = row['address']
        text = row['instruction']
        assert not re.search(r'\b(?:it|itt|ite|cbz|cbnz|movw|movt|bxj|ldrex|strex|v\w+)\b', text), 'ISA ' + text
        if row['state']=='a':
            assert len(b)==4
            word=int.from_bytes(b,'little')
            if word&0x0e000000==0x0a000000:
                off=(word&0xffffff)<<2
                if word>>28==15:off|=((word>>24)&1)<<1
                if off&(1<<25):off-=1<<26
                target=a+8+off
                state='t' if word>>28==15 else 'a'
                assert target in entries and any(r['address']<=target<r['end'] and r['kind']==state for r in ranges), 'ARM branch boundary '+hex(a)
        else:
            if len(b)==4 or h&0xf800==0xe000 or h&0xf000==0xd000:
                assert h&0xff00 not in (0xde00,0xdf00)
                edge=branch(b,a)
                state='t' if edge['state']=='thumb' else 'a'
                assert edge['target'] in entries and any(r['address']<=edge['target']<r['end'] and r['kind']==state for r in ranges), 'Thumb branch boundary '+hex(a)
            elif h&0xf800==0x4800:
                target=((a+4)&~3)+4*(h&255)
                assert any(r['kind']=='d' and r['address']<=target and target+4<=r['end'] for r in ranges), 'literal boundary'
    # A Thumb function symbol has bit0 set; an ARM function symbol has it clear.
    for name, v in symbols.items():
        assert (v - 1 if v & 1 else v) in entries, 'undefined symbol ' + name
    attrs = subprocess.check_output(['readelf', '-A', str(elf)], text=True)
    assert 'Tag_CPU_arch: v5TE\n' in attrs and 'Tag_THUMB_ISA_use: Thumb-1' in attrs and 'Tag_ABI_VFP_args' not in attrs
    return payload, symbols, {'attributes': attrs, 'decoded': decoded, 'ranges': ranges,
                              'bytes': len(payload), 'elf_sha256': sha(raw)}


def arm_call(site, target):
    assert not target & 3
    delta = target - ((site + 4) & ~3)
    assert -(1 << 22) <= delta < (1 << 22) and not delta & 3
    value = struct.pack('<HH', 0xf000 | ((delta >> 12) & 0x7ff), 0xe800 | ((delta >> 1) & 0x7ff))
    assert branch(value, site) == {'target': target, 'state': 'arm'}
    return value


def arm_branch(site,target,*,link=False):
    assert site%4==target%4==0
    delta=target-(site+8)
    assert -(1<<25)<=delta<(1<<25)
    word=(0xeb000000 if link else 0xea000000)|((delta>>2)&0xffffff)
    decoded=(word&0xffffff)<<2
    if decoded&(1<<25):decoded-=1<<26
    assert site+8+decoded==target
    return struct.pack('<I',word)


def build(root, stock, out, *, legacy_cache=None):
    raw = stock.read_bytes()
    assert sha(raw) == STOCK_SHA and raw[START - BASE:END - BASE] == bytes(8192), '8192-byte code window must be stock zero'
    for name, pin in TOOLS.items():
        assert sha((root / name).read_bytes()) == pin
    derive = derive_report()
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(root / 'usr/lib/x86_64-linux-gnu')
    cc = str(root / 'usr/bin/clang-18')
    ld = str(root / 'usr/bin/ld.lld-18')
    macros = subprocess.check_output([cc, *FLAGS[:6], '-dM', '-E', '-x', 'c', '/dev/null'], env=env, text=True)
    for value in ('#define __ARM_ARCH 5', '#define __thumb__ 1', '#define __SOFTFP__ 1',
                  '#define __ARM_EABI__ 1', '#define __BYTE_ORDER__ __ORDER_LITTLE_ENDIAN__'):
        assert value in macros
    assert '__thumb2__' not in macros and '__ARM_PCS_VFP' not in macros
    assert not out.exists()
    out.mkdir(parents=True)
    assert legacy_cache is None, 'v7 requires all native units rebuilt'
    # v7 legacy builder derives v4 with the v7 source path; CPU units are added.
    legacy_build(root, stock, out / 'legacy', allocator_profile='pool-v5', lifecycle=True,
                 service_exit_fix=True, phase_snapshot_fix=True, bounded_queue=True,
                 message_memory=True, service_adapter=True, compact_code=True, lto_code=True,
                 http_read=True, http_send=True, http_control=True, http_session=True,
                 http_consume=True)
    _, ls, lp = load(out / 'legacy/page.elf', base=0x06000200, allocator_profile='pool-v5')
    assert len(lp) <= 0xff0, 'two ARM veneers require last16 aligned bytes'
    binds = {name: ls[symbol] for name, symbol in [
        ('POST', 'uo_native_http_post'), ('READ', 'uo_native_http_read'),
        ('TRACK', 'uo_native_track'), ('BUFFER', 'uo_native_buffer_new'),
        ('DISCARD', 'uo_native_request_discard')]}
    (out / 'legacy_bindings.h').write_text(''.join(f'#define CC_LEGACY_{k} 0x{v:08x}u\n' for k, v in binds.items()))
    objects = []
    units = ('boot.S', 'console.c', 'cpu.c', 'wire.c', 'cpu_hooks.S')
    for unit in units:
        obj = out / (Path(unit).stem + '.o')
        objects.append(str(obj))
        if unit.endswith('.S'):
            flags = FLAGS[:6]
        else:
            flags = FLAGS + ['-DMF885_HTTP_CONTROL_V16', '-Oz', '-fomit-frame-pointer']
        subprocess.run([cc, *flags, '-I', str(out), '-c', str(V7_SOURCE / unit), '-o', str(obj)], env=env, check=True)
    elf = out / 'console.elf'
    subprocess.run([ld, '--threads=1', '--no-undefined', '-T', str(V7_SOURCE / 'console.ld'), *objects, '-o', str(elf)], env=env, check=True)
    payload, sy, inspection = inspect(elf)
    for symbol in ('cpu_idle_begin', 'cpu_idle_end', 'cpu_snapshot', 'cpu_serialize',
                   'cpu_native_read', 'cpu_hook_arm_begin', 'cpu_hook_arm_end',
                   'cpu_hook_arm_exit', 'cc_cpu_begin', 'cc_cpu_end'):
        assert symbol in sy, 'missing CPU symbol ' + symbol
    before = (out / 'legacy/unqualified-oslo.component.bin').read_bytes()
    patched = bytearray(before)
    assert raw[0x58d79c:0x58d7a4] == bytes.fromhex('f7b506000c00ffb0')
    assert raw[0x3d190a:0x3d1914] == bytes.fromhex('ffb50503ffb01c00ffb0')
    assert raw[0x4b5c50:0x4b5c58] == bytes.fromhex('70b5304d304c314e')
    for site in (0x060956ca, 0x0609568e):
        assert branch(raw[site - BASE:site - BASE + 4], site) == {'target': 0x0644f00e, 'state': 'thumb'}
    assert raw[0x958ac:0x958b0] == bytes.fromhex('0c28f5db')
    assert raw[0x959a0:0x959ae] == bytes.fromhex('fff71fff0121641c0c2c7974f3dd')
    for name,(site,pin) in HOOKS.items():
        assert raw[site-BASE:site-BASE+4].hex()==pin, name+' stock pin'
    hooks = [
        ('cpu-idle-begin',0x067e1b9c,arm_branch(0x067e1b9c,sy['cpu_hook_arm_begin'])),
        ('cpu-idle-end',0x067e1bc4,arm_branch(0x067e1bc4,sy['cpu_hook_arm_end'])),
        ('cpu-irq-exit',0x067e2054,arm_branch(0x067e2054,sy['cpu_hook_arm_exit'],link=True)),
    ]
    assert tuple(n for n,_,_ in hooks)==EXTRA_PATCH_ALLOWLIST
    patches = [('channel12-descriptor-init', 0x060958ac, bytes.fromhex('0d28')),
               ('console-region', START, payload),
               ('initializer-detour', 0x064b5c50, bytes.fromhex('004b1847') + struct.pack('<I', sy['placement_init'])),
               ('free-arm-veneer', 0x060011f0, bytes.fromhex('04f01fe5') + struct.pack('<I', sy['cc_worker_release'])),
               ('response-arm-veneer', 0x060011f8, bytes.fromhex('04f01fe5') + struct.pack('<I', sy['cc_response'])),
               ('parser-detour', 0x0658d79c, bytes.fromhex('10b5') + thumb_call(0x0658d79e, sy['cc_parser_entry']) + bytes.fromhex('10bd')),
               ('response-detour', 0x063d190a, bytes.fromhex('10b5') + arm_call(0x063d190c, 0x060011f8) + bytes.fromhex('10bdc046')),
               ('worker-normal-release', 0x060956ca, arm_call(0x060956ca, 0x060011f0)),
               ('worker-drop-release', 0x0609568e, arm_call(0x0609568e, 0x060011f0)),
               ('post-pointer', 0x069003fc, struct.pack('<I', sy['cc_http_post'])),
               ('read-pointer', 0x06900414, struct.pack('<I', sy['cc_http_read'])),
               *hooks]
    previous = 0
    rows = []
    for name, a, b in sorted(patches, key=lambda x: x[1]):
        o = a - BASE
        assert previous <= o and o + len(b) <= len(patched)
        assert patched[previous:o] == before[previous:o]
        rows.append({'name': name, 'address': a, 'bytes': len(b),
                     'before_sha256': sha(before[o:o + len(b)]), 'after_sha256': sha(b)})
        patched[o:o + len(b)] = b
        previous = o + len(b)
    assert patched[previous:] == before[previous:]
    # Arena-size agreement: source static assert must equal the builder's number.
    port_src = (V7_SOURCE / 'port.c').read_text()
    assert '_Static_assert(sizeof(uo_port_arena) == 3676' in port_src, 'source arena size must agree with builder'
    assert 'sizeof(uo_port_arena) == 3628' not in port_src
    (out / 'unqualified-oslo.component.bin').write_bytes(patched)
    report = {'schema': 'mf885-console-component/v7', 'diagnostic_legacy_cache': legacy_cache is not None,
              'target': '88MP1802 ARM9 ARMv5TE ARM/Thumb1 LE EABI5 soft-float; ARM926 compatibility profile',
              'stock_sha256': STOCK_SHA, 'component_sha256': sha(patched), 'tool_pins': TOOLS,
              'legacy_bindings': binds, 'symbols': sy, 'inspection': inspection, 'patches': rows,
              'extra_patch_allowlist': list(EXTRA_PATCH_ALLOWLIST), 'code_window': [START, END, 8192],
              'arena_bytes': {'legacy_control': 3628, 'v7_with_cpu': 3676, 'cpu_state': 48},
              'derivation': derive,
              'sources': {str(p.relative_to(REPO)): sha(p.read_bytes()) for p in sorted(V7_SOURCE.iterdir())
                          if p.suffix in ('.c', '.h', '.S', '.ld')},
              'limits': ['Offline unqualified component, not a container or flash image.',
                         'Native compilation and emitted-stub verification are reviewer-owned.',
                         'CPU configuration, counter width/reset, frequency and hook reachability remain hardware-unqualified.'],
              'device_actions': 0, 'firmware_ready': False}
    (out / 'COMPONENT.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'console_bytes': len(payload), 'legacy_bytes': len(lp), 'arena_bytes': 3676, 'firmware_ready': False}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('toolchain-root', 'stock', 'output-dir'):
        p.add_argument('--' + n, type=Path, required=True)
    a = p.parse_args()
    build(a.toolchain_root.resolve(), a.stock.resolve(), a.output_dir.resolve())
