# R4.6 native TTL editor — hardware test failed

**2026-09-06 hardware result: do not use the R4.6 TTL editor.** Boot and exact
static assets passed, but the first native diagnostic GET returned zero bytes
before timeout and USB identity drift was observed. The device automatically
recovered. No second read, TTL SET or Off/packet test was attempted; root cause
remains unresolved. The common build wrapper rejects this profile. Original
source/image identities remain unchanged for research; the individual historical
builder remains available only for offline analysis. The following design and
offline evidence do not establish working hardware behavior.


This is an experimental source increment, not a stable or generally installable
release. No R4.6 device callback, dynamic packet effect, Off, cold boot or recovery
has been qualified. R4.5 source snapshots and hashes remain unchanged.

## Architecture and native contract

The deployment evidence establishes the MF885 Marvell ARM9 / board88MP1802
family and the ARMv5TE/Thumb-1 compatibility profile. `arm926ej-s` is the compiler
profile, not a newly established exact core identity. All three LLVM inputs use
`thumbv5te-none-eabi`, `arm926ej-s`, and
`+thumb-mode,-thumb2,-neon,-vfp2,+strict-align`. Output is ELF32 little-endian ARM
EABI5. There is no floating-point code, Thumb-2, new target runtime library or
unresolved relocation. Check the actual deployment target before every build.

The unchanged R4.5 hook and Thumb-1 entry stub call a new configurable forward
helper. It samples one volatile configuration byte per packet. Off (native0)
performs no packet reads or writes and calls the original output once. Numeric
1..255 replaces the TTL of eligible IPv4 packets with old TTL>=2; version, IHL
and complete contiguous-header guards remain. Header accesses are byte-wide at
any alignment; checksum bytes are written before TTL. The protocol, fragment
fields, original output return and calling convention are preserved. Both
forwarding directions use this hook; local traffic and IPv6 are outside its
scope. This is an offline code contract, not a physical cellular-egress claim.

The three components occupy verified original zero reservations:

| Component | OSLO offset | Bytes |
|---|---:|---:|
| Entry stub + forward helper | `0x12a0` | 148 |
| Current-request post-set callback | `0x1340` | 224 |
| Initial RAM state, generation and names | `0x14a0` | 96 |
| Pre-get state publisher | `0x1520` | 128 |

Two diagnostic callback pointers and the existing 12-byte forwarding hook are
the only other changed spans. Every unlisted OSLO byte is compared with the exact
stock input. The decompressed component SHA-256 is
`7c3a8d06b3cdb2d8bdd91eb028d82c103d05e9e8f29b756b7f8c86192e8b30b8`.
It is not a firmware container and must never be flashed alone.

SET validates phase3, the current request context/type/tree, exact command `ttl`,
and canonical `off` or decimal1..255. It reads current request-tree fields using
the exact stock pin/PUK callback precedent, never retained command/arg values.
Invalid or missing inputs cause no state store. The callback's return does not
set HTTP status: a200 response cannot prove an accepted setting. XML duplicate
field behavior and arbitrary parser inputs are not claimed to be fully qualified.

GET phase4 samples actual state, increments an aligned 32-bit generation and
publishes `r46:GGGGGGGG:TT` through the synchronous stock property setter. G is
8 lowercase hex digits; TT is the sampled byte (00 means Off). Publication may
fail while leaving an old output. The client therefore requires advancing
readback generations, including two reads before enabling changes. This detects
stale/nonadvancing values; it is not cryptographic replay protection. Native
counter concurrency and hardware RAM writability still require qualification.

Initial TTL is64. State is in RAM; persistence is not implemented. Do not promise
retention or exact reset defaults until the relevant reset path is measured.

## Editor and tests

The versioned [WebUI sources](../../webui/r4.6/) include Russian TTL help, input
validation, actual-state readback, Off, and redacted console metadata. Initial
login, page navigation and periodic refresh issue no TTL requests. One explicit
read performs two GETs. One change performs a fresh baseline GET, at most one
POST, then one readback GET. A same-value baseline requires no POST. No ambiguous
write is retried; manual successful readback is required to unlock further writes.
Unsubmitted text survives refresh. All router operations share one UI lock.

Eleven emitted-instruction tests cover all numeric values and Off, callback
phase/context rejection, generation wrap and failed publication, byte-alignment,
all version/IHL bytes, short mappings, checksum-zero/carry boundaries and fragment
headers. The numeric Thumb-1 model rejects unsupported instructions and verifies
stock call-boundary registers/interworking; it does not execute stock callees.
Sixteen DOM scenarios cover native-state parsing, transport ordering, stale data,
timeouts, dirty edits, double-clicks, logout and console privacy. Local simulation
success is not evidence of hardware compatibility by itself.

A full container was produced by isolated stages and then reproduced byte-for-byte
by the normal builder. All73 full verification conditions and an independent
container inspection passed. Altered outside partitions and malformed headers
were rejected. This is structural/offline evidence only.

Use the offline wrapper profile `community-r4.6` with your own exact compatible
backup and identity as described in [the build guide](../../docs/BUILD_FIRMWARE.md).
The builder uses exclusive outputs, deterministic reconstruction and independent
container inspection. No binary or live delivery helper is published.
