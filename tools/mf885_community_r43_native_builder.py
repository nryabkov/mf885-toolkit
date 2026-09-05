#!/usr/bin/env python3
"""Build and verify the exact-golden R4.3 fixed64 forwarding firmware offline."""

from __future__ import annotations

import argparse
import json
import lzma
import sys
from pathlib import Path
from typing import Any

import mf885_community_r30_native_builder as shared
import mf885_community_r33_native_builder as r33_builder
import mf885_community_r43 as release
import mf885_exact_golden_comparator_builder as comparator
import mf885_firmware_inspect as inspector
import mf885_thumb_llvm_build as thumb
import mf885_ttl_native_payload_r43 as native
import mf885_webi_builder as webi
import mf885_webui_stage_builder as stage


PROFILE = release.PROFILE
ARTIFACT = "MF885_Community_0.4.3-community-r2-native-r17-cafe-r2.bin"
SCHEMA = "mf885-community-r43-fixed64-forward-build/v1"
VERIFICATION_SCHEMA = "mf885-community-r43-fixed64-forward-verification/v1"
LABEL = "R4.3"
CONFIRMATION_FLAG = "--confirm-fixed64-forwarding-risk"

QUALIFICATION = {
    "full_firmware_container_built": True,
    "flash_qualified": False,
    "packet_hook_in_candidate": True,
    "live_forward_hook_execution": False,
    "live_packet_ttl_verified": False,
    "fixed_ttl": 64,
    "runtime_off_available": False,
    "direction_filter": False,
    "custom_state_installed": False,
    "diagnostic_callbacks_installed": False,
    "persistence_proven": False,
    "cold_boot_proven": False,
    "repeatability_proven": False,
    "rollback_proven": False,
    "reason": "Offline deterministic full container and isolated packet contract only; real forwarding and absolute egress TTL remain unproved.",
}


class CommunityR43NativeError(RuntimeError):
    pass


def _native_verification_conditions(native_report: dict[str, Any], safety: dict[str, Any]) -> list[dict[str, Any]]:
    component, contract = native_report["component"], native_report["packet_contract"]
    condition = comparator.condition
    checks = [
        condition("native_helper_runtime", "0x060012a1", component["runtime"]),
        condition("native_helper_bytes", 140, component["bytes"]),
        condition("native_helper_sha256", native.FORWARD_SHA256, component["sha256"]),
        condition("native_patch_ranges", native.CHANGED_RANGES, native_report["changed_ranges"]),
        condition("native_fixed_ttl", 64, contract["fixed_ttl"]),
        condition("native_runtime_off", False, contract["runtime_off_available"]),
        condition("native_direction_filter", None, contract["direction_filter"]),
        condition("native_output_calls", 1, contract["output_calls"]),
        condition("native_output_return", True, contract["output_return_preserved"]),
        condition("native_ttl_one_preserved", True, contract["ttl_at_hook_one_preserved"]),
        condition("native_diagnostic_callbacks", False, contract["diagnostic_callbacks_installed"]),
        condition("native_custom_state_accesses", 0, contract["custom_state_accesses"]),
        condition("web_fixed_ttl", 64, safety["ttlFixedValue"]),
        condition("web_scope", "eligible-forwarded-ipv4-both-directions", safety["ttlScope"]),
        condition("web_full_image_hook", True, safety["ttlForwardingHookIncludedInFullImage"]),
        condition("web_mode", "fixed-64", safety["ttlMode"]),
    ]
    for key in ("ttlBrowserGetRequests", "ttlBrowserPostRequests", "diagnosticBrowserRequests", "diagnosticGetCallbacks", "automaticMutationRetries"):
        checks.append(condition("web_" + key, 0, safety[key]))
    for key in ("ttlAvailable", "ttlRuntimeOffAvailable", "ttlDirectionFilter", "ttlPacketPathQualified", "firmwareControlEnabled", "systemChannelBridgeUsed"):
        checks.append(condition("web_" + key, False, safety[key]))
    checks.extend(native_report["preservation_conditions"])
    return checks


def build_candidate(golden_raw: bytes, identity: inspector.IdentityMaterial) -> tuple[bytes, dict[str, Any]]:
    return comparator.build_candidate(golden_raw, identity, profile=PROFILE, schema=SCHEMA, label=LABEL, native_build=native.build_payload, error=CommunityR43NativeError)


def verify_candidate(golden_raw: bytes, candidate: bytes, identity: inspector.IdentityMaterial) -> dict[str, Any]:
    return comparator.verify_candidate(golden_raw, candidate, identity, profile=PROFILE, verification_schema=VERIFICATION_SCHEMA, label=LABEL, native_build=native.build_payload, native_conditions=_native_verification_conditions, error=CommunityR43NativeError)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Build the full R4.3 firmware container offline; does not flash")
    value.add_argument("--golden", type=Path, required=True)
    value.add_argument("--identity-xml", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--report", type=Path, required=True)
    value.add_argument(CONFIRMATION_FLAG, action="store_true")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = comparator.publish_candidate(
            golden_path=args.golden, identity_path=args.identity_xml,
            output_path=args.output, report_path=args.report, artifact_name=ARTIFACT,
            schema=SCHEMA, verification_schema=VERIFICATION_SCHEMA, profile=PROFILE,
            label=LABEL, confirmation=args.confirm_fixed64_forwarding_risk,
            confirmation_flag=CONFIRMATION_FLAG, native_build=native.build_payload,
            native_conditions=_native_verification_conditions, qualification=QUALIFICATION,
            error=CommunityR43NativeError,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (CommunityR43NativeError, shared.CommunityR30NativeError, r33_builder.CommunityR33NativeError, native.TtlR43PayloadError, thumb.NativeBuildError, inspector.InspectionError, webi.BuildError, stage.StageBuildError, OSError, lzma.LZMAError, TypeError, ValueError) as exc:
        print(f"R4.3 native build failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
