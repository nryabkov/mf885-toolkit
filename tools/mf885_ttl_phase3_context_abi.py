#!/usr/bin/env python3
"""Prove the stock request-tree ABI available to a phase-3 MF885 callback.

The exact stock ``pin_puk.post_set`` callback does not obtain its POST inputs
through the generic property store.  It validates the CGI context, takes the
request tree from ``context + 12`` and resolves named fields plus their single
text child directly.  This report pins that narrower precedent byte-for-byte;
it performs no live I/O and does not claim that any custom state address is
writable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import mf885_firmware_inspect as firmware
import mf885_thumb_disasm as thumb
import mf885_ttl_callback_abi as broad


OSLO_RUNTIME_BASE = broad.OSLO_RUNTIME_BASE

PIN_PUK_ROW_OFFSET = 0x009005E0
PIN_PUK_ROW_BYTES = broad.DUSTER_ROW_BYTES
PIN_PUK_ROW_SHA256 = "f6493f6cb77649ccb5b0977ee67858c62c0acf3120a78940f1b11849ab3ac854"
PIN_PUK_MODEL_RUNTIME = 0x068DE5CB
PIN_PUK_POST_SET_RUNTIME = 0x066C8746

PIN_PUK_POST_SET_OFFSET = 0x006C8746
PIN_PUK_POST_SET_BYTES = 0x8A
PIN_PUK_POST_SET_SHA256 = "9a36cb75c9c112992390a2f77fa95ead86cc989adf9bb3cbfbfda154316b9127"
PIN_PUK_HELPER_OFFSET = 0x006C859E
PIN_PUK_HELPER_BYTES = 0x1A8
PIN_PUK_HELPER_SHA256 = "a7c2a0003ba09ba635de403a01fe0b9ade05aadd8925825761840d613e548cc9"

CGI_CONTEXT_INIT_OFFSET = 0x0072C3F2
CGI_CONTEXT_INIT_BYTES = 0x12
CGI_CONTEXT_INIT_SHA256 = "db74422c5639da85501a8c7f1853a9985c6d2e6b5d8461a26962a4753a36b044"
CGI_TREE_STORE_OFFSET = 0x0072C488
CGI_TREE_STORE_BYTES = 4
CGI_TREE_STORE_SHA256 = "5785b4671890649f7e0260edd6a81b0a4ba2b21f4e99046333dbc0c375250d4f"
CGI_POST_DISPATCH_OFFSET = 0x0072C566
CGI_POST_DISPATCH_BYTES = 10
CGI_POST_DISPATCH_SHA256 = "8ad95004325787a1b99efedde2aac86b807c5205a62555220ba6d32357927223"
CGI_POST_DISPATCH_CALLSITE = 0x0072C56C
CGI_POST_DISPATCH_TARGET = 0x066F8EAE

POST_SET_CONTEXT_SLICE_OFFSET = 0x006C8772
POST_SET_CONTEXT_SLICE_BYTES = 0x24
POST_SET_CONTEXT_SLICE_SHA256 = "c469e2f965ed025700b54b5681b15eb6f69d565125a3e630a9593accb5501096"
PIN_PUK_HELPER_CALLSITE = 0x006C8792

COMMAND_LOOKUP_OFFSET = 0x006C85D0
COMMAND_LOOKUP_BYTES = 0x16
COMMAND_LOOKUP_SHA256 = "6e6eab3872a0a9fedad957d4cfe9e378c0d6b2b85485246f22f18a6fc02d3fb3"
PIN_LOOKUP_OFFSET = 0x006C861C
PIN_LOOKUP_BYTES = 0x1A
PIN_LOOKUP_SHA256 = "781763e4600799998bad4cce3454236cdc521c5cf2235a8ac413a55489beda97"
COMMAND_STRING_RUNTIME = 0x066C88BC
PIN_STRING_RUNTIME = 0x066C88A8

FIELD_LOOKUP_OFFSET = 0x004349EE
FIELD_LOOKUP_RUNTIME = 0x064349EE
FIELD_LOOKUP_BYTES = 0x8C
FIELD_LOOKUP_SHA256 = "d7ad9d3364d1cd78db465ea58b6b3e93efc28d83b8dcee051662e5a619f579cd"
TEXT_CHILD_OFFSET = 0x00434E9E
TEXT_CHILD_RUNTIME = 0x06434E9E
TEXT_CHILD_BYTES = 0x30
TEXT_CHILD_SHA256 = "80a918cae98d80160d61a70e721d30cf619d72da7ebd6b8bd1e259906ed83287"

GENERIC_GETTER = 0x06407492
GENERIC_FREE = 0x0644F00E


class Phase3ContextAbiError(RuntimeError):
    pass


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _u32le(value: bytes, offset: int) -> int:
    return struct.unpack_from("<I", value, offset)[0]


def _condition(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {
        "name": name,
        "expected": expected,
        "actual": actual,
        "passed": expected == actual,
    }


def _instructions(oslo: bytes, offset: int, length: int) -> list[str]:
    return [
        item["instruction"]
        for item in thumb.disassemble(
            oslo[offset : offset + length], OSLO_RUNTIME_BASE + offset
        )
    ]


def _direct_targets(oslo: bytes, offset: int, length: int) -> list[int]:
    targets: list[int] = []
    for item in thumb.disassemble(
        oslo[offset : offset + length], OSLO_RUNTIME_BASE + offset
    ):
        if item["size"] != 4 or not item["instruction"].startswith(("bl\t", "blx\t")):
            continue
        target = firmware._thumb_bl_target(oslo, item["address"] - OSLO_RUNTIME_BASE)
        if target is not None:
            targets.append(target)
    return targets


def inspect_exact_oslo(oslo: bytes) -> dict[str, Any]:
    parent = broad.inspect_exact_oslo(oslo)
    row = oslo[PIN_PUK_ROW_OFFSET : PIN_PUK_ROW_OFFSET + PIN_PUK_ROW_BYTES]
    post_set = oslo[
        PIN_PUK_POST_SET_OFFSET : PIN_PUK_POST_SET_OFFSET + PIN_PUK_POST_SET_BYTES
    ]
    helper = oslo[PIN_PUK_HELPER_OFFSET : PIN_PUK_HELPER_OFFSET + PIN_PUK_HELPER_BYTES]
    context_init = oslo[
        CGI_CONTEXT_INIT_OFFSET : CGI_CONTEXT_INIT_OFFSET + CGI_CONTEXT_INIT_BYTES
    ]
    tree_store = oslo[
        CGI_TREE_STORE_OFFSET : CGI_TREE_STORE_OFFSET + CGI_TREE_STORE_BYTES
    ]
    post_dispatch = oslo[
        CGI_POST_DISPATCH_OFFSET : CGI_POST_DISPATCH_OFFSET + CGI_POST_DISPATCH_BYTES
    ]
    context_slice = oslo[
        POST_SET_CONTEXT_SLICE_OFFSET : POST_SET_CONTEXT_SLICE_OFFSET
        + POST_SET_CONTEXT_SLICE_BYTES
    ]
    command_lookup = oslo[
        COMMAND_LOOKUP_OFFSET : COMMAND_LOOKUP_OFFSET + COMMAND_LOOKUP_BYTES
    ]
    pin_lookup = oslo[PIN_LOOKUP_OFFSET : PIN_LOOKUP_OFFSET + PIN_LOOKUP_BYTES]
    field_lookup = oslo[FIELD_LOOKUP_OFFSET : FIELD_LOOKUP_OFFSET + FIELD_LOOKUP_BYTES]
    text_child = oslo[TEXT_CHILD_OFFSET : TEXT_CHILD_OFFSET + TEXT_CHILD_BYTES]
    helper_targets = _direct_targets(oslo, PIN_PUK_HELPER_OFFSET, PIN_PUK_HELPER_BYTES)

    conditions = [
        _condition("parent_callback_abi_status", "GREEN", parent["status"]),
        _condition("pin_puk_row_sha256", PIN_PUK_ROW_SHA256, _sha256(row)),
        _condition("pin_puk_row_id", 0x235E, _u32le(row, 0x00)),
        _condition("pin_puk_model_pointer", PIN_PUK_MODEL_RUNTIME, _u32le(row, 0x04)),
        _condition("pin_puk_enabled", 1, _u32le(row, 0x08)),
        _condition("pin_puk_post_set_pointer", PIN_PUK_POST_SET_RUNTIME | 1, _u32le(row, 0x1C)),
        _condition("pin_puk_model_name", "pin_puk", broad._cstring_at_runtime(oslo, PIN_PUK_MODEL_RUNTIME)),
        _condition("pin_puk_post_set_sha256", PIN_PUK_POST_SET_SHA256, _sha256(post_set)),
        _condition("pin_puk_helper_sha256", PIN_PUK_HELPER_SHA256, _sha256(helper)),
        _condition("cgi_context_init_sha256", CGI_CONTEXT_INIT_SHA256, _sha256(context_init)),
        _condition(
            "cgi_context_init_instructions",
            [
                "movs\tr1, #0x0",
                "movs\tr2, r1",
                "movs\tr3, r1",
                "movs\tr7, r1",
                "mov\tr0, sp",
                "stm\tr0!, {r1, r2, r3, r7}",
                "movs\tr0, #0x1",
                "mov\tr3, sp",
                "strh\tr0, [r3]",
            ],
            _instructions(oslo, CGI_CONTEXT_INIT_OFFSET, CGI_CONTEXT_INIT_BYTES),
        ),
        _condition("cgi_tree_store_sha256", CGI_TREE_STORE_SHA256, _sha256(tree_store)),
        _condition(
            "cgi_tree_stored_at_context_plus_12",
            ["ldr\tr0, [pc, #0x2d4]", "str\tr7, [sp, #0xc]"],
            _instructions(oslo, CGI_TREE_STORE_OFFSET, CGI_TREE_STORE_BYTES),
        ),
        _condition("cgi_post_dispatch_sha256", CGI_POST_DISPATCH_SHA256, _sha256(post_dispatch)),
        _condition(
            "cgi_post_dispatch_phase_and_context",
            [
                "ldr\tr0, [sp, #0x18]",
                "movs\tr1, #0x3",
                "mov\tr2, sp",
                "bl\t#-0x336c2",
            ],
            _instructions(oslo, CGI_POST_DISPATCH_OFFSET, CGI_POST_DISPATCH_BYTES),
        ),
        _condition("cgi_post_dispatch_target", CGI_POST_DISPATCH_TARGET, firmware._thumb_bl_target(oslo, CGI_POST_DISPATCH_CALLSITE)),
        _condition("pin_puk_context_slice_sha256", POST_SET_CONTEXT_SLICE_SHA256, _sha256(context_slice)),
        _condition(
            "pin_puk_context_contract",
            [
                "cmp\tr7, #0x0",
                "beq\t#0xa",
                "ldrh\tr0, [r7]",
                "cmp\tr0, #0x1",
                "bne\t#0x4",
                "ldr\tr0, [r7, #0xc]",
                "cmp\tr0, #0x0",
                "bne\t#0x4",
                "movs\tr0, r4",
                "add\tsp, #0x44",
                "pop\t{r4, r5, r6, r7, pc}",
                "ldr\tr1, [sp, #0x3c]",
                "cmp\tr1, #0x1",
                "bne\t#0x2",
                "movs\tr0, #0x0",
                "b\t#-0x10",
                "bl\t#-0x1f8",
            ],
            _instructions(oslo, POST_SET_CONTEXT_SLICE_OFFSET, POST_SET_CONTEXT_SLICE_BYTES),
        ),
        _condition("pin_puk_helper_call_target", PIN_PUK_HELPER_OFFSET + OSLO_RUNTIME_BASE, firmware._thumb_bl_target(oslo, PIN_PUK_HELPER_CALLSITE)),
        _condition("command_lookup_sha256", COMMAND_LOOKUP_SHA256, _sha256(command_lookup)),
        _condition("pin_lookup_sha256", PIN_LOOKUP_SHA256, _sha256(pin_lookup)),
        _condition("command_field_name", "command", broad._cstring_at_runtime(oslo, COMMAND_STRING_RUNTIME)),
        _condition("second_field_precedent_name", "pin", broad._cstring_at_runtime(oslo, PIN_STRING_RUNTIME)),
        _condition("command_field_lookup_target", FIELD_LOOKUP_RUNTIME, firmware._thumb_bl_target(oslo, 0x006C85D4)),
        _condition("command_text_child_target", TEXT_CHILD_RUNTIME, firmware._thumb_bl_target(oslo, 0x006C85DC)),
        _condition("second_field_lookup_target", FIELD_LOOKUP_RUNTIME, firmware._thumb_bl_target(oslo, 0x006C8620)),
        _condition("second_text_child_target", TEXT_CHILD_RUNTIME, firmware._thumb_bl_target(oslo, 0x006C8628)),
        _condition("field_lookup_sha256", FIELD_LOOKUP_SHA256, _sha256(field_lookup)),
        _condition("text_child_sha256", TEXT_CHILD_SHA256, _sha256(text_child)),
        _condition(
            "text_child_exact_instructions",
            [
                "push\t{r4, r5, r6, r7, lr}",
                "movs\tr5, r0",
                "movs\tr2, #0x0",
                "movs\tr1, r2",
                "ldr\tr6, [r5, #0x4]",
                "movs\tr0, r2",
                "b\t#0x1a",
                "movs\tr3, #0xc",
                "muls\tr3, r1, r3",
                "ldr\tr4, [r5, #0x10]",
                "ldrb\tr7, [r4, r3]",
                "cmp\tr7, #0x3",
                "bne\t#0xc",
                "adds\tr3, r3, #0x4",
                "ldr\tr0, [r4, r3]",
                "adds\tr2, r2, #0x1",
                "cmp\tr2, #0x1",
                "ble\t#0x2",
                "movs\tr0, #0x0",
                "pop\t{r4, r5, r6, r7, pc}",
                "adds\tr1, r1, #0x1",
                "cmp\tr6, r1",
                "bgt\t#-0x22",
                "pop\t{r4, r5, r6, r7, pc}",
            ],
            _instructions(oslo, TEXT_CHILD_OFFSET, TEXT_CHILD_BYTES),
        ),
        _condition("stock_parser_generic_getter_calls", 0, helper_targets.count(GENERIC_GETTER)),
        _condition("stock_parser_generic_free_calls", 0, helper_targets.count(GENERIC_FREE)),
        _condition("stock_parser_field_lookup_calls", 8, helper_targets.count(FIELD_LOOKUP_RUNTIME)),
        _condition("stock_parser_text_child_calls", 8, helper_targets.count(TEXT_CHILD_RUNTIME)),
    ]
    passed = all(item["passed"] for item in conditions)
    return {
        "schema": "mf885-ttl-phase3-context-abi/v1",
        "status": "GREEN" if passed else "REJECTED",
        "source": {"bytes": len(oslo), "sha256": _sha256(oslo)},
        "conditions": conditions,
        "stock_precedent": {
            "model": "pin_puk",
            "callback": "post_set",
            "dispatcher_phase": 3,
            "context_argument": "r1_at_callback_entry",
            "context_type": 1,
            "request_tree_offset": 12,
            "field_lookup": f"0x{FIELD_LOOKUP_RUNTIME:08x}",
            "single_text_child": f"0x{TEXT_CHILD_RUNTIME:08x}",
            "text_value": "dereference_returned_pointer_once",
            "value_lifetime": "borrowed_from_request_tree_no_free",
        },
        "candidate_contract": {
            "phase": 3,
            "require_context_non_null": True,
            "require_context_type": 1,
            "require_request_tree_non_null": True,
            "fields": ["command", "arg"],
            "field_lookups": 2,
            "single_text_child_lookups": 2,
            "generic_property_getter_calls": 0,
            "generic_property_free_calls": 0,
            "free_borrowed_values": False,
            "compare_policy": "bounded_byte_exact",
            "reject_policy": "return_zero_without_state_change",
        },
        "proved": [
            "stock phase-3 CGI context carries the parsed request tree at offset 12",
            "stock pin_puk.post_set validates that context before parsing",
            "stock callback code resolves named request fields and requires a single type-3 text child",
            "request-tree values are borrowed and are not passed to the generic property free",
        ],
        "not_proved": [
            "a custom callback using the same helpers is live-safe until exercised",
            "any custom TTL state address is mapped and writable",
            "the R3.9 reset occurred in its generic getter rather than its private state write",
            "TTL packets traverse the custom forwarding hook",
            "TTL state persists across reboot",
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
        description="Inspect exact stock phase-3 request-tree context ABI"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--oslo", type=Path)
    source.add_argument("--golden-capture", type=Path)
    args = parser.parse_args(argv)
    try:
        oslo = (
            args.oslo.read_bytes()
            if args.oslo is not None
            else broad.decompress_golden_oslo(args.golden_capture.read_bytes())
        )
        report = inspect_exact_oslo(oslo)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "GREEN" else 2
    except (OSError, ValueError, Phase3ContextAbiError) as exc:
        print(
            json.dumps(
                {
                    "schema": "mf885-ttl-phase3-context-abi/v1",
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
