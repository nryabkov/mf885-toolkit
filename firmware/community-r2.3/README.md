# MF885 Community R2.3

`community-r2.3` is an immutable, golden-derived WebUI revision. It does not
replace R2.2, its artifact, or its consumed delivery evidence.

The canonical `/index.html` remains the small vendor interface. It is forced
to English, retains the typo corrections and locale-space saving, and adds one
plain link to `/r23.html`. It loads no Community authentication, menu,
Messages, Diagnostics or CSS. The vendor menu, Dashboard and SMS controller
remain byte-identical to the reviewed golden.

`/r23.html` is the isolated modern interface. All changed controllers and
documents use revision-unique paths, including its utility script, menu loader,
menu XML, Dashboard, Messages, Diagnostics, authentication and stylesheet.
This avoids relying on an old cached R2.2 subordinate asset.

Messages show sender, date and body immediately, with ten-message local pages.
Send occurs only after an explicit **Send** click and preserves one POST,
no retry, complete Sent baseline/readback and the shared unknown-outcome lock.
Delete retains the native confirmation, one POST and complete absence
readback.

An optional checkbox checks for new inbox messages while the modern tab is
open. It is off by default. The first complete read creates a baseline and
announces nothing. Each later cycle waits at least 60 seconds and reads only
page one; a changed safe fingerprint triggers one complete bounded history
read. It never overlaps Send/Delete, never stores XML, numbers, bodies or
message IDs in browser storage, and pauses after repeated incomplete reads.
The notification text is generic. On the normal plain-HTTP router address,
the reliable result is an in-page badge; system notifications are attempted
only in a secure context after an explicit permission gesture.

Diagnostics keeps exactly one sequential read of `status1`, `wan` and
`Engineer_parameter` on open or manual refresh. The visible page may show
network details, while the copied safe snapshot omits identifiers, SMS data,
APN and network addresses. The vendor image still contains its historical
`detailed_log` route; R2.3 does not expose or read it.

USSD, modem debugging, TTL, IMEI and repeater controls are not active in this
revision. They require separately proven contracts and future immutable
revisions.

Two exact-golden builds are byte-identical at 8,323,644 bytes. The current
reference-unit SHA-256 is
`06d79b9e51d54e87e4065ceabac63d70b4d34b72b21bfa096a1132d1b45af86b`;
the portable plaintext SHA-256 is
`6cac69f41874f3b559183a4539e0bd0fa5de89b085e663df337375fa505b2887`.
Only WEBI changes; OSLO, GRBI, WIFI, WCAL and RFBN remain byte-identical.
Sanitized representative renders of the canonical login and every modern
page passed desktop and phone-width review without horizontal clipping. The
native SMS delete confirmation was also invoked and dismissed in the offline
preview. This does not count as a live-router UI test. R2.3 is unflashed, not
stable, not flash-qualified and not restore-allowlisted.
