#!/usr/bin/env python3
"""Independent numeric ARMv5 zero-helper model. No LLVM or project imports.

Running this file reads only the supplied OSLO, executes lengths 0..96 normally,
then checks both real BSS lengths using an exact pinned-loop collapse. It never
allocates destination RAM or a per-store list. Only aggregate zero extents and
the one saved stack word are represented. The collapse is not an independent
instruction trace of every real-length iteration; its equivalence is checked
against the numeric executor for every length 0..96 and explained in output.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

START = 0x0644e280
OFFSET = 0x0044e280
SIZE = 84
PIN = 'f8983c95a4b6480c8eeadde47960b19928542adc0c610c1e3b7e499b3606cda8'
GOLDEN = 'd51fb378d8ccf68662174f39d6b8c4f6be5571280790bc3a4dc4a9e8a967078c'
MASK = 0xffffffff


def require(ok, message):
    if not ok:
        raise AssertionError(message)


class Machine:
    def __init__(self, raw, size, collapse=False, destination=0x0697c4ac):
        require(len(raw) == SIZE and hashlib.sha256(raw).hexdigest() == PIN, 'helper pin')
        self.code = struct.unpack('<21I', raw)
        self.r = [0x12120000 + i * 0x101 for i in range(16)]
        self.r[0], self.r[1], self.r[13], self.r[14] = destination, size, 0x08010000, 0x08020001
        self.before = self.r.copy()
        self.pc = START
        self.flags = dict(N=0, Z=0, C=0, V=0)
        self.stack = {}
        self.lo = destination
        self.end = destination
        self.bytes = 0
        self.steps = 0
        self.collapsed_blocks = 0
        self.collapse = collapse
        self.halted = False
        self.stack_stores = self.stack_loads = 0

    def condition(self, c):
        f = self.flags
        return {0: f['Z'], 1: not f['Z'], 2: f['C'], 4: f['N'], 14: True}[c]

    def nz(self, result):
        self.flags.update(N=(result >> 31) & 1, Z=int(result == 0))

    def sub(self, a, b):
        result = (a - b) & MASK
        self.nz(result)
        self.flags.update(C=int(a >= b), V=int(bool((a ^ b) & (a ^ result) & 0x80000000)))
        return result

    def zero(self, address, size, value):
        require(value == 0 and address == self.end, 'destination write must be contiguous and zero')
        require(address + size <= self.before[0] + self.before[1], 'exclusive end violated')
        self.end += size
        self.bytes += size

    def step(self):
        require(START <= self.pc < START + SIZE and self.pc % 4 == 0, 'instruction range')
        self.steps += 1
        require(self.steps < 10000, 'bounded model instruction budget')
        w = self.code[(self.pc - START) // 4]
        pc = self.pc
        self.pc += 4
        if not self.condition(w >> 28):
            return
        op = w & 0x0fffffff
        # This optional collapse covers SUBS+two STMHS+SUBSHS+BHS only.
        # Each full 32B block is written once; the final failed subtraction
        # leaves r1=remainder-32, N=1,Z=0,C=0,V=0, exactly as the real loop.
        if self.collapse and pc == START + 20 and self.r[1] >= 32:
            require(w == 0xe2511020 and self.code[6:10] == (0x28a0500c, 0x28a0500c, 0x22511020, 0x2afffffb), 'collapsed loop exact words')
            require(all(self.r[i] == 0 for i in (2, 3, 12, 14)), 'collapsed zero operands')
            n, remainder = divmod(self.r[1], 32)
            self.zero(self.r[0], n * 32, 0)
            self.r[0] += n * 32
            self.r[1] = self.sub(remainder, 32)
            self.collapsed_blocks += n
            self.pc = START + 40
            return
        if op == 0x03a02000:  # MOV r2,#0
            self.r[2] = 0
        elif op in (0x01a03002, 0x01a0c002, 0x01a0e002):
            self.r[(w >> 12) & 15] = self.r[2]
        elif op == 0x092d4000:  # STMDB sp!,{lr}
            self.r[13] -= 4
            require(not self.stack, 'only one stack word')
            self.stack[self.r[13]] = self.r[14]
            self.stack_stores += 1
        elif op == 0x08bd4000:  # LDMIA sp!,{lr}
            self.r[14] = self.stack.pop(self.r[13])
            self.r[13] += 4
            self.stack_loads += 1
        elif op == 0x02511020:  # SUBS r1,r1,#32
            self.r[1] = self.sub(self.r[1], 32)
        elif op in (0x08a0500c, 0x08a0000c):  # STMIA r0!, mask
            for reg in range(16):
                if w & (1 << reg):
                    self.zero(self.r[0], 4, self.r[reg])
                    self.r[0] += 4
        elif op == 0x0afffffb:  # BHS back to first STM, ARM PC+8
            immediate = w & 0xffffff
            if immediate & 0x800000:
                immediate -= 1 << 24
            self.pc = pc + 8 + (immediate << 2)
        elif op in (0x01b01e01, 0x01b01101):  # MOVS r1,r1,LSL #28 / #2
            shift = (w >> 7) & 31
            old = self.r[1]
            self.flags['C'] = (old >> (32 - shift)) & 1
            self.r[1] = (old << shift) & MASK
            self.nz(self.r[1])
        elif op == 0x04802004:  # STR r2,[r0],#4
            self.zero(self.r[0], 4, self.r[2]); self.r[0] += 4
        elif op == 0x00c020b2:  # STRH r2,[r0],#2
            self.zero(self.r[0], 2, self.r[2] & 0xffff); self.r[0] += 2
        elif op == 0x04c02001:  # STRB r2,[r0],#1
            self.zero(self.r[0], 1, self.r[2] & 255); self.r[0] += 1
        elif op == 0x03110101:  # TST r1,#0x40000000 (rotated immediate)
            self.nz(self.r[1] & 0x40000000)
            self.flags['C'] = 0
        elif op == 0x012fff1e:  # BX lr, including conditional BXEQ
            require(self.r[14] == self.before[14], 'return address')
            self.pc = self.r[14] & ~1
            self.halted = True
        else:
            raise AssertionError(f'unsupported numeric instruction {w:08x} at {pc:08x}')

    def run(self):
        while not self.halted:
            self.step()
        size = self.before[1]
        require(self.bytes == size and self.end == self.lo + size, 'exact write extent')
        require(self.r[0] == self.lo + size, 'r0 advance')
        require(self.r[4:12] == self.before[4:12], 'r4-r11 callee preservation')
        require(self.r[13:15] == self.before[13:15], 'SP and LR restoration')
        require(self.stack == {} and self.stack_stores == self.stack_loads == 1, 'one saved LR restored')
        return {'length': size, 'start': self.lo, 'end_exclusive': self.end,
                'zero_bytes': self.bytes, 'r0_final': self.r[0], 'steps': self.steps,
                'collapsed_32byte_blocks': self.collapsed_blocks, 'abi_preserved': True,
                'stack_words_peak': 1, 'per_store_trace_allocated': False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('oslo', type=Path)
    args = p.parse_args()
    image = args.oslo.read_bytes()
    require(len(image) == 9648064 and hashlib.sha256(image).hexdigest() == GOLDEN, 'exact golden OSLO')
    raw = image[OFFSET:OFFSET + SIZE]
    del image
    small = []
    for length in range(97):
        slow = Machine(raw, length).run()
        fast = Machine(raw, length, collapse=True).run()
        for k in ('start', 'end_exclusive', 'zero_bytes', 'r0_final', 'abi_preserved'):
            require(slow[k] == fast[k], 'loop collapse comparison ' + k)
        small.append(slow)
    real = [Machine(raw, n, collapse=True).run() for n in (0x730d88, 0x730d8c)]
    require(real[0]['end_exclusive'] == 0x070ad234, 'stock BSS bound')
    require(real[1]['end_exclusive'] == 0x070ad238, 'extended BSS bound')
    print(json.dumps({'schema': 'mf885-independent-zero-model/v1', 'passed': True,
          'helper_sha256': PIN, 'small_lengths_without_collapse': 97,
          'small_collapse_comparisons': 97, 'real_lengths': real,
          'limits': ['Numeric model of the exact pinned helper only; not physical execution.',
                     'Real lengths use a pinned affine loop collapse, compared on all lengths 0..96.',
                     'Does not prove allocation ownership, callers, mappings or boot reachability.']}, indent=2))


if __name__ == '__main__':
    main()
