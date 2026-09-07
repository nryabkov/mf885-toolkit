# Community 0.4.7-dev.4 — guided TTL editor

For the exact MF96 Ver.D / vendor 2.5.94 base, ARMv5TE/Thumb-1,
little-endian ARM EABI5. Tested on one MF885 on 2026-09-07: installed assets,
manual Read → Off → 64, separate readbacks and repeated bidirectional IPv4 UDP
host-tap observations. This is a development version, not a stable or generally
flash-qualified release. See [the Russian guide](../../docs/TTL_EDITOR_047D4_RU.md).

The six [published WebUI additions](../../webui/0.4.7-dev.4/) are exact bytes
from the tested image. The browser runs on the stock web server and uses its
API/MD5 library. Opening these files locally does not install native TTL support.
The native API is `r47-revision24-ttl8`; only 64 and Off are exposed in the editor.
Settings are RAM-only. Boot 64 is implemented; reboot-after-Off persistence was
not tested. A session lock and prewrite read do not provide cross-client CAS.

Native OSLO is byte-identical to the tested dev.2 component: 9,648,064 bytes,
SHA256 `686a5d3138cd6ee930d43d22704463b15c78dbcd3eb993ccd78dc29a45f663b7`.
The dev.2 directory supplies only the immutable native dependency and offline
models, not a separate product release. `native-reuse-pins.json` binds every
required native source. Original source comments/schema names containing
"private" or "qualification pending" are historical build-time metadata;
current external evidence is described in the guide and release notes.

Build with the common wrapper, `--variant community-0.4.7-dev.4`, using your own
exact golden image and identity XML. Never patch an earlier custom image. Native
sources explicitly select `thumbv5te-none-eabi`, `arm926ej-s` compatibility CPU,
`+thumb-mode,-thumb2,-neon,-vfp2,+strict-align`. The builder verifies source pins,
ELF32 little-endian ARM EABI5 metadata, instruction state, Thumb1 instructions,
branch/ABI boundaries and exact emitted OSLO. LLVM 20.1 on Linux x86-64 is required
by the existing offline toolchain; ARM926 is a compatibility profile, not a
new CPUID measurement. No floating-point native component is introduced.

The wrapper builds twice, compares bytes/reports, verifies all 36 comparison
conditions and inspects the complete container. Reference-unit output: 8,323,644
bytes, SHA256 `b47935d2c3edf831f46d0ae438a8e1da95cd21cc204f58ca04bb0bdedfe3bc7d`.
The encrypted header is unit-dependent: do not expect another unit's raw image
hash to match or install another unit's image. No firmware binary or live
flashing/recovery helper is distributed.

Offline tests cover the native emitted-instruction models, source/asset pins,
architecture rejection, strict parser and 23 editor DOM/transport scenarios,
including unknown outcomes and no replay. These do not establish every hardware
failure path, protocol, TTL value, persistence, global writer serialization,
physical cellular-egress TTL or universal recovery. The research delivery had
a temporary routing cleanup error after interface replacement; a separate
recovery check proved cleanup and restored the gateway. The original failed
terminal remains a failure. A successful UI test does not qualify that delivery
helper for general use.
