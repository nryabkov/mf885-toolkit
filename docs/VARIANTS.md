# Source variant registry

All variants are source-only and built locally from a strictly verified compatible backup.
None is distributed as a firmware binary.

| Wrapper name | Logical ID | Source | Status |
|---|---|---|---|
| `community-r2.1` | `0.2.1-community-r2-cafe2` | `firmware/community-r2.1/` plus exact R2 derivation rules | Recommended source: immutable R2 features plus bounded one-recipient SMS Send and a separate manual Safe Diagnostics page/menu; exact static state observed once on reviewed hardware; mutations, cold boot and rollback unqualified |
| `community-r2` | `0.2-community-r2-cafe2` | `firmware/community-r2/` plus exact derivation rules | Superseded immutable source: Community R1 SMS safety, native Messages menu, home build badge/Inbox shortcut, reviewed English fixes, English-only locale set and opt-in tab-scoped HA1 login; structurally verified and unflashed |
| `community-r1` | `0.1-community-r1-cafe2` | `firmware/community-r1/` | Superseded minimal source: installed once with exact static assets and an authenticated empty inbox; deletion and rollback remain unqualified; no composer, send request, page log or custom Logs panel |
| `logs-r1` | `0.0-logs-r1-auth-r4-cafe2` | `firmware/webui-canary-logs/` | Research-only authenticated observer; not part of the product firmware |
| `logs-r2` | `0.0-logs-r2-auth-r4-cafe2` | `firmware/webui-canary-logs-r2/` | Research-only bounded observer; not part of the product firmware |
| `sms-r1` | `0.0-sms-r1-cafe2` | `firmware/webui-sms-r1/` | Historical feature prototype with send/delete controls; not the recommended build |
| — | `0.0-ussd-r1` | `firmware/webui-ussd-r1/` | Audit-only scaffold; deliberately unbuildable because the native WebUI contract is unresolved |

The `firmware/fbf-webui-noflash/` material is inspection/simulation research,
not a delivery recommendation. Its name is literal: do not submit it to a
device merely because it reconstructs offline.

Earlier Logs artifacts are retained in their manifests as quarantined history.
Some omitted the stock Digest header; later revisions fixed authentication but
did not mask every WAN username and IPv6 representation before Copy/Export.
`community-r1`, `community-r2` and `community-r2.1` are built directly from
golden rather than layered on a Logs artifact. R2.1 adds Safe Diagnostics, not
the native `detailed_log` canary or a raw request/console observer.

## Adding a variant

1. Add source and a manifest under `firmware/`.
2. Pin the exact source size and SHA-256 in the appropriate builder profile.
3. Add it to `tools/mf885_build_variant.py` only after the independent inspector
   and exact logical-delta tests pass.
4. Add negative tests for extra records, non-WEBI changes, padding, truncation,
   input mismatch, output overwrite, and forbidden routes.
5. Keep `flash_qualified`, `restore_allowlisted`, and `stable` false until each
   claim has its own evidence. One successful device is not general proof.
