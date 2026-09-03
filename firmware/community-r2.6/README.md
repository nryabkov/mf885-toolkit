# MF885 Community R2.6

`community-r2.6` is a golden-derived WebUI revision focused on the end-user
hang in the installed R2.5 UI. It is a standalone `/r26.html` application. It
does not start the stock `initIndex` stack, synchronous XHR, or background SMS
and modem watchers.

The first paint performs no router request. An explicit Sign in runs the exact
browser Digest challenge/login/status1 sequence. Every request is asynchronous
and has a ten-second timeout. Credentials and Digest HA1 stay in RAM and are
discarded on sign-out or reload.

Expected request failures are shown inline with a stable error code and the
same per-session `R26-NNNN` request ID written to the browser console.
Unexpected JavaScript errors and unhandled promise rejections show a global
`E_UNEXPECTED` banner with a `JS-NNNN` ID while their full details remain in
the console. Console request metadata contains only method, query-free route,
status and elapsed time; response bodies, SMS, credentials and Authorization
are neither displayed nor logged.

Messages reads at most twenty router pages, renders each completed page, yields
between pages, and supports cancellation. Local Previous/Next never contacts
the router. Send and unique inbox Delete each have one mutation POST callsite,
zero automatic retries, bounded status GETs, and a complete folder readback.
Any unknown outcome locks further writes until reload. Diagnostics and Modem
remain manual reads of only `status1`, `wan`, and `Engineer_parameter`.

The exact reference-unit candidate is
`MF885_Community_0.2.6-community-r2-cafe-r2.bin`, 8,323,644 bytes, SHA-256
`66b534db9b4c14cc8e99243f4dd189dbb8f1a2a8a4b57227822023b211a38114`.
Its portable plaintext SHA-256 is
`5259fff7c799318fccb32ebc9f10484b9fe2b98e5311217d0d01a27c89165a26`.
Two in-memory builds and the retained build are byte-identical. Only WEBI
changes; 240,524 bytes of WEBI padding remain.

This source is structurally verified and offline fake-router tested. The image
is not installed, stable, generally flash-qualified, or restore-allowlisted.
Cold boot, repeatability, rollback, and live R2.6 behavior remain unproved.
