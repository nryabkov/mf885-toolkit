# MF885 Community R3.4 diagnostic no-op discriminator

Community R3.4 is a diagnostic-only isolation release built from the exact
reviewed 2.5.94 golden image. It retains the accepted Community R2.9 WebUI and
Messages behavior, but deliberately exposes no working TTL control.

The native delta is intentionally limited to two ranges:

- a four-byte Thumb leaf, `movs r0, #0; bx lr`, in an exact zero-filled cave;
- the stock-empty `diagnostic.pre_get` pointer, directed to that leaf.

There is no mutable state, data blob, load, store, call, property setter or
getter, packet-forwarding hook, TTL setter, TTL write template, or browser TTL
request. The stock Engineering, hidden `debugon`, `SystemChannelName`, and IP
forwarding surfaces remain byte-exact.

The first live qualification, after a separately approved firmware delivery,
is one authenticated `diagnostic` GET bracketed by exact USB/RNDIS identity
observations. A green response proves callback attachment only; it does not
prove TTL functionality. A timeout or re-enumeration retires this diagnostic
callback route.

The retained offline candidate is
`MF885_Community_0.3.4-community-r2-native-r7-cafe-r2.bin`, exactly 8,323,644
bytes, SHA-256
`482e51ad7ecfc7f519907dac0d813664ef330553f28382a290451858580512ea`.
Its 57,374-byte build report hashes to
`2a3085bb4dcaf4adeef9fa65b301377d52a5e3e878f2a8513dc141025cfd82eb`.
Two builds are byte-identical, independent container inspection is verified,
and all six actual OSLO byte changes are within the two declared ranges.
The final pin-bound substantive test set is green 75/75: seven R3.4
source/native/container checks, ten direct-v40 functional checks, three
JavaScript gate checks and 55 affected historical direct-flow regressions.
