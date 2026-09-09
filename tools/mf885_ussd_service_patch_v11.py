#!/usr/bin/env python3
"""Selected SS service call adaptation; exact stock, no generic transport patch."""
import hashlib,struct
import mf885_thumb_disasm as dis
from mf885_console_legacy_build_v4 import STOCK_SHA
from mf885_ussd_native_abi_v1 import branch
BASE=0x06000000
ALLOC_LITERAL=0x066e1564
SEND_LITERAL=0x066e1568

def patches(stock,symbols):
    assert hashlib.sha256(stock).hexdigest()==STOCK_SHA
    assert stock[0x6e1560:0x6e156e]==bytes.fromhex('27480021006846f536ec0298d5e7')
    assert stock[0x6e1552:0x6e1560]==bytes.fromhex('2b480021006846f53cec2000dce7')
    # Busy and v7 NULL paths use the same release/status epilogue. r4 is saved
    # by the original service frame; setting it here changes no external ABI.
    compact=bytes.fromhex('0124f6e7')
    assert branch(compact[2:],0x066e1562)=={'target':0x066e1552,'state':'thumb'}
    assert symbols['uo_native_service_alloc']&1 and symbols['uo_native_service_send']&1
    block=compact+struct.pack('<II',symbols['uo_native_service_alloc'],symbols['uo_native_service_send'])+bytes.fromhex('c046')
    result=[('service-shared-exit-and-literals-v11',0x6e1560,block)];calls=[]
    previous=dis.TRIPLE
    try:
        dis.TRIPLE=b'thumbv5te-none-eabi'
        compact_rows=dis.disassemble(compact,0x066e1560)
        for site,old,reg,literal in [(0x066e14ce,0x0644f016,3,ALLOC_LITERAL),
                (0x066e1510,0x0644f016,3,ALLOC_LITERAL),(0x066e14fe,0x065d51a4,4,SEND_LITERAL),
                (0x066e1540,0x065d51a4,4,SEND_LITERAL)]:
            raw=stock[site-BASE:site-BASE+4]
            assert branch(raw,site)=={'target':old,'state':'thumb'}
            assert stock[site-BASE+4:site-BASE+6]==bytes.fromhex('0400') # movr4,r0 after each original call
            offset=literal-((site+4)&~3)
            assert 0<=offset<=1020 and offset%4==0
            code=struct.pack('<HH',0x4800|(reg<<8)|(offset//4),0x4780|(reg<<3))
            result.append(('service-indirect-call-v11-'+hex(site),site-BASE,code))
            calls.append({'site':site,'original_target':old,'scratch_register':'r'+str(reg),
                'literal_address':literal,'new_target':symbols['uo_native_service_alloc' if reg==3 else 'uo_native_service_send'],
                'original':raw.hex(),'replacement':code.hex(),'instructions':dis.disassemble(code,site)})
    finally:dis.TRIPLE=previous
    return result,{'schema':'mf885-ussd-service-patch/v11','stock_sha256':STOCK_SHA,'calls':calls,
        'shared_exit':{'site':0x066e1560,'instructions':compact_rows,'epilogue':0x066e1552,
            'owned_literal_span':[ALLOC_LITERAL,SEND_LITERAL+4],'next_function_unchanged':0x066e156e},
        'contract':['Requires v7 NULL-release and v8 locked phase snapshot.',
            'r3 is scratch for calloc; send consumes originalr3 payload while r4 is replaced with returned status immediately afterward.',
            'Service frame, shared semaphore, phase and original caller ABI remain.',
            'New send adapter consumes request ownership on both normal outcomes.'],
        'device_actions':0,'candidate_ready':False}
