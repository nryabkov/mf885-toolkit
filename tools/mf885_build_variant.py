#!/usr/bin/env python3
"""Build a reviewed MF885 variant from operator-supplied local inputs.

This wrapper performs no network or device I/O.  It delegates to the exact,
fail-closed builders in this repository and never flashes the result.
"""

from __future__ import annotations

import argparse
import json
import sys
import subprocess
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mf885_webi_builder as logs_builder
import mf885_webui_stage_builder as stage_builder
import mf885_community_r35_native_builder as r35_native_builder
import mf885_community_r42_native_builder as r42_native_builder
import mf885_community_r43_native_builder as r43_native_builder
import mf885_community_r44_native_builder as r44_native_builder
import mf885_community_r45_native_builder as r45_native_builder
import mf885_community_r46_native_builder as r46_native_builder


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLDEN = ROOT / "input" / "MF885_golden.bin"
DEFAULT_IDENTITY = ROOT / "input" / "mf885-base.xml"
DEFAULT_OUTPUT = ROOT / "out"

VARIANTS: dict[str, dict[str, Any]] = {
    "community-0.4.7-dev.5": {"kind": "native-047d5", "profile": "0.4.7-dev.5", "artifact": "MF885-Community-0.4.7-dev.5-base-2.5.94.bin"},
    "community-0.4.7-dev.4": {"kind": "native-047d4", "profile": "0.4.7-dev.4", "artifact": "MF885-Community-0.4.7-dev.4-base-2.5.94.bin"},
    "community-r4.6": {"kind": "native-r46", "profile": r46_native_builder.PROFILE, "artifact": r46_native_builder.ARTIFACT},
    "community-r4.5": {
        "kind": "native-r45",
        "profile": r45_native_builder.PROFILE,
        "artifact": r45_native_builder.ARTIFACT,
    },
    "community-r4.4": {
        "kind": "native-r44",
        "profile": r44_native_builder.PROFILE,
        "artifact": r44_native_builder.ARTIFACT,
    },
    "community-r4.3": {
        "kind": "native-r43",
        "profile": r43_native_builder.PROFILE,
        "artifact": r43_native_builder.ARTIFACT,
    },
    "community-r4.2": {
        "kind": "native-r42",
        "profile": r42_native_builder.PROFILE,
        "artifact": r42_native_builder.ARTIFACT,
    },
    "community-r3.5": {
        "kind": "native-r35",
        "profile": "0.3.5-community-r2",
        "artifact": "MF885_Community_0.3.5-community-r2-native-r9-cafe-r2.bin",
    },
    "community-r2.9": {
        "kind": "stage",
        "profile": "0.2.9-community-r2",
        "artifact": "MF885_Community_0.2.9-community-r2-cafe-r2.bin",
    },
    "community-r2.8": {
        "kind": "stage",
        "profile": "0.2.8-community-r2",
        "artifact": "MF885_Community_0.2.8-community-r2-cafe-r2.bin",
    },
    "community-r2.7": {
        "kind": "stage",
        "profile": "0.2.7-community-r2",
        "artifact": "MF885_Community_0.2.7-community-r2-cafe-r2.bin",
    },
    "community-r2.6": {
        "kind": "stage",
        "profile": "0.2.6-community-r2",
        "artifact": "MF885_Community_0.2.6-community-r2-cafe-r2.bin",
    },
    "community-r2.5": {
        "kind": "stage",
        "profile": "0.2.5-community-r2",
        "artifact": "MF885_Community_0.2.5-community-r2-cafe-r2.bin",
    },
    "community-r2.4": {
        "kind": "stage",
        "profile": "0.2.4-community-r2",
        "artifact": "MF885_Community_0.2.4-community-r2-cafe-r2.bin",
    },
    "community-r2.3": {
        "kind": "stage",
        "profile": "0.2.3-community-r2",
        "artifact": "MF885_Community_0.2.3-community-r2-cafe-r2.bin",
    },
    "community-r2.2": {
        "kind": "stage",
        "profile": "0.2.2-community-r2",
        "artifact": "MF885_Community_0.2.2-community-r2-cafe-r2.bin",
    },
    "community-r2.1": {
        "kind": "stage",
        "profile": "0.2.1-community-r2",
        "artifact": "MF885_Community_0.2.1-community-r2-cafe-r2.bin",
    },
    "community-r2": {
        "kind": "stage",
        "profile": "0.2-community-r2",
        "artifact": "MF885_Community_0.2-community-r2-cafe-r2.bin",
    },
    "community-r1": {
        "kind": "stage",
        "profile": "0.1-community-r1",
        "artifact": "MF885_Community_0.1-community-r1-cafe-r2.bin",
    },
    "logs-r1": {
        "kind": "logs",
        "profile": "0.0-logs-r1",
        "source": ROOT / "firmware" / "webui-canary-logs" / "canary_logs.js",
        "artifact": "MF885_Community_0.0-logs-r1-auth-r4-cafe-r2.bin",
    },
    "logs-r2": {
        "kind": "logs",
        "profile": "0.0-logs-r2",
        "source": ROOT / "firmware" / "webui-canary-logs-r2" / "canary_logs.js",
        "artifact": "MF885_Community_0.0-logs-r2-auth-r4-cafe-r2.bin",
    },
    "sms-r1": {
        "kind": "stage",
        "profile": "0.0-sms-r1",
        "artifact": "MF885_Community_0.0-sms-r1-cafe-r2.bin",
    },
}


# Historical builders preserve immutable research artifacts. Their target
# assumptions do not satisfy the verified ARMv5TE/Thumb-1 deployment profile.
# A generic brick-risk acknowledgement must not bypass a known target mismatch.
QUARANTINED_VARIANTS = frozenset({"community-r3.5", "community-r4.2", "community-r4.3"})
QUARANTINE_REASON = (
    "historical ARMv7/Cortex-A9 target assumptions conflict with the verified "
    "ARMv5TE/Thumb-1 deployment profile; retained for offline analysis only"
)


HARDWARE_FAILED_VARIANTS = frozenset({"community-r4.6"})
HARDWARE_FAILURE_REASON = (
    "R4.6 passed boot/static checks but its first native TTL GET timed out with "
    "zero response bytes and USB identity drift; automatic recovery was observed, "
    "root cause is unresolved, and the editor must not be used"
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Build a local structural-only MF885 firmware variant"
    )
    value.add_argument("--variant", choices=tuple(VARIANTS))
    value.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    value.add_argument("--identity-xml", type=Path, default=DEFAULT_IDENTITY)
    value.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    value.add_argument("--list", action="store_true", help="list variants and explicit build eligibility")
    value.add_argument(
        "--acknowledge-brick-risk",
        action="store_true",
        help="acknowledge that a structurally valid image can still brick a device",
    )
    return value


def describe_variants() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "profile": specification["profile"],
            "artifact": specification["artifact"],
            "qualification": "structural-only; never flash-qualified by this wrapper",
            "build_allowed": name not in QUARANTINED_VARIANTS | HARDWARE_FAILED_VARIANTS,
            "status": "quarantined-target-mismatch" if name in QUARANTINED_VARIANTS else "quarantined-hardware-test-failed" if name in HARDWARE_FAILED_VARIANTS else "experimental",
            "reason": QUARANTINE_REASON if name in QUARANTINED_VARIANTS else HARDWARE_FAILURE_REASON if name in HARDWARE_FAILED_VARIANTS else "hardware qualification is separate",
        }
        for name, specification in VARIANTS.items()
    ]


def build(args: argparse.Namespace) -> int:
    if not args.variant:
        print("--variant is required", file=sys.stderr)
        return 2
    if args.variant in QUARANTINED_VARIANTS:
        print(f"refusing quarantined variant {args.variant}: {QUARANTINE_REASON}", file=sys.stderr)
        return 2
    if args.variant in HARDWARE_FAILED_VARIANTS:
        print(f"refusing quarantined variant {args.variant}: {HARDWARE_FAILURE_REASON}", file=sys.stderr)
        return 2
    if not args.acknowledge_brick_risk:
        print(
            "refusing to build without --acknowledge-brick-risk; "
            "a structurally valid image can still permanently brick the device",
            file=sys.stderr,
        )
        return 2
    if not args.output_dir.is_dir():
        print("output directory must already exist", file=sys.stderr)
        return 2

    specification = VARIANTS[args.variant]
    output = args.output_dir / specification["artifact"]
    report = args.output_dir / (specification["artifact"] + ".report.json")
    common = [
        "--golden",
        str(args.golden),
        "--identity-xml",
        str(args.identity_xml),
        "--output",
        str(output),
        "--report",
        str(report),
    ]
    if specification["kind"] == "native-047d5":
        return subprocess.run([sys.executable, "-B", str(TOOLS / "mf885_build_047d5.py"), *common, "--acknowledge-brick-risk"], check=False).returncode
    if specification["kind"] == "native-047d4":
        return subprocess.run([sys.executable, "-B", str(TOOLS / "mf885_build_047d4.py"), *common, "--acknowledge-brick-risk"], check=False).returncode
    if specification["kind"] == "native-r46":
        return r46_native_builder.main(common + [r46_native_builder.CONFIRMATION_FLAG])
    if specification["kind"] == "native-r45":
        return r45_native_builder.main(common + [r45_native_builder.CONFIRMATION_FLAG])
    if specification["kind"] == "native-r44":
        return r44_native_builder.main(common + [r44_native_builder.CONFIRMATION_FLAG])
    if specification["kind"] == "native-r43":
        return r43_native_builder.main(common + [r43_native_builder.CONFIRMATION_FLAG])
    if specification["kind"] == "native-r42":
        return r42_native_builder.main(common + [r42_native_builder.CONFIRMATION_FLAG])
    if specification["kind"] == "native-r35":
        return r35_native_builder.main(common + ["--confirm-native-ttl-risk"])
    common.append("--confirm-structural-only")
    if specification["kind"] == "logs":
        return logs_builder.main(
            common
            + [
                "--profile",
                specification["profile"],
                "--script",
                str(specification["source"]),
            ]
        )
    return stage_builder.main(
        common + ["--profile", specification["profile"]]
    )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.list:
        print(json.dumps(describe_variants(), indent=2))
        return 0
    return build(args)


if __name__ == "__main__":
    raise SystemExit(main())
