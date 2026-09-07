# Community 0.4.7-dev.5 — Engineering readings editor

Exact MF96 Ver.D / vendor2.5.94, ARMv5TE/Thumb-1, little-endian ARM EABI5.
Installed on one MF885 on2026-09-07: exact boot/assets, actual browser Read →
Enabled → changing readings → Disabled and registration recovery verified.
Development version; long-term stability, all radios and general recovery are
unproved. [Russian usage guide](../../docs/ENGINEERING_047D5_RU.md).

The seven [WebUI additions](../../webui/0.4.7-dev.5/) match the installed image.
release.py derives cumulative assets from the pinned dev.4 source. Native OSLO
is unchanged:9648064B, SHA256
686a5d3138cd6ee930d43d22704463b15c78dbcd3eb993ccd78dc29a45f663b7.
Native API remains r47-revision24-ttl8. dev.4 TTL packet observations retain
their original scope; the dev.5 experiment did not repeat packet testing.

Build with tools/mf885_build_variant.py --variant community-0.4.7-dev.5 and
your own exact golden/identity inputs. The wrapper checks architecture first,
builds twice, compares results and independently inspects the container. Native
LLVM20.1 toolchain remains pinned to thumbv5te-none-eabi / arm926ej-s compatibility
profile, Thumb1, no VFP/NEON. Exact CPUID was not newly measured. Metadata,
instructions, ABI/alignment/reach and complete OSLO equality are checked.

Reference unit image:8323644B, SHA256
645665bfbe8d352dae76c701c42a11a6a1ee287018fcd8b7337d23cfd157dd9b.
The encrypted header is unit-dependent; another unit's raw image hash may differ.
Original build-time comments describing a private candidate remain historical;
current qualification is documented above. No binaries or live flash tools
are distributed. Source compilation is not a universal flashing qualification.
