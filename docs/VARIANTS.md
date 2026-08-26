# Source variant registry

All variants are source-only and built locally from the exact supported backup.
None is distributed as a firmware binary.

| Wrapper name | Logical ID | Source | Status |
|---|---|---|---|
| `logs-r1` | `0.0-logs-r1-auth-r4-cafe2` | `firmware/webui-canary-logs/` | Authenticated poll with pre-storage privacy masking; current source is offline structurally verified and unflashed |
| `logs-r2` | `0.0-logs-r2-auth-r4-cafe2` | `firmware/webui-canary-logs-r2/` | Bounded authenticated observer with pre-storage privacy masking; offline structural verification only |
| `sms-r1` | `0.0-sms-r1-cafe2` | `firmware/webui-sms-r1/` | Offline structural/UI tests only; includes explicit SMS mutation controls |
| — | `0.0-ussd-r1` | `firmware/webui-ussd-r1/` | Audit-only scaffold; deliberately unbuildable because the native WebUI contract is unresolved |

The `firmware/fbf-webui-noflash/` material is inspection/simulation research,
not a delivery recommendation. Its name is literal: do not submit it to a
device merely because it reconstructs offline.

Earlier Logs artifacts are retained in their manifests as quarantined history.
Some omitted the stock Digest header; later revisions fixed authentication but
did not mask every WAN username and IPv6 representation before Copy/Export.

## Adding a variant

1. Add source and a manifest under `firmware/`.
2. Pin the exact source size and SHA-256 in the appropriate builder profile.
3. Add it to `tools/mf885_build_variant.py` only after the independent inspector
   and exact logical-delta tests pass.
4. Add negative tests for extra records, non-WEBI changes, padding, truncation,
   input mismatch, output overwrite, and forbidden routes.
5. Keep `flash_qualified`, `restore_allowlisted`, and `stable` false until each
   claim has its own evidence. One successful device is not general proof.
