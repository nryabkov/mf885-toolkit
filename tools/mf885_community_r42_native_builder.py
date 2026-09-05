#!/usr/bin/env python3
"""Build and verify the exact-golden R4.2 context-read firmware offline."""

from __future__ import annotations

import argparse
import json
import lzma
import sys
from pathlib import Path
from typing import Any

import mf885_community_r30_native_builder as shared
import mf885_community_r33_native_builder as r33_builder
import mf885_community_r42 as release
import mf885_exact_golden_comparator_builder as comparator
import mf885_firmware_inspect as inspector
import mf885_thumb_llvm_build as thumb
import mf885_ttl_native_payload_r42 as native
import mf885_webi_builder as webi
import mf885_webui_stage_builder as stage


PROFILE = release.PROFILE
ARTIFACT = "MF885_Community_0.4.2-community-r2-native-r16-cafe-r2.bin"
SCHEMA = "mf885-community-r42-guarded-context-read-build/v1"
VERIFICATION_SCHEMA = "mf885-community-r42-guarded-context-read-verification/v1"
LABEL = "R4.2"
CONFIRMATION_FLAG = "--confirm-guarded-context-read-risk"

QUALIFICATION = {
    "full_firmware_container_built": True,
    "flash_qualified": False,
    "guarded_context_read_live_survival": False,
    "context_load_execution_proven": False,
    "context_type_value_proven": False,
    "ttl_functional": False,
    "state_installed": False,
    "request_tree_parser_installed": False,
    "packet_hook_installed": False,
    "persistence_proven": False,
    "cold_boot_proven": False,
    "repeatability_proven": False,
    "rollback_proven": False,
    "reason": (
        "offline deterministic full container only; later survival of the guarded "
        "callback does not establish the taken branch or loaded context value"
    ),
}


class CommunityR42NativeError(RuntimeError):
    pass


def _native_verification_conditions(native_report: dict[str, Any], safety: dict[str, Any]) -> list[dict[str, Any]]:
    component, transport = native_report["component"], native_report["transport"]
    condition = comparator.condition
    checks = [
        condition("native_callback_slot", "post_set", transport["callback_slot"]),
        condition("native_callback_runtime", "0x06001341", component["runtime"]),
        condition("native_callback_bytes", 12, component["bytes"]),
        condition("native_callback_hex", "032801d101b1088800207047", component["hex"]),
        condition("native_callback_sha256", native.CALLBACK_SHA256, component["sha256"]),
        condition("native_guard", "phase == 3 and context != NULL", transport["read_guard"]),
        condition("native_arguments", ["r0", "r1"], [transport["phase_register"], transport["context_register"]]),
        condition("native_return", 0, transport["callback_return"]),
        condition("native_load_instruction_count", 1, transport["load_instructions"]),
        condition("native_executed_load_bounds", [0, 1], [transport["executed_loads_min"], transport["executed_loads_max"]]),
        condition("native_load_layout", [2, 0, 2], [transport["load_width_bytes"], transport["load_context_offset"], transport["load_alignment"]]),
        condition("native_value_checked_or_published", [False, False], [transport["loaded_value_checked"], transport["loaded_value_published"]]),
        condition("web_callback_runtime", "0x06001341", safety["diagnosticNativeCallbackRuntime"]),
        condition("web_callback_bytes", 12, safety["diagnosticNativeBytes"]),
        condition("web_load_instructions", 1, safety["diagnosticNativeLoads"]),
        condition("web_executed_load_bounds", [0, 1], safety["diagnosticNativeExecutedLoadBounds"]),
        condition("web_context_read_layout", [2, 0], [safety["diagnosticNativeContextReadBytes"], safety["diagnosticNativeContextReadOffset"]]),
    ]
    for key in ("stack_accesses", "calls", "stores", "literal_data_bytes", "request_tree_reads", "field_lookups", "text_child_lookups", "custom_state_reads", "custom_state_writes"):
        checks.append(condition("native_" + key, 0, transport[key]))
    for key in ("ttlBrowserGetRequests", "ttlBrowserPostRequests", "diagnosticBrowserRequests", "diagnosticNativeCalls", "diagnosticNativeStores", "diagnosticNativeStackAccesses", "diagnosticNativeFieldLookups", "diagnosticNativeTextChildLookups", "diagnosticNativeCustomStateReads", "diagnosticNativeCustomStateWrites", "diagnosticNativeDataBytes", "diagnosticGetCallbacks", "automaticMutationRetries"):
        checks.append(condition("web_" + key, 0, safety[key]))
    for key in ("ttlAvailable", "ttlForwardingHookInstalled", "contextReadExecutionProven", "contextTypeValueProven", "guardedContextReadLiveQualified", "firmwareControlEnabled", "systemChannelBridgeUsed"):
        checks.append(condition("web_" + key, False, safety[key]))
    checks.extend(native_report["preservation_conditions"])
    return checks


def build_candidate(golden_raw: bytes, identity: inspector.IdentityMaterial) -> tuple[bytes, dict[str, Any]]:
    return comparator.build_candidate(golden_raw, identity, profile=PROFILE, schema=SCHEMA, label=LABEL, native_build=native.build_payload, error=CommunityR42NativeError)


def verify_candidate(golden_raw: bytes, candidate: bytes, identity: inspector.IdentityMaterial) -> dict[str, Any]:
    return comparator.verify_candidate(golden_raw, candidate, identity, profile=PROFILE, verification_schema=VERIFICATION_SCHEMA, label=LABEL, native_build=native.build_payload, native_conditions=_native_verification_conditions, error=CommunityR42NativeError)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Build the full R4.2 firmware container offline; does not flash")
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
            label=LABEL, confirmation=args.confirm_guarded_context_read_risk,
            confirmation_flag=CONFIRMATION_FLAG, native_build=native.build_payload,
            native_conditions=_native_verification_conditions, qualification=QUALIFICATION,
            error=CommunityR42NativeError,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (CommunityR42NativeError, shared.CommunityR30NativeError, r33_builder.CommunityR33NativeError, native.TtlR42PayloadError, thumb.NativeBuildError, inspector.InspectionError, webi.BuildError, stage.StageBuildError, OSError, lzma.LZMAError, TypeError, ValueError) as exc:
        print(f"R4.2 native build failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
