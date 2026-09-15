#!/usr/bin/env python3
"""Build the pinned dev.18 source in an isolated offline Python process."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIRMATION = '--acknowledge-brick-risk'

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('golden', 'identity-xml', 'output', 'report'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument(CONFIRMATION, action='store_true')
    args = parser.parse_args(argv)
    if not args.acknowledge_brick_risk:
        parser.error(CONFIRMATION + ' is required; a generated image can brick the device')
    # A separate process prevents generic frozen module names from binding to
    # another firmware revision already imported by a caller or test suite.
    sys.path[:0] = [str(ROOT / 'firmware/community-0.4.7-dev.18'), str(ROOT / 'tools')]
    import builder as candidate
    try:
        candidate.native.architecture_inputs()
        report = candidate.comparator.publish_candidate(
            golden_path=args.golden, identity_path=args.identity_xml,
            output_path=args.output, report_path=args.report,
            artifact_name=candidate.ARTIFACT,
            schema='mf885-047d18-public-build/v1',
            verification_schema='mf885-047d18-public-verify/v1',
            profile=candidate.PROFILE, label=candidate.PROFILE,
            confirmation=True, confirmation_flag=CONFIRMATION,
            native_build=candidate.native.build_payload,
            native_conditions=candidate.native_conditions,
            qualification={
                'flash_qualified': False, 'stable': False,
                'this_output_hardware_tested': False,
                'persistence_proven': False, 'rollback_proven': False,
                'reference_status': 'one-device dev18 boot/assets, authenticated theme UI and bounded IPv4 TTL observations including Off; CPU accuracy and long-term USB stability unqualified',
                'reference_date': '2026-09-15',
                'qualification_document': 'docs/TTL_THEME_047D18_RU.md',
            }, error=candidate.release.Error,
        )
        # Full reports may contain unit fingerprints; retain them only locally.
        print(json.dumps({'status': 'verified-offline', 'output': str(args.output),
                          'report': str(args.report), 'flash_qualified': False}))
        return 0
    except Exception as exc:
        print('dev.18 offline build failed: ' + str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
