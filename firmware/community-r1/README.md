# MF885 Community R1

`community-r1` is the first product-oriented MF885 WebUI variant. It is built
directly from a strictly verified 2.5.94 / Ver.D backup and replaces only the stock SMS
page and its JavaScript. It does not inherit the experimental Logs panel.

The current scope is deliberately small:

- read and expand SMS messages;
- delete one message from the device inbox after explicit confirmation;
- keep sent, SIM and draft folders read-only;
- never send an SMS;
- never retry a mutation automatically.

Deletion uses one exact stock `DELETE_SMS` request. The page then waits for the
matching command result and reads the complete inbox again. It reports success
only when the selected unique message ID is absent. A timeout, malformed or
incomplete history, repeated ID, repeated page, or ambiguous response locks
further deletion for that page session; read-only Refresh stays available.
Deletion is also locked unless the page proves the exact MF885 / Ver.D /
2.5.94 target profile.

SMS bodies and senders are rendered only as text. The replacement SMS page
contains no page log, browser storage, third-party request, composer or
`SEND_SMS` request. The build adds no custom Logs panel; unchanged stock
diagnostic models elsewhere in the golden firmware remain present.

Build from an operator-supplied compatible backup that passes every reviewed gate:

```bash
python3 tools/mf885_build_variant.py \
  --variant community-r1 \
  --golden /path/to/MF885_golden.bin \
  --identity-xml /path/to/mf885-base.xml \
  --output-dir /existing/output/directory \
  --acknowledge-brick-risk
```

The reference-unit artifact is 8,323,644 bytes with raw SHA-256
`d42a912e31aafed4e57c6c98d94932444a0b2cf1fe0f8e223c95b3df22dae676`.
The encrypted header is unit-bound, so a build from another compatible unit
normally has a different raw hash. Its decrypted portable fingerprint must be
`6b6163036abb0b86b800b1ccc694c51bacc665231160baa911ca401fd8069ed0`.
Two independent reference captures produced byte-identical output. The inspector
verified that only the two declared WEBI records changed and every non-WEBI
partition remained byte-identical.

This is still an experimental, unflashed artifact. Structural verification is
not proof that installation, rollback or recovery will work. Flashing may
permanently brick the device; there is no warranty, no restore allowlist and no
automatic upload helper in the public toolkit.
