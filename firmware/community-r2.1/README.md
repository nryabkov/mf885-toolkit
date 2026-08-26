# MF885 Community R2.1

`community-r2.1` is a new immutable revision built directly from a strictly
verified 2.5.94 / Ver.D backup. It does not layer changes on an installed R1 or
R2 image, and it does not replace the published Community R2 artifact.

It retains Community R2's English-only UI, Messages navigation, confirmed
single-message inbox deletion, version badge, reviewed text fixes and optional
`Remember me in this tab` behavior. It adds:

- an SMS composer with a separate review step and a red **Send once** button;
- one-recipient UTF-16BE/`UNICODE` sending, limited to four UCS-2 segments;
- a top-level **Diagnostics** tab and a Diagnostics link on the home page;
- manual, read-only `status1`, `wan` and `Engineer_parameter` reads;
- a privacy-allowlisted `mf885-community-safe-diagnostics/v1` snapshot.

SMS sending accepts an optional leading `+` followed by 3–15 digits and 1–268
BMP characters. Surrogates, NUL and control characters other than line breaks
are rejected. Review and Cancel send no mutation. **Send once** submits exactly
one `SEND_SMS` / `sms_cmd=4` request with no automatic retry. Only matching
command 4 / status 3 means that the router accepted the command; it is not a
delivery receipt. Complete Sent-folder reads before and after submission are
required to claim a new matching Sent record. Any ambiguous mutation or
incomplete mutation readback locks both Send and Delete until the page reloads,
while read-only Refresh remains available.

Diagnostics performs exactly one sequential read of `status1`, `wan` and
`Engineer_parameter` when opened and after each manual refresh. It has no
background polling, native `detailed_log`, canary Logs panel, request/console
interception or event log. Values are rendered as text. The safe copied report
excludes raw XML, credentials, unit identifiers, addresses, APN and cell
location values, plus all phone numbers and SMS content.

The inherited Remember option stores no plaintext password, but its Digest HA1
is a password-equivalent credential. Use it only in a trusted tab and device.

Build from an operator-supplied compatible backup that passes every reviewed
gate:

```bash
python3 tools/mf885_build_variant.py \
  --variant community-r2.1 \
  --golden /path/to/MF885_golden.bin \
  --identity-xml /path/to/mf885-base.xml \
  --output-dir /existing/output/directory \
  --acknowledge-brick-risk
```

The reference-unit artifact is 8,323,644 bytes with raw SHA-256
`51bd396c69e9c8db96249455092634b6b54552f64f5c4daee6f710b644759c95`.
The encrypted header is unit-bound, so another compatible unit normally
produces a different raw hash. Its decrypted portable fingerprint must be
`9b7312ae365f3a381a060b4d28a0de719e64aaffe29893dcb2601987e9dfcd2a`.

This exact image was installed once on the reviewed MF885 / Ver.D unit in a
separately fenced, zero-retry experiment. Postboot checks matched all 13
reviewed assets, proved all 18 removed locale routes absent and proved the same
unit returned. Installation is qualified from the observed postboot state, not
from a transport-response claim. Neither SMS Send nor Delete has been tested
live.

Read-only browser validation later proved the Remember reload/logout flow,
reads of all four empty Messages folders, the three fixed Diagnostics reads and
the safe copied snapshot. It also found two fail-closed defects: Diagnostics is
labelled `undefined` in the menu, and the SMS mutation identity gate remains
closed on the exact unit. The current artifact is therefore not semantic-UI
qualified; a later immutable revision must fix both defects.

The image remains an experimental live-qualified canary. It is not stable,
flash-qualified or restore-allowlisted, and one successful installation does
not prove rollback, cold-boot recovery, repeatability or general compatibility.
Flashing can permanently brick the device. The public toolkit distributes no
firmware binary or live flashing helper.
