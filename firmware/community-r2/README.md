# MF885 Community R2

`community-r2` is the English-only successor to Community R1. It is rebuilt
directly from a strictly verified 2.5.94 / Ver.D backup; it is never layered on
an installed custom image.

The profile keeps the bounded Community R1 SMS behavior and adds:

- a native Messages tab with Inbox, Outbox, SIM and Drafts entries;
- a Messages shortcut and `Community R2 · base 2.5.94` badge on the home page;
- high-confidence English spelling and copy corrections;
- an English-only client UI, with the Chinese, Hong Kong and Japanese Help,
  property and localized-image records removed;
- an opt-in `Remember me in this tab` login convenience.

The checkbox does not store the plaintext password. It stores the Digest HA1
value in `sessionStorage`; HA1 is still a password-equivalent credential. On a
reload, the page performs at most one fresh Digest challenge/login and one
protected exact-version status read. It never retries. Any malformed challenge,
wrong realm, login failure, unexpected device/firmware response or failure to
renew the tab record clears the saved value and leaves the normal login page
visible. If the optional save fails after a successful manual login, that
current page remains authenticated but will not be remembered after reload.

Keyboard, touch or mouse activity extends the tab lease. Ten minutes without
those events signs out and clears the saved value. Explicit sign-out and auth
errors also clear it; closing the tab normally clears `sessionStorage`. Any
same-origin script loaded by the router page can read HA1, and a stolen HA1 does
not cryptographically expire. Enable the checkbox only on a trusted device.

The SMS page can read and expand messages and can delete one inbox message only
after inline confirmation. It contains no composer or `SEND_SMS` request. A
delete is one exact POST with no automatic retry and requires complete readback;
an ambiguous outcome locks further deletion for that page session.

Removing 18 localized CAFE records reclaims 263,312 archive bytes. It does not
shrink the outer firmware file or make flashing faster: the output remains
8,323,644 bytes and the reclaimed space becomes 306,308 bytes of WEBI reserve.

Build from an operator-supplied compatible backup that passes every reviewed
gate:

```bash
python3 tools/mf885_build_variant.py \
  --variant community-r2 \
  --golden /path/to/MF885_golden.bin \
  --identity-xml /path/to/mf885-base.xml \
  --output-dir /existing/output/directory \
  --acknowledge-brick-risk
```

The reference-unit artifact is 8,323,644 bytes with raw SHA-256
`aebc751d87d8a007fc50cfb6b0788a6168127ca8988d989176de902986a487ee`.
The encrypted header is unit-bound, so another compatible unit normally
produces a different raw hash. Its decrypted portable fingerprint must be
`022b36407d6f9e38da6b45d21a86461501398bb3e142b9048df8414594413a9f`.

This is a deterministic, structurally verified but unflashed experiment.
Structural verification is not proof of bootability, compatibility, rollback
or recovery. Flashing can permanently brick the device. The public toolkit has
no live flashing helper and distributes no vendor firmware binary.
