#!/usr/bin/env python3
"""Build and verify the exact-golden R4.6 configurable TTL editor firmware offline."""

from __future__ import annotations

import argparse
import json
import lzma
import sys
from pathlib import Path
from typing import Any

import mf885_community_r30_native_builder as shared
import mf885_community_r33_native_builder as r33_builder
import mf885_community_r46 as release
import mf885_exact_golden_comparator_builder as comparator
import mf885_firmware_inspect as inspector
import mf885_thumb_llvm_build as thumb
import mf885_ttl_native_payload_r46 as native
import mf885_webi_builder as webi
import mf885_webui_stage_builder as stage


PROFILE = release.PROFILE
ARTIFACT = "MF885_Community_0.4.6-community-r2-native-r20-cafe-r2.bin"
SCHEMA = "mf885-community-r46-native-ttl-editor-build/v1"
VERIFICATION_SCHEMA = "mf885-community-r46-native-ttl-editor-verification/v1"
LABEL = "R4.6"
CONFIRMATION_FLAG = "--confirm-native-ttl-editor-risk"

QUALIFICATION = {
    "full_firmware_container_built": True, "flash_qualified": False,
    "packet_hook_in_candidate": True, "diagnostic_callbacks_installed": True,
    "custom_state_installed": True, "runtime_off_available_in_code": True,
    "live_callbacks_verified": False, "live_dynamic_ttl_verified": False,
    "live_off_verified": False, "state_memory_writability_verified": False,
    "persistence_proven": False, "cold_boot_proven": False,
    "rollback_proven": False,
    "reason": "Offline ARMv5TE/Thumb1 native state editor; hardware qualification remains required.",
}


class CommunityR46NativeError(RuntimeError):
    pass


def _native_verification_conditions(native_report, safety):
    c = comparator.condition
    checks = [
        c("native_component_sha256", "7c3a8d06b3cdb2d8bdd91eb028d82c103d05e9e8f29b756b7f8c86192e8b30b8", native_report["artifact"]["sha256"]),
        c("native_architecture", {k:v.decode() for k,v in native.TARGET.items()}, native_report["architecture"]),
        c("native_patch_names", ["forward","post_set","ram_state_and_names","pre_get","ip_forward_hook","diagnostic_post_set","diagnostic_pre_get"], [r["name"] for r in native_report["changed_ranges"]]),
        c("native_initial_ttl",64,native_report["contract"]["initial_value"]),
        c("native_off",0,native_report["contract"]["off_value"]),
        c("web_mode","native-ram-editor",safety["ttlMode"]),
        c("web_manual_read_gets",2,safety["ttlBrowserGetRequestsPerRead"]),
        c("web_write_posts",1,safety["ttlBrowserPostRequestsPerChange"]),
        c("web_write_gets",2,safety["ttlBrowserGetRequestsPerChange"]),
        c("web_automatic_ttl_requests",0,safety["ttlAutomaticRequests"]),
        c("web_write_retries",0,safety["automaticMutationRetries"]),
        c("web_raw_response_logging",False,safety["rawResponseBodiesLogged"]),
        c("web_live_qualification",False,safety["ttlPacketPathQualified"]),
    ]
    checks.extend(native_report["stock_abi"]["conditions"])
    return checks


def build_candidate(golden_raw: bytes, identity: inspector.IdentityMaterial) -> tuple[bytes, dict[str, Any]]:
    return comparator.build_candidate(golden_raw, identity, profile=PROFILE, schema=SCHEMA, label=LABEL, native_build=native.build_payload, error=CommunityR46NativeError)


def verify_candidate(golden_raw: bytes, candidate: bytes, identity: inspector.IdentityMaterial) -> dict[str, Any]:
    return comparator.verify_candidate(golden_raw, candidate, identity, profile=PROFILE, verification_schema=VERIFICATION_SCHEMA, label=LABEL, native_build=native.build_payload, native_conditions=_native_verification_conditions, error=CommunityR46NativeError)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Build the full R4.6 firmware container offline; does not flash")
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
            label=LABEL, confirmation=args.confirm_native_ttl_editor_risk,
            confirmation_flag=CONFIRMATION_FLAG, native_build=native.build_payload,
            native_conditions=_native_verification_conditions, qualification=QUALIFICATION,
            error=CommunityR46NativeError,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (CommunityR46NativeError, shared.CommunityR30NativeError, r33_builder.CommunityR33NativeError, native.TtlR46PayloadError, thumb.NativeBuildError, inspector.InspectionError, webi.BuildError, stage.StageBuildError, OSError, lzma.LZMAError, TypeError, ValueError) as exc:
        print(f"R4.6 native build failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
