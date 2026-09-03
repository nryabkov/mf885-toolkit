# MF885 Community R2.8 extension

Community R2.8 keeps the existing MF885 interface and adds `Modem Lab` as its
fifth tab. It is not a GL.iNet page or a replacement router UI. The user signs
in to MF885 once and stays in the same Community shell.

## What R2.8 adds

- One curated read-only action, **Check signal once**, mapped to the exact
  qualified seven-byte `AT+CSQ\r` frame.
- The parsed `+CSQ` values, exact escaped raw modem response, byte count,
  SHA-256, terminal reason, request ID and cleanup state appear together.
- Every expected failure is visible with the same searchable request ID used
  in the console. Unexpected JavaScript failures receive a safe `JS28-*` ID;
  details remain in the console. The UI never fails silently.
- A lost response after dispatch becomes `OUTCOME_UNKNOWN`; checking saved
  evidence never resends the USB query. There is no polling or automatic retry.
- Non-empty Messages accepts the router's proved comma-delimited multipart
  record IDs. Reading stays available independently of mutation safety; Delete
  is enabled only when the complete history proves a unique record and unique
  component tokens, and readback requires every submitted token to disappear.
- Every router response, flow variable and condition is correlated in the
  console by request ID. The transient Modem Lab session response is the one
  deliberate raw-body exception because it carries short-lived CSRF material;
  its status, timing and size remain logged.
- The four existing Community screens retain distinct Diagnostics/Modem
  projections, bounded reads and one-owner Digest flow.

## Invisible GL.iNet half

The physical Mobile AT USB interface is attached to GL.iNet. A loopback-only
gateway therefore proxies ordinary MF885 HTTP transactions and owns the narrow
`/community-api/modem-lab/*` namespace. It mints a short-lived hidden session
only after the complete MF885 Digest login plus exact `status1` identity.

The GL package contains no LuCI page, menu, browser ACL, second login, public
listener or free-form AT input. Digest proof, router cookies and bridge secrets
are never journaled. Full raw modem evidence is private and correlated by the
same request ID shown in the MF885 tab.

Direct access to the MF885 origin still supports the four ordinary screens,
but Modem Lab stops visibly before dispatch because the stock MF885 server has
no proved route to GL.iNet. The complete fifth-tab path uses the Community
gateway access route.

## Candidate identity

The exact reference-unit structural candidate is
`MF885_Community_0.2.8-community-r2-cafe-r2.bin`, 8,323,644 bytes, SHA-256
`b39a8d516d1d37fd7d4aa474cb5973ee3d1f7c4632cbfc0faa016c060dcb4eb1`.
Its portable plaintext SHA-256 is
`19b21c5b082b3feca875b5c6b06cdd089a75dbbe32e39a61270a792c9484ad9d`.

Two independent local builds from the exact reviewed golden were byte-for-byte
identical. Only WEBI changes; every other partition remains byte-identical.
The corrected candidate retains 194,872 padding bytes. The superseded
`5ad6c52f…1237a` image is preserved under an explicit `superseded` filename.

The backend-only GL declaration is installed as backend-v4 with a green
postcheck and one loopback listener. Its last qualifier was interrupted before
authentication by an independently proved neighboring radio-route collision;
it did not reach the modem query. USB/RNDIS fallback has since proved a clean
lease and complete cleanup, and a separate live RNDIS Web capture localized the
R2.7 Messages failure to multipart-ID client validation rather than HTTP or
transport. The corrected source passes 26/26 named Messages/responsiveness,
9/9 browser-flow and 9/9 Modem Lab scenarios plus two exact-golden deterministic
builds. The corrected R2.8 UI is not installed, so its live non-empty rendering
and the complete product-path `signal_quality` round trip remain delivery
checks. Building this image is not permission to flash. Cold boot,
repeatability and rollback remain unproved.
