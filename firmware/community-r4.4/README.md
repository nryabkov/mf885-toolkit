# Community R4.4: ARMv5/Thumb-1 fixed TTL 64

This experimental full container corrects the native build profile and call
encoding used by R4.3. It has not been installed or hardware-qualified.

The old Cortex-A9/Thumb-2 target was inconsistent with the ARM9 platform
evidence. The old direct BL also exceeds Thumb-1's approximately ±4 MiB range.
R4.4 explicitly selects an ARMv5TE/Thumb-1 compatibility profile; ARM926EJ-S is
a compiler profile, not a claim that the physical custom Marvell core is that
exact model. The emitted object reports ARMv5TE and Thumb-1. Historical native
variants retain their original bytes for analysis, not as compatible releases.

The new 12-byte callsite loads an aligned full Thumb entry address, calls it
with BLX register and branches over its literal on return. An 8-byte entry
stub plus 148-byte helper fits the original 160-byte reservation. The helper
loads the original output pointer from netif+0x58, sets eligible forwarded
IPv4 TTL to 64, updates the IPv4 checksum and calls the stock output once.
Only the aligned word at header+8 may change; TTL0/1, malformed or insufficient
headers pass unchanged. Scope remains both directions through this callsite,
with no runtime Off, direction filter or diagnostic callback.

Two complete builds and their reports match byte-for-byte. All 60 container
conditions pass and an independent container inspector reports verified.
Only OSLO and WEBI payloads change from the reviewed stock image, together
with required container integrity fields. The distinct UI is `/r44.html`.
All portable and reference-unit hashes are in [manifest.json](manifest.json).

The public tests independently decode the complete raw Thumb-1 call chain,
including its return into stock code. They cover every emitted instruction,
TTL0..255, IHL5/6/15, protocols1/6/17, invalid headers, checksum positive-zero,
and both ARM/Thumb output-pointer states at a modeled ABI boundary. The
external output function body is not emulated. Hardware mapping, CPU behavior,
NAT, actual TTL on the network, stability and recovery remain unproved.

Build locally with `--variant community-r4.4` using the documented exact
stock/identity inputs. The native component alone is not an update image.
The builder never accesses a router or flashes the generated container.
