# Releases and stability labels

Current published development source is **0.4.7-dev.15**, with limited actual
AT/USSD qualification. See [dev15 usage, dependencies and build instructions](AT_USSD_047D15_RU.md).
Older version statements below describe historical checkpoints.

## 2026-09-07 — Community0.4.7-dev.6

Exact assets/boot, WAN and layout, one reboot, and one operator-observed
shutdown followed by physical-on and recovery passed on one MF96 Ver.D/2.5.94.
Native unchanged from dev.5; no new TTL packet claim. USB remained enumerated
during shutdown observation; electrical zero power was not measured.
See [usage, proof scope and limits](WAN_POWER_047D6_RU.md).

## Earlier dev.5 qualification

Community0.4.7-dev.5 adds the Engineering readings editor. Exact installed
assets and actual Read/Enabled/changing readings/Disabled/recovery passed on
one MF96 Ver.D /2.5.94 unit. Native remains byte-identical to dev.4; TTL packet
checks were not repeated. Measurement age and long-term cost remain unknown.
See [the guide](ENGINEERING_047D5_RU.md). Earlier sections retain their historical
version-specific results and test counts.

The toolkit and generated firmware variants have separate version streams.

## 2026-09-07 — Community0.4.7-dev.4 source publication

Actual installed editor Read→Off→64 and separate readbacks passed on one MF885
before publication. With source TTLs32/96, GL→VDS host captures read49/49,
17/81,49/49; reverse GL captures read64/64,16/80,64/64. Six requests/six replies,
24 frames, zero capture drops; final64/rev2. Exact assets and native source pins
are published with the [guide and full limitations](TTL_EDITOR_047D4_RU.md).
The browser used a bounded proxy with in-memory login bootstrap; core scripts
were unchanged. No claim of all protocols, physical cellular egress, concurrent
writers, reboot persistence, universal recovery or long-term stability.
The preceding delivery cleanup error and separate successful recovery are both
retained as distinct results. R4.6 remains quarantined; dev.3 was not installed
and its implementation is excluded from this export. dev.2 files are the pinned
native dependency of dev.4, not a separate release recommendation.

Publication checks: Python223 tests (161passed,62skipped for absent local
inputs), Node459 tests (455passed,4historical conditional cases skipped), public
tree policy passed. All23dev.4 editor cases ran. The public wrapper reproduced
the exact installed reference image in two equal builds, passed36conditions and
independent container inspection. Skipped tests are not counted as passed.

## Toolkit releases

Source/toolkit releases use SemVer tags such as `toolkit-v0.1.0`. A release
tag identifies the Scriptable client, builders, inspector, variant sources,
tests, and documentation at one reviewed commit. The release page must state
which test suites ran and whether any tests were skipped for lack of a local
golden image.

`Latest` means the recommended public source release. It does not qualify any
generated firmware image for flashing.

## Firmware variants

Future versions separate the Community version from the exact vendor base.
See [versioning and backward compatibility](VERSIONING_RU.md); existing R4.5
and R4.6 identifiers and artifact bytes remain unchanged.

Legacy variants have a logical ID and a container revision. For example,
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

Historical native R3.5, R4.2 and R4.3 profiles are quarantined in the common
build wrapper. Their ARMv7/Cortex-A9 target assumptions do not satisfy the
verified ARMv5TE/Thumb-1 device profile. `--list` reports the rejection and the
reason; acknowledging generic brick risk does not override it. Original native
sources, individual historical builders and hashes remain unchanged for offline
analysis. They are not compatible device-build recommendations.

Future firmware source increments are published after qualification on the
actual target, with offline checks before installation. The already published
R4.6 increment below predates this ordering rule and remains unqualified.

R4.6 is now **quarantined after a failed hardware test**. Boot and exact static
assets passed, but its first native TTL GET returned zero bytes before timeout
with USB identity drift; the device recovered automatically. Root cause is
unresolved. No second read, SET, Off or dynamic packet test was performed.
Do not use its editor or repeat the failing request. The common build wrapper
rejects R4.6 even with the general risk acknowledgement; the individual historical
builder remains offline research only. Original sources and hashes are retained.
See the [R4.6 limitations](TTL_EDITOR_R46_RU.md).

The last packet-proven research baseline as of 2026-09-06 is
[R4.5 byte-access ARMv5 fixed64](../firmware/community-r4.5/README.md), available as
`--variant community-r4.5`. It fixes R4.4's rejection of otherwise eligible
IPv4 headers at non-four-byte-aligned addresses. Actual Thumb-1 bytes pass a
complete 18,432-case alignment/checksum/ABI matrix; two full builds match.
Three byte stores finish before stock output under inherited packet ownership;
the update is not atomic. R4.5 was tested on one research unit. In each of two
separate bounded UDP experiments, four source TTLs 32/96/32/96 arrived at the
server as 49/49/49/49; four replies with source TTLs 32/96/32/96 arrived at the receiving
GL interface as 64/64/64/64. This establishes those host-tap observations, not
physical cellular-egress TTL64, direct native-hook execution or long-term
stability.
No firmware variant is a stable or generally flash-qualified release. Earlier
native variants and their hashes remain historical evidence; R4.3's
Cortex-A9/Thumb-2 forwarding patch is not a compatible reference.

The 2026-09-06 R4.5 observation used four requests and four causal replies, with
no automatic retries. All captured IPv4 and incoming UDP checksums were valid.
The server's outgoing host captures carried kernel metadata for an unfinished
checksum; matching incoming frames had completed valid checksums. The result
is therefore qualified host-tap evidence, not a physical-wire checksum claim.
Temporary test routing was removed and host services remained healthy.
Other protocols, cold boot, longer dwell and a matched control experiment remain
future work. This public summary contains no packet captures or unit identity.

The [current WebUI source](../webui/r4.5/) is byte-identical to the installed
community assets. Its original pending-measurement wording and per-variant
build-time flags remain unchanged; this document provides the later status.
See the [Russian guide](WEB_INTERFACE_RU.md) and [updated roadmap](ARCHITECTURE.md).

Historical checkpoint, 2026-09-05: the development increment was the
[R4.3 fixed64 forwarding release](../firmware/community-r4.3/README.md).
It rewrites eligible IPv4 packet TTL in emitted-machine tests, preserves the
original output ABI, and contains no custom state or diagnostic callback.
Its historical full-container builder and distinct UI remain in source;
the common wrapper now rejects `community-r4.3`. Its historical 60 structural
conditions and independent container inspection passed. There is no runtime Off switch, direction filter or live
packet qualification. R4.2 remains the separate guarded context-read
full-container builder. Neither is a qualified functional TTL release. The public export contains no binary image or delivery runner. R3.5 remains
a quarantined historical profile, not an installation recommendation.

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

## Community 0.4.7-dev.18

Manual TTL 1–255/Off (boot default 64), System/Light/Dark theme.
Entry: `/c047d18.html`; offline variant: `community-0.4.7-dev.18`.
[Usage, observed hardware results and limitations](TTL_THEME_047D18_RU.md).
CPU accuracy and long-term USB stability remain unqualified.
