# Community R4.3 fixed64 forwarding component

Status: **offline decompressed OSLO component only**. No full R4.3 firmware
container, installed image, runtime configuration or live packet test exists.
This source-only component is separate from the R4.2 context-read probe.

The helper replaces the already reviewed ip_forward output call with the
existing argument trampoline and a fixed TTL=64 algorithm. It does not attach
diagnostic callbacks or access custom state, a parser or a WebUI endpoint.
This isolates packet forwarding from the earlier configuration experiments.

## Packet contract

At the stock hook, r5 holds the IPv4 header, r6 the pbuf and r4 the selected
output netif. The trampoline supplies these as r0/r1/r2 and loads the output
function from [r4+0x58] into r3. The helper passes the original destination
argument0x0702c14c (stock literal0x0702c12c plus32), calls that output function
once and preserves its return value and callee-saved registers.

For a four-byte-aligned IPv4 header with IHL>=5 and pbuf total/contiguous
lengths covering the header, observed TTL>=2 is set to64. A TTL already64
causes no write. The helper updates TTL/protocol/checksum in one aligned
32-bit store and preserves every other packet byte. Checksums use the existing
RFC1624 incremental algorithm. TTL0/1, non-IPv4, short or unaligned inputs
pass to the original output unchanged. The TTL guard refers to the value at
this hook, after any prior stock processing, not the packet's ingress TTL.

The stock callsite must supply valid readable pointers. There is no null or
unmapped-pointer validation. No output direction is selected: eligible
forwarded IPv4 traffic in either direction is affected. Locally originated
traffic and IPv6 are outside this hook. There is **no runtime Off switch**.
These limitations need an explicit deployment and restoration design before
any complete image could be used on hardware.

## Exact offline output

The builder accepts only the existing pinned9,648,064-byte stock OSLO and
changes exactly two ranges:140 bytes at0x12a0 and the12-byte stock callsite at
0x8ed1ca. All other bytes, including diagnostic pointers and both old state
areas, are preserved by whole-source and whole-candidate checks.

- LLVM source:2983 bytes, SHA256
  `3a864b9d738f2791e91f1f1c3232fc0e7aadf1f97eef6e39744e8e9ea6d44c25`.
- Helper:136 code bytes plus4 literal bytes, SHA256
  `f1a939377d18d60688179c474d4d4bba352c0a72afd69f70fe3a81113824a6d2`.
- Decompressed candidate SHA256:
  `b0d527e2c48df02d00e76ac606636068a1e7052e1be18e406cc5f83474f8b2e6`.

```sh
python3 tools/mf885_ttl_native_payload_r43.py stock-oslo.bin --output r43-oslo-component.bin
python3 -B -m unittest discover -s tests -p mf885_ttl_native_payload_r43_test.py -v
MF885_R43_TEST_OSLO=/path/to/stock-oslo.bin python3 -B -m unittest discover -s tests -p mf885_ttl_native_payload_r43_test.py -v
```

The output is **not a flashable update**. Existing output files are refused.
No backup, generated image or live delivery helper is distributed.

Tests execute emitted machine instructions, with state/CGI memory unmapped.
They cover256 TTL values,11 IHL values and3 protocols (8448 cases), complete
checksum recomputation including a zero result, options/payload preservation,
invalid lengths/alignment, the sole packet-word store and original output ABI.
The first8 trampoline bytes execute separately and the direct BL target is
decoded; the subset emulator does not execute the complete stock forwarding
routine or hardware caches/mapping. Three additional optional fixture tests
check exact OSLO patches and reject source/candidate drift or truncation.

These checks demonstrate offline packet rewriting, not live forwarding-hook
execution or an observed TTL at a real egress interface.
