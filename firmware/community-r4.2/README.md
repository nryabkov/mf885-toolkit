# Community R4.2 native context access probe

Status: **offline native component validated; no flashable R4.2 image or live
qualification is supplied by this component**. It does not implement TTL.

This increment keeps the R4.1 low callback entry (`0x06001340`, Thumb pointer
`0x06001341`) and adds one guarded halfword read from the callback context.
The stock callback convention is `r0 = phase`, `r1 = context`. The stock
`pin_puk` path reads the context type at offset zero; that precedent does not
establish the runtime inputs of an injected callback.

The pinned LLVM source emits exactly 12 bytes:

```text
03 28 01 d1 01 b1 08 88 00 20 70 47
```

```asm
0x06001340  cmp  r0, #3
0x06001342  bne  0x06001348
0x06001344  cbz  r1, 0x06001348
0x06001346  ldrh r0, [r1]
0x06001348  movs r0, #0
0x0600134a  bx   lr
```

`volatile` keeps the load even though its result is discarded. No stack,
helper calls, literal pool, memory writes or other register changes are added.
The probe does not compare the loaded value with 1, read a request tree, parse
command/arg, publish a value, install custom state, or change packet forwarding.

| Input | Data reads | Result |
| --- | --- | --- |
| phase other than 3 | zero | return 0 |
| phase 3, null context | zero | return 0 |
| phase 3, readable aligned context | one 2-byte read | discard value, return 0 |
| phase 3, invalid non-null context | attempted read | may fault |

The non-null guard is not a pointer validity check. The LLVM load assumes
two-byte alignment, matching the stock stack context. The limited emulator
tests do not establish hardware mapping, alignment behaviour, caching or live
callback arguments.

A future surviving request would establish survival of this guarded callback
under that request. It would not, by itself, show whether the load executed or
what value it read. Proving execution requires additional runtime path evidence;
adding a response marker or state write would be a separate experiment. Tree,
helper, custom-state and packet-path work remain later increments.

## Offline use

The builder accepts only the exact pinned decompressed stock OSLO. It refuses
existing output files and never opens a network connection or device:

```sh
python3 tools/mf885_ttl_native_payload_r42.py stock-oslo.bin --output r42-oslo-component.bin
```

**The resulting file is a decompressed OSLO component, not an update image.**
Full container assembly, a distinct installed-version marker, container checks
and a separately bounded delivery protocol are still required before any
device operation. No live runner is included.

Only the callback cave and diagnostic post_set pointer are patched. Exact
whole-source and whole-candidate checks preserve all other bytes. Compared to
the R4.1 OSLO component, 11 bytes change within the 12-byte callback; the
post_set pointer remains identical.

The public tests execute the emitted machine bytes and record data reads:

```sh
python3 -B -m unittest discover -s tests -p mf885_ttl_native_payload_r42_test.py -v
MF885_R42_TEST_OSLO=/path/to/stock-oslo.bin python3 -B -m unittest discover -s tests -p mf885_ttl_native_payload_r42_test.py -v
```

The first command runs nine source/machine tests and skips three optional
exact-stock tests. The second runs all 12 against a locally supplied stock
component. Private device backups and generated binaries are not distributed.

Pinned callback SHA-256:
`3566a3b6f4ee7d2a847e49265dde1f168e6ae7be706021bfe8def3936e2bc55e`.

Pinned LLVM source SHA-256:
`1644e56f18312b9ee307a1540bbceeeda5e8c9c2f3faa3a39c87c22fcee9a558`.
