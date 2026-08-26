# Security and privacy policy

Please report security-sensitive issues privately to the repository owner
through GitHub's private vulnerability reporting when available. Do not open a
public issue containing a credential, device identifier, private firmware
backup, SMS, router log, network capture, or reproducible destructive action.

The public repository accepts source code, synthetic fixtures, hashes, and
sanitized documentation. It does not accept:

- vendor firmware or device backup binaries;
- screenshots or raw live captures;
- passwords, cookies, Digest material, tokens, private keys, or `.env` files;
- serial numbers, MAC addresses, IMEI/IMSI/ICCID, SSIDs, phone numbers, or SMS;
- unattended live-delivery helpers or scripts that automatically flash,
  reset, reboot, or switch a device into a service mode.

The Scriptable client does contain explicit, user-confirmed device-management
controls. Contributions to those controls must remain fail-closed, visibly
labelled, and free of automatic retry after an ambiguous mutation.

Firmware builders are intentionally offline and fail closed. A structural
verification result is not a safety or compatibility guarantee.
