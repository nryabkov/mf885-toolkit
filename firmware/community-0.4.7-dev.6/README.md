# Community 0.4.7-dev.6 — WAN and power controls

Exact MF96 Ver.D / vendor2.5.94, ARMv5TE/Thumb-1, little-endian ARM EABI5.
Installed on one MF885 on2026-09-07 before source publication: boot/exact assets,
WAN/PDP, layout, reboot and operator-observed shutdown followed by physical
power-on, uptime reset and recovery checked. Development version; no general
stability or universal recovery claim. [Russian guide](../../docs/WAN_POWER_047D6_RU.md).

Eight added WebUI assets match the installed image. Native9648064B remains
SHA256686a5d3138cd6ee930d43d22704463b15c78dbcd3eb993ccd78dc29a45f663b7,
identical to dev.5/dev.2; native API r47-revision24-ttl8. Earlier TTL packet
results keep their original scope; no new packet test in dev.6.
Reference image8323644B SHA256
7711055f5fbaa713b99661ddba588070bf22c575a2a6eb97eadbd951522fcb44.
Encrypted headers are unit-dependent; another unit may produce a different hash.

Use tools/mf885_build_variant.py --variant community-0.4.7-dev.6 with your own
exact golden and identity inputs. Wrapper checks architecture, performs two
builds, compares results and independently inspects the container. Native LLVM
20.1 and thumbv5te-none-eabi / arm926ej-s compatibility profile remain pinned;
exact CPUID not newly measured. Build-time private-candidate comments remain
historical; current reference qualification is described here. Each locally
built output remains hardware-unqualified until independently tested.
No binaries or live flashing tools are distributed.
