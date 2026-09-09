#!/usr/bin/env python3
"""Move USSD rollback snapshot into the existing semaphore critical section."""
import hashlib
from mf885_console_legacy_build_v4 import STOCK_SHA
from mf885_ussd_native_abi_v1 import branch
import mf885_thumb_disasm as dis
BASE=0x06000000
PATCHES=[(0x066e1490,'b878','c046'),(0x066e1496,'0190','c046'),
         (0x066e14b6,'5148','b878'),(0x066e14bc,'8078','0190')]

def patches(stock):
    assert hashlib.sha256(stock).hexdigest()==STOCK_SHA
    assert stock[0x6e1486:0x6e1488]==bytes.fromhex('5d4f')
    assert int.from_bytes(stock[0x6e15fc:0x6e1600],'little')==0x069678a0
    assert branch(stock[0x6e14a0:0x6e14a4],0x066e14a0)=={'target':0x06427dcc,'state':'arm'}
    assert stock[0x6e14b8:0x6e14bc]==bytes.fromhex('2d063606')
    assert stock[0x6e14be:0x6e14c8]==bytes.fromhex('27032d0e360e3f0b0028')
    changes=[];rows=[];old=dis.TRIPLE
    try:
        dis.TRIPLE=b'thumbv5te-none-eabi'
        for site,before,after in PATCHES:
            assert stock[site-BASE:site-BASE+2]==bytes.fromhex(before)
            data=bytes.fromhex(after)
            rows.append({'site':site,'before':before,'after':after,
                         'decoded':dis.disassemble(data,site)})
            changes.append(('phase-snapshot-v8-'+hex(site),site-BASE,data))
    finally:dis.TRIPLE=old
    return changes,{'schema':'mf885-ussd-phase-snapshot/v8','stock_sha256':STOCK_SHA,
        'patches':rows,'saved_register':'r7 remains state pointer until066e14be',
        'new_read':0x066e14b6,'new_snapshot_store':0x066e14bc,
        'lock_call':0x066e14a0,'phase_comparison':0x066e14c6,
        'target':'ARMv5TE Thumb1 LE; no frame, register-save or calling-convention change',
        'limits':['Lock semantics and assertion non-return are prerequisites.',
                  'Not scheduler, HTTP-task, page-placement or hardware qualification.'],
        'device_actions':0,'candidate_ready':False}
