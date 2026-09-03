#!/usr/bin/env python3
"""Build the exact-golden Community R3.5 same-model TTL image."""

from __future__ import annotations

import argparse
import json
import lzma
import os
import struct
import sys
from pathlib import Path
from typing import Any

import mf885_community_r30_native_builder as shared
import mf885_community_r33_native_builder as r33_builder
import mf885_community_r35 as community_r35
import mf885_firmware_inspect as inspector
import mf885_ttl_native_payload_r35 as ttl
import mf885_webi_builder as webi
import mf885_webui_stage_builder as stage


PROFILE = community_r35.PROFILE
ARTIFACT = "MF885_Community_0.3.5-community-r2-native-r9-cafe-r2.bin"
SCHEMA = "mf885-community-r35-same-model-ttl-build/v1"


class CommunityR35NativeError(RuntimeError):
    pass


def _condition(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {"name": name, "expected": expected, "actual": actual, "passed": expected == actual}


def _require(conditions: list[dict[str, Any]], context: str) -> None:
    failed = [item["name"] for item in conditions if not item["passed"]]
    if failed:
        raise CommunityR35NativeError(f"{context} failed: " + ", ".join(failed))


def build_candidate(
    golden_raw: bytes,
    identity: inspector.IdentityMaterial,
) -> tuple[bytes, dict[str, Any]]:
    golden_header, golden_parts = shared._partition_map(golden_raw, identity)
    try:
        oslo_index, oslo = next(
            (index, part) for index, part in enumerate(golden_parts) if part.name == "OSLO"
        )
    except StopIteration as exc:
        raise CommunityR35NativeError("golden has no OSLO partition") from exc
    if oslo.length != shared.OSLO_PARTITION_BYTES:
        raise CommunityR35NativeError("golden OSLO partition length changed")

    source_oslo, source_lzma = shared.decompress_oslo_partition(
        golden_raw[oslo.offset:oslo.offset + oslo.length], require_exact_source=True
    )
    patched_oslo, native_report = ttl.build_payload(source_oslo, "full")
    allowed_report = shared._allowed_native_changes(
        source_oslo, patched_oslo, native_report["changed_ranges"]
    )
    rebuilt_oslo, lzma_report = shared.compress_oslo(patched_oslo)

    web_candidate, web_report = stage.build_stage_image(golden_raw, identity, PROFILE)
    header, partitions = shared._partition_map(web_candidate, identity)
    if shared._layout(partitions) != shared._layout(golden_parts):
        raise CommunityR35NativeError("R3.5 WEBI stage changed partition layout")
    candidate = bytearray(web_candidate)
    candidate[oslo.offset:oslo.offset + oslo.length] = rebuilt_oslo
    descriptor = inspector.DESCRIPTOR_OFFSET + oslo_index * inspector.DESCRIPTOR_SIZE
    oslo_sum = inspector.byte_sum(rebuilt_oslo)
    struct.pack_into("<I", header, descriptor + 0x10, oslo_sum)
    plaintext = bytes(header) + bytes(candidate[inspector.HEADER_SIZE:])
    global_sum = inspector.byte_sum(plaintext[0x20:])
    struct.pack_into("<I", header, 0x1C, global_sum)
    encrypted = webi.encrypt_header(bytes(header), identity.key)
    candidate[:inspector.HEADER_SIZE] = (
        encrypted + bytes(header[inspector.ENCRYPTED_HEADER_SIZE:inspector.HEADER_SIZE])
    )
    result = bytes(candidate)
    if len(result) != webi.EXPECTED_SIZE:
        raise CommunityR35NativeError("final image size changed")
    engineering_web = r33_builder._engineering_web_preservation(
        golden_raw, golden_parts, result, partitions
    )
    return result, {
        "schema": SCHEMA,
        "source_oslo_lzma": source_lzma,
        "native": native_report,
        "native_allowed_ranges": allowed_report,
        "rebuilt_oslo_lzma": lzma_report,
        "webui": web_report,
        "engineering_web": engineering_web,
        "checksums": {
            "oslo_byte_sum": inspector.hex32(oslo_sum),
            "global_byte_sum": inspector.hex32(global_sum),
        },
    }


def verify_candidate(
    golden_raw: bytes,
    candidate: bytes,
    identity: inspector.IdentityMaterial,
) -> dict[str, Any]:
    golden_header, golden_parts = shared._partition_map(golden_raw, identity)
    candidate_header, candidate_parts = shared._partition_map(candidate, identity)
    web_candidate, _report = stage.build_stage_image(golden_raw, identity, PROFILE)
    web_header, web_parts = shared._partition_map(web_candidate, identity)
    conditions = [
        _condition("candidate_bytes", len(golden_raw), len(candidate)),
        _condition("partition_layout", shared._layout(golden_parts), shared._layout(candidate_parts)),
        _condition("web_stage_partition_layout", shared._layout(golden_parts), shared._layout(web_parts)),
    ]
    engineering_web = r33_builder._engineering_web_preservation(
        golden_raw, golden_parts, candidate, candidate_parts
    )
    conditions.extend(engineering_web["conditions"])

    oslo_index = next(index for index, part in enumerate(golden_parts) if part.name == "OSLO")
    oslo = golden_parts[oslo_index]
    source_oslo, _source_report = shared.decompress_oslo_partition(
        golden_raw[oslo.offset:oslo.offset + oslo.length], require_exact_source=True
    )
    expected_oslo, native_report = ttl.build_payload(source_oslo, "full")
    actual_oslo, lzma_report = shared.decompress_oslo_partition(
        candidate[oslo.offset:oslo.offset + oslo.length], require_exact_source=False
    )
    conditions.extend(
        (
            _condition("decompressed_oslo_bytes", len(expected_oslo), len(actual_oslo)),
            _condition("decompressed_oslo_sha256", inspector.sha256(expected_oslo), inspector.sha256(actual_oslo)),
            _condition("decompressed_oslo_exact", True, actual_oslo == expected_oslo),
            _condition("native_hook_installed", True, native_report["hook"]["installed"]),
            _condition("native_boot_state", 0, native_report["state"]["boot_value"]),
            _condition("native_state_runtime", "0x06001430", native_report["state"]["address"]),
            _condition("native_publisher_slot", "post_get", native_report["transport"]["publisher_slot"]),
            _condition("native_publisher_setter_calls", 1, native_report["transport"]["publisher_setter_calls"]),
            _condition("native_read_model", "diagnostic", native_report["transport"]["read_model"]),
            _condition("native_read_field", "output", native_report["transport"]["read_field"]),
            _condition("native_same_model_publication", True, native_report["transport"]["same_model_publication"]),
            _condition("native_system_channel_bridge_unused", False, native_report["transport"]["system_channel_bridge_used"]),
            _condition("native_set_response_setter_calls", 0, native_report["transport"]["set_response_setter_calls"]),
            _condition("native_debugon_unchanged", False, native_report["engineering"]["debugon_row_changed"]),
            _condition("native_debugon_callback_unchanged", False, native_report["engineering"]["debugon_callback_changed"]),
            _condition("native_wan_engineering_unchanged", False, native_report["engineering"]["wan_engineering_mode_changed"]),
            _condition("native_system_channel_unchanged", False, native_report["engineering"]["system_channel_row_changed"]),
            _condition("native_system_channel_callback_unchanged", False, native_report["engineering"]["system_channel_callback_changed"]),
            _condition("web_debugmodeon_template_unchanged", True, engineering_web["records"]["www\\xmldata\\debugmodeon.xml"]["byte_exact"]),
            _condition("web_wan_template_unchanged", True, engineering_web["records"]["www\\xmldata\\wan.xml"]["byte_exact"]),
            _condition("native_numeric_buffer", "four-byte stack-local", native_report["readback"]["numeric_buffer"]),
            _condition("native_shared_scratch", False, native_report["readback"]["shared_writable_scratch"]),
            _condition("native_persistent", False, native_report["state"]["persistent"]),
            _condition("live_get_unqualified", False, native_report["qualification"]["live_get"]),
            _condition("live_set_unqualified", False, native_report["qualification"]["live_set"]),
            _condition("live_packet_path_unqualified", False, native_report["qualification"]["live_packet_path"]),
        )
    )
    shared._allowed_native_changes(source_oslo, actual_oslo, native_report["changed_ranges"])

    for part in golden_parts:
        if part.name == "OSLO":
            continue
        start, end = part.offset, part.offset + part.length
        expected = web_candidate[start:end] if part.name == "WEBI" else golden_raw[start:end]
        conditions.append(
            _condition(f"partition:{part.name}:sha256", inspector.sha256(expected), inspector.sha256(candidate[start:end]))
        )

    allowed_header = set(range(0x1C, 0x20))
    descriptor = inspector.DESCRIPTOR_OFFSET + oslo_index * inspector.DESCRIPTOR_SIZE
    allowed_header.update(range(descriptor + 0x10, descriptor + 0x14))
    unexpected_header = [
        index
        for index, (before, after) in enumerate(zip(web_header, candidate_header))
        if before != after and index not in allowed_header
    ]
    plaintext = bytes(candidate_header) + candidate[inspector.HEADER_SIZE:]
    conditions.extend(
        (
            _condition("header_unexpected_changed_bytes", 0, len(unexpected_header)),
            _condition("oslo_descriptor_sum", inspector.byte_sum(candidate[oslo.offset:oslo.offset + oslo.length]), candidate_parts[oslo_index].checksum),
            _condition("global_byte_sum", inspector.byte_sum(plaintext[0x20:]), inspector.u32(candidate_header, 0x1C)),
        )
    )
    _require(conditions, "final R3.5 candidate verification")
    return {
        "schema": "mf885-community-r35-same-model-ttl-verification/v1",
        "status": "GREEN",
        "conditions": conditions,
        "engineering_web": engineering_web,
        "oslo": lzma_report,
        "artifact": {"bytes": len(candidate), "sha256": inspector.sha256(candidate)},
    }


def delivery_report(
    *,
    source_name: str,
    artifact_name: str,
    golden_raw: bytes,
    artifact: bytes,
    build: dict[str, Any],
    verification: dict[str, Any],
    independent_container_status: str,
) -> dict[str, Any]:
    """Return the complete deterministic report pinned by direct delivery."""

    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "source": {"file": source_name, "bytes": len(golden_raw), "sha256": inspector.sha256(golden_raw)},
        "artifact": {"file": artifact_name, "bytes": len(artifact), "sha256": inspector.sha256(artifact)},
        "build": build,
        "verification": {
            **verification,
            "double_build_equal": True,
            "independent_container_status": independent_container_status,
            "changed_partitions": ["OSLO", "WEBI"],
            "other_partitions_byte_identical": True,
        },
        "qualification": {
            "flash_qualified": False,
            "live_ttl_get_qualified": False,
            "live_ttl_set_qualified": False,
            "packet_path_qualified": False,
            "cold_boot_proven": False,
            "repeatability_proven": False,
            "rollback_proven": False,
            "reason": "offline deterministic candidate only; first post-flash action must be one read-only diagnostic.output discriminator before any TTL write",
        },
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Build exact-golden MF885 Community R3.5 same-model TTL image")
    value.add_argument("--golden", type=Path, required=True)
    value.add_argument("--identity-xml", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--report", type=Path, required=True)
    value.add_argument("--confirm-native-ttl-risk", action="store_true")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    verification_path = args.output.with_name(args.output.name + ".verify.tmp")
    try:
        if not args.confirm_native_ttl_risk:
            raise CommunityR35NativeError("--confirm-native-ttl-risk is required")
        if not args.output.parent.is_dir() or not args.report.parent.is_dir():
            raise CommunityR35NativeError("output and report directories must already exist")
        if args.output.exists() or args.report.exists() or verification_path.exists():
            raise CommunityR35NativeError("output, report or verification temporary already exists")
        identity = inspector.load_identity(args.identity_xml)
        golden_raw = webi.require_reviewed_golden(args.golden, identity)
        first, first_report = build_candidate(golden_raw, identity)
        second, second_report = build_candidate(golden_raw, identity)
        if first != second or first_report != second_report:
            raise CommunityR35NativeError("double build is not deterministic")
        verification = verify_candidate(golden_raw, first, identity)
        with verification_path.open("xb") as stream:
            stream.write(first)
            stream.flush()
            os.fsync(stream.fileno())
        independent = inspector.inspect_image(verification_path, identity, include_records=True)
        if independent.report["verification"]["status"] != "verified":
            raise CommunityR35NativeError("independent ZIMI/CAFE/LZMA inspection failed")
        report = delivery_report(
            source_name=args.golden.name,
            artifact_name=args.output.name,
            golden_raw=golden_raw,
            artifact=first,
            build=first_report,
            verification=verification,
            independent_container_status=independent.report["verification"]["status"],
        )
        report_bytes = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
        verification_path.unlink()
        shared.write_exclusive(args.report, report_bytes)
        shared.write_exclusive(args.output, first)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (
        CommunityR35NativeError,
        shared.CommunityR30NativeError,
        r33_builder.CommunityR33NativeError,
        ttl.TtlR35PayloadError,
        inspector.InspectionError,
        webi.BuildError,
        stage.StageBuildError,
        OSError,
        lzma.LZMAError,
        TypeError,
        ValueError,
    ) as exc:
        try:
            verification_path.unlink(missing_ok=True)
        except OSError:
            pass
        print(f"R3.5 native build failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
