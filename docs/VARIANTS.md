# Source variant registry

All variants are source-only and built locally from a strictly verified compatible backup.
None is distributed as a firmware binary.

| Wrapper name | Logical ID | Source | Status |
|---|---|---|---|
| `community-r3.5` | `0.3.5-community-r2-native-r9-cafe2` | `firmware/community-r3.5/` plus exact golden native/WEBI derivation rules | Recommended source: cumulative UI/SMS plus experimental modular same-model TTL; deterministic and structurally green, unflashed; live getter/setter/packet path, persistence, cold boot, repeatability and rollback unproved |
| — | `0.3.4-community-r2-native-r7-cafe2` | `firmware/community-r3.4/` | Installed experimental predecessor: strict diagnostic no-op callback proved live; this proves callback attachment only, not TTL |
| — | `0.3.0`–`0.3.3` native research line | `firmware/community-r3.0/` through `firmware/community-r3.3/` | Immutable cumulative TTL research predecessors; retained findings, not recommended outputs |
| `community-r2.9` | `0.2.9-community-r2-cafe2` | `firmware/community-r2.9/` plus exact golden derivation rules | Installed historical UI/SMS predecessor with universal refresh and on-device help; no native TTL |
| `community-r2.6` | `0.2.6-community-r2-cafe2` | `firmware/community-r2.6/` plus exact golden derivation rules | Historical installed predecessor: standalone non-blocking UI, zero startup I/O, explicit async login/reads, bounded progressive Messages and one-POST/no-replay Send/Delete; WEBI-only and not generally allowlisted |
| `community-r2.5` | `0.2.5-community-r2-cafe2` | `firmware/community-r2.5/` plus exact golden/R2.4 derivation rules | Installed immutable experimental predecessor: exact post-POST asset surface verified; compact authenticated header/version, default-on tab-local watchers, read-only Engineering state and standards-mapped RSRP/RSRQ indices; not stable or restore-allowlisted, and live SMS mutations/cold boot/repeatability/rollback remain unqualified |
| `community-r2.4` | `0.2.4-community-r2-cafe2` | `firmware/community-r2.4/` plus exact golden/R2.3 derivation rules | Older installed experimental predecessor: exact assets, authenticated navigation, Diagnostics and bounded 30-second modem polling were observed; SMS mutations, cold boot, repeatability and rollback unqualified |
| `community-r2.3` | `0.2.3-community-r2-cafe2` | `firmware/community-r2.3/` plus exact golden/R2.2 derivation rules | Immutable unflashed predecessor: minimal canonical vendor entry plus isolated modern `/r23.html`, SMS, opt-in inbox checks and Safe Diagnostics; reproducible WEBI-only build and not allowlisted |
| `community-r2.2` | `0.2.2-community-r2-cafe2` | `firmware/community-r2.2/` plus exact R2.1 derivation rules | Installed immutable experimental canary: exact static assets, locale removals and same-unit USB/RNDIS recovery verified; English login/Remember visible; authenticated UI, SMS mutations, cold boot and rollback unqualified |
| `community-r2.1` | `0.2.1-community-r2-cafe2` | `firmware/community-r2.1/` plus exact R2 derivation rules | Installed live canary: exact static state, Remember and read-only Diagnostics/Messages observed; Diagnostics menu label and SMS mutation identity gate have fail-closed live defects; mutations, cold boot and rollback unqualified |
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
`community-r1`, `community-r2`, `community-r2.1`, `community-r2.2`,
`community-r2.3`, `community-r2.4`, `community-r2.5`, `community-r2.6`,
`community-r2.7`, `community-r2.8`, `community-r2.9` and the Community R3.x
line are built directly from golden rather than layered on a Logs
artifact. R2.1 and later add Safe Diagnostics, not the native `detailed_log`
canary or a raw request/console observer.

## Adding a variant

1. Add source and a manifest under `firmware/`.
2. Pin the exact source size and SHA-256 in the appropriate builder profile.
3. Add it to `tools/mf885_build_variant.py` only after the independent inspector
   and exact logical-delta tests pass.
4. Add negative tests for extra records, non-WEBI changes, padding, truncation,
   input mismatch, output overwrite, and forbidden routes.
5. Keep `flash_qualified`, `restore_allowlisted`, and `stable` false until each
   claim has its own evidence. One successful device is not general proof.
