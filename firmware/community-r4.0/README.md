# MF885 Community R4.0 direct-context discriminator

Community R4.0 is a cumulative firmware successor which preserves the useful
R2.9 Messages/UI baseline while making one deliberately small native change.
It is not a functional TTL release.

How earlier firmware worked is the reason for this design. R3.8 installed only
the four-byte `movs r0,#0; bx lr` `diagnostic.post_set` callback. Its live SET
and later GET completed with stable identity, proving the callback slot, phase
and return boundary. R3.9 combined generic property getters/frees, a private
write at `0x06001430` and a forwarding packet hook. Its first exact `ttl/off`
POST was fully sent, then returned no response and caused RNDIS
re-enumeration. That run cannot identify which new operation failed.

R4.0 removes every R3.9 operation and tests only the next stock-proved input
boundary. Its phase-3 callback reads the current request tree from the stock
context at offset 12, looks up `command` and `arg` through the exact stock
helpers, requires one text child for each, recognizes only `command=ttl` plus
`arg=x`, and always returns zero. Returned strings are borrowed and never
freed. There is no generic property getter, property setter, custom state
read/write, diagnostic GET callback, forwarding hook, UDP probe, or browser
diagnostic traffic.

The exact post-install qualifier is challenge GET, login GET and one 112-byte
`command=ttl,arg=x` diagnostic POST. It accepts only HTTP 200 with a root-only
attribute-free `RGW` envelope or the exact ordered `ttl/x/output-empty` echo,
then compares USB/RNDIS identity. It deliberately performs no later GET. A
green result proves only that the callback safely survived this exact request;
combined with the offline instruction proof it is consistent with, but cannot
live-observe, successful field lookups. It does not prove parsing branch
selection, state retention or TTL.

The retained candidate is
`MF885_Community_0.4.0-community-r2-native-r14-cafe-r2.bin`, exactly 8,323,644
bytes, SHA-256
`6a64aba82333c36614b13fdd4d068f5b64a66bfc128b2527481d768ca091c1f9`.
Its 82,006-byte build report hashes to
`b93dc9f0f4054a62524784d5562a5fbc1a27ac668f4e6b0b7b562d860f128ca5`.
Two fresh independent output directories produced byte-identical images and reports.
The independent container inspector is green; all 57 final conditions pass.

The 116-byte Thumb body plus eight-byte literal pool occupies a declared
124-byte callback range. A separate 32-byte read-only name block contains
`command\0arg\0`, and the four-byte diagnostic `post_set` pointer targets the
odd Thumb address. Only 129 OSLO bytes actually differ from the golden image,
all inside those three declared ranges. Engineering, `debugon`,
`SystemChannelName`, the stock forwarding hook and the remaining partitions
are preserved.

The firmware is not installed. The currently proved installed release remains
Community R3.9. Live direct-context parsing, state ownership, TTL packet
behavior, persistence, cold boot, repeatability and rollback remain unproved.
