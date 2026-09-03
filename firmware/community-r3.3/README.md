# MF885 Community R3.3 isolated TTL transport

R3.3 is a cumulative TTL-only repair of the installed Community R3.2 image.
It preserves the complete R2.9 SMS/UI baseline and the reviewed native IPv4
forwarding hook. It does not add Wi-Fi repeater, USSD or IMEI behavior.

## How it worked before

R3.0 read custom state from an unproved high OSLO page and the first TTL GET
reset USB/RNDIS. R3.1 moved code and state to the first loaded page, removing
that reset, but its authenticated TTL GET connected and sent successfully and
then returned zero response bytes. R3.2 moved the same three-field publisher
from Duster post-get to pre-get; the same five-second zero-byte timeout remained
and a Base GET recovered 319 ms later.

Exact-stock analysis therefore rejects callback timing as the sufficient
repair. The remaining unique operation in R3.1/R3.2 was publishing three
invented response fields (`diagnostic.command`, `diagnostic.arg` and
`diagnostic.output`). Stock has the dormant `diagnostic` model name, but no
exact `arg` field and no registered response contract for those fields.

## R3.3 transport

The read path uses one exact registered stock field:
`SystemChannelName.PRODUCT_CHANNEL`.

1. Duster invokes the custom `diagnostic` pre-get callback.
2. The callback reads the one-byte volatile TTL state and invokes the stock
   property setter exactly once with `off` or canonical decimal `1..255`.
3. Core GET processing serializes the requested diagnostic template, which
   contains the dormant trigger model and the stock SystemChannelName field.
4. The byte-identical stock SystemChannelName post-get callback restores its
   exact `release` value.

The write path is separate. `ttl_set.xml` contains only
`diagnostic.command/arg`; its post-set callback validates exact `ttl` plus
`off` or canonical `1..255`, writes one volatile byte and invokes no response
setter. A TTL POST therefore cannot submit a PRODUCT_CHANNEL write.

The separate WAN `Engineering_mode`, hidden `debugon` descriptor and its
mode-8 callback, and `debugmodeon.xml` all remain byte-exact. R3.3 never calls,
disables or repurposes an Engineering function.

## Candidate and proof boundary

The deterministic offline candidate is
`MF885_Community_0.3.3-community-r2-native-r6-cafe-r2.bin`, exactly 8,323,644
bytes, SHA-256
`9f48745b5977f0fc6ddffe08d4efff0f2ff2d2d8e1e8bb5c208838baa42bb442`.
Its 70,539-byte build report has SHA-256
`66ccad8a3d55e128e3025c01e2f722fec4eb48b6089881095b40224c27d177d3`.
Two builds are byte-identical and independent inspection is green. Only OSLO
and cumulative WEBI differ from exact golden; GRBI, WIFI, WCAL and RFBN are
byte-identical. All 568 changed decompressed OSLO bytes are inside seven named
ranges and unauthorized changed bytes are zero. The retained candidate-b
report also records measured before/after size and SHA-256 for both Engineering
WEBI templates, the WAN row, the hidden debug row and its callback, and the
complete 20-byte stock SystemChannelName restore callback. Candidate-a has the
same firmware bytes but its shorter evidence report is superseded.

The substantive offline set is 51/51: 16 R3.3 native/Web/container scenarios,
30 inherited TTL forwarding/parser/checksum/low-page scenarios and five
browser scenarios against exact generated R3.3 assets.

This is not live qualification. The first target discriminator after a new,
separately authorized one-shot delivery must be read-only: one authenticated
TTL GET followed immediately by an exact stock
`SystemChannelName.PRODUCT_CHANNEL=release` readback. A timeout, malformed TTL
response or failed restore stops before any TTL POST. TTL mutation, packet
behavior, cold boot, repeatability and rollback remain unproved.
