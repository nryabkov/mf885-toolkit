#!/usr/bin/env python3
"""Build and verify the Community R3.1 low-page TTL repair payload offline.

R3.1 keeps the reviewed R3.0 forwarding algorithm but removes every native
reference to the unproved high-tail data range.  Code, mutable state and fixed
strings all live in the exact first-page caves beside stock Thumb code.  The
getter formats numeric readback in a four-byte stack-local buffer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mf885_thumb_llvm_build as thumb
import mf885_ttl_native_payload as r30


ROOT = Path(__file__).resolve().parents[1]
NATIVE_DIRECTORY = ROOT / "firmware" / "community-r3.1" / "native"

OSLO_BYTES = r30.OSLO_BYTES
OSLO_SHA256 = r30.OSLO_SHA256
OSLO_RUNTIME_BASE = r30.OSLO_RUNTIME_BASE

IP_FORWARD_HOOK_OFFSET = r30.IP_FORWARD_HOOK_OFFSET
IP_FORWARD_HOOK_RUNTIME = r30.IP_FORWARD_HOOK_RUNTIME
IP_FORWARD_ORIGINAL = r30.IP_FORWARD_ORIGINAL
IP_FORWARD_HOOK = r30.IP_FORWARD_HOOK

TTL_FORWARD_OFFSET = 0x000012A0
TTL_POST_SET_OFFSET = 0x00001340
TTL_DATA_OFFSET = 0x00001430
TTL_POST_GET_OFFSET = 0x00001520
TTL_FORWARD_RUNTIME = OSLO_RUNTIME_BASE + TTL_FORWARD_OFFSET
TTL_POST_SET_RUNTIME = OSLO_RUNTIME_BASE + TTL_POST_SET_OFFSET
TTL_DATA_RUNTIME = OSLO_RUNTIME_BASE + TTL_DATA_OFFSET
TTL_POST_GET_RUNTIME = OSLO_RUNTIME_BASE + TTL_POST_GET_OFFSET

DUSTER_POST_SET_POINTER = r30.DUSTER_POST_SET_POINTER
DUSTER_POST_GET_POINTER = r30.DUSTER_POST_GET_POINTER

DATA_BYTES = 0x60
DATA_END = TTL_DATA_OFFSET + DATA_BYTES
EXECUTABLE_PAGE_END = 0x00002000


class TtlR31PayloadError(RuntimeError):
    pass


@dataclass(frozen=True)
class Component:
    name: str
    source: str
    offset: int
    length: int
    code_length: int
    literal_hex: str
    sha256: str


COMPONENTS = (
    Component(
        "ttl_forward",
        "ttl_forward.ll",
        TTL_FORWARD_OFFSET,
        152,
        144,
        "301400064cc10207",
        "90a12950ccc5b672c680d34875e4ac1fa2365ab8d841c164eab3f45e934a0d1d",
    ),
    Component(
        "ttl_post_set",
        "ttl_post_set.ll",
        TTL_POST_SET_OFFSET,
        232,
        220,
        "34140006db7340060ff04406",
        "da94baa0b85ad7b057c007c39f19d7f02ade00973ba9eb911f66efd6a2d9ba0d",
    ),
    Component(
        "ttl_post_get",
        "ttl_post_get.ll",
        TTL_POST_GET_OFFSET,
        208,
        200,
        "34140006db734006",
        "ab8cbe2758fd7be96d97d6d837068b51f63e07c35494d80bb06435a68600ce59",
    ),
)


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _condition(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {"name": name, "expected": expected, "actual": actual, "passed": expected == actual}


def _require(conditions: list[dict[str, Any]], context: str) -> None:
    failed = [item["name"] for item in conditions if not item["passed"]]
    if failed:
        raise TtlR31PayloadError(f"{context} failed: " + ", ".join(failed))


def data_blob() -> bytes:
    value = bytearray(DATA_BYTES)
    fields = {
        0x04: b"diagnostic\0",
        0x10: b"command\0",
        0x18: b"arg\0",
        0x1C: b"output\0",
        0x24: b"ttl\0",
        0x28: b"off\0",
        0x2C: b"TTL_OFF\0",
        0x34: b"TTL_SET\0",
        0x3C: b"TTL_REJECTED\0",
        0x4C: b"TTL_VALUE\0",
    }
    for offset, raw in fields.items():
        end = offset + len(raw)
        if end > len(value) or any(value[offset:end]):
            raise TtlR31PayloadError("internal low-page TTL data layout overlaps")
        value[offset:end] = raw
    result = bytes(value)
    expected = "14f8f5a2d3ce5060eab4fab0c397504407ed0dc15a6ff0bdc6cba8c291500bd1"
    if sha256(result) != expected:
        raise TtlR31PayloadError("internal low-page TTL data layout changed")
    return result


def compile_components() -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    compiled: dict[str, bytes] = {}
    conditions: list[dict[str, Any]] = []
    for item in COMPONENTS:
        source = (NATIVE_DIRECTORY / item.source).read_bytes()
        layout = thumb.compile_ir_layout(source)
        raw = layout["raw"]
        expected_ranges = [
            {"kind": "thumb", "offset": 0, "bytes": item.code_length},
            {"kind": "data", "offset": item.code_length, "bytes": item.length - item.code_length},
        ]
        expected_functions = [
            {"name": item.name, "offset": 0, "thumb": True, "bytes": item.length}
        ]
        conditions.extend(
            (
                _condition(f"component:{item.name}:bytes", item.length, len(raw)),
                _condition(f"component:{item.name}:sha256", item.sha256, sha256(raw)),
                _condition(f"component:{item.name}:alignment", 0, item.offset % 4),
                _condition(f"component:{item.name}:mapping_ranges", expected_ranges, layout["ranges"]),
                _condition(f"component:{item.name}:function_symbol", expected_functions, layout["functions"]),
                _condition(f"component:{item.name}:literal_pool", item.literal_hex, raw[item.code_length:].hex()),
            )
        )
        compiled[item.name] = raw
    _require(conditions, "native component compilation")
    return compiled, conditions


def inspect_exact_oslo(oslo: bytes) -> dict[str, Any]:
    try:
        inherited = r30.require_exact_oslo(oslo)
    except r30.TtlPayloadError as exc:
        raise TtlR31PayloadError(str(exc)) from exc
    source_data = oslo[TTL_DATA_OFFSET:DATA_END]
    conditions = list(inherited["conditions"])
    conditions.extend(
        (
            _condition("low_page_data_bytes", DATA_BYTES, len(source_data)),
            _condition("low_page_data_source_all_zero", True, source_data == b"\0" * DATA_BYTES),
            _condition("low_page_payload_end_before_stock_thumb", True, DATA_END <= r30.CODE_CAVE_A_END),
            _condition("getter_end_before_stock_thumb", True, TTL_POST_GET_OFFSET + 208 <= r30.CODE_CAVE_B_END),
            _condition("all_payload_runtime_below_first_page_end", True, TTL_POST_GET_OFFSET + 208 < EXECUTABLE_PAGE_END),
        )
    )
    return {
        "schema": "mf885-community-r31-ttl-oslo-source/v1",
        "status": "GREEN" if all(item["passed"] for item in conditions) else "REJECTED",
        "conditions": conditions,
    }


def require_exact_oslo(oslo: bytes) -> dict[str, Any]:
    report = inspect_exact_oslo(oslo)
    _require(report["conditions"], "exact R3.1 OSLO source")
    return report


def build_payload(oslo: bytes, mode: str = "full") -> tuple[bytes, dict[str, Any]]:
    if mode not in {"observer", "full"}:
        raise TtlR31PayloadError("mode must be observer or full")
    source = require_exact_oslo(oslo)
    compiled, component_conditions = compile_components()
    blob = data_blob()
    hook_target = r30.thumb_bl_target(IP_FORWARD_HOOK[8:12], IP_FORWARD_HOOK_RUNTIME + 8)
    hook_condition = _condition("hook_bl_target", TTL_FORWARD_RUNTIME, hook_target)
    _require([hook_condition], "forward hook target")

    candidate = bytearray(oslo)
    for item in COMPONENTS:
        r30._write_exact(candidate, item.offset, compiled[item.name])
    r30._write_exact(candidate, TTL_DATA_OFFSET, blob)
    struct.pack_into("<I", candidate, DUSTER_POST_SET_POINTER, TTL_POST_SET_RUNTIME | 1)
    struct.pack_into("<I", candidate, DUSTER_POST_GET_POINTER, TTL_POST_GET_RUNTIME | 1)
    if mode == "full":
        r30._write_exact(candidate, IP_FORWARD_HOOK_OFFSET, IP_FORWARD_HOOK)

    ranges = [
        {"name": item.name, "offset": item.offset, "bytes": len(compiled[item.name])}
        for item in COMPONENTS
    ]
    ranges.extend(
        (
            {"name": "ttl_low_page_data", "offset": TTL_DATA_OFFSET, "bytes": len(blob)},
            {"name": "diagnostic_post_set_pointer", "offset": DUSTER_POST_SET_POINTER, "bytes": 4},
            {"name": "diagnostic_post_get_pointer", "offset": DUSTER_POST_GET_POINTER, "bytes": 4},
        )
    )
    if mode == "full":
        ranges.append({"name": "ip_forward_hook", "offset": IP_FORWARD_HOOK_OFFSET, "bytes": len(IP_FORWARD_HOOK)})

    result = bytes(candidate)
    return result, {
        "schema": "mf885-community-r31-ttl-native-payload/v1",
        "status": "GREEN",
        "mode": mode,
        "source": {"bytes": len(oslo), "sha256": sha256(oslo), "conditions": source["conditions"]},
        "components": component_conditions,
        "hook": {"installed": mode == "full", "bytes": IP_FORWARD_HOOK.hex(), "bl_target": f"0x{hook_target:08x}", "condition": hook_condition},
        "state": {
            "address": f"0x{TTL_DATA_RUNTIME:08x}",
            "boot_value": 0,
            "accepted_values": {"off": 0, "numeric_min": 1, "numeric_max": 255},
            "persistent": False,
            "page": "same first loaded page as callback code and exact stock Thumb",
        },
        "readback": {"numeric_buffer": "four-byte stack-local", "shared_writable_scratch": False},
        "changed_ranges": sorted(ranges, key=lambda item: item["offset"]),
        "artifact": {"bytes": len(result), "sha256": sha256(result)},
        "safety": {"device_requests": 0, "network_changes": 0, "firmware_posts": 0},
    }


def verify_payload(source: bytes, candidate: bytes, mode: str = "full") -> dict[str, Any]:
    expected, report = build_payload(source, mode)
    conditions = [
        _condition("candidate_bytes", len(expected), len(candidate)),
        _condition("candidate_sha256", sha256(expected), sha256(candidate)),
        _condition("candidate_byte_exact", True, expected == candidate),
    ]
    return {
        "schema": "mf885-community-r31-ttl-native-verification/v1",
        "status": "GREEN" if all(item["passed"] for item in conditions) else "REJECTED",
        "mode": mode,
        "conditions": conditions,
        "build": report,
    }


parse_ttl_argument = r30.parse_ttl_argument
rewrite_ipv4_ttl = r30.rewrite_ipv4_ttl
rfc1624_ttl_checksum = r30.rfc1624_ttl_checksum


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an offline MF885 R3.1 low-page TTL payload")
    parser.add_argument("oslo", type=Path)
    parser.add_argument("--mode", choices=("inspect", "observer", "full"), default="inspect")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        source = args.oslo.read_bytes()
        if args.mode == "inspect":
            report = inspect_exact_oslo(source)
        else:
            candidate, report = build_payload(source, args.mode)
            if args.output is not None:
                with args.output.open("xb") as stream:
                    stream.write(candidate)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "GREEN" else 2
    except (OSError, TtlR31PayloadError, thumb.NativeBuildError) as exc:
        print(json.dumps({"schema": "mf885-community-r31-ttl-native-payload/v1", "status": "REJECTED", "reason": str(exc)}, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
