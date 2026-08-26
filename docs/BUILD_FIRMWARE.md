# Build firmware locally

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
  --variant community-r2.1 \
  --golden input/MF885_golden.bin \
  --identity-xml input/mf885-base.xml \
  --output-dir out \
  --acknowledge-brick-risk
```

The Logs variants are research observers and `sms-r1` is a historical
send/delete prototype. Choose them only after reading their source and
manifest; `community-r2.1` is the recommended product-oriented profile. The
output and a JSON report are created exclusively; rerunning does not overwrite
them. Delete or move an old local output deliberately before rebuilding.

## Compare the result

```bash
python tools/mf885_firmware_inspect.py \
  input/MF885_golden.bin \
  --identity-xml input/mf885-base.xml \
  --compare out/MF885_Community_0.2.1-community-r2-cafe-r2.bin \
  --json
```

For `community-r2.1`, the report must show exactly 10 reviewed replacements,
three additions (Community auth, Diagnostics HTML and Diagnostics JavaScript),
and 18 removed locale records. Only WEBI may differ; all other partitions must
remain byte-identical. The output keeps the fixed 8,323,644-byte container and
turns the removed locale space into WEBI padding. Because every build starts
from golden, it contains no custom Logs loader or native `detailed_log` panel.
The predecessor `community-r2` remains immutable at 10 replacements, one
addition and 18 removals.

Community R2.1 inherits R2's auth component and stores no plaintext password.
Its opt-in tab convenience stores
Digest HA1, which is still a password-equivalent credential; read its manifest
and on-device warning before enabling it.

The output header remains bound to the supplied unit. Consequently its raw
SHA-256 can differ from the reference manifest even when the portable plaintext
fingerprint and all logical changes match. Never flash a binary built for a
different unit.

## Deliberate omissions

There is no public flash command. There is no promise that a normal WebUI,
service mode, bootloader, FBF tool, or recovery route will accept the output.
Delivery and recovery must be independently established for the exact unit.
