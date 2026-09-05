#!/usr/bin/env python3
"""Shared exact-golden container path for native comparators.

Release modules supply only their profile, native payload builder and explicit
verification conditions.  This module owns the repeated ZIMI/OSLO/WEBI
container work so later native increments do not copy that mechanism.
"""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path
from typing import Any, Callable

import mf885_community_r30_native_builder as shared
import mf885_community_r33_native_builder as r33_builder
import mf885_firmware_inspect as inspector
import mf885_webi_builder as webi
import mf885_webui_stage_builder as stage


Condition = dict[str, Any]
NativeBuild = Callable[[bytes], tuple[bytes, dict[str, Any]]]
NativeConditions = Callable[[dict[str, Any], dict[str, Any]], list[Condition]]
ErrorType = type[RuntimeError]


def condition(name: str, expected: Any, actual: Any) -> Condition:
    return {
        "name": name,
        "expected": expected,
        "actual": actual,
        "passed": expected == actual,
    }


def require(conditions: list[Condition], context: str, error: ErrorType) -> None:
    failed = [item["name"] for item in conditions if not item["passed"]]
    if failed:
        raise error(f"{context} failed: " + ", ".join(failed))


def build_candidate(
    golden_raw: bytes,
    identity: inspector.IdentityMaterial,
    *,
    profile: str,
    schema: str,
    label: str,
    native_build: NativeBuild,
    error: ErrorType,
) -> tuple[bytes, dict[str, Any]]:
    _golden_header, golden_parts = shared._partition_map(golden_raw, identity)
    try:
        oslo_index, oslo = next(
            (index, part)
            for index, part in enumerate(golden_parts)
            if part.name == "OSLO"
        )
    except StopIteration as exc:
        raise error("golden has no OSLO partition") from exc
    if oslo.length != shared.OSLO_PARTITION_BYTES:
        raise error("golden OSLO partition length changed")

    source_oslo, source_lzma = shared.decompress_oslo_partition(
        golden_raw[oslo.offset : oslo.offset + oslo.length],
        require_exact_source=True,
    )
    patched_oslo, native_report = native_build(source_oslo)
    allowed_report = shared._allowed_native_changes(
        source_oslo, patched_oslo, native_report["changed_ranges"]
    )
    rebuilt_oslo, lzma_report = shared.compress_oslo(patched_oslo)

    web_candidate, web_report = stage.build_stage_image(golden_raw, identity, profile)
    header, partitions = shared._partition_map(web_candidate, identity)
    if shared._layout(partitions) != shared._layout(golden_parts):
        raise error(f"{label} WEBI stage changed partition layout")
    candidate = bytearray(web_candidate)
    candidate[oslo.offset : oslo.offset + oslo.length] = rebuilt_oslo
    descriptor = inspector.DESCRIPTOR_OFFSET + oslo_index * inspector.DESCRIPTOR_SIZE
    oslo_sum = inspector.byte_sum(rebuilt_oslo)
    struct.pack_into("<I", header, descriptor + 0x10, oslo_sum)
    plaintext = bytes(header) + bytes(candidate[inspector.HEADER_SIZE :])
    global_sum = inspector.byte_sum(plaintext[0x20:])
    struct.pack_into("<I", header, 0x1C, global_sum)
    encrypted = webi.encrypt_header(bytes(header), identity.key)
    candidate[: inspector.HEADER_SIZE] = encrypted + bytes(
        header[inspector.ENCRYPTED_HEADER_SIZE : inspector.HEADER_SIZE]
    )
    result = bytes(candidate)
    if len(result) != webi.EXPECTED_SIZE:
        raise error("final image size changed")
    engineering_web = r33_builder._engineering_web_preservation(
        golden_raw, golden_parts, result, partitions
    )
    return result, {
        "schema": schema,
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
    *,
    profile: str,
    verification_schema: str,
    label: str,
    native_build: NativeBuild,
    native_conditions: NativeConditions,
    error: ErrorType,
) -> dict[str, Any]:
    _golden_header, golden_parts = shared._partition_map(golden_raw, identity)
    candidate_header, candidate_parts = shared._partition_map(candidate, identity)
    web_candidate, _web_report = stage.build_stage_image(golden_raw, identity, profile)
    web_header, web_parts = shared._partition_map(web_candidate, identity)
    conditions = [
        condition("candidate_bytes", len(golden_raw), len(candidate)),
        condition("partition_layout", shared._layout(golden_parts), shared._layout(candidate_parts)),
        condition("web_stage_partition_layout", shared._layout(golden_parts), shared._layout(web_parts)),
    ]
    engineering_web = r33_builder._engineering_web_preservation(
        golden_raw, golden_parts, candidate, candidate_parts
    )
    conditions.extend(engineering_web["conditions"])

    oslo_index = next(
        index for index, part in enumerate(golden_parts) if part.name == "OSLO"
    )
    oslo = golden_parts[oslo_index]
    source_oslo, _source_report = shared.decompress_oslo_partition(
        golden_raw[oslo.offset : oslo.offset + oslo.length],
        require_exact_source=True,
    )
    expected_oslo, native_report = native_build(source_oslo)
    actual_oslo, lzma_report = shared.decompress_oslo_partition(
        candidate[oslo.offset : oslo.offset + oslo.length],
        require_exact_source=False,
    )
    conditions.extend(
        (
            condition("decompressed_oslo_bytes", len(expected_oslo), len(actual_oslo)),
            condition("decompressed_oslo_sha256", inspector.sha256(expected_oslo), inspector.sha256(actual_oslo)),
            condition("decompressed_oslo_exact", True, actual_oslo == expected_oslo),
        )
    )
    conditions.extend(
        native_conditions(native_report, stage.STAGE_PROFILES[profile]["safety"])
    )
    conditions.extend(
        (
            condition(
                "web_debugmodeon_template_unchanged",
                True,
                engineering_web["records"]["www\\xmldata\\debugmodeon.xml"]["byte_exact"],
            ),
            condition(
                "web_wan_template_unchanged",
                True,
                engineering_web["records"]["www\\xmldata\\wan.xml"]["byte_exact"],
            ),
        )
    )
    shared._allowed_native_changes(
        source_oslo, actual_oslo, native_report["changed_ranges"]
    )

    for part in golden_parts:
        if part.name == "OSLO":
            continue
        start, end = part.offset, part.offset + part.length
        expected = web_candidate[start:end] if part.name == "WEBI" else golden_raw[start:end]
        conditions.append(
            condition(
                f"partition:{part.name}:sha256",
                inspector.sha256(expected),
                inspector.sha256(candidate[start:end]),
            )
        )

    allowed_header = set(range(0x1C, 0x20))
    descriptor = inspector.DESCRIPTOR_OFFSET + oslo_index * inspector.DESCRIPTOR_SIZE
    allowed_header.update(range(descriptor + 0x10, descriptor + 0x14))
    unexpected_header = [
        index
        for index, (before, after) in enumerate(zip(web_header, candidate_header))
        if before != after and index not in allowed_header
    ]
    plaintext = bytes(candidate_header) + candidate[inspector.HEADER_SIZE :]
    conditions.extend(
        (
            condition("header_unexpected_changed_bytes", 0, len(unexpected_header)),
            condition(
                "oslo_descriptor_sum",
                inspector.byte_sum(candidate[oslo.offset : oslo.offset + oslo.length]),
                candidate_parts[oslo_index].checksum,
            ),
            condition(
                "global_byte_sum",
                inspector.byte_sum(plaintext[0x20:]),
                inspector.u32(candidate_header, 0x1C),
            ),
        )
    )
    require(conditions, f"final {label} candidate verification", error)
    return {
        "schema": verification_schema,
        "status": "GREEN",
        "conditions": conditions,
        "engineering_web": engineering_web,
        "oslo": lzma_report,
        "artifact": {"bytes": len(candidate), "sha256": inspector.sha256(candidate)},
    }


def delivery_report(
    *,
    schema: str,
    profile: str,
    source_name: str,
    artifact_name: str,
    golden_raw: bytes,
    artifact: bytes,
    build: dict[str, Any],
    verification: dict[str, Any],
    qualification: dict[str, Any],
    independent_container_status: str,
) -> dict[str, Any]:
    return {
        "schema": schema,
        "profile": profile,
        "source": {
            "file": source_name,
            "bytes": len(golden_raw),
            "sha256": inspector.sha256(golden_raw),
        },
        "artifact": {
            "file": artifact_name,
            "bytes": len(artifact),
            "sha256": inspector.sha256(artifact),
        },
        "build": build,
        "verification": {
            **verification,
            "double_build_equal": True,
            "independent_container_status": independent_container_status,
            "changed_partitions": ["OSLO", "WEBI"],
            "other_partitions_byte_identical": True,
        },
        "qualification": qualification,
    }


def publish_candidate(
    *,
    golden_path: Path,
    identity_path: Path,
    output_path: Path,
    report_path: Path,
    artifact_name: str,
    schema: str,
    verification_schema: str,
    profile: str,
    label: str,
    confirmation: bool,
    confirmation_flag: str,
    native_build: NativeBuild,
    native_conditions: NativeConditions,
    qualification: dict[str, Any],
    error: ErrorType,
) -> dict[str, Any]:
    verification_path = output_path.with_name(output_path.name + ".verify.tmp")
    if not confirmation:
        raise error(f"{confirmation_flag} is required")
    if not output_path.parent.is_dir() or not report_path.parent.is_dir():
        raise error("output and report directories must already exist")
    if output_path.exists() or report_path.exists() or verification_path.exists():
        raise error("output, report or verification temporary already exists")

    try:
        identity = inspector.load_identity(identity_path)
        golden_raw = webi.require_reviewed_golden(golden_path, identity)
        first, first_report = build_candidate(
            golden_raw,
            identity,
            profile=profile,
            schema=schema,
            label=label,
            native_build=native_build,
            error=error,
        )
        second, second_report = build_candidate(
            golden_raw,
            identity,
            profile=profile,
            schema=schema,
            label=label,
            native_build=native_build,
            error=error,
        )
        if first != second or first_report != second_report:
            raise error("double build is not deterministic")
        verification = verify_candidate(
            golden_raw,
            first,
            identity,
            profile=profile,
            verification_schema=verification_schema,
            label=label,
            native_build=native_build,
            native_conditions=native_conditions,
            error=error,
        )
        with verification_path.open("xb") as stream:
            stream.write(first)
            stream.flush()
            os.fsync(stream.fileno())
        independent = inspector.inspect_image(
            verification_path, identity, include_records=True
        )
        if independent.report["verification"]["status"] != "verified":
            raise error("independent ZIMI/CAFE/LZMA inspection failed")
        report = delivery_report(
            schema=schema,
            profile=profile,
            source_name=golden_path.name,
            artifact_name=artifact_name,
            golden_raw=golden_raw,
            artifact=first,
            build=first_report,
            verification=verification,
            qualification=qualification,
            independent_container_status=independent.report["verification"]["status"],
        )
        report_bytes = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
        verification_path.unlink()
        shared.write_exclusive(report_path, report_bytes)
        shared.write_exclusive(output_path, first)
        return report
    finally:
        try:
            verification_path.unlink(missing_ok=True)
        except OSError:
            pass
