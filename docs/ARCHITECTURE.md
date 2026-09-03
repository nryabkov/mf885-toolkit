# Architecture and roadmap

## Standalone target

The finished community firmware must run entirely on the MF885. A GL.iNet
router, desktop, VDS, USB hub or cloud service may be used in a laboratory to
inspect, transfer or recover an image, but none may be a runtime dependency of
the installed firmware or its management UI.

Every variant is rebuilt from the exact supported MF885 2.5.94 golden image.
Installed canaries are never used as a base. Generic MF96 2.5.96 is a
comparison source only: it targets a different hardware/version profile and
does not authorize cross-flashing or reuse of native offsets.

## Historical development through R3.4

1. **Community R2.6 WebUI** — the canonical `/index.html` stays a small English
   vendor interface with one link to the isolated `/r26.html`. The standalone
   modern entry paints before I/O, loads no legacy controller stack, performs
   only explicit asynchronous requests with ten-second deadlines, and starts
   no background watcher. It owns immediately visible message bodies, 10-item
   client-side pages, one separately confirmed inbox delete and bounded direct
   SMS Send. Credentials remain RAM-only. The exact model/hardware/full-version
   proof gates authentication and all later requests. This historical
   milestone remained WEBI-only and was later installed and superseded.
2. **Safe Diagnostics** — implemented as a separate page/menu with one manual
   sequential read of `status1`, `wan` and `Engineer_parameter`. It shows
   SIM/registration, operator/RAT/band/cell, signal, WAN, traffic and battery
   data. Its copied snapshot omits unit IDs, addresses/APN, cell location,
   credentials, phone numbers and SMS bodies; there is no background polling,
   raw capture or native `detailed_log`. Compact metric labels expose full
   English names through a closed-by-default **Radio terms** panel and
   hover/focus help, with no extra router request.
3. **Unified visual system** — scoped only to `/r25.html` and its private
   Dashboard, menu, Messages and Diagnostics assets. Shared colors,
   typography, spacing, cards and controls cover Login, Dashboard, Internet,
   Wireless, Settings, Messages and Diagnostics without changing the
   canonical vendor pages. Revision-unique paths avoid stale Community assets
   after an upgrade.
4. **Tab-local message watcher** — enabled by default only after Messages is
   opened and active only while the modern tab is open. An explicit opt-out is
   remembered for that tab; unavailable session storage disables the watcher.
   It establishes a complete baseline, checks one inbox
   page no more often than every 60 seconds, performs a bounded full read only
   after a safe ephemeral fingerprint changes, and never stores numbers,
   bodies, XML or message IDs. Plain HTTP gets a generic in-page badge; system
   notifications require a secure context and an explicit permission gesture.
5. **Read-only Modem monitor** — one fixed sequential read of `status1`, `wan`
   and `Engineer_parameter`, with a default-on-after-open 30-second tab-local
   watcher, explicit opt-out and storage-failure fail-closed behavior, bounded
   RAM samples and a strictly normalized safe trace. It may display
   firmware-reported Wi-Fi-uplink state but has no scan/connect, USSD, TTL or
   IMEI write path. RSRP/RSRQ report indices use their proved 3GPP/ETSI
   mappings and retain the index; SINR/RSSI stay explicitly raw. Engineering
   state is visible but read-only because detailed values were observed while
   Disabled and its freshness/resource semantics remain unresolved.
6. **Narrow native control plane** — a version-bound, authenticated community
   model with bounded inputs/outputs and no generic command execution. A
   harmless version/echo endpoint comes before state-changing features.
7. **USSD** — one in-flight operation, explicit result/cancel state, bounded
   timeout and no automatic replay. Native request/result ownership is still
   unresolved.
8. **AT reference and query allowlist** — static command documentation plus a
   small reviewed set of read-only queries. Raw arbitrary AT is not a default
   WebUI capability; reset, flash and service-mode commands remain denied.
9. **TTL** — first as disabled-by-default RAM state, only after a forwarded
   IPv4 hook and checksum-safe enable/disable path are proved. Persistence and
   IPv6 are separate milestones.
10. **IMEI laboratory workflow** — only after original-value backup, atomicity,
   post-write readback and restoration are independently demonstrated. It is
   not bundled with the first TTL experiment.
11. **Repeater/WISP research** — concurrent station plus access-point support is
   not established. Routed WISP is the first plausible target; transparent WDS
   is not promised.

## Current cumulative development order

1. **Community R3.5 TTL** — keep boot state Off and volatile; prove one strict
   same-model read before any write, then separately qualify setter/readback
   and the real forwarded IPv4 packet with checksum repair. The UI accepts
   `off` or canonical `1..255` and offers recommended presets without limiting
   the operator to them.
2. **Community R3.6 repeater/WISP** — add routed station-plus-AP behavior only
   after coexistence, recovery and UI state ownership are proved. Transparent
   WDS is not promised.
3. **Community R3.7 on-device USSD** — no GL.iNet runtime dependency: one
   request in flight, bounded result states, SMS-delivered and direct replies,
   no automatic replay.
4. **Community R3.8 IMEI laboratory workflow** — backup the exact original,
   require explicit mutation, verify readback and demonstrate restoration
   before any broader product claim.
5. **Community R3.9 cumulative integration** — combine only independently
   qualified milestones and rerun the complete UI, native, device and recovery
   evidence set. A feature remains labelled unproved until its own live proof
   is green.

## Release discipline

Each milestone changes one capability class at a time, keeps every mutation
serialized and explicit, and never automatically repeats an ambiguous write.
Golden restoration is a future rollback qualification experiment, not a
routine prerequisite before development. Until repeatable delivery, cold boot
and independent recovery are proved, all generated firmware remains
experimental and non-stable.
