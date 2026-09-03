#!/usr/bin/env python3
"""Build and verify the Community R3.5 same-model TTL payload.

R3.5 keeps the reviewed low-page RAM state, write parser and IPv4 forwarding
hook, but replaces every previously failed readback bridge.  The dormant stock
``diagnostic`` model now has one post-get callback which publishes exactly one
field on that same model: ``diagnostic.output``.  This mirrors the proven stock
one-model/one-setter callback pattern and never touches SystemChannelName,
Engineering or debugon.
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
import mf885_ttl_native_payload_r31 as r31
import mf885_ttl_native_payload_r33 as r33


ROOT = Path(__file__).resolve().parents[1]
NATIVE_DIRECTORY = ROOT / "firmware" / "community-r3.5" / "native"

OSLO_BYTES = r31.OSLO_BYTES
OSLO_SHA256 = r31.OSLO_SHA256
OSLO_RUNTIME_BASE = r31.OSLO_RUNTIME_BASE

IP_FORWARD_HOOK_OFFSET = r31.IP_FORWARD_HOOK_OFFSET
IP_FORWARD_HOOK_RUNTIME = r31.IP_FORWARD_HOOK_RUNTIME
IP_FORWARD_ORIGINAL = r31.IP_FORWARD_ORIGINAL
IP_FORWARD_HOOK = r31.IP_FORWARD_HOOK

TTL_FORWARD_OFFSET = r31.TTL_FORWARD_OFFSET
TTL_POST_SET_OFFSET = r31.TTL_POST_SET_OFFSET
TTL_DATA_OFFSET = r31.TTL_DATA_OFFSET
TTL_POST_GET_OFFSET = r31.TTL_POST_GET_OFFSET
TTL_FORWARD_RUNTIME = r31.TTL_FORWARD_RUNTIME
TTL_POST_SET_RUNTIME = r31.TTL_POST_SET_RUNTIME
TTL_DATA_RUNTIME = r31.TTL_DATA_RUNTIME
TTL_POST_GET_RUNTIME = r31.TTL_POST_GET_RUNTIME

DUSTER_PRE_SET_POINTER = r30.DUSTER_PRE_SET_POINTER
DUSTER_POST_SET_POINTER = r30.DUSTER_POST_SET_POINTER
DUSTER_PRE_GET_POINTER = r30.DUSTER_PRE_GET_POINTER
DUSTER_POST_GET_POINTER = r30.DUSTER_POST_GET_POINTER
DUSTER_DIAGNOSTIC_NAME_POINTER = r30.DUSTER_DIAGNOSTIC_OFFSET + 0x04

TTL_DATA_BYTES = 0x30
TTL_DATA_END = TTL_DATA_OFFSET + TTL_DATA_BYTES
EXECUTABLE_PAGE_END = r31.EXECUTABLE_PAGE_END

ALERT0_CALLBACK_OFFSET = 0x00267776
ALERT0_CALLBACK_BYTES = 24
ALERT0_CALLBACK_SHA256 = "67b451bbd3fa64c516c50167825fbfab8aed0d1064e0c519c1855aff80e0dec6"
ALERT0_SETTER_CALLSITE = 0x00267788
PROPERTY_SETTER_RUNTIME = 0x064073DA
STOCK_DIAGNOSTIC_MODEL_RUNTIME = 0x068DE3EF


class TtlR35PayloadError(RuntimeError):
    pass


@dataclass(frozen=True)
class Component:
    name: str
    source: Path
    offset: int
    length: int
    code_length: int
    literal_hex: str
    sha256: str


COMPONENTS = (
    Component(
        "ttl_forward",
        r31.NATIVE_DIRECTORY / "ttl_forward.ll",
        TTL_FORWARD_OFFSET,
        152,
        144,
        "301400064cc10207",
        "90a12950ccc5b672c680d34875e4ac1fa2365ab8d841c164eab3f45e934a0d1d",
    ),
    Component(
        "ttl_post_set",
        NATIVE_DIRECTORY / "ttl_post_set.ll",
        TTL_POST_SET_OFFSET,
        208,
        192,
        "30140006efe38d06937440060ff04406",
        "be9b3332cca6771ec4472791de5fbba988fe6560d5e3fc82dd3a264e6bc3d0db",
    ),
    Component(
        "ttl_post_get",
        NATIVE_DIRECTORY / "ttl_post_get.ll",
        TTL_POST_GET_OFFSET,
        168,
        156,
        "30140006efe38d06db734006",
        "7b94a4375e6557df537233321d0e83193528d99625128f0959b71c6fea1e7d6b",
    ),
)


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _condition(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {"name": name, "expected": expected, "actual": actual, "passed": expected == actual}


def _require(conditions: list[dict[str, Any]], context: str) -> None:
    failed = [item["name"] for item in conditions if not item["passed"]]
    if failed:
        raise TtlR35PayloadError(f"{context} failed: " + ", ".join(failed))


def data_blob() -> bytes:
    """Return the entire low-page mutable state and string block."""

    value = bytearray(TTL_DATA_BYTES)
    fields = {
        0x10: b"command\0",
        0x18: b"arg\0",
        0x1C: b"output\0",
        0x28: b"off\0",
    }
    for offset, raw in fields.items():
        end = offset + len(raw)
        if end > len(value) or any(value[offset:end]):
            raise TtlR35PayloadError("internal R3.5 TTL data layout overlaps")
        value[offset:end] = raw
    result = bytes(value)
    expected = "0eaca06bf0695b710699e8dd10850899b182c0ad722808f2085601ec413a5815"
    if sha256(result) != expected:
        raise TtlR35PayloadError("internal R3.5 TTL data layout changed")
    return result


def compile_components() -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    compiled: dict[str, bytes] = {}
    conditions: list[dict[str, Any]] = []
    for item in COMPONENTS:
        try:
            source = item.source.read_bytes()
        except OSError as exc:
            raise TtlR35PayloadError(f"R3.5 component source is unavailable: {item.source.name}") from exc
        layout = thumb.compile_ir_layout(source)
        raw = bytes(layout["raw"])
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
    _require(conditions, "R3.5 native component compilation")
    return compiled, conditions


def inspect_exact_oslo(oslo: bytes) -> dict[str, Any]:
    try:
        inherited = r33.inspect_exact_oslo(oslo)
    except r33.TtlR33PayloadError as exc:
        raise TtlR35PayloadError(str(exc)) from exc
    conditions = list(inherited["conditions"])
    alert0 = oslo[ALERT0_CALLBACK_OFFSET:ALERT0_CALLBACK_OFFSET + ALERT0_CALLBACK_BYTES]
    conditions.extend(
        (
            _condition("r35_data_source_all_zero", True, oslo[TTL_DATA_OFFSET:TTL_DATA_END] == b"\0" * TTL_DATA_BYTES),
            _condition("r35_data_end_before_stock_thumb", True, TTL_DATA_END <= r30.CODE_CAVE_A_END),
            _condition("r35_setter_end_before_data", True, TTL_POST_SET_OFFSET + 208 <= TTL_DATA_OFFSET),
            _condition("r35_getter_end_before_stock_thumb", True, TTL_POST_GET_OFFSET + 168 <= r30.CODE_CAVE_B_END),
            _condition("r35_payload_below_first_page_end", True, TTL_POST_GET_OFFSET + 168 < EXECUTABLE_PAGE_END),
            _condition("stock_diagnostic_descriptor_name_pointer", STOCK_DIAGNOSTIC_MODEL_RUNTIME, struct.unpack_from("<I", oslo, DUSTER_DIAGNOSTIC_NAME_POINTER)[0]),
            _condition("stock_diagnostic_model_string", b"diagnostic\0".hex(), oslo[STOCK_DIAGNOSTIC_MODEL_RUNTIME - OSLO_RUNTIME_BASE:STOCK_DIAGNOSTIC_MODEL_RUNTIME - OSLO_RUNTIME_BASE + 11].hex()),
            _condition("stock_alert0_callback_sha256", ALERT0_CALLBACK_SHA256, sha256(alert0)),
            _condition("stock_alert0_same_setter_target", PROPERTY_SETTER_RUNTIME, _thumb_bl_target(oslo, ALERT0_SETTER_CALLSITE)),
        )
    )
    return {
        "schema": "mf885-community-r35-same-model-ttl-oslo-source/v1",
        "status": "GREEN" if all(item["passed"] for item in conditions) else "REJECTED",
        "conditions": conditions,
    }


def _thumb_bl_target(oslo: bytes, offset: int) -> int:
    return r30.thumb_bl_target(oslo[offset:offset + 4], OSLO_RUNTIME_BASE + offset)


def require_exact_oslo(oslo: bytes) -> dict[str, Any]:
    report = inspect_exact_oslo(oslo)
    _require(report["conditions"], "exact R3.5 OSLO source")
    return report


def build_payload(oslo: bytes, mode: str = "full") -> tuple[bytes, dict[str, Any]]:
    if mode not in {"observer", "full"}:
        raise TtlR35PayloadError("mode must be observer or full")
    source = require_exact_oslo(oslo)
    compiled, component_conditions = compile_components()
    blob = data_blob()
    hook_target = r30.thumb_bl_target(IP_FORWARD_HOOK[8:12], IP_FORWARD_HOOK_RUNTIME + 8)
    hook_condition = _condition("hook_bl_target", TTL_FORWARD_RUNTIME, hook_target)
    _require([hook_condition], "R3.5 forward hook target")

    candidate = bytearray(oslo)
    for item in COMPONENTS:
        r30._write_exact(candidate, item.offset, compiled[item.name])
    r30._write_exact(candidate, TTL_DATA_OFFSET, blob)
    struct.pack_into("<I", candidate, DUSTER_POST_SET_POINTER, TTL_POST_SET_RUNTIME | 1)
    struct.pack_into("<I", candidate, DUSTER_POST_GET_POINTER, TTL_POST_GET_RUNTIME | 1)
    if mode == "full":
        r30._write_exact(candidate, IP_FORWARD_HOOK_OFFSET, IP_FORWARD_HOOK)

    engineering_conditions = [
        _condition("wan_row_sha256_preserved", sha256(oslo[r33.WAN_ROW_OFFSET:r33.WAN_ROW_OFFSET + r33.WAN_ROW_BYTES]), sha256(bytes(candidate[r33.WAN_ROW_OFFSET:r33.WAN_ROW_OFFSET + r33.WAN_ROW_BYTES]))),
        _condition("debugon_row_sha256_preserved", sha256(oslo[r33.DEBUGON_ROW_OFFSET:r33.DEBUGON_ROW_OFFSET + r33.DEBUGON_ROW_BYTES]), sha256(bytes(candidate[r33.DEBUGON_ROW_OFFSET:r33.DEBUGON_ROW_OFFSET + r33.DEBUGON_ROW_BYTES]))),
        _condition("debugon_callback_sha256_preserved", sha256(oslo[r33.DEBUGON_CALLBACK_OFFSET:r33.DEBUGON_CALLBACK_OFFSET + r33.DEBUGON_CALLBACK_BYTES]), sha256(bytes(candidate[r33.DEBUGON_CALLBACK_OFFSET:r33.DEBUGON_CALLBACK_OFFSET + r33.DEBUGON_CALLBACK_BYTES]))),
        _condition("system_channel_row_sha256_preserved", sha256(oslo[r33.SYSTEM_CHANNEL_ROW_OFFSET:r33.SYSTEM_CHANNEL_ROW_OFFSET + r33.SYSTEM_CHANNEL_ROW_BYTES]), sha256(bytes(candidate[r33.SYSTEM_CHANNEL_ROW_OFFSET:r33.SYSTEM_CHANNEL_ROW_OFFSET + r33.SYSTEM_CHANNEL_ROW_BYTES]))),
        _condition("system_channel_callback_sha256_preserved", sha256(oslo[r33.SYSTEM_CHANNEL_CALLBACK_OFFSET:r33.SYSTEM_CHANNEL_CALLBACK_OFFSET + r33.SYSTEM_CHANNEL_CALLBACK_BYTES]), sha256(bytes(candidate[r33.SYSTEM_CHANNEL_CALLBACK_OFFSET:r33.SYSTEM_CHANNEL_CALLBACK_OFFSET + r33.SYSTEM_CHANNEL_CALLBACK_BYTES]))),
    ]
    callback_conditions = [
        _condition("diagnostic_pre_set_candidate_pointer", 0, struct.unpack_from("<I", candidate, DUSTER_PRE_SET_POINTER)[0]),
        _condition("diagnostic_post_set_candidate_pointer", TTL_POST_SET_RUNTIME | 1, struct.unpack_from("<I", candidate, DUSTER_POST_SET_POINTER)[0]),
        _condition("diagnostic_pre_get_candidate_pointer", 0, struct.unpack_from("<I", candidate, DUSTER_PRE_GET_POINTER)[0]),
        _condition("diagnostic_post_get_candidate_pointer", TTL_POST_GET_RUNTIME | 1, struct.unpack_from("<I", candidate, DUSTER_POST_GET_POINTER)[0]),
    ]
    _require(engineering_conditions + callback_conditions, "R3.5 callback and Engineering preservation")

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
        "schema": "mf885-community-r35-same-model-ttl-native-payload/v1",
        "status": "GREEN",
        "mode": mode,
        "source": {"bytes": len(oslo), "sha256": sha256(oslo), "conditions": source["conditions"]},
        "components": component_conditions,
        "transport": {
            "trigger_model": "diagnostic",
            "read_model": "diagnostic",
            "read_field": "output",
            "publisher_slot": "post_get",
            "publisher_setter_calls": 1,
            "same_model_publication": True,
            "set_model": "diagnostic",
            "set_fields": ["command", "arg"],
            "set_response_setter_calls": 0,
            "system_channel_bridge_used": False,
            "engineering_used": False,
            "debugon_used": False,
            "target_get_qualified": False,
            "conditions": callback_conditions,
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
        "engineering": {
            "wan_engineering_mode_changed": False,
            "debugon_row_changed": False,
            "debugon_callback_changed": False,
            "system_channel_row_changed": False,
            "system_channel_callback_changed": False,
            "conditions": engineering_conditions,
        },
        "changed_ranges": sorted(ranges, key=lambda item: item["offset"]),
        "artifact": {"bytes": len(result), "sha256": sha256(result)},
        "qualification": {
            "offline_machine_contract": True,
            "live_get": False,
            "live_set": False,
            "live_packet_path": False,
            "cold_boot": False,
            "repeatability": False,
            "rollback": False,
        },
        "safety": {"device_requests": 0, "network_changes": 0, "firmware_posts": 0},
    }


def verify_payload(source: bytes, candidate: bytes, mode: str = "full") -> dict[str, Any]:
    expected, report = build_payload(source, mode)
    allowed: set[int] = set()
    for item in report["changed_ranges"]:
        allowed.update(range(item["offset"], item["offset"] + item["bytes"]))
    actual_changed = {
        index for index, (before, after) in enumerate(zip(source, candidate)) if before != after
    }
    conditions = [
        _condition("candidate_bytes", len(expected), len(candidate)),
        _condition("candidate_sha256", sha256(expected), sha256(candidate)),
        _condition("candidate_byte_exact", True, expected == candidate),
        _condition("changed_bytes_within_named_ranges", True, actual_changed <= allowed),
        _condition("diagnostic_pre_get_zero", 0, struct.unpack_from("<I", candidate, DUSTER_PRE_GET_POINTER)[0]),
        _condition("diagnostic_post_get_exact", TTL_POST_GET_RUNTIME | 1, struct.unpack_from("<I", candidate, DUSTER_POST_GET_POINTER)[0]),
        _condition("engineering_preserved", True, all(item["passed"] for item in report["engineering"]["conditions"])),
    ]
    return {
        "schema": "mf885-community-r35-same-model-ttl-native-verification/v1",
        "status": "GREEN" if all(item["passed"] for item in conditions) else "REJECTED",
        "mode": mode,
        "conditions": conditions,
        "build": report,
    }


parse_ttl_argument = r31.parse_ttl_argument
rewrite_ipv4_ttl = r31.rewrite_ipv4_ttl
rfc1624_ttl_checksum = r31.rfc1624_ttl_checksum


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an offline MF885 R3.5 same-model TTL payload")
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
    except (OSError, TtlR35PayloadError, thumb.NativeBuildError) as exc:
        print(json.dumps({"schema": "mf885-community-r35-same-model-ttl-native-payload/v1", "status": "REJECTED", "reason": str(exc)}, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
