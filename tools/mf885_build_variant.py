#!/usr/bin/env python3
"""Build a reviewed MF885 variant from operator-supplied local inputs.

This wrapper performs no network or device I/O.  It delegates to the exact,
fail-closed builders in this repository and never flashes the result.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mf885_webi_builder as logs_builder
import mf885_webui_stage_builder as stage_builder


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLDEN = ROOT / "input" / "MF885_golden.bin"
DEFAULT_IDENTITY = ROOT / "input" / "mf885-base.xml"
DEFAULT_OUTPUT = ROOT / "out"

VARIANTS: dict[str, dict[str, Any]] = {
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


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Build a local structural-only MF885 firmware variant"
    )
    value.add_argument("--variant", choices=tuple(VARIANTS))
    value.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    value.add_argument("--identity-xml", type=Path, default=DEFAULT_IDENTITY)
    value.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    value.add_argument("--list", action="store_true", help="list reviewed variants")
    value.add_argument(
        "--acknowledge-brick-risk",
        action="store_true",
        help="acknowledge that a structurally valid image can still brick a device",
    )
    return value


def describe_variants() -> list[dict[str, str]]:
    return [
        {
            "name": name,
            "profile": specification["profile"],
            "artifact": specification["artifact"],
            "qualification": "structural-only; never flash-qualified by this wrapper",
        }
        for name, specification in VARIANTS.items()
    ]


def build(args: argparse.Namespace) -> int:
    if not args.variant:
        print("--variant is required", file=sys.stderr)
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
        "--confirm-structural-only",
    ]
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
