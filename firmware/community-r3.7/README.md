# MF885 Community R3.7

R3.7 is a deliberately narrow native discriminator after the installed R3.6
getter failed. It is not a functional TTL release and adds no repeater, USSD or
IMEI feature.

The native delta starts again from the exact golden image and installs one
phase-3 `diagnostic.post_set` callback. That callback builds `output` and `off`
on its own stack and calls the exact stock property setter once. Both
diagnostic GET callbacks remain zero. There is no custom TTL state, packet
hook, persistence path or Engineering/debugon/SystemChannel change.

The live question is intentionally small: after one authenticated
`command=ttl,arg=off` SET, does one later ordinary diagnostic GET return the
stock-shaped `output=off` value without identity drift? A green result proves
only cross-request stock-property retention and serialization. It does not
prove that TTL is implemented, changed on packets or survives reboot.

The browser keeps TTL visibly locked, performs zero diagnostic/TTL requests
during login or background refresh, and leaves the accepted cumulative R2.9
UI/SMS behavior intact. The external one-shot qualifier owns the single SET
and later GET and saves every raw response, request body, variable, condition,
timing, counter and exact failure reason.

The retained offline candidate is
`MF885_Community_0.3.7-community-r2-native-r11-cafe-r2.bin`, exactly 8,323,644
bytes, SHA-256
`2b1a40fc0e794f4b876aeb16b1377d359c06ef0bb56f8997fc73ff0f8851d6af`.
Its 64,645-byte build report hashes to
`810dbe4e799a6eccc61981bb6ec9279b3c9f8a3020673106a5a1aeabb8adfb9e`.
Two exact-golden builds and their reports are identical; the independent
container inspector is green, all 44 final conditions pass, and only OSLO and
WEBI change while all other partitions remain byte-identical.

The essential firmware set is 15 tests: six exact-stock/native machine and
payload scenarios, three WEBI/source scenarios and six deterministic
native-container scenarios. Live retention, TTL getter/setter, packet path,
persistence, cold boot, repeatability and rollback remain unproved.
