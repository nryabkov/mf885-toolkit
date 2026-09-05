#!/usr/bin/env python3
"""Offline fixed64 forwarding component; output is not a firmware update.

Only the existing ip_forward callsite and its low-page helper are replaced.
Diagnostic callbacks, custom state, WEBI and all other OSLO bytes are preserved.
The hook has no direction filter or runtime Off control.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import mf885_thumb_llvm_build as thumb
import mf885_ttl_native_payload as stock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "firmware/community-r4.3/native/ttl_forward_fixed64.ll"
SOURCE_BYTES = 2983
SOURCE_SHA256 = "3a864b9d738f2791e91f1f1c3232fc0e7aadf1f97eef6e39744e8e9ea6d44c25"
FUNCTION = "ttl_forward_fixed64"
TARGET_TTL = 64
OSLO_BYTES = stock.OSLO_BYTES
OSLO_SHA256 = stock.OSLO_SHA256
OSLO_RUNTIME_BASE = stock.OSLO_RUNTIME_BASE
FORWARD_OFFSET = stock.TTL_FORWARD_OFFSET
FORWARD_RUNTIME = OSLO_RUNTIME_BASE + FORWARD_OFFSET
FORWARD_BYTES = 140
FORWARD_CODE_BYTES = 136
FORWARD_SHA256 = "f1a939377d18d60688179c474d4d4bba352c0a72afd69f70fe3a81113824a6d2"
FORWARD_LITERAL_HEX = "4cc10207"
RESERVATION_END = stock.TTL_POST_SET_OFFSET
IP_FORWARD_HOOK_OFFSET = stock.IP_FORWARD_HOOK_OFFSET
IP_FORWARD_HOOK_RUNTIME = stock.IP_FORWARD_HOOK_RUNTIME
IP_FORWARD_ORIGINAL = stock.IP_FORWARD_ORIGINAL
IP_FORWARD_HOOK = stock.IP_FORWARD_HOOK
CHANGED_RANGES = [
    {"name": FUNCTION, "offset": FORWARD_OFFSET, "bytes": FORWARD_BYTES},
    {"name": "ip_forward_hook", "offset": IP_FORWARD_HOOK_OFFSET, "bytes": len(IP_FORWARD_HOOK)},
]

class TtlR43PayloadError(RuntimeError):
    pass

def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def condition(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {"name": name, "expected": expected, "actual": actual, "passed": expected == actual}

def require(conditions: list[dict[str, Any]], context: str) -> None:
    failed = [c["name"] for c in conditions if not c["passed"]]
    if failed:
        raise TtlR43PayloadError(context + ": " + ", ".join(failed))

def compile_forward() -> tuple[bytes, list[dict[str, Any]]]:
    source = SOURCE.read_bytes()
    conditions = [
        condition("source_bytes", SOURCE_BYTES, len(source)),
        condition("source_sha256", SOURCE_SHA256, sha256(source)),
    ]
    require(conditions, "R4.3 LLVM source rejected")
    layout = thumb.compile_ir_layout(source)
    raw = bytes(layout["raw"])
    conditions.extend([
        condition("forward_bytes", FORWARD_BYTES, len(raw)),
        condition("forward_sha256", FORWARD_SHA256, sha256(raw)),
        condition("mapping_ranges", [
            {"kind": "thumb", "offset": 0, "bytes": FORWARD_CODE_BYTES},
            {"kind": "data", "offset": FORWARD_CODE_BYTES, "bytes": FORWARD_BYTES - FORWARD_CODE_BYTES},
        ], layout["ranges"]),
        condition("function_symbol", [{"name": FUNCTION, "offset": 0, "thumb": True, "bytes": FORWARD_BYTES}], layout["functions"]),
        condition("literal_pool", FORWARD_LITERAL_HEX, raw[FORWARD_CODE_BYTES:].hex()),
        condition("helper_fits_before_callback_cave", True, FORWARD_OFFSET + len(raw) <= RESERVATION_END),
    ])
    require(conditions, "R4.3 emitted machine code rejected")
    return raw, conditions

def inspect_exact_oslo(oslo: bytes) -> dict[str, Any]:
    inherited = stock.inspect_exact_oslo(oslo)
    conditions = list(inherited["conditions"])
    conditions.extend([
        condition("forward_reservation_zero", True, oslo[FORWARD_OFFSET:RESERVATION_END] == bytes(RESERVATION_END - FORWARD_OFFSET)),
        condition("hook_original_exact", IP_FORWARD_ORIGINAL.hex(), oslo[IP_FORWARD_HOOK_OFFSET:IP_FORWARD_HOOK_OFFSET + len(IP_FORWARD_ORIGINAL)].hex()),
    ])
    return {"status": "GREEN" if all(c["passed"] for c in conditions) else "REJECTED", "conditions": conditions}

def _candidate_conditions(source: bytes, candidate: bytes, expected: bytes) -> list[dict[str, Any]]:
    # Preserve complete spans, including every diagnostic pointer and both
    # previous state locations. Only two explicit ranges may differ.
    spans = [(0, FORWARD_OFFSET), (FORWARD_OFFSET + FORWARD_BYTES, IP_FORWARD_HOOK_OFFSET),
             (IP_FORWARD_HOOK_OFFSET + len(IP_FORWARD_HOOK), len(source))]
    return [
        condition("candidate_bytes", len(expected), len(candidate)),
        condition("candidate_sha256", sha256(expected), sha256(candidate)),
        condition("candidate_byte_exact", True, candidate == expected),
        condition("all_unpatched_spans_preserved", True, all(source[a:b] == candidate[a:b] for a, b in spans)),
        condition("forward_sha256", FORWARD_SHA256, sha256(candidate[FORWARD_OFFSET:FORWARD_OFFSET + FORWARD_BYTES])),
        condition("hook_exact", IP_FORWARD_HOOK.hex(), candidate[IP_FORWARD_HOOK_OFFSET:IP_FORWARD_HOOK_OFFSET + len(IP_FORWARD_HOOK)].hex()),
        condition("unused_reservation_zero", True, candidate[FORWARD_OFFSET + FORWARD_BYTES:RESERVATION_END] == bytes(RESERVATION_END - FORWARD_OFFSET - FORWARD_BYTES)),
    ]

def build_payload(oslo: bytes) -> tuple[bytes, dict[str, Any]]:
    source_report = inspect_exact_oslo(oslo)
    require(source_report["conditions"], "R4.3 stock OSLO rejected")
    forward, compiled = compile_forward()
    candidate = bytearray(oslo)
    candidate[FORWARD_OFFSET:FORWARD_OFFSET + len(forward)] = forward
    candidate[IP_FORWARD_HOOK_OFFSET:IP_FORWARD_HOOK_OFFSET + len(IP_FORWARD_HOOK)] = IP_FORWARD_HOOK
    result = bytes(candidate)
    preserved = _candidate_conditions(oslo, result, result)
    require(preserved, "R4.3 component isolation rejected")
    return result, {
        "schema": "mf885-community-r43-fixed64-forward-native-payload/v1", "status": "GREEN",
        "source": {"bytes": len(oslo), "sha256": sha256(oslo), "conditions": source_report["conditions"]},
        "component": {"bytes": len(forward), "sha256": sha256(forward), "runtime": f"0x{FORWARD_RUNTIME | 1:08x}", "conditions": compiled},
        "changed_ranges": CHANGED_RANGES, "preservation_conditions": preserved,
        "packet_contract": {
            "fixed_ttl": TARGET_TTL, "runtime_off_available": False, "direction_filter": None,
            "scope": "Eligible IPv4 packets passing the existing ip_forward output call, in either direction.",
            "header_guards": ["4-byte aligned header", "IPv4", "IHL >= 5", "pbuf total and contiguous length cover header", "observed TTL >= 2"],
            "input_pointer_validity": "Inherited stock callsite precondition; null/unmapped pointers are not validated.",
            "checksum": "RFC1624 incremental replacement of TTL/protocol word; recomputation tested independently.",
            "packet_store": "One aligned volatile 32-bit TTL/protocol/checksum word at header+8 when TTL differs.",
            "output_calls": 1, "output_return_preserved": True,
            "diagnostic_callbacks_installed": False, "custom_state_accesses": 0,
            "ttl_at_hook_one_preserved": True,
        },
        "artifact": {"kind": "decompressed_oslo_component", "flashable": False, "bytes": len(result), "sha256": sha256(result)},
        "qualification": {"offline_exact_machine_contract": True, "full_firmware_container_built": False, "live_forward_hook_execution": False, "live_packet_ttl_verified": False, "runtime_configuration_available": False},
        "live_actions": {"http": 0, "usb": 0, "firmware_posts": 0, "service_changes": 0, "network_changes": 0},
    }

def verify_payload(source: bytes, candidate: bytes) -> dict[str, Any]:
    expected, built = build_payload(source)
    conditions = _candidate_conditions(source, candidate, expected)
    return {"schema": "mf885-community-r43-fixed64-forward-native-verification/v1", "status": "GREEN" if all(c["passed"] for c in conditions) else "REJECTED", "conditions": conditions, "build": built}

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build an offline fixed64 OSLO component, not a flashable image")
    p.add_argument("oslo", type=Path); p.add_argument("--output", type=Path)
    a = p.parse_args(argv)
    try:
        candidate, report = build_payload(a.oslo.read_bytes())
        if a.output is not None:
            with a.output.open("xb") as stream: stream.write(candidate)
        print(json.dumps(report, indent=2, sort_keys=True)); return 0
    except (OSError, ValueError, TtlR43PayloadError, thumb.NativeBuildError) as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc)})); return 2

if __name__ == "__main__":
    raise SystemExit(main())
