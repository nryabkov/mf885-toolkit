# MF885 Community R2.2

`community-r2.2` is a new immutable revision built directly from a strictly
verified 2.5.94 / Ver.D backup. It preserves Community R2.1 as an installed
historical canary and fixes the two defects discovered during its authenticated
read-only UI check:

- uniquely named Community scripts and a bootstrap label map prevent a cached
  English property bundle from rendering the Diagnostics menu as `undefined`;
- the SMS mutation gate reads the exact live `status1` `sysinfo/model_name`,
  hardware and full firmware fields from one fresh `status1` response instead
  of the incorrect generic `<model>` field and a relaxed version prefix.
- the optional tab-scoped Digest resume uses a uniquely named R2.2 auth script
  and the same exact identity proof before retaining or renewing HA1.

R2.2 also introduces one scoped, legacy-browser visual system. The Remember
checkbox is restored to a native 16-pixel control aligned with its label and
warning. The dashboard Community block is compact, and Messages and Safe
Diagnostics share the same headings, toolbars, status panels, controls and
spacing. The CSS deliberately avoids Grid, Flexbox, fixed/sticky positioning,
variables and other modern-only features.

All R2.1 safety behavior remains in force. SMS review and Cancel issue no
mutation. **Send once** submits at most one `SEND_SMS` / `sms_cmd=4` request,
never retries automatically, and requires a complete Sent-folder comparison.
Inbox Delete remains a separately confirmed one-request operation with complete
absence readback. Any ambiguous mutation locks both actions until page reload.
Router command acceptance is not a delivery receipt.

Safe Diagnostics still performs exactly one sequential read of `status1`,
`wan` and `Engineer_parameter` on open or manual refresh. It has no background
polling, native `detailed_log`, request interception or raw-body storage. Its
copied snapshot remains privacy-allowlisted.

Build from an operator-supplied compatible backup that passes every reviewed
gate:

```bash
python3 tools/mf885_build_variant.py \
  --variant community-r2.2 \
  --golden /path/to/MF885_golden.bin \
  --identity-xml /path/to/mf885-base.xml \
  --output-dir /existing/output/directory \
  --acknowledge-brick-risk
```

The reference-unit artifact is 8,323,644 bytes with raw SHA-256
`80e94750bf820e1fdbf6f51b8b2462cad633e28d19571610ce744bac7e6e04d5`.
The encrypted header is unit-bound, so another compatible unit normally
produces a different raw hash. Its decrypted portable fingerprint must be
`c712f4774d8d4dc05e1a70ddd34cb8f508e705705b9cb16e3174bbb991d612ec`.

R2.2 has been built twice byte-identically and structurally verified. It has
not been flashed or tested live. It is not stable, flash-qualified or
restore-allowlisted, and rollback remains unproved. Flashing can permanently
brick the device. The public toolkit distributes no firmware binary or live
flashing helper.
