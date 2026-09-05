# MF885 Community R3.6

R3.6 is the isolated functional TTL repair after the installed R3.5 getter
failed. It remains cumulative with the accepted R2.9 interface and SMS
features; it adds no repeater, on-device USSD or IMEI feature.

The native delta from R3.5 is deliberately one-dimensional: the exact
single-field `diagnostic.output` publisher moves from `post_get` to `pre_get`.
The strict setter, one-byte volatile state and IPv4 forwarding hook remain
unchanged. Exact stock disassembly proves that GET does not dispatch the
installed `post_set`, so no speculative recursion guard is added.

The browser no longer reads TTL during login or background universal polling.
It keeps TTL controls locked and visibly asks for one explicit **Read current
state** action. Dashboard, Messages, Diagnostics and Modem data keep their
existing universal background refresh. This prevents an unqualified native
TTL path from being invoked merely by signing in.

TTL remains RAM-only and boots as Off. Persistence, cold boot, setter,
forwarded-packet behavior, repeatability and rollback remain unproved until
separate live qualification.

The retained offline candidate is
`MF885_Community_0.3.6-community-r2-native-r10-cafe-r2.bin`, exactly 8,323,644
bytes, SHA-256
`4984024babae9aa89e967101771063be0ae9cd8481a7f7992d05fa875cd6969f`.
Its 76,325-byte build report hashes to
`e80acdec514497a018ebbbf17c68ac433c3d65ba59061f8b144422b01d8798a3`.
Two exact-golden builds are byte- and report-identical, the independent
container inspector is green, all 52 final conditions pass, and every change
outside OSLO and WEBI is byte-identical.

The essential functional set is 29/29: five exact-stock dispatcher and
ownership scenarios, six native machine/payload scenarios, three WEBI/source
scenarios, six native-container scenarios and nine browser scenarios. The
browser scenarios prove that normal login and universal non-TTL polling still
work, that login/background activity sends zero TTL requests, that one manual
click sends exactly one TTL GET, and that malformed or ambiguous responses
keep all TTL writes locked.
