# MF885 Community R2.9 extension

Community R2.9 is a focused usability successor to the proven installed R2.8
image. It keeps the existing MF885 interface and the R2.8 transport, Messages
wire contract, diagnostics projections and failure IDs. It does not replace
the router settings UI.

## What R2.9 changes

- Core controls become usable immediately after the exact three-request MF885
  login. A slow or missing hidden GL.iNet bridge is no longer part of login and
  cannot hold the whole interface disabled for another 35 seconds.
- The authenticated shell progressively loads one shared device/radio snapshot
  and the newest Messages page without waiting for a button click. The login
  `status1` identity response is reused as the first snapshot source, so the
  bootstrap ceiling after login is two model GETs plus one semantic Messages
  POST/GET pair.
- One universal scheduler restores bounded live data for every Community
  screen regardless of the active tab. It refreshes the three-source device
  snapshot every 30 seconds and the newest Messages page every 60 seconds.
  The same complete cycle is available as **Refresh all**. Polling pauses when
  the browser is hidden, defers while a user or mutation operation owns the
  router, resumes after completion and never retries a router request or
  catches up with a burst.
- Automatic Messages refresh is deliberately limited to one page. A complete
  history remains an explicit button action because the inherited 20-page
  flow can require up to 40 sequential requests and must not starve device
  status.
- `Modem Lab` and its external transport are removed from the firmware-facing
  product surface. Modem uses only the router's existing authenticated HTTP
  models; login, refresh and logout do not depend on the hidden GL.iNet
  backend.
- Modem now contains a full help catalogue. It separates fields observed on
  this exact MF885 from UMTS/GSM/GPRS fields merely present in the firmware
  schema, identifies private WAN values, defines the main LTE terms and lists
  functions that are deliberately unavailable.
- Engineering mode is described and displayed read only. It is a stock WAN
  diagnostic selector, not a modem command console; controlled observations
  returned the complete LTE report while it was disabled, so R2.9 neither
  enables it nor offers a switch.
- Diagnostics keeps the three detailed source cards. Modem keeps its distinct
  radio projection and a compact freshness pointer instead of repeating the
  same source grid, so the two screens no longer look identical.
- URL hash/back navigation is honored. An early application-load watchdog
  replaces a permanently stuck `Loading interface…` screen with a visible
  searchable `JS29-BOOT` error.

Every router request, raw response, scheduler variable, condition, skip reason
and expected failure remains correlated by request ID in the console. Private
subscriber and WAN values may be shown locally when the router returns them,
but are not suitable for public evidence.

## Safety boundaries

Live polling performs only existing router read surfaces. The R2.9 browser
bundle has no modem-command endpoint, no manual or automatic external modem
query and no debug-profile control. It never sends a firmware POST, MINI
transition, SMS mutation, reset or automatic retry.

## Known-good installed identity

R2.9 is the latest proven installed firmware and the retained known-good SMS
baseline. Authenticated Inbox reading on the installed unit returned the two
new messages produced after the two one-shot `*100#` requests; ordinary SMS
content decoding and display therefore work. This does not claim live proof of
Send or Delete.

The exact 8,323,644-byte known-good image has SHA-256
`366f85045f84d669412d14ef9cb2e0445eddec57658e3676ee7c7388bba5ff91`
and portable plaintext SHA-256
`fee126ed00b6dddd64d8df67cc806f7934908290e325ec7fe49830edb58f63e2`.
The rebuilt WEBI retains 195,644 bytes of padding. The exact file remains at
`build/MF885_Community_0.2.9-community-r2-cafe-r2.bin`; a second private copy
under candidate-v2 has the same SHA-256. A same-named candidate-v1 file has a
different SHA-256 and is not the known-good image, so selection must always use
the exact hash rather than the basename.

Future releases must keep this artifact intact and prove Inbox read/decode as
an explicit regression gate. Cold boot, repeatability and rollback remain
unproved; retaining the file is not proof that rollback is safe.
