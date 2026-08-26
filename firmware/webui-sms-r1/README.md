# WebUI SMS 0.0-sms-r1 — CAFE container revision 2

This is a compact replacement for the exact stock `SMS.html` and `SMS.js`
records. It is rebuilt directly from the exact 2.5.94 golden image; it is not
based on either Logs Canary.

The page performs no automatic mutation. Reading history uses the stock
semantic-read message contract. Send and delete require an explicit click,
issue exactly one stock `message` command, poll only its status, and keep all
mutation controls locked if the outcome becomes ambiguous. Delete also needs a
native browser confirmation. The page log records command numbers and status,
never SMS bodies or participants.

The generated image is an offline structural artifact only. It is unflashed,
not restore-allowlisted, has no FBF delivery wrapper, and is not flash-qualified.

Build from the exact golden image only:

```bash
python3 tools/mf885_webui_stage_builder.py \
  --golden /path/to/MF885-golden.bin \
  --identity-xml /path/to/status1-identity.xml \
  --profile 0.0-sms-r1 \
  --output build/MF885_Community_0.0-sms-r1-cafe-r2.bin \
  --report build/MF885_Community_0.0-sms-r1-cafe-r2.report.json \
  --confirm-structural-only
```

The expected artifact is 8,323,644 bytes with SHA-256
`c27b5f7989ac4e4ac6ff1ebdd603685f6f1fe777918458059b620b1c36ec73ce`.
The command only writes the requested local artifact and report; it has no
router, upload, reset, FBF-publish, or flash path.

The historical artifact `f1f5f7…71a6` is quarantined as noncanonical because
its two replacement records were not stored on four-byte CAFE boundaries. It
was never flashed. The corrected container adds the required `0xff` padding;
it is still experimental, unflashed, not stable and not restore-allowlisted.
