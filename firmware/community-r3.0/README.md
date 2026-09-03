# MF885 Community R3.0 TTL extension

R3.0 preserves the complete proven R2.9 UI/SMS surface and adds one temporary
TTL control inside the same authenticated Community extension. It is not a new
router interface.

The browser reads and writes only the stock-shaped `diagnostic` model. R3.0
accepts one narrow command, `ttl`, with exact argument `off` or a canonical
decimal integer from `1` through `255`. The UI presents `64` as the recommended
iPhone-compatible value, `65` as an explicit compatibility preset, and also
allows a custom value. Every change is one POST followed by one GET readback
with zero automatic retry. A lost readback locks further mutation until a
fresh GET proves state.

The native state is one RAM byte initialized to zero (`Off`) on each OSLO load.
Readback uses an immutable 256-slot table (`off`, then canonical `1..255`), so
there is no shared formatting scratch or concurrent-read race. When enabled,
one aligned 32-bit commit updates TTL/protocol/checksum bytes for forwarded
IPv4 packets only. IPv6 and router-originated traffic do not enter the hook,
and an observed TTL of zero or one is never raised. The setting is not
persisted.

The first structural candidate is superseded. The current offline candidate is
`MF885_Community_0.3.0-community-r2-native-r3-cafe-r2.bin`, exactly 8,323,644
bytes, SHA-256
`78c785527c9e6cafc301e9c8937be3ceaace0d7d7265e1d78f77b1094e880e42`.
The fixed outer size is deliberately unchanged; the rebuilt OSLO still leaves
37,935 bytes of deterministic partition padding.

The emitted Thumb helpers are now executed by a bounded concrete subset
machine in 2,589 focused paths in addition to strict disassembly, source-range
proofs and 441,344 independent checksum recomputations. This materially closes
the earlier source-model-only test gap. The machine uses LLVM-decoded
instruction records, so a second independent decoder is not claimed.

The code now lives in exact zero caves on a page that also contains proved
stock executable Thumb. The state/table block is within the exact loaded OSLO
range and has no aligned source reference, but its live writability/ownership
is still a qualification boundary: the first setter/getter and GL.iNet packet
path must pass before the feature is considered proven on hardware.

The internal model deliberately retains the generic name `diagnostic`: later
R3.2 can add the separate `ussd` command to the same authenticated dispatcher
without removing the already accepted TTL command.
