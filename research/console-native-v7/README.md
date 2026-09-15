# Native console v7: CPU idle accounting

Private offline component for 88MP1802 ARM9, ARMv5TE ARM/Thumb1,
little-endian EABI5 soft-float. ARM926 is a compatibility model, not CPUID proof.

The v6 source package is preserved. v7 derives port.h/port.c (48-byte CPU state
appended to the allocated arena, 3628 to 3676 bytes), console.c (guarded hooks
and optional cpu_v1 readback), and this README. Other existing files retain
identical bytes. The new versioned legacy build AND component wrappers both
use v7, so allocation and use agree. No writable linked section or fixed BSS.

Timer1 mode at 0x12385 (0x1235c + 24 decimal + 0x11) must equal 1. Clock select
(d4080000 >> 2) & 7 must equal 1; d4080084 bit1 must be set. Preload registers
d408005c/d4080050 must be zero; d4080088 bit1 must be clear. At most 16 reads
of d408002c seek consecutive equal samples. No MMIO writes or stock busy loops.
The 32768 Hz value is the firmware contract, not a measured hardware frequency.
Exact hardware counter continuity/width and hook reachability need qualification.

All sample and state changes occur under stock I/F guards. Total counts every
elapsed tick, while idle counts only ticks in the previous open idle interval.
Transitions are idempotent. Snapshots accrue elapsed time into live state before
copying; later calls cannot count it twice. Read failure or delta >= 2^31
invalidates counters; recovery starts a new epoch. An epoch begins warming,
then becomes valid after elapsed time exists. No stale percentage after failure.
Counters use two u32 words; errors and transitions saturate.

Wire cpu2: is 40 bytes as lowercase hex, 85 characters plus NUL. Ten LE u32:
version=1, flags, epoch, frequency_hz, total_low, total_high, idle_low, idle_high,
read_errors, transitions. Flags: warming=1, valid=2, unavailable=4. HTTP uses
cpu_v1 alongside console_v1 and owns/replaces its allocated response string.

Three four-byte ARM patches: 067e1b9c B to idle begin (reproduce LDR r2 literal
0695e0d8); 067e1bc4 B to idle end (reproduce MSR CPSR_fsxc,r1 first); 067e2054
BL to IRQ accounting (end idle, then tail-call original Thumb 06085073 with
original LR). Poll/backedge instructions are untouched. Hooks preserve live
registers/flags and exact SP and align C calls to 8 bytes. C validates the
published arena including null, stock fallback and magic before accessing CPU.

Validation commands: tests/mf885_cpu_native_v1_test.py (actual host C oracle),
tools/mf885_cpu_native_execution_v1.py (actual assembled hooks, ARM926), and
existing console startup/transport plus stock-pool execution fixtures. These
exercise offline behavior and do not establish live device qualification.
