# Releases and stability labels

The toolkit and generated firmware variants have separate version streams.

## Toolkit releases

Source/toolkit releases use SemVer tags such as `toolkit-v0.1.0`. A release
tag identifies the Scriptable client, builders, inspector, variant sources,
tests, and documentation at one reviewed commit. The release page must state
which test suites ran and whether any tests were skipped for lack of a local
golden image.

`Latest` means the recommended public source release. It does not qualify any
generated firmware image for flashing.

## Firmware variants

Each variant has a logical ID and a container revision. For example,
`0.0-logs-r1-cafe2` means Logs r1 content rebuilt with the second reviewed CAFE
container encoding. A new container revision always gets a new ID and output
filename; old hashes are never silently replaced.

Every manifest must expose explicit booleans/status fields. Use these meanings:

- `experimental-unflashed`: reproducible offline build only;
- `superseded-unflashed`: reproducible offline build retained unchanged after
  a newer source revision became the recommendation; it remains unflashed;
- `experimental-live-qualified-canary`: observed on a named exact hardware and
  firmware profile, but not generally safe;
- `quarantined-*`: known-invalid or misleading artifact retained only for
  historical analysis;
- `stable`: reserved for a future variant with repeatable delivery, verified
  cold boot and dwell behavior, and a separately demonstrated recovery path.

At present **no firmware variant is stable, generally flash-qualified, or
restore-allowlisted**. Do not infer stability from a successful build, a known
SHA-256, one live device, or the word `verified` in a structural report.

Operation-safety records are not toolkit releases and are never stability
labels.
