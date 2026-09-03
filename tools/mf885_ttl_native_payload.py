#!/usr/bin/env python3
"""Build and verify the exact Community R3.0 TTL native OSLO payload.

This module is deliberately an OSLO-level offline primitive.  It accepts only
the exact decompressed 2.5.94 OSLO, compiles three pinned Thumb components,
checks every source anchor independently and returns an observer or full
candidate in memory.  It does not assemble a flash image or contact a device.
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


ROOT = Path(__file__).resolve().parents[1]
NATIVE_DIRECTORY = ROOT / "firmware" / "community-r3.0" / "native"

OSLO_BYTES = 9_648_064
OSLO_SHA256 = "d51fb378d8ccf68662174f39d6b8c4f6be5571280790bc3a4dc4a9e8a967078c"
OSLO_RUNTIME_BASE = 0x06000000

IP_FORWARD_HOOK_OFFSET = 0x008ED1CA
IP_FORWARD_HOOK_RUNTIME = OSLO_RUNTIME_BASE + IP_FORWARD_HOOK_OFFSET
IP_FORWARD_ORIGINAL = bytes.fromhex("c4 4a a3 6d 31 00 20 32 20 00 98 47")
IP_FORWARD_HOOK = bytes.fromhex("28 00 31 00 22 00 a3 6d 14 f7 65 d8")

# Native code stays in two exact zero-filled ranges immediately before exact
# stock Thumb code on the first loaded OSLO page.  A stock aligned literal at
# file offset 0x1714 points to the exact Thumb function at 0x06001a2d.  The
# former tail placement was only a data/BSS reservation and is deliberately
# not executable payload space.
TTL_FORWARD_OFFSET = 0x000012A0
TTL_POST_SET_OFFSET = 0x00001340
TTL_POST_GET_OFFSET = 0x00001520
TTL_DATA_OFFSET = 0x00933200
TTL_FORWARD_RUNTIME = OSLO_RUNTIME_BASE + TTL_FORWARD_OFFSET
TTL_POST_SET_RUNTIME = OSLO_RUNTIME_BASE + TTL_POST_SET_OFFSET
TTL_POST_GET_RUNTIME = OSLO_RUNTIME_BASE + TTL_POST_GET_OFFSET
TTL_DATA_RUNTIME = OSLO_RUNTIME_BASE + TTL_DATA_OFFSET

DUSTER_DIAGNOSTIC_OFFSET = 0x009003E8
DUSTER_PRE_SET_POINTER = DUSTER_DIAGNOSTIC_OFFSET + 0x14
DUSTER_POST_SET_POINTER = DUSTER_DIAGNOSTIC_OFFSET + 0x1C
DUSTER_PRE_GET_POINTER = DUSTER_DIAGNOSTIC_OFFSET + 0x24
DUSTER_POST_GET_POINTER = DUSTER_DIAGNOSTIC_OFFSET + 0x2C

CODE_CAVE_A_START = 0x00001295
CODE_CAVE_A_END = 0x00001500
CODE_CAVE_A_SHA256 = "fa9ef72c7116ed4e52fc3f5f9a2798ee5ea2b44fb33f8ddbaffc9a45161be40b"
CODE_CAVE_B_START = 0x00001511
CODE_CAVE_B_END = 0x00001600
CODE_CAVE_B_SHA256 = "92426fa49cf0d59a470bc4d7cc53b8e52489315dc449ab2a4e69539c76ce8e42"
DATA_CAVE_START = 0x0092B7E2
DATA_CAVE_END = 0x009337C0
DATA_CAVE_SHA256 = "26f6a4c5a69444d86a494f1a607acd13128319505e076facec6cd144158a15c0"


class TtlPayloadError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceSlice:
    name: str
    offset: int
    length: int
    sha256: str


@dataclass(frozen=True)
class Component:
    name: str
    source: str
    offset: int
    length: int
    code_length: int
    literal_hex: str
    sha256: str


SOURCE_SLICES = (
    SourceSlice(
        "ip_forward",
        0x008ED0EC,
        250,
        "5bddc55d3de272b70494e70e116d60774c4feefbae6c30365042e37ab86bf8ac",
    ),
    SourceSlice(
        "ip_forward_hook",
        IP_FORWARD_HOOK_OFFSET,
        len(IP_FORWARD_ORIGINAL),
        "91ca878984de512e58088ef573c1ebbb48e1a52493ae046e278c20aa4f32caa8",
    ),
    SourceSlice(
        "ip_input_ttl_check",
        0x008ED2FA,
        14,
        "2d56670cf30d4af4c4c6818fee53c8e8766c5473285181a4196e88668a274dfb",
    ),
    SourceSlice(
        "ip_input_forward_call",
        0x008ED732,
        14,
        "a6e747f9d57d5eb6614cc15b44d0cdc8d683237f0f8b90f0ba4f0da522896cd5",
    ),
    SourceSlice(
        "checksum_callsite",
        0x007914D4,
        20,
        "4670ab7070827e0159436c27df4adc8ee8b511e207b7537d9e093a99439ac080",
    ),
    SourceSlice(
        "checksum_wrapper",
        0x00791518,
        14,
        "f8a9001707b17069bf14639dcc596f0e8f1c5ba1612f81c3aebf7c3e28230c7d",
    ),
    SourceSlice(
        "checksum_core",
        0x007924E4,
        142,
        "a11086adac37ea5780417697c9947d7526556b3b6a5de2344c56177754559aa4",
    ),
    SourceSlice(
        "duster_callback_wrappers",
        0x006F8E5E,
        80,
        "eb6278cf18b6e813b2a1496a34a78aa513525cfafa4dff50aabbec72f7a3eaee",
    ),
    SourceSlice(
        "duster_property_getter",
        0x00407492,
        96,
        "473e93676c2a2836fa658f9fb553f55b5076bcd153da1c42c318ee03dc1c23fa",
    ),
    SourceSlice(
        "duster_property_setter",
        0x004073DA,
        184,
        "e2aae0a98a9d1a84239e5c3d2abd49cddcbeb0f98bb34681ceedd5f4efb5b118",
    ),
    SourceSlice(
        "duster_diagnostic_row",
        DUSTER_DIAGNOSTIC_OFFSET,
        56,
        "6e8dca202d2bfbba8583ea6a2d71e9a2c3f54683fa9363d241ea34ef06af1886",
    ),
    SourceSlice(
        "oslo_load_table",
        0x000001C0,
        64,
        "6cc377361940b1105058408d5c8f3394acef14e2b7fb5db515dd00efc90932fb",
    ),
    SourceSlice(
        "stock_code_after_caves",
        0x00001600,
        128,
        "ffbb4777cdab63bc37da8de2b47b2fb09155bd7f948d71ac6e97cba236b9839f",
    ),
    SourceSlice(
        "stock_referenced_thumb",
        0x00001A2C,
        128,
        "25df38186260be12489f71b6330f1ca5c79cf9336488925290a6ed02ca2cd53a",
    ),
    SourceSlice(
        "stock_reference_literal",
        0x00001714,
        4,
        "1a0da49cfde5c8fe2ec5bcaf34df738812d7651b0c5daace41d7049568d08fe7",
    ),
    SourceSlice(
        "cinit_reserved_copy_routine",
        0x004B5BEC,
        96,
        "fc11f7b2c052b297c9b3a7b6f00e1338682827c4cf48fb3c61cccbf14cffc960",
    ),
    SourceSlice(
        "cinit_reserved_copy_source",
        0x0092B7D0,
        20,
        "1eed548f21b12febc492c4342f226eeb15d9f2b72216824a7a5bfa04cb30b319",
    ),
    SourceSlice(
        "executable_zero_cave_a",
        CODE_CAVE_A_START,
        CODE_CAVE_A_END - CODE_CAVE_A_START,
        CODE_CAVE_A_SHA256,
    ),
    SourceSlice(
        "executable_zero_cave_b",
        CODE_CAVE_B_START,
        CODE_CAVE_B_END - CODE_CAVE_B_START,
        CODE_CAVE_B_SHA256,
    ),
    SourceSlice(
        "trailing_zero_data_cave",
        DATA_CAVE_START,
        DATA_CAVE_END - DATA_CAVE_START,
        DATA_CAVE_SHA256,
    ),
    SourceSlice(
        "ttl_data_exact_source",
        TTL_DATA_OFFSET,
        0x500,
        "bfe492baf731a0dbf6e1e050f5bc3fe8c1b049383194dcdf82f023bfa409f462",
    ),
)

COMPONENTS = (
    Component(
        "ttl_forward",
        "ttl_forward.ll",
        TTL_FORWARD_OFFSET,
        152,
        144,
        "003293064cc10207",
        "2a97d1fc60fdf095a3a6dbb40476fbb0af01ead767da8b85657057c1eae9d3cb",
    ),
    Component(
        "ttl_post_set",
        "ttl_post_set.ll",
        TTL_POST_SET_OFFSET,
        232,
        220,
        "04329306db7340060ff04406",
        "93c9f564f2eb092b47d3ac91311283ff7b8dba6f7ab2523e30d69184c8cbc58b",
    ),
    Component(
        "ttl_post_get",
        "ttl_post_get.ll",
        TTL_POST_GET_OFFSET,
        84,
        76,
        "04329306db734006",
        "864f2e95e06bc08f7d3eb9340a4e2404f6d4c447f3b7498391744773ca182323",
    ),
)


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _condition(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {"name": name, "expected": expected, "actual": actual, "passed": actual == expected}


def _aligned_absolute_pointer_count(oslo: bytes, start: int, end: int) -> int:
    count = 0
    for offset in range(0, max(0, len(oslo) - 3), 4):
        value = struct.unpack_from("<I", oslo, offset)[0] & ~1
        if start <= value < end:
            count += 1
    return count


def data_blob() -> bytes:
    # Numeric readback is immutable and therefore reentrant: every possible
    # one-byte state indexes one fixed four-byte canonical string.  No GET
    # callback writes shared scratch memory.
    value = bytearray(0x500)
    fields = {
        0x04: b"diagnostic\0",
        0x10: b"command\0",
        0x18: b"arg\0",
        0x1C: b"output\0",
        0x24: b"ttl\0",
        0x28: b"off\0",
        0x2C: b"64\0",
        0x30: b"65\0",
        0x34: b"TTL_OFF\0",
        0x3C: b"TTL_64\0",
        0x44: b"TTL_65\0",
        0x4C: b"TTL_REJECTED\0",
        0x5C: b"TTL_STATE_INVALID\0",
        0x78: b"TTL_SET\0",
        0x80: b"TTL_VALUE\0",
    }
    for offset, raw in fields.items():
        value[offset : offset + len(raw)] = raw
    for state in range(256):
        raw = ("off" if state == 0 else str(state)).encode("ascii") + b"\0"
        if len(raw) > 4:
            raise TtlPayloadError("internal canonical TTL readback exceeds four bytes")
        offset = 0x100 + state * 4
        value[offset : offset + len(raw)] = raw
    result = bytes(value)
    expected = "b391fea1c3a269ddfbfdba0cb395aeed1fc1789e8d4bd3304b7b509515e77bca"
    if sha256(result) != expected:
        raise TtlPayloadError("internal TTL data layout changed")
    return result


def inspect_exact_oslo(oslo: bytes) -> dict[str, Any]:
    exact_identity = len(oslo) == OSLO_BYTES and sha256(oslo) == OSLO_SHA256
    conditions = [
        _condition("oslo_bytes", OSLO_BYTES, len(oslo)),
        _condition("oslo_sha256", OSLO_SHA256, sha256(oslo)),
        _condition(
            "ip_forward_original_bytes",
            IP_FORWARD_ORIGINAL.hex(),
            oslo[IP_FORWARD_HOOK_OFFSET : IP_FORWARD_HOOK_OFFSET + len(IP_FORWARD_ORIGINAL)].hex(),
        ),
    ]
    for item in SOURCE_SLICES:
        raw = oslo[item.offset : item.offset + item.length]
        conditions.append(_condition(f"source:{item.name}:bytes", item.length, len(raw)))
        conditions.append(_condition(f"source:{item.name}:sha256", item.sha256, sha256(raw)))
    if len(oslo) >= 0x1D8:
        load_start, load_end = struct.unpack_from("<II", oslo, 0x1C0)
        load_marker = oslo[0x1C8:0x1D8]
    else:
        load_start = load_end = None
        load_marker = b""
    conditions.extend(
        (
            _condition("load_table_runtime_start", OSLO_RUNTIME_BASE + 4, load_start),
            _condition("load_table_runtime_end", OSLO_RUNTIME_BASE + OSLO_BYTES, load_end),
            _condition("load_table_marker", b"LOAD_TABLE_SIGN\0".hex(), load_marker.hex()),
            _condition(
                "stock_thumb_literal_target",
                OSLO_RUNTIME_BASE + 0x1A2D,
                struct.unpack_from("<I", oslo, 0x1714)[0] if len(oslo) >= 0x1718 else None,
            ),
            _condition(
                "code_cave_a_aligned_absolute_references",
                0,
                _aligned_absolute_pointer_count(
                    oslo,
                    OSLO_RUNTIME_BASE + CODE_CAVE_A_START,
                    OSLO_RUNTIME_BASE + CODE_CAVE_A_END,
                ) if exact_identity else None,
            ),
            _condition(
                "code_cave_b_aligned_absolute_references",
                0,
                _aligned_absolute_pointer_count(
                    oslo,
                    OSLO_RUNTIME_BASE + CODE_CAVE_B_START,
                    OSLO_RUNTIME_BASE + CODE_CAVE_B_END,
                ) if exact_identity else None,
            ),
            _condition(
                "ttl_data_aligned_absolute_references",
                0,
                _aligned_absolute_pointer_count(
                    oslo,
                    TTL_DATA_RUNTIME,
                    TTL_DATA_RUNTIME + 0x500,
                ) if exact_identity else None,
            ),
        )
    )
    callbacks = {
        "pre_set": struct.unpack_from("<I", oslo, DUSTER_PRE_SET_POINTER)[0]
        if len(oslo) >= DUSTER_PRE_SET_POINTER + 4
        else None,
        "post_set": struct.unpack_from("<I", oslo, DUSTER_POST_SET_POINTER)[0]
        if len(oslo) >= DUSTER_POST_SET_POINTER + 4
        else None,
        "pre_get": struct.unpack_from("<I", oslo, DUSTER_PRE_GET_POINTER)[0]
        if len(oslo) >= DUSTER_PRE_GET_POINTER + 4
        else None,
        "post_get": struct.unpack_from("<I", oslo, DUSTER_POST_GET_POINTER)[0]
        if len(oslo) >= DUSTER_POST_GET_POINTER + 4
        else None,
    }
    for name, actual in callbacks.items():
        conditions.append(_condition(f"diagnostic_{name}_pointer", 0, actual))
    return {
        "schema": "mf885-community-r30-ttl-oslo-source/v1",
        "status": "GREEN" if all(item["passed"] for item in conditions) else "REJECTED",
        "conditions": conditions,
    }


def require_exact_oslo(oslo: bytes) -> dict[str, Any]:
    report = inspect_exact_oslo(oslo)
    failed = [item["name"] for item in report["conditions"] if not item["passed"]]
    if failed:
        raise TtlPayloadError("exact OSLO conditions failed: " + ", ".join(failed))
    return report


def compile_components() -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    results: dict[str, bytes] = {}
    conditions: list[dict[str, Any]] = []
    for item in COMPONENTS:
        source = (NATIVE_DIRECTORY / item.source).read_bytes()
        layout = thumb.compile_ir_layout(source)
        raw = layout["raw"]
        expected_ranges = [
            {"kind": "thumb", "offset": 0, "bytes": item.code_length},
            {
                "kind": "data",
                "offset": item.code_length,
                "bytes": item.length - item.code_length,
            },
        ]
        expected_function = [
            {"name": item.name, "offset": 0, "thumb": True, "bytes": item.length}
        ]
        conditions.extend(
            (
                _condition(f"component:{item.name}:bytes", item.length, len(raw)),
                _condition(f"component:{item.name}:sha256", item.sha256, sha256(raw)),
                _condition(f"component:{item.name}:placement_alignment", 0, item.offset % 4),
                _condition(f"component:{item.name}:mapping_ranges", expected_ranges, layout["ranges"]),
                _condition(f"component:{item.name}:function_symbol", expected_function, layout["functions"]),
                _condition(
                    f"component:{item.name}:literal_pool",
                    item.literal_hex,
                    raw[item.code_length :].hex(),
                ),
            )
        )
        results[item.name] = raw
    failed = [item["name"] for item in conditions if not item["passed"]]
    if failed:
        raise TtlPayloadError("native component conditions failed: " + ", ".join(failed))
    return results, conditions


def thumb_bl_target(instruction: bytes, address: int) -> int | None:
    if len(instruction) != 4:
        return None
    first, second = struct.unpack("<HH", instruction)
    if first & 0xF800 != 0xF000 or second & 0xD000 != 0xD000:
        return None
    sign = (first >> 10) & 1
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    i1 = (~(j1 ^ sign)) & 1
    i2 = (~(j2 ^ sign)) & 1
    immediate = (
        (sign << 24)
        | (i1 << 23)
        | (i2 << 22)
        | ((first & 0x03FF) << 12)
        | ((second & 0x07FF) << 1)
    )
    if immediate & (1 << 24):
        immediate -= 1 << 25
    return address + 4 + immediate


def _write_exact(target: bytearray, offset: int, value: bytes) -> None:
    if offset < 0 or offset + len(value) > len(target):
        raise TtlPayloadError("payload placement escapes OSLO")
    target[offset : offset + len(value)] = value


def build_payload(oslo: bytes, mode: str) -> tuple[bytes, dict[str, Any]]:
    if mode not in {"observer", "full"}:
        raise TtlPayloadError("mode must be observer or full")
    source_report = require_exact_oslo(oslo)
    compiled, component_conditions = compile_components()
    blob = data_blob()
    hook_target = thumb_bl_target(IP_FORWARD_HOOK[8:12], IP_FORWARD_HOOK_RUNTIME + 8)
    hook_condition = _condition("hook_bl_target", TTL_FORWARD_RUNTIME, hook_target)
    if not hook_condition["passed"]:
        raise TtlPayloadError("TTL hook BL target changed")

    candidate = bytearray(oslo)
    for item in COMPONENTS:
        _write_exact(candidate, item.offset, compiled[item.name])
    _write_exact(candidate, TTL_DATA_OFFSET, blob)
    struct.pack_into("<I", candidate, DUSTER_POST_SET_POINTER, TTL_POST_SET_RUNTIME | 1)
    struct.pack_into("<I", candidate, DUSTER_POST_GET_POINTER, TTL_POST_GET_RUNTIME | 1)
    if mode == "full":
        _write_exact(candidate, IP_FORWARD_HOOK_OFFSET, IP_FORWARD_HOOK)

    ranges = [
        {"name": item.name, "offset": item.offset, "bytes": len(compiled[item.name])}
        for item in COMPONENTS
    ]
    ranges.extend(
        (
            {"name": "ttl_data", "offset": TTL_DATA_OFFSET, "bytes": len(blob)},
            {"name": "diagnostic_post_set_pointer", "offset": DUSTER_POST_SET_POINTER, "bytes": 4},
            {"name": "diagnostic_post_get_pointer", "offset": DUSTER_POST_GET_POINTER, "bytes": 4},
        )
    )
    if mode == "full":
        ranges.append(
            {"name": "ip_forward_hook", "offset": IP_FORWARD_HOOK_OFFSET, "bytes": len(IP_FORWARD_HOOK)}
        )
    result = bytes(candidate)
    report = {
        "schema": "mf885-community-r30-ttl-native-payload/v1",
        "status": "GREEN",
        "mode": mode,
        "source": {
            "bytes": len(oslo),
            "sha256": sha256(oslo),
            "conditions": source_report["conditions"],
        },
        "components": component_conditions,
        "hook": {
            "installed": mode == "full",
            "bytes": IP_FORWARD_HOOK.hex(),
            "bl_target": f"0x{hook_target:08x}",
            "condition": hook_condition,
        },
        "state": {
            "address": f"0x{TTL_DATA_RUNTIME:08x}",
            "boot_value": 0,
            "accepted_values": {"off": 0, "numeric_min": 1, "numeric_max": 255},
            "persistent": False,
        },
        "changed_ranges": sorted(ranges, key=lambda item: item["offset"]),
        "artifact": {"bytes": len(result), "sha256": sha256(result)},
        "safety": {
            "device_requests": 0,
            "network_changes": 0,
            "firmware_posts": 0,
            "observer_mutates_forwarding": False if mode == "observer" else None,
        },
    }
    return result, report


def verify_payload(source: bytes, candidate: bytes, mode: str) -> dict[str, Any]:
    expected, build_report = build_payload(source, mode)
    conditions = [
        _condition("candidate_bytes", len(expected), len(candidate)),
        _condition("candidate_sha256", sha256(expected), sha256(candidate)),
        _condition("candidate_byte_exact", True, candidate == expected),
    ]
    return {
        "schema": "mf885-community-r30-ttl-native-verification/v1",
        "status": "GREEN" if all(item["passed"] for item in conditions) else "REJECTED",
        "mode": mode,
        "conditions": conditions,
        "build": build_report,
    }


def internet_checksum(value: bytes) -> int:
    if len(value) % 2:
        value += b"\0"
    total = sum(struct.unpack(f">{len(value) // 2}H", value))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def rfc1624_ttl_checksum(old_checksum: int, old_ttl: int, protocol: int, new_ttl: int) -> int:
    if not all(0 <= item <= 0xFF for item in (old_ttl, protocol, new_ttl)):
        raise ValueError("TTL and protocol values must fit one byte")
    if not 0 <= old_checksum <= 0xFFFF:
        raise ValueError("checksum must fit two bytes")
    old_word = (old_ttl << 8) | protocol
    new_word = (new_ttl << 8) | protocol
    total = ((~old_checksum) & 0xFFFF) + ((~old_word) & 0xFFFF) + new_word
    total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def parse_ttl_argument(value: str) -> int:
    """Return the native state byte for one canonical public TTL argument."""

    if value == "off":
        return 0
    if not value or len(value) > 3 or not value.isascii() or not value.isdecimal():
        raise ValueError("TTL must be Off or a canonical decimal integer from 1 to 255")
    if value[0] == "0":
        raise ValueError("TTL must be Off or a canonical decimal integer from 1 to 255")
    numeric = int(value, 10)
    if not 1 <= numeric <= 255 or str(numeric) != value:
        raise ValueError("TTL must be Off or a canonical decimal integer from 1 to 255")
    return numeric


def rewrite_ipv4_ttl(header: bytes, target: int) -> bytes:
    if not 1 <= target <= 255:
        raise ValueError("target TTL must be from 1 to 255")
    if len(header) < 20 or header[0] >> 4 != 4:
        raise ValueError("input is not a complete IPv4 header")
    ihl = (header[0] & 0x0F) * 4
    if ihl < 20 or len(header) < ihl:
        raise ValueError("IPv4 header length is invalid")
    result = bytearray(header)
    if result[8] != target:
        checksum = struct.unpack_from(">H", result, 10)[0]
        updated = rfc1624_ttl_checksum(checksum, result[8], result[9], target)
        result[8] = target
        struct.pack_into(">H", result, 10, updated)
    return bytes(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an offline MF885 R3.0 TTL OSLO payload")
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
    except (OSError, TtlPayloadError, thumb.NativeBuildError) as exc:
        print(
            json.dumps(
                {
                    "schema": "mf885-community-r30-ttl-native-payload/v1",
                    "status": "REJECTED",
                    "reason": str(exc),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
