# MF885 Community R3.2 TTL response repair

R3.2 is a cumulative, TTL-only repair of the installed Community R3.1 image.
It preserves the complete R2.9 UI/SMS baseline, the R3.1 low-page native TTL
implementation and the existing TTL product contract. It does not add Wi-Fi
repeater, USSD or IMEI behavior.

## Why R3.1 did not answer

R3.0's first authenticated TTL GET coincided with an immediate USB/RNDIS
reset. R3.1 removed that reset by moving native code and state into the first
loaded OSLO page, but the TTL request still returned no first response byte
within five seconds. A later Base request from the same unit succeeded in
458 ms, so this was not a general router failure.

Exact stock control flow now identifies a specific lifecycle hypothesis. The
Duster pre-get registry call at OSLO `0x72c51a` runs before a bounded core GET
region entered at `0x72c532`; the post-get registry call at `0x72c5be` runs
afterwards. The calls at `0x72c51e` and `0x72c536` only set and clear a global
flag; they are not identified as model serialization. Retained stock `debugon`
evidence independently shows that its post-get update was absent from that
request's response. Moving R3.1 publication earlier is therefore the smallest
evidence-backed repair, but the target root cause remains unproved.

## Repair

R3.2 moves the byte-identical 200-byte R3.1 publisher from the dormant Duster
post-get pointer to the pre-get pointer. The post-get pointer remains exact
stock zero. The forwarder, setter, low-page state, strings, accepted values,
stack-local numeric buffer and UI request shape are unchanged.

The user-visible UI is intentionally unchanged. It uses cache-safe `/r32.html`,
`/js/r32app.js` and `/css/r32ui.css` identities so a browser cannot reuse R3.1
assets while the native lifecycle changes underneath them.

The deterministic offline candidate is
`MF885_Community_0.3.2-community-r2-native-r5-cafe-r2.bin`, exactly 8,323,644
bytes, SHA-256
`a3326c9bf18f024e898c7cf8108c237d09b7ef92579209eb5e51a3d209ff3dfc`.
Two builds are byte-identical and an independent container inspection is
green. Only OSLO and cumulative WEBI differ from exact golden; GRBI, WIFI,
WCAL and RFBN are byte-identical.

The complete substantive offline set is 49/49: five R3.2 lifecycle tests,
three R3.2 WEBI/profile tests, six R3.2 container-builder tests, nine inherited
R3.1 low-page tests, 21 inherited R3.0 TTL parser/forwarder/checksum tests and
five browser TTL-flow tests executed against exact derived R3.2 assets.

This is not live qualification. R3.2 has not been flashed. Its first safe live
acceptance after a separately approved delivery is one authenticated TTL GET
returning the exact model without USB/RNDIS identity change. TTL setter,
packet-path behavior, cold boot, repeatability and rollback remain unproved.
