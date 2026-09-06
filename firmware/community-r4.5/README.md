# Community R4.5: fixed TTL 64 at every IPv4 header alignment

R4.4 forwards a valid IPv4 packet unchanged when its header address is not
four-byte aligned. R4.5 removes that eligibility restriction and accesses the
packet header only through byte loads and stores. This fixes a concrete
coverage defect; alignment has not been proved to cause an observed uplink
failure, and alternative packet paths are not qualified by this change.

The complete build profile is ARMv5TE/Thumb-1, little-endian, ARM EABI5,
`arm926ej-s`, `+thumb-mode,-thumb2,-neon,-vfp2,+strict-align`. ARM926EJ-S is a
compatibility compiler profile, not identification of the physical custom
Marvell core. The profile is checked before compilation. Independent object
inspection reports ARMv5TE, Thumb-1 and no unaligned-access requirement; actual
emitted bytes, code/data boundaries and complete hook-to-return execution are
checked separately. There is one newly compiled native function. The exact
Thumb-1 hook/stub and all other stock native code are retained.

The 8-byte stub and 124-byte body total 132 bytes inside the original 160-byte
reservation. Body 116 mapped code bytes include 2 unreachable padding bytes;
8 bytes are literals. No reservation expansion or extra callback is needed.
Eligible IPv4 headers retain IHL>=5, total/contiguous-length and TTL>=2 guards;
TTL0/1/64 and invalid/short headers incur no packet writes. When changed, only
checksum bytes+10,+11 and TTL+8 are stored, in that order, before the original
output callback is called once with its stock arguments and return behavior.
Protocol, options and payload remain unchanged. Scope remains both directions
through the existing callsite; no runtime Off or direction filter is added.

Three byte stores are not atomic. Valid pointers, a valid incoming checksum,
aligned pbuf/netif objects and exclusive packet mutation until output remain
inherited stock preconditions. The tests establish the completed packet at
callback entry; they do not prove absence of asynchronous observers or DMA.

The independent numeric instruction model runs 18,432 complete chains: all four
header alignments, TTL0..255, IHL5/6/15, protocols1/6/17 and ARM/Thumb callback
states. It recomputes full-header checksums and enforces byte access widths,
exact ordered writes, output ABI, register/SP preservation and code boundaries.
Additional cases cover length boundaries, every version/IHL byte, short
mappings, checksum zero/carry and rejected corrupt instruction/branch/store
encodings. The R4.4 model defaults and historical release pins are retained.

Two complete offline builds and reports match. All 63 container conditions and
independent inspection pass. OSLO and versioned WEBI assets change, plus
required container integrity fields; other partitions remain byte-identical.
The distinct UI is `/r45.html`. Exact portable and reference-unit hashes are in
[manifest.json](manifest.json). Build with `--variant community-r4.5` and the
reviewed local stock/identity inputs described in the build documentation.

This is an uninstalled experimental candidate. Hardware hook execution,
actual network TTL, stability and recovery are not proved. A decompressed OSLO
component alone is not an update image. Builders never access or flash a router.
