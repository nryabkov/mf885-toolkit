# MF885 Toolkit

Public, source-only tools for the ZMI MF885:

- a Scriptable management dashboard;
- read-only firmware inspection;
- the current on-device Community WebUI, with a Russian usage guide;
- deterministic WebUI patch builders;
- reviewed source variants and tests.

This repository intentionally contains **no firmware image, device backup,
screenshot, private capture, credential, or live flashing helper**. You must
lawfully obtain the exact firmware backup from a device you own and keep it
under the ignored `input/` directory.

## Current qualification

| Version | Evidence and status |
|---|---|
| 0.4.7-dev.6 | Installed on one MF96 Ver.D /2.5.94; WAN/layout, reboot, operator-observed shutdown and physical-on recovery passed. Native unchanged; limited one-device qualification. |
| 0.4.7-dev.5 | Installed on one research MF885; Engineering Read / Enabled / changing readings / Disabled and registration recovery passed. Native unchanged from dev.4; long-term stability and exact measurement age unknown. |
| 0.4.7-dev.4 | Installed on one research MF885; guided Read / Off /64 and repeatable bidirectional IPv4 UDP host-tap behavior passed. Development version; persistence, all protocols and general recovery remain unproved. |
| R4.5 | Installed on one research MF885; exact assets checked and two bounded TTL packet observations passed. USB disconnects remain unexplained; not stable. |
| R4.6 | Quarantined after hardware test: boot/static passed; first native TTL GET timed out with USB identity drift. Do not use the editor; SET and Off were not tested. |
| R3.5, R4.2, R4.3 | Historical native profiles using ARMv7/Cortex-A9 assumptions. The common build wrapper rejects them for the verified ARMv5TE/Thumb-1 target. |

Future firmware implementation increments are tested on the actual target before
public publication. This includes exact installed assets, recovery and the new
behavior; TTL claims require real packet evidence. Offline checks are completed
before installation. Source-only changes to documentation or host-side safeguards
are validated by the checks relevant to them. No firmware here is generally
flash-qualified. See [current results and limits](docs/RELEASES.md).

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

For future firmware names, base-version compatibility and legacy aliases, see
[versioning rules (Russian)](docs/VERSIONING_RU.md) and [the registry](versioning.json).

## Community WebUI 0.4.7-dev.6

The [current interface](webui/0.4.7-dev.6/) adds WAN/PDP values and confirmed
Restart / Power off controls, removes duplicate Home navigation buttons and
improves Engineering form spacing. On matching firmware open `/c047d6.html`.
Read the [Russian usage and qualification guide](docs/WAN_POWER_047D6_RU.md).
Build from your own exact original with `--variant community-0.4.7-dev.6`.
Power off requires physical power-on; a successful HTTP response alone does not
prove the action. Earlier versions and aliases remain available.

## Previous Community WebUI 0.4.7-dev.5

The [dev.5 interface](webui/0.4.7-dev.5/) adds an explicit Engineering readings
switch with readback and delayed-response handling. On the matching firmware,
open `/c047d5.html` and select Modem. See the [Russian guide](docs/ENGINEERING_047D5_RU.md).
Detailed readings can take about a minute to appear; disabling can interrupt
mobile registration briefly, and retained values have no known measurement age.
The exact new UI was tested on the router before this source publication.
No firmware binary is supplied. Build from your own exact original using
`--variant community-0.4.7-dev.5`. Earlier versions and aliases remain available.

## Previous Community WebUI 0.4.7-dev.4

Read the [Russian TTL editor and build guide](docs/TTL_EDITOR_047D4_RU.md).
The [HTML, JavaScript, CSS and capability JSON](webui/0.4.7-dev.4/) match the
installed tested image byte for byte. On the corresponding firmware, open
`/c047d4.html`. Home, Messages, Diagnostics and Modem are inherited; TTL now
provides manual Read and two explained choices,64 andOff, with one write and
separate readback. Settings are RAM-only. This is an on-device interface, not
a standalone website. No firmware image or live flashing helper is supplied.

The actual editor and64→Off→64 IPv4 UDP host observations were tested before
this source publication. See [current results and limits](docs/RELEASES.md).
Historical [R4.5 instructions](docs/WEB_INTERFACE_RU.md) and
[R4.6 quarantine notice](docs/TTL_EDITOR_R46_RU.md) remain available.

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
  --variant community-0.4.7-dev.4 \
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

`community-r3.5` is a quarantined historical profile rejected by the common
build wrapper because its native target assumptions do not match the hardware.
Its source contract and immutable build hashes remain in
`firmware/community-r3.5/`. No native TTL variant is a stable or generally flash-qualified release.

Historical checkpoint,2026-09-06: the packet-proven research baseline was
[R4.5 byte-access ARMv5 fixed64](firmware/community-r4.5/README.md), available as
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

Historical checkpoint: the prior development increment was the [R4.3 fixed64 forwarding
release](firmware/community-r4.3/README.md), now rejected by the common wrapper
because its ARMv7/Thumb-2 assumptions do not match the verified target. It has
a reproducible full container, emitted-machine packet,
checksum and ABI tests. It has no runtime Off, direction filter or live TTL
qualification.
The earlier [R4.2 guarded context-read builder](firmware/community-r4.2/README.md)
is retained with its exact machine-code and container tests. It supplies no binary image or live runner. Per-variant READMEs,
manifests and stage metadata describe historical checkpoints; their device
installation and qualification fields are not current device status. See
[release and research status](docs/RELEASES.md).

`community-r2.6` is a historical product-oriented source profile. Its
standalone `/r26.html` paints before network I/O and replaces the legacy
synchronous startup, login, SMS-page loop and default background watchers with
explicit asynchronous requests that each have a ten-second timeout. It stores
neither the password nor Digest HA1. Messages keeps the one-POST/no-replay
Send/Delete contract, complete readback and locked unknown outcome; it renders
bounded pages progressively and paginates locally. Diagnostics and Modem stay
manual, read-only three-endpoint views. Exact candidate hashes are in
`firmware/community-r2.6/manifest.json`.

`community-r2.5` is an older installed historical predecessor. The
canonical `/index.html` remains a small English vendor interface with one link
to `/r25.html`; it loads no Community authentication, menu, Messages,
Diagnostics or CSS. The isolated modern entry keeps R2.3's exact identity and
authentication gates, one-POST/no-replay SMS mutations and manual
**Diagnostics** reads. It shows message bodies immediately, sends only after
one explicit **Send** click and displays ten messages per local page. A compact
authenticated-header pill links back to `Community 0.2.5`. Revision-unique
subordinate paths avoid silently reusing an older cached Community interface.

R2.5 keeps the read-only **Modem monitor** and fixed `status1`, `wan`,
`Engineer_parameter` sequence. Messages checking is default-on at no more than
once a minute after opening Messages; Modem monitoring is default-on at no
more than once every 30 seconds after opening Modem monitor. Each checkbox has
an explicit tab-scoped opt-out, stores no message or modem payload, and fails
closed if session storage is unavailable. Plain HTTP uses an in-page alert;
system notifications need a trusted HTTPS origin.

Diagnostics shows the stock Engineering-mode state and the unitless
`status1/rssi` vendor scale without mislabelling it as dBm. Detailed radio
rows are shown only when returned; otherwise one concise `Not returned` row
preserves the evidence without deleting any parser or field. Returned
RSRP/RSRQ report indices are mapped through the primary 3GPP/ETSI reporting
tables while retaining the index; SINR and RSSI remain explicitly raw. Metric
labels expose full English names, with the same explanations in a collapsed
**Radio terms** panel that performs no router request.

A controlled single enable/read/rollback cycle on the predecessor confirmed
that the mode changes but its immediate `Engineer_parameter` read was empty.
Two later GET-only reads while the state was confirmed Disabled returned the
full 107-tag engineering schema and detailed LTE values. Enabled is not
required for the observed reads; data freshness/cache behavior and resource
cost remain unproved, so R2.5 keeps the selector read-only. The copied
snapshots still omit raw XML, identifiers, addresses, APN, SSID, cell location
and SMS. Wi-Fi repeater scan/connect, USSD, TTL, IMEI and Engineering-mode
writes remain absent from R2.5.

R2.5 removes the same 18 Chinese, Hong Kong and Japanese locale records,
reclaiming 263,312 bytes inside WEBI without changing the fixed 8,323,644-byte
firmware size. Two cumulative reference builds are byte-identical. Their raw
SHA-256 is
`231e98622e19883d704edc490eed76d249e78f4303af86007b8cfaa12171a84d`;
portable plaintext SHA-256 is
`d9d75cfed7526c108d22e7833adec0085a1637e8635807324d5dfef228c89d70`.
Only WEBI changes and 34,528 padding bytes remain. Desktop review aligned the
Diagnostics columns and narrowed abbreviation hints to their labels. The prior
`186ca73a…ff7` and `ef7a077d…f544` candidates remain retained privately as
`superseded-unflashed`, not silently overwritten. R2.5 is installed and its
asset surface is byte-verified; SMS Send/Delete, cold boot, repeatability and
firmware rollback remain unqualified. It is not stable, generally
flash-qualified or restore-allowlisted. R2.4 is an immutable older
experimental live predecessor;
one successful installation does not qualify repeatability or rollback.

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
npm ci
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
