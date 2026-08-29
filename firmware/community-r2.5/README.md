# MF885 Community R2.5

`community-r2.5` is an immutable, golden-derived WebUI revision. It extends
R2.4 without changing the R2.4 transformer, sources, binary, report, or live
evidence.

The stock `/index.html` remains a small English vendor login and links to the
cache-safe `/r25.html` entry. After authentication, the shared stock/modern
header shows one compact `Community 0.2.5` pill linked to `/r25.html`; its
tooltip and the Dashboard keep the exact `0.2.5-community-r2` profile. The
Dashboard badge carries the same version instead of the former generic
`Community UI` text.

The Messages and Modem monitor checkboxes are default-on when their page is
first opened in a tab. Messages schedules one inbox fingerprint check every 60
seconds; Modem monitor schedules the existing fixed three-GET read every 30
seconds. Neither watcher starts before its page is opened. Explicitly turning a
watcher off stores only `0` in tab-scoped session storage, so a refresh does not
silently turn it back on. Storage failure remains fail-closed. Automatic
mutation retries remain zero, and the two read paths stay serialized with SMS
Send/Delete.

At the router's native `http://192.168.21.1` origin, the Notifications API is
not available because the page is not a secure context. R2.5 therefore says
that system alerts need HTTPS and keeps the in-page badge/title fallback. It
does not prompt for notification permission without a user gesture.

Diagnostics and Modem monitor still read only `status1`, `wan`, and
`Engineer_parameter`. R2.5 makes the returned `Engineering_mode` state visible,
accepts both the flat and nested stock engineering XML schemas, and shows the
stock `status1/rssi` value as a unitless vendor-scale signal quality with the
same 2G/3G/4G bar thresholds used by the golden login page. It never labels
that fallback as dBm or RSRP.

When the detailed LTE schema returns RSRP or RSRQ report indices, R2.5 maps
only those two fields through the primary 3GPP/ETSI reporting tables and keeps
the original index beside the derived dBm/dB value. Already signed flat values
remain compatible. SINR and RSSI stay explicitly labelled `raw` because their
MF885 conversion contract is not yet proved. A closed-by-default **Radio
terms** panel expands the abbreviations used by Diagnostics and Modem monitor;
the same full English names are available on the compact metric labels without
adding router requests.

R2.5 contains no Engineering-mode write path. One controlled live cycle on the
installed R2.4 changed only the stock WAN selector: `Disabled` was read, one
enable POST was accepted, `Enabled` was read back, the immediate fixed
diagnostic cycle returned no detailed values, and one rollback POST restored a
confirmed `Disabled`. Two later GET-only probes while still Disabled each
returned the full 107-tag engineering schema and detailed LTE values. Enabled
is therefore not required for the observed reads. Freshness/cache semantics
and any CPU, memory, battery, RF, or traffic cost remain unmeasured, so R2.5
shows the state read-only and does not offer a routine toggle. The WAN selector
is not conflated with the separate USB `debugmodeon` profile.

When detailed radio values are absent, Diagnostics and Modem monitor collapse
the repeated empty rows into one `Detailed radio metrics · Not returned` row.
No field or parser is removed: every returned value appears automatically, and
the safe snapshots keep the same explicit null evidence.

The firmware remains 8,323,644 bytes. Two independent reference-unit builds
are byte-identical with SHA-256
`231e98622e19883d704edc490eed76d249e78f4303af86007b8cfaa12171a84d`;
the portable plaintext SHA-256 is
`d9d75cfed7526c108d22e7833adec0085a1637e8635807324d5dfef228c89d70`.
Only WEBI changes; OSLO, GRBI, WIFI, WCAL, and RFBN remain byte-identical.
WEBI retains 34,528 padding bytes. Offline desktop review also replaced the
legacy floating Diagnostics columns with an aligned two-column grid and keeps
the dotted abbreviation hint under the term only.

The earlier pre-design-review R2.5 draft
`e6570e0ddea735c990f30df5148a88211921b9c1a4d1042a780f8d4c42eb8263`
and the later pre-radio-index/term-help candidate
`186ca73ade1bbd22a3f764456ae0503a3207bab967080d30e224a030d7f4eff7`
and the pre-grid-review candidate
`ef7a077dd92410fcde41e548242092ee658a2cc34a74532324b482bcca1df544`
were never published or flashed and remain retained privately as superseded
evidence; none was overwritten or deleted.

R2.5 is unflashed, not stable, not flash-qualified, and not
restore-allowlisted. USSD, repeater writes, TTL, IMEI, and Engineering-mode
mutations remain absent.
