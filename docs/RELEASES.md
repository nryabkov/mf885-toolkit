# Releases and stability labels

The toolkit and generated firmware variants have separate version streams.

## Toolkit releases

Source/toolkit releases use SemVer tags such as `toolkit-v0.1.0`. A release
tag identifies the Scriptable client, builders, inspector, variant sources,
tests, and documentation at one reviewed commit. The release page must state
which test suites ran and whether any tests were skipped for lack of a local
golden image.

`Latest` means the recommended public source release. It does not qualify any
generated firmware image for flashing.

## Firmware variants

Each variant has a logical ID and a container revision. For example,
`0.0-logs-r1-cafe2` means Logs r1 content rebuilt with the second reviewed CAFE
container encoding. A new container revision always gets a new ID and output
filename; old hashes are never silently replaced.

Every manifest must expose explicit booleans/status fields. Use these meanings:

- `experimental-unflashed`: reproducible offline build only;
- `superseded-unflashed`: reproducible offline build retained unchanged after
  a newer source revision became the recommendation; it remains unflashed;
- `experimental-live-qualified-canary`: observed on a named exact hardware and
  firmware profile, but not generally safe;
- `quarantined-*`: known-invalid or misleading artifact retained only for
  historical analysis;
- `stable`: reserved for a future variant with repeatable delivery, verified
  cold boot and dwell behavior, and a separately demonstrated recovery path.

At present **no firmware variant is stable, generally flash-qualified, or
restore-allowlisted**. Do not infer stability from a successful build, a known
SHA-256, one live device, or the word `verified` in a structural report.

As of 2026-09-06, the current development candidate is
[R4.5 byte-access ARMv5 fixed64](../firmware/community-r4.5/README.md), available as
`--variant community-r4.5`. It fixes R4.4's rejection of otherwise eligible
IPv4 headers at non-four-byte-aligned addresses. Actual Thumb-1 bytes pass a
complete 18,432-case alignment/checksum/ABI matrix; two full builds match.
Three byte stores finish before stock output under inherited packet ownership;
the update is not atomic. The candidate is uninstalled and live TTL remains
unproved. Earlier native variants and their hashes remain historical evidence;
R4.3's Cortex-A9/Thumb-2 forwarding patch is not a compatible reference.

Historical checkpoint, 2026-09-05: the development increment was the
[R4.3 fixed64 forwarding release](../firmware/community-r4.3/README.md).
It rewrites eligible IPv4 packet TTL in emitted-machine tests, preserves the
original output ABI, and contains no custom state or diagnostic callback.
A reproducible full R4.3 container and distinct UI are available through
`--variant community-r4.3`; 60 structural conditions and independent container
inspection passed. There is no runtime Off switch, direction filter or live
packet qualification. R4.2 remains the separate guarded context-read
full-container builder. Neither is a qualified functional TTL release. The public export contains no binary image or delivery runner. R3.5 remains
a historical build-wrapper example, not an installation recommendation.

Per-variant READMEs, manifests and stage safety metadata are retained snapshots
from their original build/research checkpoints. In particular, fields such as
`NOT_INSTALLED`, `installed_predecessor`, and `live_qualified` do not describe
current device state or a transferable hardware guarantee. Old status fields
and immutable hashes are not silently rewritten when later research advances.
Current device observations and operational evidence are maintained separately
from this source-only distribution.

The R4.2 probe performs at most one guarded two-byte read and returns zero. A
future successful response alone would not reveal whether the read branch ran
or what it read; it would not qualify tree helpers, state or packet TTL.

Operation-safety records are not toolkit releases and are never stability
labels.
