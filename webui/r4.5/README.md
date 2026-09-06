# MF885 Community WebUI 0.4.5

[Инструкция на русском](../../docs/WEB_INTERFACE_RU.md)

The three HTML/JavaScript/CSS files are the exact original community additions
from the R4.5 image, checked against the pinned outputs in
[the R4.5 source builder](../../tools/mf885_community_r45.py).
[manifest.json](manifest.json) records their sizes and hashes. The source tree
contains no saved device data and does not include vendor WebUI files.

This is an on-device interface: open `/r45.html` on an MF885 that already has
the corresponding firmware. It depends on the router's existing
`js/library/md5.js`, Digest/API endpoints and origin. Opening the HTML locally
or on GitHub Pages does not create a working remote management client.
Copying these files does not install the native TTL hook.

For source reproduction use the offline `community-r4.5` builder with your own
supported backup and Base response; see the [build guide](../../docs/BUILD_FIRMWARE.md).
The interface's original measurement-pending text is retained to preserve its
exact deployed bytes. Read [current results and limits](../../docs/RELEASES.md).
TTL is fixed at 64; there is no value editor or runtime Off switch.

Current browser logging includes full router response bodies. Keep console
logs, HAR, SMS, identifiers and raw reports private. This source publication
is not a general stability, safe flashing or recovery qualification.
