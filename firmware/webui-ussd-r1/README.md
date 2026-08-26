# WebUI USSD 0.0-ussd-r1

This is an intentionally locked, source-only scaffold showing how an eventual
USSD panel could fit the stock Custom Firewall layout without a new menu
loader. It is not registered in the builder, and no USSD firmware image exists.

The exact 2.5.94 OSLO contains modem-level `+CUSD`. Its three argument parsers
and call into the local supplementary-service API are statically closed, but no
exact WebUI/Duster endpoint or XML schema reaches that bridge. A separate
hard-coded service branch remains unsafe and is not a test code. The earlier
guessed endpoints were rejected live. Consequently this source contains no
XHR/fetch helper, no POST, no polling and no automatic router request. The Dial
control is natively disabled. A later revision may unlock it only after the
WebUI transport contract is statically identified and independently reproduced.

The scaffold is unbuildable, has no artifact hash or FBF delivery wrapper, is
not restore-allowlisted, and is not flash-qualified.
