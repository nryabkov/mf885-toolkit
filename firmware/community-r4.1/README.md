# MF885 Community R4.1 low-entry return-zero comparator

Community R4.1 is a cumulative firmware successor that preserves the useful
Messages/UI baseline and changes only one native hypothesis. It is not a
functional TTL release.

How it worked earlier matters. R3.8 installed the exact four-byte
`movs r0,#0; bx lr` `diagnostic.post_set` leaf at `0x06001521`. Its live
`command=ttl,arg=off` SET returned HTTP 200 with stable identity. R4.0 moved
the callback to `0x06001341`, expanded it to 116 code bytes plus eight literal
bytes, used field-name data at `0x06001430`, called two stock helpers twice
each and changed the request to `command=ttl,arg=x`. That POST was fully sent,
returned zero response bytes and was followed by USB/RNDIS re-enumeration.
The four simultaneous changes mean the reset cannot honestly be attributed to
the parser alone.

R4.1 keeps the R4.0 callback entry `0x06001341`, but puts the already proven
four-byte return-zero leaf there. The remaining 236 bytes before the former
field-name block and all 32 bytes of that block stay zero. It performs zero
calls, loads, stores, field lookups, text-child lookups, state accesses, GET
callbacks and packet-path changes. The exact eventual live request stays
`command=ttl,arg=x` without `output`, so callback address/request shape are
held constant while parser code, helpers and data are removed.

A green separately authorized qualifier would prove only that the lower entry
survives the exact `ttl/x` request. It would clear R4.0's non-leaf body as the
failure boundary and permit the next single-variable step: context/type/tree
loads without a helper. Another reset would instead leave the lower address
or request-shape delta as the live boundary; they would then be separated
before any parser code returns. TTL remains unavailable in either case.

The retained candidate is
`MF885_Community_0.4.1-community-r2-native-r15-cafe-r2.bin`, exactly 8,323,644
bytes, SHA-256
`e3aa9bd67a6d558443ecb80e14c3035bf080cf75c2031ff6f7a2e1f749934b56`.
Its 70,610-byte build report hashes to
`da5aa48adeb67fa99344631f2f445f9a0d4960bddefff49a2f3be4a09c12f997`.
The two in-process builds are byte/report-identical, all 71 final conditions
pass, and the independent container inspector reports `verified`.

Only six individual decompressed OSLO bytes differ from the golden image:
three nonzero bytes in the four-byte leaf and three nonzero bytes in the
four-byte `diagnostic.post_set` pointer. All are inside the two declared
ranges. WEBI carries the cumulative UI with a locked explanation panel and
zero browser TTL/diagnostic traffic. Engineering, `debugon`, SystemChannel,
stock forwarding and every other partition remain unchanged.

The firmware is not installed. Community R4.0 remains the proved installed
release. Low-entry callback survival, TTL, persistence, cold boot,
repeatability and rollback remain unproved.
