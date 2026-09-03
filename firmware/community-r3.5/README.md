# MF885 Community R3.5 same-model TTL repair

Community R3.5 is the next cumulative TTL-only revision built directly from
the exact reviewed 2.5.94 golden image. It keeps the proved Community R2.9
SMS/UI surface and the R3.4 diagnostic callback finding, but does not reuse the
failed R3.3 cross-model `SystemChannelName` bridge.

The native implementation is split into three modules:

- `ttl_post_set` accepts only `off` or a canonical decimal value from 1 to 255
  from the isolated `ttl_set.xml` write template and stores one byte;
- `ttl_post_get` reads that byte, formats it with a stack-local four-byte
  buffer, and publishes exactly `diagnostic.output` using the same model and
  stock property setter used by a known stock callback;
- `ttl_forward` is the separately inherited IPv4 forwarding hook which applies
  the selected value and repairs the header checksum.

The mutable state and four short field strings occupy 48 bytes in the first
loaded OSLO page. The boot value is `0` (`Off`) and is deliberately volatile:
R3.5 does not claim persistence across a restart. WAN Engineering, hidden
`debugon`, `SystemChannelName`, their callbacks and the stock web templates are
byte-identical to the golden image.

The UI is an extension of the existing MF885 interface at `/r35.html`. It
loads TTL during the normal authenticated bootstrap and universal refresh.
Writes remain disabled until a fresh response contains exactly one
`diagnostic` model with exactly one `output` field holding `off` or canonical
`1..255`. A write is exactly one POST followed by one GET; any invalid,
ambiguous or failed readback locks further writes until another fresh green
GET. Automatic retries are zero.

Offline validation is green for 24/24 named functional scenarios:

- 6 native machine-contract scenarios covering all 256 states, canonical and
  malformed inputs, callback return propagation, exact caves and stock-path
  preservation;
- 3 deterministic WEBI/source scenarios;
- 6 deterministic native-container scenarios, including a byte-for-byte
  comparison between a fresh build and the retained delivery artifact/report;
- 9 browser scenarios covering bootstrap, presets, custom boundaries,
  fail-closed ambiguity, exact root/model/field structure, attributes, nested
  elements, significant text, noncanonical whitespace and universal
  polling/logout.

The retained candidate is
`MF885_Community_0.3.5-community-r2-native-r9-cafe-r2.bin`, exactly 8,323,644
bytes, SHA-256
`efd74c1ff0127961f8036d0f6e51b7fec35856b128f23b3f18de5191663087f3`.
Its 70,789-byte build report hashes to
`360193c2ebb8b8731429945f99ef424a1368840c9010a4e3992a44272c08a41c`.
The deterministic double build, independent container inspection and all 47
final container conditions are green.

The earlier unflashed `native-r8` candidate with SHA-256
`c9b552fb2f71cf8c9a436dbef2ee623a2f999383914b0cf7b10ac79f3a4ea6c6`
is retained only as superseded history. Its browser parser did not enforce the
same exact XML shape as direct-v43, so its identifier and hash were not reused.

R3.5 is not installed and TTL is not yet live-qualified. The first post-flash
TTL action must be one read-only `diagnostic.output` discriminator with stable
identity. Only a green discriminator may unlock a separately bounded setter
and forwarded-packet proof. Until getter, setter and packet proof are all
green, the product claim remains **TTL unproved**. Cold boot, persistence,
repeatability and rollback are also unproved.
