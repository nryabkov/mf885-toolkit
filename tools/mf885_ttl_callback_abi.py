#!/usr/bin/env python3
"""Inspect the exact MF885 Duster/property callback ABI without live I/O.

This analyzer intentionally works from the exact golden OSLO bytes.  It does
not emulate a convenient callback model.  Every conclusion below is tied to a
specific instruction, call target, row wrapper or exact source identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import re
from pathlib import Path
from typing import Any

import mf885_firmware_inspect as firmware
import mf885_thumb_disasm as thumb


OSLO_BYTES = 9_648_064
OSLO_SHA256 = "d51fb378d8ccf68662174f39d6b8c4f6be5571280790bc3a4dc4a9e8a967078c"
OSLO_RUNTIME_BASE = 0x06000000

GOLDEN_OSLO_OFFSET = 0x23C
GOLDEN_OSLO_COMPRESSED_BYTES = 0x460000
DECOMPRESS_LIMIT = 32 * 1024 * 1024
DECOMPRESS_MEMLIMIT = 64 * 1024 * 1024

DISPATCH_CALLS = {
    "set_pre": (0x72C4E2, 0x066F8EE8, 3),
    "get_pre": (0x72C51A, 0x066F8F22, 4),
    "get_core": (0x72C532, 0x0672B61E, None),
    "set_post": (0x72C56C, 0x066F8EAE, 3),
    "get_post": (0x72C5BE, 0x066F8F5C, 4),
}

POST_SET_WRAPPER = (0x6F8E5E, 0x14)
POST_GET_WRAPPER = (0x6F8E9A, 0x14)
SETTER_RANGE = (0x4073DA, 0xB8)
SETTER_CORE_WRAPPER_RANGE = (0x6B488E, 0x22)
SETTER_CORE_RANGE = (0x6B4812, 0x7C)
GETTER_RANGE = (0x407492, 0x152)
GETTER_COPY_RANGE = (0x6B4A50, 0x98)

DUSTER_DISPATCHERS = {
    0x066F8EE8,
    0x066F8F22,
    0x066F8EAE,
    0x066F8F5C,
}

DUSTER_ROW_BYTES = 56
WEBDAV_ROW_OFFSET = 0x9001F0
WEBDAV_ROW_SHA256 = "76e8fb63a0c8b3735819b468caf002b171d556bacb144ac241df24eb31ab2b09"
WEBDAV_POST_SET_OFFSET = 0x6564EE
WEBDAV_POST_SET_BYTES = 450
WEBDAV_POST_SET_SHA256 = "754fb729b29b6010dbbfdfc1555b3c1c52fad8ccb2de6ff6ed3fbe470119c445"
WEBDAV_SETTER_CALLSITE = 0x656594
WEBDAV_PHASE_GATE_OFFSET = 0x656522
WEBDAV_PHASE_GATE_BYTES = 18
WEBDAV_SETTER_SETUP_OFFSET = 0x656588
WEBDAV_SETTER_SETUP_BYTES = 16
WEBDAV_ARGUMENT_BASE_LITERAL_OFFSET = 0x65670C
WEBDAV_ARGUMENT_BASE = 0x06655CCC
WEBDAV_MODEL_ADDRESS = 0x06655D88
WEBDAV_FIELD_ADDRESS = 0x06655D70
WEBDAV_VALUE_ADDRESS = 0x066566B4

LOG_MANAGEMENT_ROW_OFFSET = 0x900260
LOG_MANAGEMENT_ROW_SHA256 = "82f2155863a9fd7385f7e449c32c127be2b66cad853a4927ba9336cb0dcb9dbf"
LOG_MANAGEMENT_PRE_GET_OFFSET = 0x6AD528
LOG_MANAGEMENT_PRE_GET_BYTES = 134
LOG_MANAGEMENT_PRE_GET_SHA256 = "7d436c07c064f6733a490546d0e828bab82d07ac028375aa786ca266d0a6a27e"
LOG_MANAGEMENT_SETTER_CALLSITE = 0x6AD58C
LOG_MANAGEMENT_FORMAT_SETUP_OFFSET = 0x6AD55C
LOG_MANAGEMENT_FORMAT_SETUP_BYTES = 12
LOG_MANAGEMENT_SETTER_SETUP_OFFSET = 0x6AD584
LOG_MANAGEMENT_SETTER_SETUP_BYTES = 12
LOG_MANAGEMENT_FORMAT_ADDRESS = 0x066AD8F0
LOG_MANAGEMENT_MODEL_ADDRESS = 0x066AD868
LOG_MANAGEMENT_FIELD_ADDRESS = 0x066AD90C

DIAGNOSTIC_ROW_OFFSET = 0x9003E8
DIAGNOSTIC_ROW_SHA256 = "6e8dca202d2bfbba8583ea6a2d71e9a2c3f54683fa9363d241ea34ef06af1886"


class CallbackAbiError(RuntimeError):
    pass


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _condition(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {
        "name": name,
        "expected": expected,
        "actual": actual,
        "passed": expected == actual,
    }


def _u32le(value: bytes, offset: int) -> int:
    return int.from_bytes(value[offset : offset + 4], "little")


def _cstring_at_runtime(oslo: bytes, address: int, limit: int = 64) -> str:
    offset = address - OSLO_RUNTIME_BASE
    value = oslo[offset : offset + limit]
    terminator = value.find(b"\0")
    if terminator < 0:
        raise CallbackAbiError(f"unterminated string at 0x{address:08x}")
    return value[:terminator].decode("ascii")


def _instructions(oslo: bytes, offset: int, length: int) -> list[dict[str, Any]]:
    return thumb.disassemble(
        oslo[offset : offset + length], OSLO_RUNTIME_BASE + offset
    )


def _direct_call_targets(
    oslo: bytes, offset: int, length: int
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for item in _instructions(oslo, offset, length):
        instruction = item["instruction"]
        if item["size"] != 4 or not instruction.startswith(("bl\t", "blx\t")):
            continue
        file_offset = item["address"] - OSLO_RUNTIME_BASE
        target = firmware._thumb_bl_target(oslo, file_offset)
        calls.append(
            {
                "callsite": f"0x{item['address']:08x}",
                "instruction": instruction,
                "target": None if target is None else f"0x{target:08x}",
            }
        )
    return calls


def _register_indirect_calls(
    oslo: bytes, offset: int, length: int
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _instructions(oslo, offset, length):
        if re.fullmatch(r"blx\tr(?:1[0-2]|[0-9])", item["instruction"]):
            result.append(
                {
                    "callsite": f"0x{item['address']:08x}",
                    "instruction": item["instruction"],
                }
            )
    return result


def decompress_golden_oslo(golden: bytes) -> bytes:
    if len(golden) < GOLDEN_OSLO_OFFSET + GOLDEN_OSLO_COMPRESSED_BYTES:
        raise CallbackAbiError("golden capture is too short for the exact OSLO envelope")
    decoder = lzma.LZMADecompressor(
        format=lzma.FORMAT_ALONE, memlimit=DECOMPRESS_MEMLIMIT
    )
    try:
        oslo = decoder.decompress(
            golden[
                GOLDEN_OSLO_OFFSET : GOLDEN_OSLO_OFFSET
                + GOLDEN_OSLO_COMPRESSED_BYTES
            ],
            max_length=DECOMPRESS_LIMIT,
        )
    except lzma.LZMAError as exc:
        raise CallbackAbiError("golden OSLO decompression failed") from exc
    return oslo


def inspect_exact_oslo(oslo: bytes) -> dict[str, Any]:
    conditions: list[dict[str, Any]] = [
        _condition("source_bytes", OSLO_BYTES, len(oslo)),
        _condition("source_sha256", OSLO_SHA256, _sha256(oslo)),
    ]

    dispatch: dict[str, Any] = {}
    for name, (callsite, expected_target, phase) in DISPATCH_CALLS.items():
        target = firmware._thumb_bl_target(oslo, callsite)
        dispatch[name] = {
            "callsite": f"0x{OSLO_RUNTIME_BASE + callsite:08x}",
            "target": None if target is None else f"0x{target:08x}",
            "phase": phase,
        }
        conditions.append(
            _condition(f"dispatch:{name}:target", expected_target, target)
        )

    phase_bytes = {
        "set_pre": oslo[0x72C4DC:0x72C4E2].hex(),
        "get_pre": oslo[0x72C50E:0x72C51A].hex(),
        "set_post": oslo[0x72C566:0x72C56C].hex(),
        "get_post": oslo[0x72C5B8:0x72C5BE].hex(),
    }
    expected_phase_bytes = {
        "set_pre": "069803216a46",
        "get_pre": "6a4601e066e097e006980421",
        "set_post": "069803216a46",
        "get_post": "069804216a46",
    }
    for name, expected in expected_phase_bytes.items():
        conditions.append(
            _condition(f"dispatch:{name}:phase_context_bytes", expected, phase_bytes[name])
        )

    post_set = _instructions(oslo, *POST_SET_WRAPPER)
    post_get = _instructions(oslo, *POST_GET_WRAPPER)
    expected_post_set = [
        "push\t{r4, lr}",
        "ldr\tr3, [r0, #0x18]",
        "movs\tr4, r1",
        "movs\tr1, r2",
        "cmp\tr3, #0x0",
        "beq\t#0x2",
        "movs\tr0, r4",
        "blx\tr3",
        "movs\tr0, #0x0",
        "pop\t{r4, pc}",
    ]
    expected_post_get = list(expected_post_set)
    expected_post_get[1] = "ldr\tr3, [r0, #0x28]"
    conditions.extend(
        (
            _condition(
                "wrapper:post_set:instructions",
                expected_post_set,
                [item["instruction"] for item in post_set],
            ),
            _condition(
                "wrapper:post_get:instructions",
                expected_post_get,
                [item["instruction"] for item in post_get],
            ),
        )
    )

    setter_calls = _direct_call_targets(oslo, *SETTER_RANGE)
    setter_core_wrapper_calls = _direct_call_targets(
        oslo, *SETTER_CORE_WRAPPER_RANGE
    )
    setter_core_calls = _direct_call_targets(oslo, *SETTER_CORE_RANGE)
    setter_indirect = _register_indirect_calls(oslo, *SETTER_RANGE)
    setter_core_indirect = _register_indirect_calls(oslo, *SETTER_CORE_RANGE)
    known_targets = {
        int(item["target"], 16)
        for item in setter_calls + setter_core_wrapper_calls + setter_core_calls
        if item["target"] is not None
    }
    conditions.extend(
        (
            _condition(
                "setter:outer_lock_enter",
                "0x0651a496",
                setter_calls[0]["target"] if setter_calls else None,
            ),
            _condition(
                "setter:outer_lock_exit_present",
                True,
                any(item["target"] == "0x0651a4ba" for item in setter_calls),
            ),
            _condition(
                "setter:temporary_value_copy",
                "0x06406cd0",
                next(
                    (
                        item["target"]
                        for item in setter_calls
                        if item["callsite"] == "0x06407410"
                    ),
                    None,
                ),
            ),
            _condition(
                "setter:temporary_value_free",
                "0x0644f00e",
                next(
                    (
                        item["target"]
                        for item in setter_calls
                        if item["callsite"] == "0x06407486"
                    ),
                    None,
                ),
            ),
            _condition(
                "setter:core_wrapper",
                "0x066b488e",
                next(
                    (
                        item["target"]
                        for item in setter_calls
                        if item["callsite"] == "0x0640747a"
                    ),
                    None,
                ),
            ),
            _condition(
                "setter:core_entry",
                "0x066b4812",
                next(
                    (
                        item["target"]
                        for item in setter_core_wrapper_calls
                        if item["callsite"] == "0x066b48a2"
                    ),
                    None,
                ),
            ),
            _condition(
                "setter:duster_dispatch_target_count",
                0,
                len(known_targets & DUSTER_DISPATCHERS),
            ),
            _condition(
                "setter:register_callback_call_count",
                0,
                len(setter_indirect) + len(setter_core_indirect),
            ),
        )
    )

    getter_calls = _direct_call_targets(oslo, *GETTER_RANGE)
    getter_copy_calls = _direct_call_targets(oslo, *GETTER_COPY_RANGE)
    conditions.extend(
        (
            _condition(
                "getter:outer_lock_enter",
                "0x0651a496",
                getter_calls[0]["target"] if getter_calls else None,
            ),
            _condition(
                "getter:outer_lock_exit",
                "0x0651a4ba",
                next(
                    (
                        item["target"]
                        for item in getter_calls
                        if item["callsite"] == "0x064075de"
                    ),
                    None,
                ),
            ),
            _condition(
                "getter:allocated_result",
                "0x0644efdc",
                next(
                    (
                        item["target"]
                        for item in getter_copy_calls
                        if item["callsite"] == "0x066b4aa4"
                    ),
                    None,
                ),
            ),
            _condition(
                "getter:nul_termination_bytes",
                "009800210155",
                oslo[0x6B4ABE:0x6B4AC4].hex(),
            ),
            _condition(
                "getter:returns_result_after_unlock_bytes",
                "12f16cff2800",
                oslo[0x4075DE:0x4075E4].hex(),
            ),
        )
    )

    webdav_row = oslo[WEBDAV_ROW_OFFSET : WEBDAV_ROW_OFFSET + DUSTER_ROW_BYTES]
    webdav_post_set = oslo[
        WEBDAV_POST_SET_OFFSET : WEBDAV_POST_SET_OFFSET + WEBDAV_POST_SET_BYTES
    ]
    webdav_phase_gate = [
        item["instruction"]
        for item in _instructions(
            oslo, WEBDAV_PHASE_GATE_OFFSET, WEBDAV_PHASE_GATE_BYTES
        )
    ]
    webdav_setter_setup = [
        item["instruction"]
        for item in _instructions(
            oslo, WEBDAV_SETTER_SETUP_OFFSET, WEBDAV_SETTER_SETUP_BYTES
        )
    ]
    expected_webdav_phase_gate = [
        "ldr\tr0, [sp, #0x8c]",
        "cmp\tr0, #0x1",
        "bne\t#0x4",
        "movs\tr0, #0x0",
        "add\tsp, #0x94",
        "pop\t{r4, r5, r6, r7, pc}",
        "cmp\tr0, #0x3",
        "bne\t#0xfc",
        "ldr\tr2, [pc, #0x1d8]",
    ]
    expected_webdav_setter_setup = [
        "strb\tr0, [r1, #0x4]",
        "adds\tr2, #0xa4",
        "movs\tr0, r2",
        "movs\tr1, #0x0",
        "adds\tr0, #0x18",
        "adr\tr3, #288",
        "bl\t#-0x24f1be",
    ]
    conditions.extend(
        (
            _condition("stock:webdav:row_sha256", WEBDAV_ROW_SHA256, _sha256(webdav_row)),
            _condition("stock:webdav:pre_set", 0x0665649F, _u32le(webdav_row, 0x14)),
            _condition("stock:webdav:post_set", 0x066564EF, _u32le(webdav_row, 0x1C)),
            _condition("stock:webdav:pre_get", 0, _u32le(webdav_row, 0x24)),
            _condition("stock:webdav:post_get", 0, _u32le(webdav_row, 0x2C)),
            _condition(
                "stock:webdav:post_set_sha256",
                WEBDAV_POST_SET_SHA256,
                _sha256(webdav_post_set),
            ),
            _condition(
                "stock:webdav:phase_gate",
                expected_webdav_phase_gate,
                webdav_phase_gate,
            ),
            _condition(
                "stock:webdav:setter_setup",
                expected_webdav_setter_setup,
                webdav_setter_setup,
            ),
            _condition(
                "stock:webdav:setter_target",
                0x064073DA,
                firmware._thumb_bl_target(oslo, WEBDAV_SETTER_CALLSITE),
            ),
            _condition(
                "stock:webdav:argument_base_literal",
                WEBDAV_ARGUMENT_BASE,
                _u32le(oslo, WEBDAV_ARGUMENT_BASE_LITERAL_OFFSET),
            ),
            _condition(
                "stock:webdav:model_address_from_setup",
                WEBDAV_MODEL_ADDRESS,
                WEBDAV_ARGUMENT_BASE + 0xA4 + 0x18,
            ),
            _condition(
                "stock:webdav:field_address_from_setup",
                WEBDAV_FIELD_ADDRESS,
                WEBDAV_ARGUMENT_BASE + 0xA4,
            ),
            _condition(
                "stock:webdav:model",
                "webdav_shared_management",
                _cstring_at_runtime(oslo, WEBDAV_MODEL_ADDRESS),
            ),
            _condition(
                "stock:webdav:field",
                "webdav_shared_enable",
                _cstring_at_runtime(oslo, WEBDAV_FIELD_ADDRESS),
            ),
            _condition(
                "stock:webdav:value",
                "1",
                _cstring_at_runtime(oslo, WEBDAV_VALUE_ADDRESS),
            ),
        )
    )

    log_management_row = oslo[
        LOG_MANAGEMENT_ROW_OFFSET : LOG_MANAGEMENT_ROW_OFFSET + DUSTER_ROW_BYTES
    ]
    log_management_pre_get = oslo[
        LOG_MANAGEMENT_PRE_GET_OFFSET
        : LOG_MANAGEMENT_PRE_GET_OFFSET + LOG_MANAGEMENT_PRE_GET_BYTES
    ]
    log_management_format_setup = [
        item["instruction"]
        for item in _instructions(
            oslo, LOG_MANAGEMENT_FORMAT_SETUP_OFFSET, LOG_MANAGEMENT_FORMAT_SETUP_BYTES
        )
    ]
    log_management_setter_setup = [
        item["instruction"]
        for item in _instructions(
            oslo, LOG_MANAGEMENT_SETTER_SETUP_OFFSET, LOG_MANAGEMENT_SETTER_SETUP_BYTES
        )
    ]
    conditions.extend(
        (
            _condition(
                "stock:log_management:row_sha256",
                LOG_MANAGEMENT_ROW_SHA256,
                _sha256(log_management_row),
            ),
            _condition(
                "stock:log_management:pre_get",
                0x066AD529,
                _u32le(log_management_row, 0x24),
            ),
            _condition(
                "stock:log_management:pre_get_sha256",
                LOG_MANAGEMENT_PRE_GET_SHA256,
                _sha256(log_management_pre_get),
            ),
            _condition(
                "stock:log_management:setter_target",
                0x064073DA,
                firmware._thumb_bl_target(oslo, LOG_MANAGEMENT_SETTER_CALLSITE),
            ),
            _condition(
                "stock:log_management:format_setup",
                [
                    "movs\tr3, r0",
                    "movs\tr1, #0x4",
                    "adr\tr2, #908",
                    "mov\tr0, sp",
                    "bl\t#0x2fc04",
                ],
                log_management_format_setup,
            ),
            _condition(
                "stock:log_management:setter_setup",
                [
                    "movs\tr1, #0x0",
                    "adr\tr2, #900",
                    "adr\tr0, #732",
                    "mov\tr3, sp",
                    "bl\t#-0x2a61b6",
                ],
                log_management_setter_setup,
            ),
            _condition(
                "stock:log_management:format",
                "%d",
                _cstring_at_runtime(oslo, LOG_MANAGEMENT_FORMAT_ADDRESS),
            ),
            _condition(
                "stock:log_management:model",
                "log_management",
                _cstring_at_runtime(oslo, LOG_MANAGEMENT_MODEL_ADDRESS),
            ),
            _condition(
                "stock:log_management:field",
                "sd_support_format",
                _cstring_at_runtime(oslo, LOG_MANAGEMENT_FIELD_ADDRESS),
            ),
        )
    )

    diagnostic_row = oslo[
        DIAGNOSTIC_ROW_OFFSET : DIAGNOSTIC_ROW_OFFSET + DUSTER_ROW_BYTES
    ]
    diagnostic_callbacks = {
        "pre_set": _u32le(diagnostic_row, 0x14),
        "post_set": _u32le(diagnostic_row, 0x1C),
        "pre_get": _u32le(diagnostic_row, 0x24),
        "post_get": _u32le(diagnostic_row, 0x2C),
    }
    conditions.extend(
        (
            _condition(
                "stock:diagnostic:row_sha256",
                DIAGNOSTIC_ROW_SHA256,
                _sha256(diagnostic_row),
            ),
            _condition(
                "stock:diagnostic:callbacks",
                {"pre_set": 0, "post_set": 0, "pre_get": 0, "post_get": 0},
                diagnostic_callbacks,
            ),
        )
    )

    passed = all(item["passed"] for item in conditions)
    return {
        "schema": "mf885-ttl-callback-abi-inspection/v1",
        "status": "GREEN" if passed else "REJECTED",
        "source": {"bytes": len(oslo), "sha256": _sha256(oslo)},
        "conditions": conditions,
        "dispatch": dispatch,
        "wrappers": {
            "post_set": {
                "callback_offset_from_biased_handle": 0x18,
                "callback_return_propagated": False,
                "forced_return": 0,
            },
            "post_get": {
                "callback_offset_from_biased_handle": 0x28,
                "callback_return_propagated": False,
                "forced_return": 0,
            },
        },
        "property_setter": {
            "entry": "0x064073da",
            "input_lifetime": "copied_synchronously",
            "duster_dispatch_targets": sorted(
                f"0x{target:08x}" for target in known_targets & DUSTER_DISPATCHERS
            ),
            "register_callback_calls": setter_indirect + setter_core_indirect,
            "direct_calls": setter_calls,
            "core_wrapper_calls": setter_core_wrapper_calls,
            "core_calls": setter_core_calls,
        },
        "property_getter": {
            "entry": "0x06407492",
            "result_ownership": "caller_owned",
            "allocation_target": "0x0644efdc",
            "unlocks_before_return": True,
        },
        "stock_publishers": {
            "phase3_same_model_post_set": {
                "model": "webdav_shared_management",
                "row_runtime": "0x069001f0",
                "post_set": "0x066564ef",
                "required_phase": 3,
                "setter_callsite": "0x06656594",
                "setter": "0x064073da",
                "setter_arguments": [
                    "webdav_shared_management",
                    None,
                    "webdav_shared_enable",
                    "1",
                ],
                "pre_get": 0,
                "post_get": 0,
                "later_get_structure": "zero_get_callbacks_then_generic_get_core",
                "nonempty_later_wire_value_proved": False,
            },
            "current_get_pre_setter": {
                "model": "log_management",
                "pre_get": "0x066ad529",
                "setter_callsite": "0x066ad58c",
                "setter": "0x064073da",
                "field": "sd_support_format",
                "value_source": "stack_percent_d",
            },
            "diagnostic_stock_row": {
                "row_runtime": "0x069003e8",
                "callbacks": diagnostic_callbacks,
            },
        },
        "proved_conclusion": {
            "get_dispatches_post_set": False,
            "setter_dispatches_post_set": False,
            "r35_post_set_reachable_from_failed_get": False,
            "setter_stack_or_static_input_valid_for_call": True,
            "getter_result_must_be_freed_by_caller": True,
            "callback_return_can_fail_cgi": False,
            "phase3_post_set_calls_same_model_setter_with_zero_get_callbacks": True,
        },
        "not_proved": [
            "diagnostic.output retains an arbitrary nonempty value across requests",
            "diagnostic.output published in post_set remains retrievable until the following GET",
            "custom low-page state store is safe and correctly ordered",
            "empty stock diagnostic.output means TTL Off",
            "TTL persistence across reboot",
        ],
        "live_actions": {
            "router_http": 0,
            "usb_transfers": 0,
            "network_mutations": 0,
            "firmware_posts": 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect the exact stock MF885 callback/property ABI"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--oslo", type=Path)
    source.add_argument("--golden-capture", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.oslo is not None:
            oslo = args.oslo.read_bytes()
        else:
            oslo = decompress_golden_oslo(args.golden_capture.read_bytes())
        report = inspect_exact_oslo(oslo)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "GREEN" else 2
    except (OSError, lzma.LZMAError, CallbackAbiError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "schema": "mf885-ttl-callback-abi-inspection/v1",
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
