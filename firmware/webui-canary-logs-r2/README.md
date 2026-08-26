# WEBI Canary Logs 0.0-logs-r2 — authenticated source revision 4

Logs r2 is a separate observer-only WebUI source. It does not modify or
supersede the byte identity of Logs r1.

Compared with r1 it adds bounded event and serialized-unit counters, dropped-event
reporting, request correlation, XHR/fetch start/end/error/abort/timeout phases,
console `log`/`info`, online/offline/page visibility events, category filtering
and a change summary for `detailed_log`.

SMS detection is endpoint/envelope based rather than treating every XML
`<content>` element as a message. SMS bodies, credentials, unit identifiers,
APNs, WAN usernames, IP addresses (including bare IPv6 forms), MAC addresses
and SSIDs are masked before event storage.
Bounded request phases, endpoint names, status, duration, sizes and parser
summaries remain available. Raw browser responses exist only transiently.

Build from the exact golden image only:

```bash
python3 tools/mf885_webi_builder.py \
  --golden /path/to/MF885-golden.bin \
  --identity-xml /path/to/status1-identity.xml \
  --script firmware/webui-canary-logs-r2/canary_logs.js \
  --output build/MF885_Community_0.0-logs-r2-auth-r4-cafe-r2.bin \
  --report build/MF885_Community_0.0-logs-r2-auth-r4-cafe-r2.report.json \
  --profile 0.0-logs-r2 \
  --confirm-structural-only
```

The current artifact SHA-256 is
`aeaceb9cd193a44100bd33c3f14dc48ede6d2e163d7a214a87411d7875adf07f`.
The 13,402 logical bytes are stored as 13,404 bytes with two trailing `0xff`
bytes and `size_flags=0x0200345c`; 16 bytes remain in the fixed WEBI slot. Its
`detailed_log` poll uses the stock `getAuthHeader("GET")` Digest header and
never stores that value.

The historical artifact `444252…0758` has valid CAFE padding but is
quarantined because its poll omitted the stock Digest header. The still older
`0cc9eb…c1f1` also declared three padding bytes without appending them. The
intermediate `d18f87…e6459f` added authentication but retained incomplete
diagnostic redaction and is quarantined unflashed. The later `5bfe13…f6d875c`
revision is also quarantined because alternate JSON/header spellings remained
unmasked. The later `auth-r2` and `auth-r3` builds are retained as quarantined
history because WAN username and bare-IPv6 coverage was incomplete. The current
`auth-r4` revision remains structural-only, unflashed, not stable, not
restore-allowlisted and not flash-qualified.
