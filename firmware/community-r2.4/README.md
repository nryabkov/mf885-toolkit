# MF885 Community R2.4

`community-r2.4` is an immutable, golden-derived WebUI revision. It extends
R2.3 without changing R2.3 sources, binary, report, or evidence.

The stock `/index.html` remains a small English vendor login with one link to
`/r24.html`. The modern interface uses revision-unique asset paths, so an old
cached Community page cannot silently mix R2.3 and R2.4 controllers.

R2.4 adds **Modem monitor** under Diagnostics. Opening it performs one
sequential read of `status1`, `wan`, and `Engineer_parameter`. The optional
watch checkbox is off by default and repeats that same three-read cycle every
30 seconds only while the tab is active. It keeps at most 60 samples and 20
change labels in memory. It never calls a write route, `wlan_cli_scan`, USSD,
TTL, or IMEI controls. A Messages mutation and a monitor read are mutually
serialized.

The visible page shows registration, radio mode, signal, battery, uplink, and
schema-confirmed modem metrics. It also shows the firmware-reported Wi-Fi
uplink state, but exposes no repeater scan or connect button: the dormant stock
write path is not live-qualified. The copied safe trace strictly normalizes
known states and bounded numeric metrics and omits raw unknown values, XML,
credentials, identifiers, addresses, APN, SSID, cell location, SMS, and phone
data.

Messages, the opt-in one-minute inbox watcher, Diagnostics, tab-scoped
remember-me, English-only resources, and the isolated visual system are
inherited from R2.3. Send/Delete keep one explicit mutation, no automatic
retry, exact command status, complete readback, and a page-session unknown
outcome lock.

Sanitized offline renders of Dashboard and Modem monitor were reviewed at
1280x900 and 390x844. They have no page-level horizontal overflow, and the
watch checkbox remains a compact 15x15 control attached to its label. A live
device visual review is still required before any flash authorization.

The firmware stays 8,323,644 bytes. The reference-unit SHA-256 is
`5bc408710afa5e78836c49da91656a8f94d804ee4fe64c53f6ef7d53786fd7db`;
the portable plaintext SHA-256 is
`e33038e8a80838db6d91d347c4fc0c06480e365f577627edbf7a3cdf95e0bdc1`.
Only WEBI changes; OSLO, GRBI, WIFI, WCAL, and RFBN remain byte-identical.

R2.4 is unflashed, not stable, not flash-qualified, and not
restore-allowlisted. USSD remains research-only until an exact WebUI transport
and status lifecycle are proven. TTL and IMEI controls remain absent.
