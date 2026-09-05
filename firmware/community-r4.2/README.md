# Community R4.2 native context access probe

Status: **full R4.2 container verified offline; not installed or live-qualified**.
The source-only distribution supplies builders and tests, not a binary image.
R4.2 does not implement TTL.

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
The separate full-container builder below performs container assembly and
verification with distinct R4.2 versioned assets. Device delivery and live
qualification remain separate; no live runner is included in the public export.

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

## Full firmware container

The full offline builder combines this exact OSLO component with the cumulative
UI under `/r42.html`, `/js/r42app.js` and `/css/r42ui.css`. The page keeps TTL
unavailable and emits no diagnostic requests. Browser JavaScript is identical
to R4.1 after version renaming; CSS is byte-identical. The stock UI links point
to R4.2 and all other partitions stay byte-identical to the supplied golden.

```sh
python3 tools/mf885_build_variant.py --variant community-r4.2 --golden input/MF885_golden.bin --identity-xml input/mf885-base.xml --output-dir out --acknowledge-brick-risk
```

The output directory must already exist. The builder compares two sequential
builds and their reports, checks native/WebUI preservation and independently
inspects the final ZIMI/CAFE/LZMA container. It refuses to overwrite outputs.
No network, USB or device action is performed by this command.

Reference artifact: `MF885_Community_0.4.2-community-r2-native-r16-cafe-r2.bin`,
8,323,644 bytes, raw SHA-256
`c30af4456cf5232939a1926bb6f5d31e390470d79a959dfd0db37686feab096d`.
The raw encrypted header is bound to the supplied unit. Portable plaintext
SHA-256 is `fce690236a567a8e57ffa1dc59718e9d35e8486c1d8427aac3e17a07e400b285`.
All 79 final verification conditions passed and the independent inspector
reported verified. Exact asset and report pins are in manifest.json.

Full-container tests use optional local fixtures via `MF885_TEST_GOLDEN` and
`MF885_TEST_IDENTITY`; native-component tests use `MF885_R42_TEST_OSLO`.
Successful container checks do not establish callback execution, packet TTL,
persistence, recovery, or compatibility with another firmware revision.
