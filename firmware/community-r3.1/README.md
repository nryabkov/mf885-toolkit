# MF885 Community R3.1 TTL repair

R3.1 is a cumulative repair of the installed Community R3.0 image. It keeps
the complete R2.9 UI/SMS baseline and the same temporary TTL product contract;
it does not add the later Wi-Fi repeater increment.

The installed R3.0 ordinary UI worked because those paths never invoked the
new native `diagnostic` callbacks. Its first authenticated TTL GET loaded the
custom state byte from the unproved high-tail OSLO range at runtime
`0x06933200`, then the MF885 reset before returning an HTTP byte. Later exact
stock disassembly corrected an overly strong diagnosis: at least the stock
`debugon` and `alert0` post-get callbacks ignore the incoming context and call
the same property setter on their own model. Stock `sd_log_managment` also
performs two sequential same-model setter calls on either branch. Calling that
setter from post-get is therefore not uniquely invalid and a recursive-lock
root cause is not proved.

R3.1 removes every native reference to the old high-tail block. The mutable
state, model/field names and fixed output strings occupy 96 bytes at runtime
`0x06001430`, inside the first exact page that already contains proved stock
Thumb code. Numeric readback is formatted into a four-byte stack-local buffer;
the former 1,280-byte state/table block and shared high-tail dependency are
gone. The forwarding and setter contracts remain unchanged:

- boot state is `Off` and is not persistent;
- accepted values are `off` or canonical decimal `1..255`;
- `64` is recommended, `65` remains a compatibility preset;
- only forwarded IPv4 is rewritten; IPv6, router-originated IPv4 and observed
  TTL zero/one are unchanged;
- a setting change requires one POST and one GET readback, with no automatic
  retry.

The deterministic offline candidate is
`MF885_Community_0.3.1-community-r2-native-r4-cafe-r2.bin`, exactly 8,323,644
bytes, SHA-256
`74e61b4d0f386cfc079c7eb19d7e11ad640f96a144800d6625306104ef95ceeb`.
It was rebuilt twice identically inside the retained builder and passed an
independent container inspection. This is not live proof: R3.1 is not installed
and its first TTL GET, TTL writes, packet behavior, cold boot, repeatability and
rollback remain unproved. The installed R3.0 TTL getter/setter must not be
invoked again.
