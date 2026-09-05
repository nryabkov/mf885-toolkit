#!/usr/bin/env python3
"""Build the R4.2 guarded context-type access probe, entirely offline.

The output is a decompressed OSLO research component, not a flashable image.
The exact source hash and whole-image comparison preserve every byte except
the low callback cave and diagnostic post_set pointer. No live I/O is present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import mf885_thumb_llvm_build as thumb
import mf885_ttl_native_payload_r31 as r31


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "firmware/community-r4.2/native/diagnostic_context_type_read_post_set.ll"
SOURCE_BYTES = 790
SOURCE_SHA256 = "1644e56f18312b9ee307a1540bbceeeda5e8c9c2f3faa3a39c87c22fcee9a558"
FUNCTION = "diagnostic_context_type_read_post_set"

# Same exact stock OSLO, entry and pointer slot used by the R4.1 comparator.
OSLO_BYTES = r31.OSLO_BYTES
OSLO_SHA256 = r31.OSLO_SHA256
OSLO_RUNTIME_BASE = r31.OSLO_RUNTIME_BASE
CALLBACK_OFFSET = r31.TTL_POST_SET_OFFSET
CALLBACK_RUNTIME = OSLO_RUNTIME_BASE + CALLBACK_OFFSET
CALLBACK_EXACT = bytes.fromhex("03 28 01 d1 01 b1 08 88 00 20 70 47")
CALLBACK_BYTES = 12
CALLBACK_SHA256 = "3566a3b6f4ee7d2a847e49265dde1f168e6ae7be706021bfe8def3936e2bc55e"
RESERVATION_END = 0x1450
DUSTER_POST_SET_POINTER = r31.DUSTER_POST_SET_POINTER
INSTRUCTIONS = [
    "cmp r0, #3", "bne 0x06001348", "cbz r1, 0x06001348",
    "ldrh r0, [r1]", "movs r0, #0", "bx lr",
]
CHANGED_RANGES = [
    {"name": FUNCTION, "offset": CALLBACK_OFFSET, "bytes": CALLBACK_BYTES},
    {"name": "diagnostic_post_set_pointer", "offset": DUSTER_POST_SET_POINTER, "bytes": 4},
]


class TtlR42PayloadError(RuntimeError):
    pass


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def condition(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {"name": name, "expected": expected, "actual": actual, "passed": expected == actual}


def require(conditions: list[dict[str, Any]], context: str) -> None:
    failed = [item["name"] for item in conditions if not item["passed"]]
    if failed:
        raise TtlR42PayloadError(context + ": " + ", ".join(failed))


def compile_callback() -> tuple[bytes, list[dict[str, Any]]]:
    source = SOURCE.read_bytes()
    conditions = [
        condition("source_bytes", SOURCE_BYTES, len(source)),
        condition("source_sha256", SOURCE_SHA256, sha256(source)),
    ]
    require(conditions, "R4.2 LLVM source rejected")
    layout = thumb.compile_ir_layout(source)
    raw = bytes(layout["raw"])
    conditions.extend([
        condition("callback_bytes", CALLBACK_BYTES, len(raw)),
        condition("callback_sha256", CALLBACK_SHA256, sha256(raw)),
        condition("callback_byte_exact", CALLBACK_EXACT.hex(), raw.hex()),
        condition("mapping_ranges", [{"kind": "thumb", "offset": 0, "bytes": CALLBACK_BYTES}], layout["ranges"]),
        condition("function_symbol", [{"name": FUNCTION, "offset": 0, "thumb": True, "bytes": CALLBACK_BYTES}], layout["functions"]),
    ])
    require(conditions, "R4.2 emitted machine code rejected")
    return raw, conditions


def inspect_exact_oslo(oslo: bytes) -> dict[str, Any]:
    conditions = [
        condition("stock_oslo_bytes", OSLO_BYTES, len(oslo)),
        condition("stock_oslo_sha256", OSLO_SHA256, sha256(oslo)),
        condition("low_reservation_zero", bytes(RESERVATION_END - CALLBACK_OFFSET).hex(), oslo[CALLBACK_OFFSET:RESERVATION_END].hex()),
        condition("stock_post_set_pointer_zero", "00000000", oslo[DUSTER_POST_SET_POINTER:DUSTER_POST_SET_POINTER + 4].hex()),
    ]
    return {"status": "GREEN" if all(c["passed"] for c in conditions) else "REJECTED", "conditions": conditions}


def _candidate_conditions(source: bytes, candidate: bytes, expected: bytes) -> list[dict[str, Any]]:
    # Comparing all three unpatched spans also preserves the stock packet hook,
    # other callbacks, old high cave, engineering rows, data, and parser tail.
    spans = [
        (0, CALLBACK_OFFSET),
        (CALLBACK_OFFSET + CALLBACK_BYTES, DUSTER_POST_SET_POINTER),
        (DUSTER_POST_SET_POINTER + 4, len(source)),
    ]
    return [
        condition("candidate_bytes", len(expected), len(candidate)),
        condition("candidate_sha256", sha256(expected), sha256(candidate)),
        condition("candidate_byte_exact", True, candidate == expected),
        condition("all_unpatched_spans_preserved", True, all(source[a:b] == candidate[a:b] for a, b in spans)),
        condition("callback_exact", CALLBACK_EXACT.hex(), candidate[CALLBACK_OFFSET:CALLBACK_OFFSET + CALLBACK_BYTES].hex()),
        condition("post_set_thumb_pointer", struct.pack("<I", CALLBACK_RUNTIME | 1).hex(), candidate[DUSTER_POST_SET_POINTER:DUSTER_POST_SET_POINTER + 4].hex()),
        condition("unused_reservation_zero", True, candidate[CALLBACK_OFFSET + CALLBACK_BYTES:RESERVATION_END] == bytes(RESERVATION_END - CALLBACK_OFFSET - CALLBACK_BYTES)),
    ]


def build_payload(oslo: bytes) -> tuple[bytes, dict[str, Any]]:
    source_report = inspect_exact_oslo(oslo)
    require(source_report["conditions"], "R4.2 exact stock OSLO rejected")
    callback, machine_conditions = compile_callback()
    candidate = bytearray(oslo)
    candidate[CALLBACK_OFFSET:CALLBACK_OFFSET + CALLBACK_BYTES] = callback
    struct.pack_into("<I", candidate, DUSTER_POST_SET_POINTER, CALLBACK_RUNTIME | 1)
    result = bytes(candidate)
    preservation = _candidate_conditions(oslo, result, result)
    require(preservation, "R4.2 isolation rejected")
    return result, {
        "schema": "mf885-community-r42-context-type-read-native-payload/v1",
        "status": "GREEN",
        "source": {"bytes": len(oslo), "sha256": sha256(oslo), "conditions": source_report["conditions"]},
        "component": {
            "bytes": len(callback), "sha256": sha256(callback), "hex": callback.hex(),
            "runtime": f"0x{CALLBACK_RUNTIME | 1:08x}", "conditions": machine_conditions,
        },
        "transport": {
            "model": "diagnostic", "callback_slot": "post_set", "callback_return": 0,
            "phase_register": "r0", "context_register": "r1",
            "read_guard": "phase == 3 and context != NULL",
            "instructions": INSTRUCTIONS,
            "load_instructions": 1, "executed_loads_min": 0, "executed_loads_max": 1,
            "load_width_bytes": 2, "load_context_offset": 0, "load_alignment": 2,
            "valid_pointer_proven_by_non_null_guard": False,
            "loaded_value_checked": False, "loaded_value_published": False,
            "stack_accesses": 0, "calls": 0, "stores": 0, "literal_data_bytes": 0,
            "request_tree_reads": 0, "field_lookups": 0, "text_child_lookups": 0,
            "custom_state_reads": 0, "custom_state_writes": 0,
        },
        "changed_ranges": CHANGED_RANGES,
        "preservation_conditions": preservation,
        "artifact": {"kind": "decompressed_oslo_component", "flashable": False, "bytes": len(result), "sha256": sha256(result)},
        "qualification": {
            "offline_exact_machine_contract": True,
            "full_firmware_container_built": False,
            "live_guarded_callback_survival": False,
            "live_load_execution_proven": False,
            "live_context_type_value_proven": False,
            "live_parser": False, "ttl_functional": False, "ttl_persistent": False,
            "packet_hook_installed": False,
            "survival_interpretation": "A surviving guarded callback does not reveal which branch ran or the loaded value.",
        },
        "live_actions": {"http": 0, "usb": 0, "firmware_posts": 0, "service_changes": 0, "network_changes": 0},
    }


def verify_payload(source: bytes, candidate: bytes) -> dict[str, Any]:
    expected, report = build_payload(source)
    conditions = _candidate_conditions(source, candidate, expected)
    return {
        "schema": "mf885-community-r42-context-type-read-native-verification/v1",
        "status": "GREEN" if all(c["passed"] for c in conditions) else "REJECTED",
        "conditions": conditions, "build": report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an offline R4.2 OSLO component (not a flashable image)")
    parser.add_argument("oslo", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        candidate, report = build_payload(args.oslo.read_bytes())
        if args.output is not None:
            with args.output.open("xb") as stream:
                stream.write(candidate)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, TtlR42PayloadError, thumb.NativeBuildError) as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
