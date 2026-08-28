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

## Development order

1. **Community R2.4 WebUI** — the canonical `/index.html` stays a small English
   vendor interface with one link to the isolated `/r24.html`. The modern
   entry owns the responsive UI, immediately visible message bodies, 10-item
   client-side pages, one separately confirmed inbox delete, bounded direct
   SMS Send, build identity and opt-in tab-scoped login continuity. SMS
   mutation and HA1 retention share one exact model/hardware/full-version
   identity proof. This remains WEBI-only and unflashed.
2. **Safe Diagnostics** — implemented as a separate page/menu with one manual
   sequential read of `status1`, `wan` and `Engineer_parameter`. It shows
   SIM/registration, operator/RAT/band/cell, signal, WAN, traffic and battery
   data. Its copied snapshot omits unit IDs, addresses/APN, cell location,
   credentials, phone numbers and SMS bodies; there is no background polling,
   raw capture or native `detailed_log`.
3. **Unified visual system** — scoped only to `/r24.html` and its private
   Dashboard, menu, Messages and Diagnostics assets. Shared colors,
   typography, spacing, cards and controls cover Login, Dashboard, Internet,
   Wireless, Settings, Messages and Diagnostics without changing the
   canonical vendor pages. Revision-unique paths avoid stale Community assets
   after an upgrade.
4. **Opt-in message watcher** — disabled by default and active only while the
   modern tab is open. It establishes a complete baseline, checks one inbox
   page no more often than every 60 seconds, performs a bounded full read only
   after a safe ephemeral fingerprint changes, and never stores numbers,
   bodies, XML or message IDs. Plain HTTP gets a generic in-page badge; system
   notifications require a secure context and an explicit permission gesture.
5. **Read-only Modem monitor** — one fixed sequential read of `status1`, `wan`
   and `Engineer_parameter`, with a default-off 30-second tab-local watcher,
   bounded RAM samples and a strictly normalized safe trace. It may display
   firmware-reported Wi-Fi-uplink state but has no scan/connect, USSD, TTL or
   IMEI write path.
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

## Release discipline

Each milestone changes one capability class at a time, keeps every mutation
serialized and explicit, and never automatically repeats an ambiguous write.
Golden restoration is a future rollback qualification experiment, not a
routine prerequisite before development. Until repeatable delivery, cold boot
and independent recovery are proved, all generated firmware remains
experimental and non-stable.
