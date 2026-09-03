# MF885 Community R2.7 extension

Community R2.7 extends the existing MF885 interface. It does not try to copy
every router setting: the original settings stay at `/index.html`, while the
extension concentrates on Messages, device health and cellular radio details.

## Functional fixes

- Messages XML now starts at byte zero with the stock declaration
  `<?xml version="1.0" encoding="US-ASCII"?> `. A live four-variant check on
  the installed R2.6 proved this is the decisive difference between HTTP 500
  and a valid HTTP 200 message model.
- Diagnostics and Modem no longer render the same rows. One explicit refresh
  reads `status1`, `wan` and `Engineer_parameter` once, then projects the same
  snapshot into two purpose-specific views. Page navigation makes no request.

## Two roadmap increments

1. Modem shows RAT, operator, band, EARFCN, PCI, Cell ID, TAC, RSRP, RSRQ,
   SINR and RSSI with the exact endpoint/path source. Proven signed RSRP/RSRQ
   units and reviewed report-index mappings are used; SINR/RSSI remain labelled
   raw. The closed Radio terms panel makes no router request.
2. Diagnostics shows device identity, SIM, registration, battery/power and the
   read-only Engineering state. Each endpoint has its own success/failure,
   request ID, elapsed time, capture time and age. Partial failure stays visible.

The async Digest/login/error layer, bounded folder reads, one-shot Send/Delete,
locked ambiguous mutation outcome and zero background router polling remain.
All Community router operations share one owner at a time: login, Snapshot,
folder read, Send and Delete cannot interleave Digest nonce use, overwrite the
active request or cancel another operation. A cancellation failure receives a
visible `JS27-*` identifier instead of being swallowed.
Expected failures include a searchable `R27-*` request ID onscreen and in the
console; unexpected JavaScript failures show a safe `JS27-*` ID onscreen and
retain details only in the console. Request logs exclude query strings, bodies,
credentials, Authorization and SMS content.

The exact reference-unit candidate is
`MF885_Community_0.2.7-community-r2-cafe-r2.bin`, 8,323,644 bytes, SHA-256
`d96a93560d8f48f8cc200ef3867576ee533e5ae182bf2b8dc405286077652e90`.
Its portable plaintext SHA-256 is
`001aeaa42d55e9a41ba3076dcf9b0e5af2df5ffbad82e06947c1d3126440945c`.
It is generated directly from the exact golden 2.5.94 image; R2.6 is not used
as a binary base. Only WEBI changes and 224,308 padding bytes remain. This
source and artifact are not themselves permission to flash; cold boot,
repeatability and rollback remain unproved.
