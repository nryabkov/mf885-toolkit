#!/usr/bin/env python3
"""Build and verify the Community R3.3 isolated TTL transport payload.

R3.3 keeps the R3.1 forwarding hook and low-page volatile state, but replaces
the failed three-property diagnostic response publisher.  The dormant
``diagnostic`` pre-get callback now publishes one value through the exact stock
``SystemChannelName.PRODUCT_CHANNEL`` response field.  The stock
SystemChannelName post-get callback remains byte-exact and restores ``release``
after core serialization.  Both Engineering implementations remain untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mf885_firmware_inspect as inspector
import mf885_thumb_llvm_build as thumb
import mf885_ttl_native_payload as r30
import mf885_ttl_native_payload_r31 as r31


ROOT = Path(__file__).resolve().parents[1]
NATIVE_DIRECTORY = ROOT / "firmware" / "community-r3.3" / "native"

OSLO_BYTES = r31.OSLO_BYTES
OSLO_SHA256 = r31.OSLO_SHA256
OSLO_RUNTIME_BASE = r31.OSLO_RUNTIME_BASE

IP_FORWARD_HOOK_OFFSET = r31.IP_FORWARD_HOOK_OFFSET
IP_FORWARD_HOOK_RUNTIME = r31.IP_FORWARD_HOOK_RUNTIME
IP_FORWARD_HOOK = r31.IP_FORWARD_HOOK

TTL_FORWARD_OFFSET = r31.TTL_FORWARD_OFFSET
TTL_POST_SET_OFFSET = r31.TTL_POST_SET_OFFSET
TTL_DATA_OFFSET = r31.TTL_DATA_OFFSET
TTL_PRE_GET_OFFSET = r31.TTL_POST_GET_OFFSET
TTL_FORWARD_RUNTIME = r31.TTL_FORWARD_RUNTIME
TTL_POST_SET_RUNTIME = r31.TTL_POST_SET_RUNTIME
TTL_DATA_RUNTIME = r31.TTL_DATA_RUNTIME
TTL_PRE_GET_RUNTIME = r31.TTL_POST_GET_RUNTIME

DUSTER_DIAGNOSTIC_OFFSET = r30.DUSTER_DIAGNOSTIC_OFFSET
DUSTER_PRE_SET_POINTER = r30.DUSTER_PRE_SET_POINTER
DUSTER_POST_SET_POINTER = r30.DUSTER_POST_SET_POINTER
DUSTER_PRE_GET_POINTER = r30.DUSTER_PRE_GET_POINTER
DUSTER_POST_GET_POINTER = r30.DUSTER_POST_GET_POINTER

DEBUGON_ROW_OFFSET = 0x009007A0
DEBUGON_ROW_BYTES = 56
DEBUGON_POST_GET_POINTER = DEBUGON_ROW_OFFSET + 0x2C
DEBUGON_POST_GET_RUNTIME = 0x06266E05
DEBUGON_CALLBACK_OFFSET = 0x00266E04
DEBUGON_CALLBACK_BYTES = 42

WAN_ROW_OFFSET = 0x009000A0
WAN_ROW_BYTES = 56

SYSTEM_CHANNEL_ROW_OFFSET = 0x00900880
SYSTEM_CHANNEL_ROW_BYTES = 56
SYSTEM_CHANNEL_POST_GET_POINTER = SYSTEM_CHANNEL_ROW_OFFSET + 0x2C
SYSTEM_CHANNEL_POST_GET_RUNTIME = 0x062677BF
SYSTEM_CHANNEL_CALLBACK_OFFSET = 0x002677BE
SYSTEM_CHANNEL_CALLBACK_BYTES = 20

TTL_DATA_BYTES = 0x50
TTL_DATA_END = TTL_DATA_OFFSET + TTL_DATA_BYTES
EXECUTABLE_PAGE_END = r31.EXECUTABLE_PAGE_END


class TtlR33PayloadError(RuntimeError):
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
        "ttl_post_set",
        "ttl_post_set.ll",
        TTL_POST_SET_OFFSET,
        204,
        192,
        "30140006937440060ff04406",
        "71513273361bf33d20965d7ab101e19611eabd1f658f527b8ac04d61625b6e10",
    ),
    Component(
        "ttl_pre_get",
        "ttl_pre_get.ll",
        TTL_PRE_GET_OFFSET,
        164,
        156,
        "30140006db734006",
        "69045bebf5ff7f176be67d12481dbc2e42066b071e2a99f18da6207b5f047523",
    ),
)


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _condition(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {"name": name, "expected": expected, "actual": actual, "passed": expected == actual}


def _require(conditions: list[dict[str, Any]], context: str) -> None:
    failed = [item["name"] for item in conditions if not item["passed"]]
    if failed:
        raise TtlR33PayloadError(f"{context} failed: " + ", ".join(failed))


def data_blob() -> bytes:
    value = bytearray(TTL_DATA_BYTES)
    fields = {
        0x04: b"diagnostic\0",
        0x10: b"command\0",
        0x18: b"arg\0",
        0x1C: b"ttl\0",
        0x20: b"off\0",
        0x24: b"SystemChannelName\0",
        0x38: b"PRODUCT_CHANNEL\0",
    }
    for offset, raw in fields.items():
        end = offset + len(raw)
        if end > len(value) or any(value[offset:end]):
            raise TtlR33PayloadError("internal R3.3 TTL data layout overlaps")
        value[offset:end] = raw
    result = bytes(value)
    if sha256(result) != "48520f57bd485e5c545ae7f280da4cafb75b7228fdb6fc33e27019a2713def30":
        raise TtlR33PayloadError("internal R3.3 TTL data layout changed")
    return result


def compile_components() -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    inherited, inherited_conditions = r31.compile_components()
    compiled = {"ttl_forward": inherited["ttl_forward"]}
    conditions = [
        item
        for item in inherited_conditions
        if item["name"].startswith("component:ttl_forward:")
    ]
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
    _require(conditions, "R3.3 native component compilation")
    return compiled, conditions


def inspect_exact_oslo(oslo: bytes) -> dict[str, Any]:
    try:
        inherited = r31.inspect_exact_oslo(oslo)
    except r31.TtlR31PayloadError as exc:
        raise TtlR33PayloadError(str(exc)) from exc
    conditions = list(inherited["conditions"])
    conditions.extend(
        (
            _condition("r33_data_source_all_zero", True, oslo[TTL_DATA_OFFSET:TTL_DATA_END] == b"\0" * TTL_DATA_BYTES),
            _condition("r33_data_end_before_stock_thumb", True, TTL_DATA_END <= r30.CODE_CAVE_A_END),
            _condition("r33_setter_end_before_data", True, TTL_POST_SET_OFFSET + 204 <= TTL_DATA_OFFSET),
            _condition("r33_getter_end_before_stock_thumb", True, TTL_PRE_GET_OFFSET + 164 <= r30.CODE_CAVE_B_END),
            _condition("diagnostic_pre_set_source_pointer", 0, struct.unpack_from("<I", oslo, DUSTER_PRE_SET_POINTER)[0]),
            _condition("diagnostic_post_set_source_pointer", 0, struct.unpack_from("<I", oslo, DUSTER_POST_SET_POINTER)[0]),
            _condition("diagnostic_pre_get_source_pointer", 0, struct.unpack_from("<I", oslo, DUSTER_PRE_GET_POINTER)[0]),
            _condition("diagnostic_post_get_source_pointer", 0, struct.unpack_from("<I", oslo, DUSTER_POST_GET_POINTER)[0]),
            _condition("debugon_row_sha256", "f5395c1b7239522713d89a04bf37688ba1028ba3d172bd320e60514d3299e3bd", sha256(oslo[DEBUGON_ROW_OFFSET:DEBUGON_ROW_OFFSET + DEBUGON_ROW_BYTES])),
            _condition("debugon_post_get_pointer", DEBUGON_POST_GET_RUNTIME, struct.unpack_from("<I", oslo, DEBUGON_POST_GET_POINTER)[0]),
            _condition("debugon_callback_sha256", "a726d474a84f0e4c953a18308f078c27b4d0f8485043c63f9471f693b2dad2df", sha256(oslo[DEBUGON_CALLBACK_OFFSET:DEBUGON_CALLBACK_OFFSET + DEBUGON_CALLBACK_BYTES])),
            _condition("wan_row_sha256", "2acd419cb2665e906855ac1fda930fa23d1a9e7c4b9498aa0f6a7f2dd20d2b17", sha256(oslo[WAN_ROW_OFFSET:WAN_ROW_OFFSET + WAN_ROW_BYTES])),
            _condition("system_channel_row_sha256", "74e45fb5195d88f8a205fcd52e87327266faf576e1f3f2886d193a9d1d0063dd", sha256(oslo[SYSTEM_CHANNEL_ROW_OFFSET:SYSTEM_CHANNEL_ROW_OFFSET + SYSTEM_CHANNEL_ROW_BYTES])),
            _condition("system_channel_post_get_pointer", SYSTEM_CHANNEL_POST_GET_RUNTIME, struct.unpack_from("<I", oslo, SYSTEM_CHANNEL_POST_GET_POINTER)[0]),
            _condition("system_channel_callback_sha256", "fcd8f7f90c71947bb75fc23639d56747d1b352d9b53d553b90a70cff6dd0826e", sha256(oslo[SYSTEM_CHANNEL_CALLBACK_OFFSET:SYSTEM_CHANNEL_CALLBACK_OFFSET + SYSTEM_CHANNEL_CALLBACK_BYTES])),
            _condition("system_channel_model_string_hex", b"SystemChannelName\0".hex(), oslo[0x00267B6C:0x00267B7E].hex()),
            _condition("system_channel_field_string_hex", b"PRODUCT_CHANNEL\0".hex(), oslo[0x00267B5C:0x00267B6C].hex()),
            _condition("system_channel_constant_hex", b"release\0".hex(), oslo[0x00085A44:0x00085A4C].hex()),
            _condition("system_channel_constant_getter_target", 0x06085928, inspector._thumb_bl_target(oslo, 0x002677C0)),
            _condition("system_channel_property_setter_target", 0x064073DA, inspector._thumb_bl_target(oslo, 0x002677CC)),
        )
    )
    return {
        "schema": "mf885-community-r33-ttl-oslo-source/v1",
        "status": "GREEN" if all(item["passed"] for item in conditions) else "REJECTED",
        "conditions": conditions,
    }


def require_exact_oslo(oslo: bytes) -> dict[str, Any]:
    report = inspect_exact_oslo(oslo)
    _require(report["conditions"], "exact R3.3 OSLO source")
    return report


def build_payload(oslo: bytes, mode: str = "full") -> tuple[bytes, dict[str, Any]]:
    if mode not in {"observer", "full"}:
        raise TtlR33PayloadError("mode must be observer or full")
    source = require_exact_oslo(oslo)
    compiled, component_conditions = compile_components()
    blob = data_blob()
    hook_target = r30.thumb_bl_target(IP_FORWARD_HOOK[8:12], IP_FORWARD_HOOK_RUNTIME + 8)
    hook_condition = _condition("hook_bl_target", TTL_FORWARD_RUNTIME, hook_target)
    _require([hook_condition], "forward hook target")

    candidate = bytearray(oslo)
    r30._write_exact(candidate, TTL_FORWARD_OFFSET, compiled["ttl_forward"])
    r30._write_exact(candidate, TTL_POST_SET_OFFSET, compiled["ttl_post_set"])
    r30._write_exact(candidate, TTL_DATA_OFFSET, blob)
    r30._write_exact(candidate, TTL_PRE_GET_OFFSET, compiled["ttl_pre_get"])
    struct.pack_into("<I", candidate, DUSTER_POST_SET_POINTER, TTL_POST_SET_RUNTIME | 1)
    struct.pack_into("<I", candidate, DUSTER_PRE_GET_POINTER, TTL_PRE_GET_RUNTIME | 1)
    if mode == "full":
        r30._write_exact(candidate, IP_FORWARD_HOOK_OFFSET, IP_FORWARD_HOOK)

    engineering_conditions = [
        _condition("wan_row_sha256_preserved", sha256(oslo[WAN_ROW_OFFSET:WAN_ROW_OFFSET + WAN_ROW_BYTES]), sha256(bytes(candidate[WAN_ROW_OFFSET:WAN_ROW_OFFSET + WAN_ROW_BYTES]))),
        _condition("debugon_row_sha256_preserved", sha256(oslo[DEBUGON_ROW_OFFSET:DEBUGON_ROW_OFFSET + DEBUGON_ROW_BYTES]), sha256(bytes(candidate[DEBUGON_ROW_OFFSET:DEBUGON_ROW_OFFSET + DEBUGON_ROW_BYTES]))),
        _condition("debugon_callback_sha256_preserved", sha256(oslo[DEBUGON_CALLBACK_OFFSET:DEBUGON_CALLBACK_OFFSET + DEBUGON_CALLBACK_BYTES]), sha256(bytes(candidate[DEBUGON_CALLBACK_OFFSET:DEBUGON_CALLBACK_OFFSET + DEBUGON_CALLBACK_BYTES]))),
    ]
    preservation_conditions = [
        _condition("diagnostic_post_set_candidate_pointer", TTL_POST_SET_RUNTIME | 1, struct.unpack_from("<I", candidate, DUSTER_POST_SET_POINTER)[0]),
        _condition("diagnostic_pre_get_candidate_pointer", TTL_PRE_GET_RUNTIME | 1, struct.unpack_from("<I", candidate, DUSTER_PRE_GET_POINTER)[0]),
        _condition("diagnostic_post_get_remains_zero", 0, struct.unpack_from("<I", candidate, DUSTER_POST_GET_POINTER)[0]),
        _condition("system_channel_row_sha256_preserved", sha256(oslo[SYSTEM_CHANNEL_ROW_OFFSET:SYSTEM_CHANNEL_ROW_OFFSET + SYSTEM_CHANNEL_ROW_BYTES]), sha256(bytes(candidate[SYSTEM_CHANNEL_ROW_OFFSET:SYSTEM_CHANNEL_ROW_OFFSET + SYSTEM_CHANNEL_ROW_BYTES]))),
        _condition("system_channel_callback_sha256_preserved", sha256(oslo[SYSTEM_CHANNEL_CALLBACK_OFFSET:SYSTEM_CHANNEL_CALLBACK_OFFSET + SYSTEM_CHANNEL_CALLBACK_BYTES]), sha256(bytes(candidate[SYSTEM_CHANNEL_CALLBACK_OFFSET:SYSTEM_CHANNEL_CALLBACK_OFFSET + SYSTEM_CHANNEL_CALLBACK_BYTES]))),
    ]
    _require(engineering_conditions + preservation_conditions, "R3.3 transport and Engineering preservation")

    ranges = [
        {"name": "ttl_forward", "offset": TTL_FORWARD_OFFSET, "bytes": len(compiled["ttl_forward"])},
        {"name": "ttl_post_set", "offset": TTL_POST_SET_OFFSET, "bytes": len(compiled["ttl_post_set"])},
        {"name": "ttl_low_page_data", "offset": TTL_DATA_OFFSET, "bytes": len(blob)},
        {"name": "ttl_pre_get", "offset": TTL_PRE_GET_OFFSET, "bytes": len(compiled["ttl_pre_get"])},
        {"name": "diagnostic_post_set_pointer", "offset": DUSTER_POST_SET_POINTER, "bytes": 4},
        {"name": "diagnostic_pre_get_pointer", "offset": DUSTER_PRE_GET_POINTER, "bytes": 4},
    ]
    if mode == "full":
        ranges.append({"name": "ip_forward_hook", "offset": IP_FORWARD_HOOK_OFFSET, "bytes": len(IP_FORWARD_HOOK)})
    result = bytes(candidate)
    return result, {
        "schema": "mf885-community-r33-ttl-native-payload/v1",
        "status": "GREEN",
        "mode": mode,
        "source": {"bytes": len(oslo), "sha256": sha256(oslo), "conditions": source["conditions"]},
        "components": component_conditions,
        "transport": {
            "trigger_model": "diagnostic",
            "read_model": "SystemChannelName",
            "read_field": "PRODUCT_CHANNEL",
            "publisher_slot": "pre_get",
            "publisher_setter_calls": 1,
            "stock_restore_slot": "SystemChannelName.post_get",
            "stock_restore_value": "release",
            "stock_restore_callback_preserved": True,
            "set_model": "diagnostic",
            "set_fields": ["command", "arg"],
            "set_response_setter_calls": 0,
            "target_get_and_restore_proven": False,
            "conditions": preservation_conditions,
        },
        "engineering": {
            "wan_engineering_mode_changed": oslo[WAN_ROW_OFFSET:WAN_ROW_OFFSET + WAN_ROW_BYTES] != bytes(candidate[WAN_ROW_OFFSET:WAN_ROW_OFFSET + WAN_ROW_BYTES]),
            "debugon_row_changed": oslo[DEBUGON_ROW_OFFSET:DEBUGON_ROW_OFFSET + DEBUGON_ROW_BYTES] != bytes(candidate[DEBUGON_ROW_OFFSET:DEBUGON_ROW_OFFSET + DEBUGON_ROW_BYTES]),
            "debugon_callback_changed": oslo[DEBUGON_CALLBACK_OFFSET:DEBUGON_CALLBACK_OFFSET + DEBUGON_CALLBACK_BYTES] != bytes(candidate[DEBUGON_CALLBACK_OFFSET:DEBUGON_CALLBACK_OFFSET + DEBUGON_CALLBACK_BYTES]),
            "conditions": engineering_conditions,
        },
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
        _condition("candidate_diagnostic_post_get_zero", 0, struct.unpack_from("<I", candidate, DUSTER_POST_GET_POINTER)[0]),
        _condition("candidate_debugon_row_sha256", sha256(source[DEBUGON_ROW_OFFSET:DEBUGON_ROW_OFFSET + DEBUGON_ROW_BYTES]), sha256(candidate[DEBUGON_ROW_OFFSET:DEBUGON_ROW_OFFSET + DEBUGON_ROW_BYTES])),
        _condition("candidate_system_channel_row_sha256", sha256(source[SYSTEM_CHANNEL_ROW_OFFSET:SYSTEM_CHANNEL_ROW_OFFSET + SYSTEM_CHANNEL_ROW_BYTES]), sha256(candidate[SYSTEM_CHANNEL_ROW_OFFSET:SYSTEM_CHANNEL_ROW_OFFSET + SYSTEM_CHANNEL_ROW_BYTES])),
    ]
    return {
        "schema": "mf885-community-r33-ttl-native-verification/v1",
        "status": "GREEN" if all(item["passed"] for item in conditions) else "REJECTED",
        "mode": mode,
        "conditions": conditions,
        "build": report,
    }


parse_ttl_argument = r31.parse_ttl_argument
rewrite_ipv4_ttl = r31.rewrite_ipv4_ttl
rfc1624_ttl_checksum = r31.rfc1624_ttl_checksum


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an offline MF885 R3.3 isolated TTL transport payload")
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
    except (OSError, TtlR33PayloadError, thumb.NativeBuildError) as exc:
        print(json.dumps({"schema": "mf885-community-r33-ttl-native-payload/v1", "status": "REJECTED", "reason": str(exc)}, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
