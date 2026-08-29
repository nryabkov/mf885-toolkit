# MF885 Community R2.6

`community-r2.6` is a golden-derived WebUI revision focused on the end-user
hang in the installed R2.5 UI. It is a standalone `/r26.html` application. It
does not start the stock `initIndex` stack, synchronous XHR, or background SMS
and modem watchers.

The first paint performs no router request. An explicit Sign in runs the exact
browser Digest challenge/login/status1 sequence. Every request is asynchronous
and has a ten-second timeout. Credentials and Digest HA1 stay in RAM and are
discarded on sign-out or reload.

Messages reads at most twenty router pages, renders each completed page, yields
between pages, and supports cancellation. Local Previous/Next never contacts
the router. Send and unique inbox Delete each have one mutation POST callsite,
zero automatic retries, bounded status GETs, and a complete folder readback.
Any unknown outcome locks further writes until reload. Diagnostics and Modem
remain manual reads of only `status1`, `wan`, and `Engineer_parameter`.

The exact reference-unit candidate is
`MF885_Community_0.2.6-community-r2-cafe-r2.bin`, 8,323,644 bytes, SHA-256
`de69ecf3474d74efd8dde139a7ccbb950c3db90c572936930fed20abdc579e54`.
Its portable plaintext SHA-256 is
`43f770b91f2bf199ab5cd486068cb7007a2af5158fd4a1ce667bf63c73a6e39b`.
Two in-memory builds and the retained build are byte-identical. Only WEBI
changes; 244,472 bytes of WEBI padding remain.

This source is structurally verified and offline fake-router tested. The image
is not installed, stable, generally flash-qualified, or restore-allowlisted.
Cold boot, repeatability, rollback, and live R2.6 behavior remain unproved.

