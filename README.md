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
  --variant community-r2.4 \
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

`community-r2.4` is the recommended product-oriented source profile. The
canonical `/index.html` remains a small English vendor interface with one link
to `/r24.html`; it loads no Community authentication, menu, Messages,
Diagnostics or CSS. The isolated modern entry keeps R2.3's exact identity and
authentication gates, one-POST/no-replay SMS mutations and manual
**Diagnostics** reads. It shows message bodies immediately, sends only after
one explicit **Send** click and displays ten messages per local page. Its
opt-in watcher checks at most once a minute while the tab is open, persists no
message data and uses only a generic in-page alert on the normal HTTP address.
Revision-unique subordinate paths avoid silently reusing an older cached
Community interface.

R2.4 adds a read-only **Modem monitor**. It reads only `status1`, `wan` and
`Engineer_parameter`; a default-off checkbox repeats the same fixed sequence
every 30 seconds while the tab is active. The copied trace strictly normalizes
known states and numeric radio metrics and omits raw unknowns, identifiers,
addresses, APN, SSID, cell location and SMS. Wi-Fi uplink/repeater state is
display-only: scan/connect writes remain disabled. USSD, TTL and IMEI controls
remain absent.

R2.4 removes the same 18 Chinese, Hong Kong and Japanese locale records,
reclaiming 263,312 bytes inside WEBI without changing the fixed 8,323,644-byte
firmware size. Its reference-unit SHA-256 is
`5bc408710afa5e78836c49da91656a8f94d804ee4fe64c53f6ef7d53786fd7db`;
portable plaintext SHA-256 is
`e33038e8a80838db6d91d347c4fc0c06480e365f577627edbf7a3cdf95e0bdc1`.
Another compatible unit normally has a different raw hash because the header
is unit-bound.

Two exact R2.4 builds were byte-identical, exactly six records were replaced,
15 were added, 18 locale records were removed, and only WEBI changed. R2.4 remains
`experimental-unflashed`; its live UI, SMS Send/Delete, cold boot,
repeatability and rollback are unqualified. It is not stable, flash-qualified
or restore-allowlisted. R2.3 remains an immutable unflashed predecessor and
installed R2.2 remains an immutable experimental live canary.

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
no automatic retry. R2.3 derives a uniquely named auth script after its strict
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
