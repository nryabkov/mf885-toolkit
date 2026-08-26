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

1. **Community R2.1 WebUI** — English-only UI, native Messages navigation,
   read/expand SMS, one explicitly confirmed inbox delete, review-first bounded
   SMS Send, build identity on the home page, and opt-in tab-scoped login
   continuity. This remains WEBI-only.
2. **Safe Diagnostics** — implemented as a separate page/menu with one manual
   sequential read of `status1`, `wan` and `Engineer_parameter`. It shows
   SIM/registration, operator/RAT/band/cell, signal, WAN, traffic and battery
   data. Its copied snapshot omits unit IDs, addresses/APN, cell location,
   credentials, phone numbers and SMS bodies; there is no background polling,
   raw capture or native `detailed_log`.
3. **Unified visual system** — in the next separate revision, consolidate Home,
   Messages and Diagnostics around shared colors, typography, spacing, cards,
   buttons and loading/error/confirmation states. Keep this as a separate
   WEBI-only revision so visual changes do not obscure functional validation.
4. **Narrow native control plane** — a version-bound, authenticated community
   model with bounded inputs/outputs and no generic command execution. A
   harmless version/echo endpoint comes before state-changing features.
5. **USSD** — one in-flight operation, explicit result/cancel state, bounded
   timeout and no automatic replay. Native request/result ownership is still
   unresolved.
6. **AT reference and query allowlist** — static command documentation plus a
   small reviewed set of read-only queries. Raw arbitrary AT is not a default
   WebUI capability; reset, flash and service-mode commands remain denied.
7. **TTL** — first as disabled-by-default RAM state, only after a forwarded
   IPv4 hook and checksum-safe enable/disable path are proved. Persistence and
   IPv6 are separate milestones.
8. **IMEI laboratory workflow** — only after original-value backup, atomicity,
   post-write readback and restoration are independently demonstrated. It is
   not bundled with the first TTL experiment.
9. **Repeater/WISP research** — concurrent station plus access-point support is
   not established. Routed WISP is the first plausible target; transparent WDS
   is not promised.

## Release discipline

Each milestone changes one capability class at a time, keeps every mutation
serialized and explicit, and never automatically repeats an ambiguous write.
Golden restoration is a future rollback qualification experiment, not a
routine prerequisite before development. Until repeatable delivery, cold boot
and independent recovery are proved, all generated firmware remains
experimental and non-stable.
