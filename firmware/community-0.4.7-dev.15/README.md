# Community 0.4.7-dev.15

Source-only AT and variable initial USSD interface for MF96 Ver.D/base2.5.94.
Open `/c047d15.html` on matching installed firmware. Read the
[usage/build guide](../../docs/AT_USSD_047D15_RU.md).

Reference unit: exact boot/assets/recovery, AT+CSQ, AT+CREG? and one attributed
nonempty *100# reply passed on2026-09-09. No universal command/carrier/stability
claim; interactive USSD continuation is not qualified. Prior USB instability
remains unresolved. Generated outputs are not hardware-tested by the builder.

Native source equals the dev14 implementation; dev15 changes web error semantics
and registration checks. Build only from a user-supplied exact original. The
public adapter removes private cache/path dependencies and retains the original
native and served-asset hashes. No binary firmware or live installer is supplied.
Reference qualification checkpoint in private mf885-management:ca51392;
execution source:591b445. These are provenance, not additional public dependencies.
