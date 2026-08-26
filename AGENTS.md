# Public MF885 toolkit rules

This repository is the source-only public distribution generated from the
private `mf885-management` source of truth.

- Accept Scriptable code, firmware variant sources, offline builders,
  inspectors, synthetic fixtures, tests and sanitized documentation only.
- Never add firmware/device backups, generated binary images, screenshots,
  live evidence, raw captures/logs, credentials, personal or unit identifiers,
  or live flashing/service-mode helpers.
- A structural build result is not a flash or recovery guarantee. Keep every
  firmware variant status explicit and never silently replace an old hash.
- When both repositories are available in the project, make or mirror shared
  source changes in `mf885-management`, update its export allowlist, and rerun
  the exporter plus privacy/security review before publishing this repository.
- Preserve local Scriptable storage names beginning with `mf885-smsreader` for
  compatibility. Do not rewrite historical private repository/fence identities.
