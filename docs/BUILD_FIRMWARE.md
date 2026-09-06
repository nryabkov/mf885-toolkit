# Build firmware locally

As of 2026-09-06, the current development candidate is
[R4.5 byte-access ARMv5 fixed64](../firmware/community-r4.5/README.md), available as
`--variant community-r4.5`. It fixes R4.4's rejection of otherwise eligible
IPv4 headers at non-four-byte-aligned addresses. Actual Thumb-1 bytes pass a
complete 18,432-case alignment/checksum/ABI matrix; two full builds match.
Three byte stores finish before stock output under inherited packet ownership;
the update is not atomic. R4.5 is now installed on one research unit. In one
bounded UDP experiment, four source TTLs 32/96/32/96 arrived at the server as
49/49/49/49; four replies with source TTLs 32/96/32/96 arrived at the receiving
GL interface as 64/64/64/64. This establishes those host-tap observations, not
physical cellular-egress TTL64, direct native-hook execution or repeatability.
No firmware variant is a stable or generally flash-qualified release. Earlier
native variants and their hashes remain historical evidence; R4.3's
Cortex-A9/Thumb-2 forwarding patch is not a compatible reference.

Variant installation and qualification statements below are historical
checkpoint descriptions; see [release and research status](RELEASES.md). The
R4.2 full-container builder is available as `--variant community-r4.2`; its
standalone decompressed native-component output is not an update image.
The newer [R4.3 fixed64 forwarding release](../firmware/community-r4.3/README.md)
is available as `--variant community-r4.3`. Its full container changes the
forwarding hook and versioned UI; the separate decompressed OSLO component
is not an update image. There is no runtime Off or direction filter and no
live packet TTL qualification.

## What this workflow does

It patches a strictly verified operator-supplied MF885 BackupFw image, recalculates the
reviewed CAFE/ZIMI integrity fields, writes a new file, and independently
inspects the result. It never contacts a router and never flashes anything.

Passing every check means only that the output matches the reviewed structural
model. It does not prove bootability, compatibility, rollback, recovery, or
safe delivery. A wrong assumption can permanently brick the device.

## Inputs

Create these ignored paths locally:

```text
input/MF885_golden.bin
input/mf885-base.xml
out/
```

`MF885_golden.bin` must be a lawful backup from hardware you own. The reviewed
base is exactly 8,323,644 bytes. A reference-unit capture has raw SHA-256:

```text
2b5880fc26805918bb574d07341ea9b863f8261be34c3bf9766fac0929204531
```

The raw hash normally differs between units because the ZIMI header is encrypted
with a unit-derived key. After decryption, the supported 2.5.94 / Ver.D base must
have portable plaintext SHA-256:

```text
2bf4151a6e209845fd8d30f576577f6a66fe4cdf6d770c8bb45f0204c3486850
```

The builder also pins the decrypted header, complete partition layout, checksums
and every partition payload hash. A version string alone is never accepted.

`mf885-base.xml` is the local `GetInfo&Id=Base` response used to derive the
device-bound header key. It can contain private unit identity and default
network credentials. Keep it local and never attach it to an issue or commit.

Generated JSON reports can also contain stable pseudonymous unit fingerprints
and derived-key fingerprints. Those values are useful for local reproducibility
checks but can correlate reports from the same device and assist offline
guessing. Keep every raw report private; publish only deliberately sanitized
booleans and fixed variant hashes.

This project does not redistribute the vendor image and does not include an
automated live-backup or mode-switching path. Obtain the inputs using lawful,
device-owner tooling appropriate to your exact firmware revision.

## Inspect the backup

Python 3.10 or newer is required. The public requirements file pins the
reviewed Python dependency version; do not silently substitute a newer
cryptography stack when comparing reproducible outputs.

```bash
python tools/mf885_firmware_inspect.py \
  input/MF885_golden.bin \
  --identity-xml input/mf885-base.xml \
  --json
```

Continue only when the inspector reports `verification.status = verified`.
The builder then checks the exact reviewed portable fingerprint and partition
set. Never weaken a failed gate to make an unknown image fit.

## Build

```bash
mkdir -p out
python tools/mf885_build_variant.py --list
python tools/mf885_build_variant.py \
  --variant community-r4.5 \
  --golden input/MF885_golden.bin \
  --identity-xml input/mf885-base.xml \
  --output-dir out \
  --acknowledge-brick-risk
```

The Logs variants are research observers and `sms-r1` is a historical
send/delete prototype. Choose them only after reading their source and
manifest; `community-r4.5` above is the current experimental source profile. The
output and a JSON report are created exclusively; rerunning does not overwrite
them. Delete or move an old local output deliberately before rebuilding.

## Compare the result

```bash
python tools/mf885_firmware_inspect.py \
  input/MF885_golden.bin \
  --identity-xml input/mf885-base.xml \
  --compare out/MF885_Community_0.4.5-community-r2-native-r19-cafe-r2.bin \
  --json
```

For R4.5, the reference image is 8,323,644 bytes with SHA-256
`a5c2dc109101156d3c707231d269968c6fa65ab80e86025f4af50a0b8c764583`.
This raw hash is unit-bound; use the builder and independent inspector for your
own lawful inputs. All 63 R4.5 container conditions passed on the research image.
The exact [WebUI source snapshot](../webui/r4.5/) and
[Russian usage guide](WEB_INTERFACE_RU.md) are also available.

Historical R3.5 reference: the retained candidate is exactly 8,323,644
bytes with SHA-256
`efd74c1ff0127961f8036d0f6e51b7fec35856b128f23b3f18de5191663087f3`.
Only OSLO and WEBI may differ; the independent inspector, all 47 final
conditions and the deterministic double build must be green. The output must
preserve the exact Engineering/debugon and SystemChannel surfaces. The native
TTL code is experimental: a structural pass is not proof that its getter,
setter or packet hook works on hardware.

The following R2.6 details are retained as historical build documentation.

For `community-r2.6`, the report must show exactly six reviewed replacements,
three standalone additions (`/r26.html`, `r26app.js`, `r26ui.css`) and 18
removed locale records. Only WEBI may differ; all other partitions must remain
byte-identical. The output keeps the fixed 8,323,644-byte container and leaves
244,472 bytes of WEBI padding. The standalone entry performs zero startup
requests and does not load the legacy synchronous stack or background watchers.
Because every build starts from golden, it contains no custom Logs loader. The
vendor image retains its historical `detailed_log` route, but R2.6 neither
exposes nor reads it.
The predecessors remain immutable: `community-r2.1` stays at 10/3/18 and
`community-r2` at 10/1/18.

Community R2.5 derives the R2.4 components into unique cache-safe `r25*`
routes, applies the same strict device identity proof used by SMS,
and stores no plaintext password. Its opt-in tab convenience stores
Digest HA1, which is still a password-equivalent credential; read its manifest
and on-device warning before enabling it.

The R2.5 Modem monitor is read-only. It performs the fixed sequential GET set
`status1`, `wan`, `Engineer_parameter`; after its page is opened, watching is
on by default and uses the same set no more often than every 30 seconds while
the tab is active. Messages checking follows the same default-on/explicit-off
pattern at a 60-second minimum. Session-storage failure disables either watch.
R2.5 has no WISP scan/connect, USSD, TTL, IMEI or Engineering-mode write route.
The visible Wi-Fi-uplink section reports only fields already returned by
`status1`. Empty detailed-radio rows collapse to one concise evidence row; no
field or parser is removed. Returned RSRP/RSRQ report indices use the primary
3GPP/ETSI mappings and retain their index; SINR/RSSI and the stock bandwidth
value remain explicitly raw until their conversion contracts are proved. A
collapsed **Radio terms** panel and metric-label hover/focus text expand the
abbreviations without another router request. Two GET-only observations on the
installed predecessor returned the 107-tag engineering schema while the state
was Disabled, so the selector remains visible but read-only.

The exact reference R2.5 build has fixed size 8,323,644 bytes and
reference-unit SHA-256 is
`231e98622e19883d704edc490eed76d249e78f4303af86007b8cfaa12171a84d`,
and portable plaintext SHA-256 is
`d9d75cfed7526c108d22e7833adec0085a1637e8635807324d5dfef228c89d70`.
Two reference builds were byte-identical. Exact R2.5 is installed on the
reference device and its full 84-GET static asset surface was verified after
the POST. It is still not stable, generally flash-qualified or
restore-allowlisted; live SMS mutations, cold boot, repeatability and rollback
remain unqualified. R2.4 remains an immutable older experimental predecessor.

The exact reference R2.6 build also has fixed size 8,323,644 bytes. Its
reference-unit SHA-256 is
`de69ecf3474d74efd8dde139a7ccbb950c3db90c572936930fed20abdc579e54`,
and portable plaintext SHA-256 is
`43f770b91f2bf199ab5cd486068cb7007a2af5158fd4a1ce667bf63c73a6e39b`.
R2.6 is structurally verified and offline fake-router tested, but remains
unflashed, not stable, not generally flash-qualified and not
restore-allowlisted. Live behavior, cold boot, repeatability and rollback are
unproved.

The output header remains bound to the supplied unit. Consequently its raw
SHA-256 can differ from the reference manifest even when the portable plaintext
fingerprint and all logical changes match. Never flash a binary built for a
different unit.

## Deliberate omissions

There is no public flash command. There is no promise that a normal WebUI,
service mode, bootloader, FBF tool, or recovery route will accept the output.
Delivery and recovery must be independently established for the exact unit.
