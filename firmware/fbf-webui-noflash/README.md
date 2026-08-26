# WEBI-only FBF candidate — offline / NOFLASH

This directory records the smallest reproducible stock-updater experiment for
the exact LV01 / MF885 Ver.D target. It is an **offline structural artifact**,
not a qualified firmware release and not an instruction to upload it.

The reviewed official `MF96-ROUTER-C2` 2.5.89 package is a Marvell FBF v11
container. Reconstructing its fourteen WEBI records with erased `0xff` tails
produces a 1,835,008-byte partition whose SHA-256 is byte-identical to the
stock WEBI inside this unit's 2.5.94 golden backup:

The recorded vendor URL uses unauthenticated HTTP. Treat that transport as
untrusted: accept donor bytes only when both the exact size and SHA-256 in the
manifest match. Never weaken the hash gate because a download succeeded.

```text
86fda63366438a166c7ef334042af410e55289e7591a0743c47797404c08bb56
```

That closes the earlier uncertainty about the target WEBI flash address,
partition size, record order, 128 KiB chunking, omitted erased tails and
XOR32 fields. The builder copies the donor's exact 12-byte hardware/version
field and emits fourteen WEBI records only. It deliberately omits `RSAI`.

Exact target OSLO control flow shows that normal `ZMIFI` does not take the
`TPLIN`-only fatal branch when `RSAI` is absent. This establishes only that the
flow reaches later checks; it does not establish upload acceptance, a safe
write, boot success, or rollback.

Historical reproduction (requires the exact quarantined ZIMI bytes retained by
the operator; the current wrapper deliberately does not generate that name):

```bash
python3 tools/mf885_fbf.py build-webi-noflash \
  --donor /path/to/MF96-ROUTER-C2_2.5.89_official.bin \
  --zimi build/MF885_Community_0.0-logs-r1-cafe-r2.bin \
  --output build/MF885_Community_0.0-logs-r1-cafe2.NOFLASH.fbf \
  --report build/MF885_Community_0.0-logs-r1-cafe2.NOFLASH.report.json \
  --confirm-offline-only
```

Expected output:

```text
bytes   1,843,200
sha256  63e040d385b29d2732c06cabee81e3f85d6fd000e8661b22eb049627e91460a7
images  WEBI x14
RSAI    absent
```

`tools/mf885_fbf.py inspect` independently checks FBF magic/version, device and
record-table bounds, non-overlapping file and flash ranges, the three master
byte totals, every non-RSA XOR32 checksum and reconstruction of erased tails.
The candidate then reconstructs exactly the reviewed 321-record observer WEBI.
The narrower write-plan gate additionally requires the exact donor version,
fourteen `IBEW` records only, flags 3, descending `0x20000`-byte extents covering
`0x00ac0000..0x00c80000`, exact per-record stored lengths and packed data order.
It reports 1,835,008 bytes erased and 1,833,320 bytes written.

The separate simulator models that reviewed loop without exposing an output
or transport path:

```bash
python3 tools/mf885_fbf_sim.py \
  --image build/MF885_Community_0.0-logs-r1-cafe2.NOFLASH.fbf \
  --initial-webi /path/to/exact-stock-WEBI.bin \
  --scenario success
```

For the native `-5` branch, `--scenario worker-return-minus-five
--fail-record N` models only the records known to have completed before `N`.
The failed record and all later bytes are reported as unknown. The simulator
prints deterministic JSON, writes no file, and labels every erase, write,
selector, status and reset event as `planned_only`.

Safety state is intentionally fixed:

```text
offline_only              true
flash_qualified           false
live_tested               false
router_requests_attempted 0
firmware_posts_attempted  0
flash_bytes_actually_written 0
reset_attempted           false
```

Do not rename the binary to remove `NOFLASH`, do not use it with the stock
upload form, and do not treat the static unsigned branch as a rollback path.
The per-record parser/write loop is now traced: the native routine erases each
full extent, writes the stored bytes and provides no identified readback. A
failure may leave earlier records changed; success selects `MAXS` and resets
later. No native partition allowlist, rollback/A-B path, live WEBI-only
acceptance or independent recovery has been proved.

The historical FBF `fd2984…82d3` wrapped the invalid-padding
`65e5f5…53517` WEBI and is itself quarantined. The later
`63e040…60a7` FBF has valid CAFE padding but wraps `a9a284…b642a`, whose
canary `detailed_log` request omitted the stock Digest header. It is therefore
also quarantined historical research. Neither was submitted. Current
authenticated Logs sources have no FBF wrapper; all FBF material remains
offline-only, unflashed and non-stable.
