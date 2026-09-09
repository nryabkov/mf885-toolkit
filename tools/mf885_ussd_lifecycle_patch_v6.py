#!/usr/bin/env python3
"""Pinned direct-call instrumentation; computed/indirect coverage remains open."""
import hashlib
import struct
from mf885_console_legacy_build_v4 import STOCK_SHA
from mf885_ussd_native_abi_v1 import branch
from mf885_console_legacy_component_v4 import BASE, thumb_call

CALLS = {
    0x061d82fe: ('uo_native_error_release', [0x061d83d2,0x061d9c46]),
    0x061d9b1e: ('uo_native_error_reject', [0x061d9bf6]),
    0x061da742: ('uo_native_error_return', [0x061d9a82]),
    0x061da17a: ('uo_native_allocate_id', [0x061d7700,0x061d7b56,0x061d7d06,0x061d7d72,0x061d8124,0x061d81d0,0x061d8216,0x061d863a,0x061da1ae]),
    0x061d76a8: ('uo_native_insert', [0x061d7714,0x061d7c58,0x061d7d42,0x061d7dae,0x061d8140,0x061d822c,0x061d8666,0x061da202]),
    0x061d827c: ('uo_native_retire', [0x061d832e,0x061d8408,0x061d8ed0,0x061d9902,0x061d9a62,0x061d9b02,0x061d9b8a,0x061da762]),
}

def patches(stock, symbols):
    assert hashlib.sha256(stock).hexdigest() == STOCK_SHA
    inventory = {a: [] for a in CALLS}
    for o in range(0,len(stock)-3,2):
        h,j = struct.unpack_from('<HH',stock,o)
        if h & 0xf800 != 0xf000 or j & 0xf800 not in (0xf800,0xe800): continue
        try: edge = branch(stock[o:o+4],BASE+o)
        except ValueError: continue
        if edge['target'] in inventory: inventory[edge['target']].append(BASE+o)
    rows=[]; changes=[]
    for target,(name,sites) in CALLS.items():
        assert inventory[target] == sites, 'changed direct-call inventory'
        needle=struct.pack('<I',target|1)
        assert all(stock[o:o+4] != needle for o in range(0,len(stock)-3,4)), 'unexpected function pointer'
        for site in sites:
            original=stock[site-BASE:site-BASE+4]
            assert branch(original,site)=={'target':target,'state':'thumb'}
            replacement=thumb_call(site,symbols[name])
            changes.append((name+'-'+hex(site),site-BASE,replacement))
            rows.append({'site':site,'original_target':target,'before':original.hex(),'after':replacement.hex(),'wrapper':name})
    tables=[]
    for table, original, name in [
        (0x06846c10,0x061d8151,'uo_native_outgoing'),
        (0x06846c28,0x061d9777,'uo_native_result'),
        (0x06846c34,0x061d9ab1,'uo_native_error_message'),
        (0x06846c40,0x061d9c83,'uo_native_confirmation'),
        (0x06846c44,0x061d9de1,'uo_native_invoke')]:
        assert struct.unpack_from('<I',stock,table-BASE)[0]==original
        changes.append((name+'-table',table-BASE,struct.pack('<I',symbols[name])))
        tables.append({'address':table,'original':original,'replacement':symbols[name],'wrapper':name})
    return changes, {'schema':'mf885-ussd-lifecycle-patch/v6','stock_sha256':STOCK_SHA,
        'direct_calls':rows,'handler_tables':tables,'coverage_enabled':False,
        'limits':['Exact stock direct-call inventory; computed aliases and task serialization remain unproved.',
                  'Timeout boundaries, all producer aliases and complete boot coverage remain unproved.',
                  'No firmware container or hardware qualification.'],'device_actions':0}
