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
SOURCE = ROOT / "firmware/community-r4.5/native/ttl_forward_fixed64_bytes_armv5.ll"
SOURCE_BYTES = 3252
SOURCE_SHA256 = '3cc62316cbe312888f15643e6b32dd9bf2455c46750d4036c77daa7ccd303317'
FUNCTION = "ttl_forward_fixed64_bytes_armv5"
TARGET_TTL = 64
OSLO_BYTES = stock.OSLO_BYTES
OSLO_SHA256 = stock.OSLO_SHA256
OSLO_RUNTIME_BASE = stock.OSLO_RUNTIME_BASE
FORWARD_OFFSET = stock.TTL_FORWARD_OFFSET
FORWARD_RUNTIME = OSLO_RUNTIME_BASE + FORWARD_OFFSET
TARGET = {"target_triple": b"thumbv5te-none-eabi", "target_cpu": b"arm926ej-s",
          "target_features": b"+thumb-mode,-thumb2,-neon,-vfp2,+strict-align"}
ENTRY_STUB = bytes.fromhex("280031002200ffe7")
BODY_BYTES = 124
BODY_CODE_BYTES = 116
BODY_SHA256 = 'a9245ebcdbd1aa4379553bec8ac39cf04afd51f9c55b2bd6bacdacabe3c2f34e'
FORWARD_BYTES = 132
FORWARD_CODE_BYTES = 124
FORWARD_SHA256 = '02ce2cf936f5265d3a0eb7e6f2450cd9e5c359d516c857609006dd07182aa62a'
FORWARD_LITERAL_HEX = "ffff00004cc10207"
RESERVATION_END = stock.TTL_POST_SET_OFFSET
IP_FORWARD_HOOK_OFFSET = stock.IP_FORWARD_HOOK_OFFSET
IP_FORWARD_HOOK_RUNTIME = stock.IP_FORWARD_HOOK_RUNTIME
IP_FORWARD_ORIGINAL = stock.IP_FORWARD_ORIGINAL
# LDR literal; BLX r3; B stock continuation; aligned Thumb entry; skipped NOP.
# A direct BL cannot span this distance on Thumb-1.
IP_FORWARD_HOOK = bytes.fromhex("014b984702e0a1120006c046")
CHANGED_RANGES = [
    {"name": FUNCTION, "offset": FORWARD_OFFSET, "bytes": FORWARD_BYTES},
    {"name": "ip_forward_hook", "offset": IP_FORWARD_HOOK_OFFSET, "bytes": len(IP_FORWARD_HOOK)},
]

class TtlR45PayloadError(RuntimeError):
    pass

def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def condition(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {"name": name, "expected": expected, "actual": actual, "passed": expected == actual}

def require(conditions: list[dict[str, Any]], context: str) -> None:
    failed = [c["name"] for c in conditions if not c["passed"]]
    if failed:
        raise TtlR45PayloadError(context + ": " + ", ".join(failed))

def compile_forward() -> tuple[bytes, list[dict[str, Any]]]:
    source = SOURCE.read_bytes()
    # The only compiled native unit in this release. Check the complete profile
    # before invoking LLVM; emitted bytes and mapping ranges are pinned below.
    expected_target = {"target_triple": b"thumbv5te-none-eabi", "target_cpu": b"arm926ej-s",
                       "target_features": b"+thumb-mode,-thumb2,-neon,-vfp2,+strict-align"}
    if TARGET != expected_target:
        raise TtlR45PayloadError("R4.5 architecture profile changed before compilation")
    conditions = [
        condition("source_bytes", SOURCE_BYTES, len(source)),
        condition("source_sha256", SOURCE_SHA256, sha256(source)),
    ]
    require(conditions, "R4.5 LLVM source rejected")
    layout = thumb.compile_ir_layout(source, **TARGET)
    raw = bytes(layout["raw"])
    conditions.extend([
        condition("body_bytes", BODY_BYTES, len(raw)),
        condition("body_sha256", BODY_SHA256, sha256(raw)),
        condition("mapping_ranges", [
            {"kind": "thumb", "offset": 0, "bytes": BODY_CODE_BYTES},
            {"kind": "data", "offset": BODY_CODE_BYTES, "bytes": BODY_BYTES - BODY_CODE_BYTES},
        ], layout["ranges"]),
        condition("function_symbol", [{"name": FUNCTION, "offset": 0, "thumb": True, "bytes": BODY_BYTES}], layout["functions"]),
        condition("literal_pool", FORWARD_LITERAL_HEX, raw[BODY_CODE_BYTES:].hex()),
        condition("helper_fits_before_callback_cave", True, FORWARD_OFFSET + len(ENTRY_STUB) + len(raw) <= RESERVATION_END),
    ])
    require(conditions, "R4.5 emitted machine code rejected")
    result = ENTRY_STUB + raw
    conditions.extend([
        condition("forward_bytes", FORWARD_BYTES, len(result)),
        condition("forward_sha256", FORWARD_SHA256, sha256(result)),
        condition("stub_branch_to_body", 0x060012A8,
                  FORWARD_RUNTIME + 6 + 4 - 2),
        condition("hook_literal_aligned", 0, (IP_FORWARD_HOOK_RUNTIME + 6) % 4),
        condition("hook_thumb_entry", FORWARD_RUNTIME | 1,
                  int.from_bytes(IP_FORWARD_HOOK[6:10], "little")),
    ])
    require(conditions, "R4.5 complete helper rejected")
    return result, conditions

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
    require(source_report["conditions"], "R4.5 stock OSLO rejected")
    forward, compiled = compile_forward()
    candidate = bytearray(oslo)
    candidate[FORWARD_OFFSET:FORWARD_OFFSET + len(forward)] = forward
    candidate[IP_FORWARD_HOOK_OFFSET:IP_FORWARD_HOOK_OFFSET + len(IP_FORWARD_HOOK)] = IP_FORWARD_HOOK
    result = bytes(candidate)
    preserved = _candidate_conditions(oslo, result, result)
    require(preserved, "R4.5 component isolation rejected")
    return result, {
        "schema": "mf885-community-r45-fixed64-forward-native-payload/v1", "status": "GREEN",
        "source": {"bytes": len(oslo), "sha256": sha256(oslo), "conditions": source_report["conditions"]},
        "architecture": {key: value.decode("ascii") for key, value in TARGET.items()},
        "component": {"bytes": len(forward), "sha256": sha256(forward), "runtime": f"0x{FORWARD_RUNTIME | 1:08x}", "conditions": compiled},
        "changed_ranges": CHANGED_RANGES, "preservation_conditions": preserved,
        "packet_contract": {
            "fixed_ttl": TARGET_TTL, "runtime_off_available": False, "direction_filter": None,
            "scope": "Eligible IPv4 packets passing the existing ip_forward output call, in either direction.",
            "header_guards": ["IPv4", "IHL >= 5", "pbuf total and contiguous length cover header", "observed TTL >= 2"],
            "input_pointer_validity": "Inherited stock callsite precondition; null/unmapped pointers are not validated.",
            "checksum": "RFC1624 incremental replacement of TTL/protocol word; recomputation tested independently.",
            "packet_store": "Three volatile byte stores at header+10, +11, then +8, before output when TTL differs; protocol is never stored.",
            "header_alignment": "Any byte alignment; packet accesses are byte-wide.",
            "packet_ownership": "Inherited exclusive mutation until output; three stores are not atomic and asynchronous observers are not modeled.",
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
    return {"schema": "mf885-community-r45-fixed64-forward-native-verification/v1", "status": "GREEN" if all(c["passed"] for c in conditions) else "REJECTED", "conditions": conditions, "build": built}

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build an offline fixed64 OSLO component, not a flashable image")
    p.add_argument("oslo", type=Path); p.add_argument("--output", type=Path)
    a = p.parse_args(argv)
    try:
        candidate, report = build_payload(a.oslo.read_bytes())
        if a.output is not None:
            with a.output.open("xb") as stream: stream.write(candidate)
        print(json.dumps(report, indent=2, sort_keys=True)); return 0
    except (OSError, ValueError, TtlR45PayloadError, thumb.NativeBuildError) as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc)})); return 2

if __name__ == "__main__":
    raise SystemExit(main())
