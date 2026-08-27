# MF885 Toolkit

Public, source-only tools for the ZMI MF885:

- a Scriptable management dashboard;
- read-only firmware inspection;
- deterministic WebUI patch builders;
- reviewed source variants and tests.

This repository intentionally contains **no firmware image, device backup,
screenshot, private capture, credential, or live flashing helper**. You must
lawfully obtain the exact firmware backup from a device you own and keep it
under the ignored `input/` directory.

## Severe risk warning

**A generated image can permanently brick the router.** Structural validation
does not prove that flashing is accepted, power-loss-safe, recoverable, or
compatible with another MF885 revision. There is no proven universal rollback
or rescue procedure. Neither the authors nor contributors guarantee fitness,
recovery, data preservation, network availability, or device survival.

Use this project entirely at your own risk. Verify every hash and report, keep
an independent backup, do not experiment on hardware you cannot afford to
lose, and never treat the word “verified” as permission to flash.

The public **firmware workflow** provides build and inspection only. It has no
compiled, allowlisted firmware-upload transport and does not switch service
modes, reboot a router, or attempt recovery.

The separate Scriptable dashboard is an interactive management client. It
contains clearly labelled, confirmation-gated controls such as SMS mutation,
cellular changes, reboot, and power-off for an exact detected device profile.
Those controls can interrupt service or lose data; read their source and use
them independently of the firmware workflow. They never make a firmware image
safe to install.

## AI assistance disclosure

This project is human-directed and was developed with substantial assistance
from AI coding and research systems. Source and stated results were reviewed
and tested to the extent documented, but AI involvement is not a warranty and
may leave errors or incorrect assumptions. Independently inspect everything
before relying on it.

## Scriptable dashboard

1. Install [Scriptable](https://scriptable.app/) on iOS.
2. Create a new Scriptable script and paste the contents of `loader.js`.
3. Run it while the phone can reach both GitHub and the MF885.
4. The loader pins every application update to one Git commit before launching
   it. On first run it asks for the current router admin password and stores it
   only in Scriptable Keychain. Local storage names remain
   `mf885-smsreader*` for compatibility with existing installations.

The default upstream is `nryabkov/mf885-toolkit`. Copy
`mf885-smsreader-config.json` into Scriptable Documents only when you need to
override the router address, branch, storage, polling, or experimental UI.
Debug collection is off by default. When explicitly enabled, copyable debug
snapshots always mask credentials, SMS, phone numbers, unit identifiers,
SSID/APN, MAC addresses and IP addresses.

Translation is disabled until you configure an endpoint. Pressing
**Translate** sends the selected SMS body to that third-party service. Use an
HTTPS endpoint you trust, or leave the setting empty to keep SMS text local.

## Build a firmware variant from your own backup

The short version is:

```text
input/MF885_golden.bin   # your own exact BackupFw image; never commit it
input/mf885-base.xml     # your own GetInfo&Id=Base response; never commit it
```

Then:

```bash
python3 --version  # Python 3.10 or newer is required
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p out
python tools/mf885_build_variant.py --list
python tools/mf885_build_variant.py \
  --variant community-r2.2 \
  --acknowledge-brick-risk
```

The wrapper performs no network or device I/O. It refuses to overwrite an
existing output and delegates to the fail-closed builder and independent
inspector. The supported backup is exactly 8,323,644 bytes and must match the
reviewed 2.5.94 / Ver.D decrypted header, partition layout and every partition
payload. Its portable plaintext SHA-256 is
`2bf4151a6e209845fd8d30f576577f6a66fe4cdf6d770c8bb45f0204c3486850`.
The raw backup hash is unit-specific because its header is encrypted; the
reference-unit raw hash is documented only as a reproducibility example. Any
semantic mismatch is rejected; do not bypass this check or use another unit's
built binary.

`community-r2.2` is the recommended product-oriented source profile. It keeps
R2.1's review-first, one-POST/no-replay SMS sender and manual **Diagnostics**
tab, fixes the installed canary's stale-label cache path and exact live
`status1` identity gate, and adds one compact legacy-safe visual system for
login, Home, Messages and Diagnostics. It never restores the old native
`detailed_log` observer, raw request capture or background polling. R2.1
remains an immutable installed canary rather than being silently replaced.

R2.2 still removes 18 Chinese, Hong Kong and Japanese locale records,
reclaiming 263,312 bytes inside WEBI without changing the fixed 8,323,644-byte
firmware size. Its reference-unit SHA-256 is
`80e94750bf820e1fdbf6f51b8b2462cad633e28d19571610ce744bac7e6e04d5`;
another compatible unit normally has a different raw hash because the header
is unit-bound.

The exact R2.2 reference build is deterministic, structurally verified and was
installed once through the reviewed Genesys-hub one-shot path. All 21 exact
R2.2 assets, 18 locale removals, same-unit USB/RNDIS recovery and cleanup were
verified; the English login page and native-sized Remember control were also
observed after reload. Its status is `experimental-live-qualified-canary`;
authenticated semantic UI, SMS Send/Delete, cold-boot persistence,
repeatability and rollback remain unqualified. It is not stable,
flash-qualified or restore-allowlisted.

Authenticated read-only validation of immutable R2.1 proved Remember reload/logout, reads
of all four empty Messages folders, the three fixed Diagnostics reads and the
safe copied snapshot. It found two fail-closed UI defects: the Diagnostics menu
label renders as `undefined`, and the SMS mutation identity gate stays closed.
R2.1 is therefore not semantic-UI qualified; R2.2 contains the offline-tested
fixes without rewriting the installed artifact's history.

The optional **Remember me in this tab** control stores Digest HA1 in
`sessionStorage`, not the plaintext password. HA1 is nevertheless a
password-equivalent credential readable by same-origin page scripts. Use it
only on a trusted device; sign-out, authentication failure, ten minutes without
keyboard/touch/mouse activity, or normally closing the tab clears it. Reload
uses one fresh challenge, one login and one protected exact-version read, with
no automatic retry. R2.2 loads a uniquely named auth script after its strict
model/hardware/full-version bootstrap and applies that same proof before HA1 is
retained or renewed. The Logs variants remain research material.

Inspector and builder reports can contain stable pseudonymous fingerprints of
your unit and derived-key checks. Keep reports private and never attach raw
reports or identity XML to a public issue.

Read [the complete build guide](docs/BUILD_FIRMWARE.md) and
[variant registry](docs/VARIANTS.md) before doing anything with the output.
Version and stability labels are defined in [RELEASES.md](docs/RELEASES.md).
The standalone target and feature order are recorded in
[ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tests

```bash
python -m unittest discover -s tests -p '*_test.py'
npm install
npm test
```

Some firmware tests require the exact ignored golden image and will skip when
it is absent. Tests prove only the behavior they name.

## Contributions

New firmware variants must be source-only, deterministic, hash-pinned,
independently inspected, and clearly marked as structural-only until actual
qualification evidence exists. Do not submit firmware binaries, device
backups, screenshots, personal identifiers, credentials, or raw router logs.

See [SECURITY.md](SECURITY.md) for reporting sensitive issues and
[NOTICE.md](NOTICE.md) for vendor-content, trademark and non-affiliation terms.
