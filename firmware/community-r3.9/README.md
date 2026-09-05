# MF885 Community R3.9 functional TTL candidate

Community R3.9 is the first candidate that connects the already studied
diagnostic input to the already studied IPv4 forwarding hook. It keeps the
cumulative R2.9 interface, Messages and modem/diagnostics behavior.

How earlier versions worked matters here. R3.0–R3.6 tried to publish a custom
TTL result during diagnostic GET or through a bridge. R3.7 moved the stock
property setter to phase-3 SET and still caused a reset-class failure. R3.8
removed the setter and all state work; its one live SET and later GET returned
normally and proved that the stock diagnostic model itself retains
`command=ttl,arg=off` across requests. Therefore R3.9 does not invent an
`output` value and does not call the property setter.

The R3.9 phase-3 `diagnostic.post_set` callback calls the exact stock getter
twice for `command` and `arg`, frees every non-null returned copy, accepts only
the exact command `ttl` and `off` or canonical decimal `1..255`, then writes
exactly one state byte. Missing, malformed or wrong-phase input writes
nothing. The callback is 204 bytes and calls no property setter. All
diagnostic GET callback slots remain zero.

The inherited 152-byte forwarding helper reads that byte. State zero leaves
forwarded IPv4 unchanged; state `1..255` rewrites the TTL and updates the IPv4
header checksum before calling the same stock output function. IPv6,
router-originated traffic, malformed/short/unaligned headers and incoming TTL
zero or one are left unchanged. The image byte is initialized to Off. Live
restart and persistence behavior remain deliberately unclaimed.

The browser code is modular. `r39app.js` retains the cumulative interface and
exposes only a narrow diagnostic bridge; `r39ttl.js` owns TTL parsing,
controls, logging and the one-POST/one-GET flow. A safe diagnostic GET runs
with the normal authenticated bootstrap and universal 30-second refresh. A
manual change sends exactly one command/argument-only POST and one separate
readback GET, with no automatic retry. Every raw router response is emitted
by the shared transport with a request ID, and the TTL module emits every
flow variable, condition, reason and counter separately.

The UI deliberately says **last requested value**. Stock diagnostic readback
does not prove that a packet was rewritten. Malformed state locks all writes;
an uncertain write remains locked until a separate manual read. The first
live release qualification must therefore prove both a retained request and
an observed packet, then restore Off.

The retained offline candidate is
`MF885_Community_0.3.9-community-r2-native-r13-cafe-r2.bin`, exactly 8,323,644
bytes, SHA-256
`1d43893883f84dc353f3df393f78bca7d6ef09806916b0e94064344da50f3b55`.
Its 62,759-byte build report hashes to
`2ceba60078d6fafaa6d1784d53558f875b57ec08baf4484ba23a230c5145347a`.
Two builds and reports are byte-identical, all 52 final conditions pass, the
independent image inspector is green, and all changes stay inside OSLO and
WEBI allowlists.

The substantive pre-flash suite is 23 tests: five exact-stock ABI/tamper
tests, seven emitted-machine and exact-golden native tests, three WEBI/full
container tests and eight browser-flow tests. It covers all 256 accepted states,
malformed input, callback getter/free counts, absence of the property setter,
all forwarding TTL values, checksum preservation, invalid packet shapes,
valid/invalid SET integration, deterministic image construction, UI request
ceilings, both observed stock POST envelopes, exact failure counters, nested
field rejection, mutation locking and stable universal read-only refresh.

The earlier private candidate with SHA-256
`d5e46e6469314fad1baaed269e0ad6b5031eac7c8fda5b39a1c2695f6e81641a`
is retained as rejected evidence. It must not be flashed: review found that its
browser accepted only `<RGW/>`, while the device had already proved a strict
matching diagnostic echo response; it also had a zero-due scheduling race,
an inaccurate failure GET counter and overclaimed restart wording.

The image is not installed. Live low-page state writing and the actual packet
path remain unproved until one separately authorized firmware attempt and one
bounded post-install Off→64→Off packet observation. Persistence, cold boot,
repeatability and rollback are also unproved.
