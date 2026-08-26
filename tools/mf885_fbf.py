#!/usr/bin/env python3
"""Inspect Marvell FBF images and build an offline-only MF885 WEBI capsule.

The builder is deliberately narrow.  It accepts only the reviewed official
MF96-ROUTER-C2 2.5.89 FBF and the exact observer-only ZIMI image, copies the
official WEBI geometry, and emits a file whose name must contain ``NOFLASH``.
It never contacts a router and never claims that the result is accepted by the
device or safe to install.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mf885_firmware_inspect as zimi


FBF_MAGIC = b"Marvell_FBF\0"
FBF_FORMAT_WORD = 0x2000000B
FBF_BLOCK_SIZE = 0x2000
FBF_RECORD_SIZE = 0x34
FBF_DEVICE_OFFSET = 0x4C
FBF_RECORD_COUNT_OFFSET = FBF_DEVICE_OFFSET + 0xF0
FBF_RECORD_TABLE_OFFSET = FBF_DEVICE_OFFSET + 0xF4
FBF_FLASH_LIMIT = 0x02000000

OFFICIAL_C2_2589_SIZE = 7_634_944
OFFICIAL_C2_2589_SHA256 = (
    "6c94a3404e624b8c4318a991f5531c77e484d463c6917c51942b2d3827290e58"
)
OFFICIAL_C2_2589_VERSION = b"020589ABCD-2"
OFFICIAL_C2_2589_WEBI_SHA256 = (
    "86fda63366438a166c7ef334042af410e55289e7591a0743c47797404c08bb56"
)

CUSTOM_ZIMI_SIZE = 8_323_644
CUSTOM_ZIMI_SHA256 = (
    "a9a284c5e5d2c8d0a18a55b0e324693b5a4a9f099eed814c3d20cd66a9cb642a"
)
CUSTOM_ZIMI_WEBI_OFFSET = 0x52023C
CUSTOM_WEBI_SHA256 = (
    "1f4d86037ce54e95e87fd4aed5370199ca62c6dd34693f9deb827168c4c21cce"
)
WEBI_FLASH_ADDRESS = 0x00AC0000
WEBI_FLASH_BYTES = 0x001C0000
WEBI_CHUNK_BYTES = 0x00020000
CUSTOM_WEBI_SENTINEL = 0x001BF964

TAG_NAMES = {
    b"LNPA": "APNL",
    b"NBFR": "RFBN",
    b"LACW": "WCAL",
    b"IFIW": "WIFI",
    b"IBEW": "WEBI",
    b"IBRG": "GRBI",
    b"OLSO": "OSLO",
    b"IASR": "RSAI",
}


class FbfError(Exception):
    """Raised when an FBF artifact fails a structural or provenance gate."""


@dataclass(frozen=True)
class FbfRecord:
    index: int
    record_offset: int
    raw_tag: bytes
    name: str
    extent_bytes: int
    flags: int
    data_block: int
    stored_bytes: int
    flash_address: int
    expected_xor32: int

    @property
    def data_offset(self) -> int:
        return self.data_block * FBF_BLOCK_SIZE


@dataclass(frozen=True)
class ParsedFbf:
    raw: bytes
    version: bytes
    records: tuple[FbfRecord, ...]
    report: dict[str, Any]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def u32(data: bytes | bytearray, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise FbfError(f"32-bit field outside FBF at 0x{offset:x}")
    return struct.unpack_from("<I", data, offset)[0]


def put_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def xor32(data: bytes) -> int:
    if not data or len(data) % 4:
        raise FbfError("FBF checksum scope must be non-empty and four-byte aligned")
    value = 0
    for offset in range(0, len(data), 4):
        value ^= struct.unpack_from("<I", data, offset)[0]
    return value


def _safe_version(raw: bytes) -> str:
    if len(raw) != 12 or any(value < 0x20 or value > 0x7E for value in raw):
        raise FbfError("FBF version is not the reviewed 12-byte printable field")
    return raw.decode("ascii")


def parse_fbf(raw: bytes, *, include_records: bool = False) -> ParsedFbf:
    """Parse and independently validate the observed FBF v11 structure."""

    if len(raw) < FBF_BLOCK_SIZE:
        raise FbfError("FBF is shorter than one 0x2000-byte block")
    if raw[: len(FBF_MAGIC)] != FBF_MAGIC:
        raise FbfError("FBF magic is not Marvell_FBF")
    version = raw[0x0C:0x18]
    version_text = _safe_version(version)
    errors: list[str] = []

    format_word = u32(raw, 0x20)
    if format_word != FBF_FORMAT_WORD:
        errors.append(f"format word is 0x{format_word:08x}, expected 0x{FBF_FORMAT_WORD:08x}")
    totals = [u32(raw, offset) for offset in (0x24, 0x28, 0x2C)]
    if len(set(totals)) != 1:
        errors.append("three FBF stored-byte totals disagree")
    if u32(raw, 0x34) != 1:
        errors.append("FBF does not contain exactly one device")
    if u32(raw, 0x3C) != FBF_DEVICE_OFFSET:
        errors.append("FBF device block is not at the reviewed 0x4c offset")

    count = u32(raw, FBF_RECORD_COUNT_OFFSET)
    if count < 1 or count > 1024:
        raise FbfError(f"invalid FBF image count: {count}")
    table_end = FBF_RECORD_TABLE_OFFSET + count * FBF_RECORD_SIZE
    if table_end > len(raw):
        raise FbfError("FBF image table is truncated")
    expected_last_record = FBF_RECORD_TABLE_OFFSET + (count - 1) * FBF_RECORD_SIZE
    if u32(raw, 0x40) != expected_last_record:
        errors.append("FBF last-record offset does not match image count")

    records: list[FbfRecord] = []
    file_ranges: list[tuple[int, int, int]] = []
    flash_ranges: list[tuple[int, int, int]] = []
    checksum_failures: list[int] = []
    for index in range(count):
        offset = FBF_RECORD_TABLE_OFFSET + index * FBF_RECORD_SIZE
        raw_tag = raw[offset : offset + 4]
        extent = u32(raw, offset + 0x0C)
        flags = u32(raw, offset + 0x10)
        data_block = u32(raw, offset + 0x14)
        stored = u32(raw, offset + 0x18)
        flash_address = u32(raw, offset + 0x1C)
        expected_checksum = u32(raw, offset + 0x30)
        name = TAG_NAMES.get(raw_tag, raw_tag[::-1].decode("latin1"))
        record = FbfRecord(
            index=index,
            record_offset=offset,
            raw_tag=raw_tag,
            name=name,
            extent_bytes=extent,
            flags=flags,
            data_block=data_block,
            stored_bytes=stored,
            flash_address=flash_address,
            expected_xor32=expected_checksum,
        )
        records.append(record)

        data_start = record.data_offset
        data_end = data_start + stored
        if stored == 0 or data_start < align_up(table_end, FBF_BLOCK_SIZE) or data_end > len(raw):
            errors.append(f"record {index} has an invalid data range")
            continue
        file_ranges.append((data_start, data_end, index))
        payload = raw[data_start:data_end]
        if raw_tag != b"IASR":
            if extent == 0 or stored > extent:
                errors.append(f"record {index} stored length exceeds its flash extent")
            if flash_address + extent > FBF_FLASH_LIMIT:
                errors.append(f"record {index} exceeds the reviewed 32 MiB address space")
            else:
                flash_ranges.append((flash_address, flash_address + extent, index))
            try:
                computed = xor32(payload)
            except FbfError:
                computed = None
            if computed != expected_checksum:
                checksum_failures.append(index)
        elif extent != 0 or flash_address != 0:
            errors.append(f"RSAI record {index} unexpectedly has a flash extent")

    for ranges, label in ((file_ranges, "data"), (flash_ranges, "flash")):
        ordered = sorted(ranges)
        for left, right in zip(ordered, ordered[1:]):
            if left[1] > right[0]:
                errors.append(
                    f"FBF {label} ranges overlap between records {left[2]} and {right[2]}"
                )

    flash_gaps: list[dict[str, Any]] = []
    flash_cursor = 0
    for start, end, _index in sorted(flash_ranges):
        if start > flash_cursor:
            flash_gaps.append(
                {
                    "start": f"0x{flash_cursor:08x}",
                    "end": f"0x{start:08x}",
                    "bytes": start - flash_cursor,
                }
            )
        flash_cursor = max(flash_cursor, end)
    if flash_cursor < FBF_FLASH_LIMIT:
        flash_gaps.append(
            {
                "start": f"0x{flash_cursor:08x}",
                "end": f"0x{FBF_FLASH_LIMIT:08x}",
                "bytes": FBF_FLASH_LIMIT - flash_cursor,
            }
        )
    if checksum_failures:
        errors.append(
            "FBF XOR32 checksum mismatch in records "
            + ", ".join(str(value) for value in checksum_failures)
        )

    non_rsa_total = sum(record.stored_bytes for record in records if record.raw_tag != b"IASR")
    if any(total != non_rsa_total for total in totals):
        errors.append("FBF master stored-byte total does not match non-RSA records")

    max_data_end = max(end for _start, end, _index in file_ranges) if file_ranges else 0
    tail = raw[max_data_end:]
    record_summaries = [
        {
            "index": record.index,
            "name": record.name,
            "raw_tag": record.raw_tag.decode("latin1"),
            "record_offset": f"0x{record.record_offset:x}",
            "data_offset": f"0x{record.data_offset:x}",
            "stored_bytes": record.stored_bytes,
            "extent_bytes": record.extent_bytes,
            "flash_address": f"0x{record.flash_address:08x}",
            "flags": f"0x{record.flags:08x}",
            "expected_xor32": f"0x{record.expected_xor32:08x}",
        }
        for record in records
    ]
    report: dict[str, Any] = {
        "schema": "mf885-fbf-inspection/v1",
        "artifact": {"bytes": len(raw), "sha256": sha256(raw)},
        "header": {
            "magic": "Marvell_FBF",
            "version": version_text,
            "format_word": f"0x{format_word:08x}",
            "device_count": u32(raw, 0x34),
            "image_count": count,
            "non_rsa_stored_bytes": non_rsa_total,
            "master_totals": totals,
        },
        "images_by_type": {
            name: sum(1 for record in records if record.name == name)
            for name in sorted({record.name for record in records})
        },
        "rsa": {
            "record_present": any(record.raw_tag == b"IASR" for record in records),
            "signature_verified": False,
        },
        "layout": {
            "table_offset": f"0x{FBF_RECORD_TABLE_OFFSET:x}",
            "table_end": f"0x{table_end:x}",
            "max_data_end": f"0x{max_data_end:x}",
            "trailing_bytes": len(tail),
            "trailing_all_zero": bool(tail) and all(value == 0 for value in tail),
            "flash_address_space_bytes": FBF_FLASH_LIMIT,
            "uncovered_by_records": flash_gaps,
        },
        "verification": {
            "status": "structurally-verified" if not errors else "invalid",
            "structurally_verified": not errors,
            "errors": errors,
            "flash_qualified": False,
            "offline_only": True,
            "firmware_posts_attempted": 0,
        },
    }
    if include_records:
        report["records"] = record_summaries
    return ParsedFbf(raw=raw, version=version, records=tuple(records), report=report)


def reconstruct_partition(
    parsed: ParsedFbf,
    name: str,
    flash_address: int,
    extent_bytes: int,
) -> bytes:
    """Reconstruct a flash range, filling omitted bytes with erased 0xff."""

    selected = [record for record in parsed.records if record.name == name]
    if not selected:
        raise FbfError(f"FBF has no {name} records")
    extents = sorted(
        (
            (record.flash_address, record.flash_address + record.extent_bytes, record)
            for record in selected
        ),
        key=lambda item: (item[0], item[1], item[2].index),
    )
    cursor = flash_address
    for start, end, _record in extents:
        if start != cursor or end <= start:
            raise FbfError(f"{name} records do not cover one contiguous flash range")
        cursor = end
    if cursor != flash_address + extent_bytes:
        raise FbfError(f"{name} records do not match the reviewed partition extent")
    output = bytearray(b"\xFF" * extent_bytes)
    for _start, _end, record in extents:
        relative = record.flash_address - flash_address
        payload = parsed.raw[record.data_offset : record.data_offset + record.stored_bytes]
        output[relative : relative + len(payload)] = payload
    return bytes(output)


def webi_only_write_plan(parsed: ParsedFbf) -> list[dict[str, Any]]:
    """Validate and expose the exact reviewed WEBI-only native write order.

    The generic FBF parser intentionally accepts unknown image types for
    research.  This narrower profile is fail-closed: it models only the
    deterministic fourteen-record NOFLASH capsule built by this module.
    """

    if not parsed.report["verification"]["structurally_verified"]:
        raise FbfError("FBF is structurally invalid before WEBI profile validation")
    if parsed.version != OFFICIAL_C2_2589_VERSION:
        raise FbfError("WEBI-only profile requires the reviewed donor version field")
    records = list(parsed.records)
    expected_count = WEBI_FLASH_BYTES // WEBI_CHUNK_BYTES
    if len(records) != expected_count:
        raise FbfError("WEBI-only profile requires exactly 14 image records")

    expected_addresses = [
        WEBI_FLASH_ADDRESS + index * WEBI_CHUNK_BYTES
        for index in reversed(range(expected_count))
    ]
    expected_data_offset = FBF_BLOCK_SIZE
    plan: list[dict[str, Any]] = []
    for index, (record, expected_address) in enumerate(zip(records, expected_addresses)):
        chunk_index = expected_count - index - 1
        relative = chunk_index * WEBI_CHUNK_BYTES
        expected_stored = min(
            WEBI_CHUNK_BYTES,
            CUSTOM_WEBI_SENTINEL + 4 - relative,
        )
        if record.raw_tag != b"IBEW":
            raise FbfError(f"record {index} is not the reviewed WEBI tag")
        if record.flash_address != expected_address:
            raise FbfError(f"record {index} is not in the reviewed descending write order")
        if record.extent_bytes != WEBI_CHUNK_BYTES:
            raise FbfError(f"record {index} does not erase exactly one WEBI chunk")
        if record.flags != 3:
            raise FbfError(f"record {index} does not use the reviewed WEBI flags")
        if record.stored_bytes != expected_stored or record.stored_bytes % 4:
            raise FbfError(f"record {index} does not use the reviewed write length")
        if record.data_offset != expected_data_offset:
            raise FbfError(f"record {index} data is not in the reviewed packed order")
        payload = parsed.raw[record.data_offset : record.data_offset + record.stored_bytes]
        if len(payload) != record.stored_bytes or xor32(payload) != record.expected_xor32:
            raise FbfError(f"record {index} payload checksum changed")
        plan.append(
            {
                "record_index": index,
                "tag": "WEBI",
                "flash_address": f"0x{record.flash_address:08x}",
                "erase_bytes": record.extent_bytes,
                "write_bytes": record.stored_bytes,
                "omitted_erased_ff_bytes": record.extent_bytes - record.stored_bytes,
                "payload_sha256": sha256(payload),
                "xor32": f"0x{record.expected_xor32:08x}",
            }
        )
        expected_data_offset = align_up(
            record.data_offset + record.stored_bytes, FBF_BLOCK_SIZE
        )

    if len(parsed.raw) != expected_data_offset:
        raise FbfError("WEBI-only FBF has an unexpected trailing or missing data block")
    if sum(item["erase_bytes"] for item in plan) != WEBI_FLASH_BYTES:
        raise FbfError("WEBI-only erase plan does not cover the exact partition")
    return plan


def verify_official_donor(raw: bytes) -> tuple[ParsedFbf, bytes]:
    if len(raw) != OFFICIAL_C2_2589_SIZE or sha256(raw) != OFFICIAL_C2_2589_SHA256:
        raise FbfError("donor is not the exact official MF96-ROUTER-C2 2.5.89 FBF")
    parsed = parse_fbf(raw, include_records=False)
    if not parsed.report["verification"]["structurally_verified"]:
        raise FbfError("official donor failed independent FBF structure checks")
    if parsed.version != OFFICIAL_C2_2589_VERSION:
        raise FbfError("official donor version field changed")
    webi = reconstruct_partition(parsed, "WEBI", WEBI_FLASH_ADDRESS, WEBI_FLASH_BYTES)
    if sha256(webi) != OFFICIAL_C2_2589_WEBI_SHA256:
        raise FbfError("official donor WEBI does not match the reviewed stock payload")
    cafe, _records = zimi.parse_cafe(webi, include_records=False)
    if (
        not cafe["adler32_valid"]
        or not cafe["record_padding_valid"]
        or not cafe["stored_sizes_aligned_4"]
        or cafe["record_count"] != 320
    ):
        raise FbfError("official donor WEBI CAFE verification failed")
    return parsed, webi


def extract_custom_webi(raw: bytes) -> tuple[bytes, dict[str, Any]]:
    if len(raw) != CUSTOM_ZIMI_SIZE or sha256(raw) != CUSTOM_ZIMI_SHA256:
        raise FbfError("source is not the exact observer-only 0.0-logs-r1 ZIMI image")
    end = CUSTOM_ZIMI_WEBI_OFFSET + WEBI_FLASH_BYTES
    webi = raw[CUSTOM_ZIMI_WEBI_OFFSET:end]
    if len(webi) != WEBI_FLASH_BYTES or sha256(webi) != CUSTOM_WEBI_SHA256:
        raise FbfError("source WEBI bytes do not match the reviewed observer build")
    cafe, _records = zimi.parse_cafe(webi, include_records=False)
    if (
        not cafe["adler32_valid"]
        or cafe["duplicate_paths"]
        or not cafe["record_padding_valid"]
        or not cafe["stored_sizes_aligned_4"]
        or cafe["record_count"] != 321
        or int(cafe["sentinel_offset"], 16) != CUSTOM_WEBI_SENTINEL
        or not cafe["padding_all_ff"]
    ):
        raise FbfError("observer WEBI CAFE archive failed its exact structural profile")
    return webi, cafe


def _assemble_webi_only_fbf(
    donor: ParsedFbf,
    webi: bytes,
    meaningful_bytes: int,
) -> bytes:
    if len(webi) != WEBI_FLASH_BYTES:
        raise FbfError("WEBI must occupy the exact 0x1c0000-byte flash extent")
    if meaningful_bytes <= WEBI_FLASH_BYTES - WEBI_CHUNK_BYTES or meaningful_bytes > len(webi):
        raise FbfError("WEBI meaningful length does not exercise all reviewed chunks")
    if any(value != 0xFF for value in webi[meaningful_bytes:]):
        raise FbfError("bytes omitted from the FBF are not erased 0xff padding")
    templates = [record for record in donor.records if record.name == "WEBI"]
    if len(templates) != WEBI_FLASH_BYTES // WEBI_CHUNK_BYTES:
        raise FbfError("donor does not contain the expected 14 WEBI record templates")

    count = len(templates)
    header = bytearray(donor.raw[:FBF_RECORD_TABLE_OFFSET])
    header.extend(b"\0" * (count * FBF_RECORD_SIZE))
    header.extend(b"\0" * (FBF_BLOCK_SIZE - len(header)))
    put_u32(header, FBF_RECORD_COUNT_OFFSET, count)
    put_u32(header, 0x40, FBF_RECORD_TABLE_OFFSET + (count - 1) * FBF_RECORD_SIZE)

    candidate = bytearray(header)
    next_data_offset = FBF_BLOCK_SIZE
    stored_total = 0
    source_template = donor.raw[
        templates[0].record_offset : templates[0].record_offset + FBF_RECORD_SIZE
    ]
    for output_index, chunk_index in enumerate(reversed(range(count))):
        relative = chunk_index * WEBI_CHUNK_BYTES
        stored = min(WEBI_CHUNK_BYTES, meaningful_bytes - relative)
        if stored <= 0 or stored % 4:
            raise FbfError("WEBI chunk length is invalid for native XOR32 validation")
        payload = webi[relative : relative + stored]
        record = bytearray(source_template)
        record[0:4] = b"IBEW"
        put_u32(record, 0x0C, WEBI_CHUNK_BYTES)
        put_u32(record, 0x10, 3)
        put_u32(record, 0x14, next_data_offset // FBF_BLOCK_SIZE)
        put_u32(record, 0x18, stored)
        put_u32(record, 0x1C, WEBI_FLASH_ADDRESS + relative)
        put_u32(record, 0x30, xor32(payload))
        record_offset = FBF_RECORD_TABLE_OFFSET + output_index * FBF_RECORD_SIZE
        candidate[record_offset : record_offset + FBF_RECORD_SIZE] = record
        if len(candidate) < next_data_offset:
            candidate.extend(b"\0" * (next_data_offset - len(candidate)))
        candidate.extend(payload)
        next_data_offset = align_up(len(candidate), FBF_BLOCK_SIZE)
        candidate.extend(b"\0" * (next_data_offset - len(candidate)))
        stored_total += stored

    for offset in (0x24, 0x28, 0x2C):
        put_u32(candidate, offset, stored_total)
    return bytes(candidate)


def build_webi_noflash(donor_raw: bytes, zimi_raw: bytes) -> tuple[bytes, dict[str, Any]]:
    donor, stock_webi = verify_official_donor(donor_raw)
    custom_webi, cafe = extract_custom_webi(zimi_raw)
    meaningful_bytes = CUSTOM_WEBI_SENTINEL + 4
    candidate = _assemble_webi_only_fbf(donor, custom_webi, meaningful_bytes)
    parsed = parse_fbf(candidate, include_records=False)
    if not parsed.report["verification"]["structurally_verified"]:
        raise FbfError("rebuilt FBF failed independent structure verification")
    if parsed.report["rsa"]["record_present"]:
        raise FbfError("rebuilt FBF unexpectedly contains an RSAI record")
    if set(parsed.report["images_by_type"]) != {"WEBI"}:
        raise FbfError("rebuilt FBF contains a non-WEBI image record")
    write_plan = webi_only_write_plan(parsed)
    reconstructed = reconstruct_partition(
        parsed, "WEBI", WEBI_FLASH_ADDRESS, WEBI_FLASH_BYTES
    )
    if reconstructed != custom_webi:
        raise FbfError("rebuilt FBF does not reconstruct the exact source WEBI")

    report = {
        "schema": "mf885-webi-fbf-noflash-build/v1",
        "artifact": {
            "bytes": len(candidate),
            "sha256": sha256(candidate),
            "format": "Marvell FBF v11",
        },
        "donor": {
            "id": "official-mf96-router-c2-2.5.89",
            "bytes": len(donor_raw),
            "sha256": sha256(donor_raw),
            "version_field": _safe_version(donor.version),
            "stock_webi_sha256": sha256(stock_webi),
            "stock_webi_matches_target_2_5_94": True,
        },
        "source": {
            "id": "mf885-community-0.0-logs-r1-cafe2",
            "zimi_bytes": len(zimi_raw),
            "zimi_sha256": sha256(zimi_raw),
            "webi_bytes": len(custom_webi),
            "webi_sha256": sha256(custom_webi),
            "cafe_records": cafe["record_count"],
            "cafe_adler32_valid": cafe["adler32_valid"],
            "cafe_padding_valid": cafe["record_padding_valid"],
            "cafe_stored_sizes_aligned_4": cafe["stored_sizes_aligned_4"],
        },
        "fbf": {
            "version_field_copied_from_donor": _safe_version(donor.version),
            "image_types": parsed.report["images_by_type"],
            "rsa_record_present": False,
            "webi_flash_address": f"0x{WEBI_FLASH_ADDRESS:08x}",
            "webi_flash_bytes": WEBI_FLASH_BYTES,
            "webi_record_bytes": WEBI_CHUNK_BYTES,
            "reconstructed_webi_sha256": sha256(reconstructed),
            "all_xor32_checksums_valid": True,
            "structurally_verified": True,
            "strict_webi_only_profile_verified": True,
            "write_plan": write_plan,
            "write_plan_summary": {
                "records": len(write_plan),
                "first_flash_address": write_plan[0]["flash_address"],
                "last_flash_address": write_plan[-1]["flash_address"],
                "erase_bytes": sum(item["erase_bytes"] for item in write_plan),
                "write_bytes": sum(item["write_bytes"] for item in write_plan),
            },
        },
        "static_target_observation": {
            "exact_oslo_sha256": zimi.EXACT_OSLO_SHA256,
            "normal_system_type": "ZMIFI",
            "unsigned_no_rsai_branch_reaches_post_signature_gates": True,
            "native_iterates_supplied_record_list": True,
            "native_erases_extent_then_writes_stored_bytes": True,
            "native_partition_whitelist_identified": False,
            "native_write_readback_identified": False,
            "writer_failure_may_follow_partial_writes": True,
            "success_selector": "MAXS",
            "success_delayed_reset_identified": True,
            "live_acceptance_proven": False,
        },
        "safety": {
            "offline_only": True,
            "flash_qualified": False,
            "live_tested": False,
            "router_requests_attempted": 0,
            "firmware_posts_attempted": 0,
            "output_name_requires_noflash_marker": True,
            "remaining_blockers": [
                "native writer has no identified partition whitelist or readback verification",
                "no independent rollback or A/B fallback path is proven",
                "the target has not accepted a WEBI-only unsigned FBF",
                "post-reset boot and recovery remain unproved",
            ],
        },
    }
    return candidate, report


def _read(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise FbfError(f"could not read {label}") from exc


def publish_pair(output: Path, payload: bytes, report_path: Path, report: bytes) -> None:
    if output.parent != report_path.parent:
        raise FbfError("output and report must use the same existing directory")
    if not output.parent.is_dir():
        raise FbfError("output directory does not exist")
    if "NOFLASH" not in output.name.upper() or output.suffix.lower() != ".fbf":
        raise FbfError("output must end in .fbf and contain the marker NOFLASH")
    temporary_output = output.with_name(output.name + ".tmp")
    temporary_report = report_path.with_name(report_path.name + ".tmp")
    paths = (output, report_path, temporary_output, temporary_report)
    if any(path.exists() for path in paths):
        raise FbfError("refusing to overwrite an output, report, or temporary file")
    published: list[Path] = []
    try:
        for path, content in ((temporary_output, payload), (temporary_report, report)):
            with path.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        for temporary, final in ((temporary_output, output), (temporary_report, report_path)):
            os.link(temporary, final)
            published.append(final)
        temporary_output.unlink()
        temporary_report.unlink()
    except OSError as exc:
        for path in (*published, temporary_output, temporary_report):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        raise FbfError("could not publish the offline FBF and report atomically") from exc


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Inspect Marvell FBF images or build an offline-only MF885 WEBI capsule"
    )
    sub = value.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="inspect an FBF without contacting a router")
    inspect.add_argument("image", type=Path)
    inspect.add_argument("--records", action="store_true")
    inspect.add_argument("--json", action="store_true")

    build = sub.add_parser(
        "build-webi-noflash",
        help="wrap the exact observer WEBI in a structural-only FBF candidate",
    )
    build.add_argument("--donor", type=Path, required=True)
    build.add_argument("--zimi", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--report", type=Path, required=True)
    build.add_argument("--confirm-offline-only", action="store_true")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "inspect":
            raw = _read(args.image, "FBF image")
            parsed = parse_fbf(raw, include_records=args.records)
            if args.json:
                print(json.dumps(parsed.report, indent=2, sort_keys=True))
            else:
                report = parsed.report
                print(f"Artifact: {args.image.name}")
                print(f"Size: {report['artifact']['bytes']} bytes")
                print(f"SHA-256: {report['artifact']['sha256']}")
                print(f"Version: {report['header']['version']}")
                print(f"Images: {report['images_by_type']}")
                print(f"RSAI present: {report['rsa']['record_present']}")
                print(f"Structure: {report['verification']['status']}")
                print("Flash qualified: no (offline inspector only)")
                for error in report["verification"]["errors"]:
                    print(f"ERROR: {error}")
            return 0 if parsed.report["verification"]["structurally_verified"] else 2

        if not args.confirm_offline_only:
            raise FbfError("--confirm-offline-only is required; this does not qualify a flash")
        donor = _read(args.donor, "official donor")
        source = _read(args.zimi, "observer ZIMI")
        candidate, report = build_webi_noflash(donor, source)
        encoded_report = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        publish_pair(args.output, candidate, args.report, encoded_report)
        print(f"Built offline-only FBF: {args.output.name}")
        print(f"Size: {len(candidate)} bytes")
        print(f"SHA-256: {sha256(candidate)}")
        print("Flash qualified: no")
        print("Router requests: 0")
        return 0
    except FbfError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
