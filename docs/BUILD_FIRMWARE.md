# Build firmware locally

## What this workflow does

It patches an exact operator-supplied MF885 BackupFw image, recalculates the
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

`MF885_golden.bin` must be a lawful backup from hardware you own. The currently
reviewed base is 8,323,644 bytes with SHA-256:

```text
2b5880fc26805918bb574d07341ea9b863f8261be34c3bf9766fac0929204531
```

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

Continue only when the inspector reports `verification.status = verified` and
the exact supported size/hash above. Never weaken a failed gate to make an
unknown image fit.

## Build

```bash
mkdir -p out
python tools/mf885_build_variant.py --list
python tools/mf885_build_variant.py \
  --variant logs-r1 \
  --golden input/MF885_golden.bin \
  --identity-xml input/mf885-base.xml \
  --output-dir out \
  --acknowledge-brick-risk
```

Choose `logs-r2` or `sms-r1` only after reading its source and manifest. The
output and a JSON report are created exclusively; rerunning does not overwrite
them. Delete or move an old local output deliberately before rebuilding.

## Compare the result

```bash
python tools/mf885_firmware_inspect.py \
  input/MF885_golden.bin \
  --identity-xml input/mf885-base.xml \
  --compare out/MF885_Community_0.0-logs-r1-auth-r4-cafe-r2.bin \
  --json
```

For Logs variants, only `WEBI:www/index.html` and the appended reviewed script
may differ logically; all non-WEBI partitions must remain byte-identical. The
SMS variant has its own exact two-record allowlist.

## Deliberate omissions

There is no public flash command. There is no promise that a normal WebUI,
service mode, bootloader, FBF tool, or recovery route will accept the output.
Delivery and recovery must be independently established for the exact unit.
