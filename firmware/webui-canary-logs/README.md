# WEBI Canary Logs 0.0-logs-r1 — authenticated source revision 4

This is the smallest first firmware experiment. It keeps every native partition
byte-identical and changes only the fixed-size `WEBI` archive:

- a 41-byte whitespace slot immediately before `</body>` in `www/index.html`
  becomes a same-length loader for `js/canary_logs.js`;
- `www/js/canary_logs.js` is appended as one new CAFE record in existing `0xff`
  padding;
- no existing CAFE record moves or changes size;
- 856 bytes of WEBI padding remain.

The panel records XHR, fetch, form submissions, control clicks, JavaScript
errors, `console.warn/error`, and the stock `detailed_log` GET while the panel is
open. The poll now uses the same `getAuthHeader("GET")` Digest header as the
stock WebUI. If the stock helper is unavailable, the request fails before it is
sent. The header value is never stored in the panel. SMS bodies, credentials,
unit identifiers and network identifiers, including WAN usernames and bare
IPv6 forms, are masked before event storage;
bounded request method, endpoint, status, duration and byte counts remain.

Reproduce the image from the exact target-unit golden and read-only identity XML:

```bash
python3 tools/mf885_webi_builder.py \
  --golden /path/to/MF885_golden.bin \
  --identity-xml /path/to/getinfo-base.xml \
  --script firmware/webui-canary-logs/canary_logs.js \
  --output build/MF885_Community_0.0-logs-r1-auth-r4-cafe-r2.bin \
  --report build/MF885_Community_0.0-logs-r1-auth-r4-cafe-r2.report.json \
  --confirm-structural-only
```

Expected artifact SHA-256:

`a1d970c68bde7534519b942bd73a57c6805d321860dead6b437392b0319fe922`

The builder requires the exact golden hash, recalculates CAFE Adler-32 plus the
WEBI/global additive byte sums, re-encrypts the unit-bound ZIMI header, and then
runs the independent full inspector. A second build from the independent golden
copy was byte-identical. The logical script is 12,561 bytes; its aligned CAFE
record stores 12,564 bytes with three trailing `0xff` bytes and uses
`size_flags=0x03003114`.

The historical artifact `65e5f5…53517` is quarantined. Its record declared
three padding bytes without storing an `0xff` tail, so the live web server
removed the real suffix `);\n`; the script raised `Unexpected end of input` and
the panel did not initialize.

The previous canonical-container artifact `a9a284…b642a` was observed on one
exact device profile: its panel loaded and its polling cadence worked. That
source omitted the stock Digest header from the canary's own `detailed_log`
XHR, however. The router's HTTP 200 response with an empty body therefore did
not verify native log content. It is retained as a quarantined historical
artifact and is not the output of the current source.

The intermediate authenticated artifact `de17be…a518b` is also quarantined. It
added the correct Digest header but did not comprehensively mask copied
credentials and stable identifiers. It was never flashed.

The intermediate privacy revision `fde992…0ec6af` is likewise quarantined:
alternate JSON/header spellings could still survive diagnostic redaction. It
was never flashed.

The historical `auth-r2` source revision (`c77b66…a7431`) was installed once through the reviewed
MINI/USB-RNDIS path: one MINI transition, one RestoreFw POST and zero retries.
Its exact 12,568-byte script and loader returned in FULL. A separate
authenticated GET returned a non-empty 179-byte `text/xml` `detailed_log`
document with a valid root and zero current items, proving that the native read
is no longer being mistaken for an empty authentication challenge. The live
browser panel also loaded; its captured tab was logged out, so its own zero-byte
polls are retained only as UI evidence, not as the authenticated semantic proof.

That installed revision is now quarantined because copied diagnostics did not
cover every WAN username and IPv6 representation. The intermediate `auth-r3`
artifact is also quarantined unflashed: it improved the vocabulary but still
used an incomplete bare-IPv6 matcher. The current `auth-r4` source fixes both
cases without reusing either historical artifact identity.

The current image is reproducible and structurally verified offline, but it has
not been flashed. Cold-boot persistence, repeatability, a browser-authenticated
canary poll and a golden rollback remain unproved. No Logs image is generally
flash-qualified, restore-allowlisted or stable. Detailed live evidence and
screenshots remain in the private repository and are intentionally excluded
from the source-only public toolkit.
