#!/usr/bin/env python3
"""Build the exact-golden Community R3.0 WebUI + native TTL image offline.

The builder has no transport and no flash action.  It first derives the exact
R3.0 WEBI from the reviewed golden, then replaces only the reviewed OSLO
partition with a deterministic LZMA-alone stream containing the byte-pinned
TTL payload.  All other partitions must remain byte-identical to the golden.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import lzma
import os
import struct
import sys
from pathlib import Path
from typing import Any

import mf885_community_r30 as community_r30
import mf885_firmware_inspect as inspector
import mf885_ttl_native_payload as ttl
import mf885_webi_builder as base
import mf885_webui_stage_builder as stage


ROOT = Path(__file__).resolve().parents[1]
PROFILE = community_r30.PROFILE
ARTIFACT = "MF885_Community_0.3.0-community-r2-native-r3-cafe-r2.bin"
SCHEMA = "mf885-community-r30-native-build/v1"
OSLO_PARTITION_BYTES = 0x460000
LZMA_PROPERTIES = bytes.fromhex("5d00008000")
LZMA_PRESET = 6
LIBLZMA_PATH = Path("/lib/x86_64-linux-gnu/liblzma.so.5")
LIBLZMA_VERSION = "5.4.5"
LIBLZMA_SHA256 = "696e868dd0700a19a6d65fc01608ec2d70d3cb91f65710e89180cd2e688f30cb"


class CommunityR30NativeError(RuntimeError):
    pass


def _condition(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {"name": name, "expected": expected, "actual": actual, "passed": expected == actual}


def _require(conditions: list[dict[str, Any]], context: str) -> None:
    failed = [item["name"] for item in conditions if not item["passed"]]
    if failed:
        raise CommunityR30NativeError(f"{context} failed: " + ", ".join(failed))


def compressor_provenance() -> dict[str, Any]:
    try:
        library_bytes = LIBLZMA_PATH.read_bytes()
        library = ctypes.CDLL(str(LIBLZMA_PATH))
        library.lzma_version_string.restype = ctypes.c_char_p
        raw_version = library.lzma_version_string()
        version = raw_version.decode("ascii", "strict") if raw_version else None
    except (OSError, UnicodeError) as exc:
        raise CommunityR30NativeError("exact liblzma provenance is unavailable") from exc
    conditions = [
        _condition("liblzma_version", LIBLZMA_VERSION, version),
        _condition("liblzma_sha256", LIBLZMA_SHA256, hashlib.sha256(library_bytes).hexdigest()),
    ]
    _require(conditions, "liblzma provenance")
    return {
        "path": str(LIBLZMA_PATH.resolve()),
        "version": version,
        "sha256": hashlib.sha256(library_bytes).hexdigest(),
        "conditions": conditions,
    }


def _partition_map(raw: bytes, identity: inspector.IdentityMaterial) -> tuple[bytearray, list[inspector.Partition]]:
    header = bytearray(inspector.decrypt_header(raw, identity))
    partitions, errors = inspector.parse_partitions(header, len(raw))
    if errors:
        raise CommunityR30NativeError("partition layout is not the exact contiguous layout")
    return header, partitions


def _layout(partitions: list[inspector.Partition]) -> list[tuple[str, int, int]]:
    return [(part.name, part.offset, part.length) for part in partitions]


def decompress_oslo_partition(payload: bytes, require_exact_source: bool) -> tuple[bytes, dict[str, Any]]:
    decoder = lzma.LZMADecompressor(
        format=lzma.FORMAT_ALONE,
        memlimit=inspector.MAX_LZMA_MEMORY_BYTES,
    )
    try:
        unpacked = decoder.decompress(payload, max_length=ttl.OSLO_BYTES + 1)
    except lzma.LZMAError as exc:
        raise CommunityR30NativeError("OSLO LZMA stream could not be decoded") from exc
    consumed = len(payload) - len(decoder.unused_data)
    conditions = [
        _condition("oslo_partition_bytes", OSLO_PARTITION_BYTES, len(payload)),
        _condition("lzma_stream_complete", True, decoder.eof),
        _condition("lzma_properties", LZMA_PROPERTIES.hex(), payload[:5].hex()),
        _condition("lzma_declared_uncompressed_bytes", ttl.OSLO_BYTES, struct.unpack("<Q", payload[5:13])[0] if len(payload) >= 13 else None),
        _condition("oslo_uncompressed_bytes", ttl.OSLO_BYTES, len(unpacked)),
        _condition("lzma_padding_present", True, bool(decoder.unused_data)),
        _condition("lzma_padding_all_ff", True, bool(decoder.unused_data) and all(value == 0xFF for value in decoder.unused_data)),
    ]
    if require_exact_source:
        conditions.append(_condition("oslo_source_sha256", ttl.OSLO_SHA256, inspector.sha256(unpacked)))
    _require(conditions, "OSLO decompression")
    return unpacked, {
        "conditions": conditions,
        "compressed_bytes": consumed,
        "padding_bytes": len(decoder.unused_data),
        "uncompressed_bytes": len(unpacked),
        "uncompressed_sha256": inspector.sha256(unpacked),
    }


def compress_oslo(oslo: bytes) -> tuple[bytes, dict[str, Any]]:
    if len(oslo) != ttl.OSLO_BYTES:
        raise CommunityR30NativeError("patched OSLO size changed")
    provenance = compressor_provenance()
    stream = bytearray(lzma.compress(oslo, format=lzma.FORMAT_ALONE, preset=LZMA_PRESET))
    if len(stream) < 13 or bytes(stream[:5]) != LZMA_PROPERTIES:
        raise CommunityR30NativeError("liblzma emitted unexpected LZMA-alone properties")
    stream[5:13] = struct.pack("<Q", len(oslo))
    if len(stream) > OSLO_PARTITION_BYTES:
        raise CommunityR30NativeError("patched OSLO compressed stream does not fit its fixed partition")
    payload = bytes(stream) + b"\xFF" * (OSLO_PARTITION_BYTES - len(stream))
    decoded, report = decompress_oslo_partition(payload, require_exact_source=False)
    conditions = report["conditions"] + [
        _condition("compressed_oslo_round_trip", inspector.sha256(oslo), inspector.sha256(decoded)),
        _condition("compressed_oslo_partition_bytes", OSLO_PARTITION_BYTES, len(payload)),
    ]
    _require(conditions, "OSLO compression")
    report.update(
        {
            "conditions": conditions,
            "preset": LZMA_PRESET,
            "properties": LZMA_PROPERTIES.hex(),
            "implementation": provenance,
            "partition_sha256": inspector.sha256(payload),
        }
    )
    return payload, report


def _allowed_native_changes(source: bytes, candidate: bytes, ranges: list[dict[str, Any]]) -> dict[str, Any]:
    allowed = bytearray(len(source))
    conditions: list[dict[str, Any]] = []
    previous_end = -1
    for item in sorted(ranges, key=lambda value: value["offset"]):
        start = int(item["offset"])
        end = start + int(item["bytes"])
        within = 0 <= start < end <= len(source)
        nonoverlap = start >= previous_end
        conditions.append(_condition(f"range:{item['name']}:within_oslo", True, within))
        conditions.append(_condition(f"range:{item['name']}:nonoverlap", True, nonoverlap))
        if within:
            allowed[start:end] = b"\x01" * (end - start)
        previous_end = max(previous_end, end)
    unauthorized = [index for index, (before, after) in enumerate(zip(source, candidate)) if before != after and not allowed[index]]
    conditions.extend(
        (
            _condition("native_candidate_size", len(source), len(candidate)),
            _condition("unauthorized_changed_bytes", 0, len(unauthorized)),
        )
    )
    _require(conditions, "native allowed-range verification")
    changed_count, changed_ranges = inspector.diff_ranges(source, candidate)
    return {
        "conditions": conditions,
        "declared_ranges": sorted(ranges, key=lambda value: value["offset"]),
        "actual_changed_bytes": changed_count,
        "actual_changed_ranges": changed_ranges,
    }


def build_candidate(
    golden_raw: bytes,
    identity: inspector.IdentityMaterial,
) -> tuple[bytes, dict[str, Any]]:
    golden_header, golden_partitions = _partition_map(golden_raw, identity)
    try:
        oslo_index, oslo = next(
            (index, part) for index, part in enumerate(golden_partitions) if part.name == "OSLO"
        )
    except StopIteration as exc:
        raise CommunityR30NativeError("golden has no OSLO partition") from exc
    if oslo.length != OSLO_PARTITION_BYTES:
        raise CommunityR30NativeError("golden OSLO partition length changed")

    source_oslo, source_lzma = decompress_oslo_partition(
        golden_raw[oslo.offset : oslo.offset + oslo.length],
        require_exact_source=True,
    )
    patched_oslo, native_report = ttl.build_payload(source_oslo, "full")
    allowed_report = _allowed_native_changes(
        source_oslo,
        patched_oslo,
        native_report["changed_ranges"],
    )
    rebuilt_oslo, lzma_report = compress_oslo(patched_oslo)

    web_candidate, web_report = stage.build_stage_image(
        golden_raw,
        identity,
        PROFILE,
    )
    header, partitions = _partition_map(web_candidate, identity)
    if _layout(partitions) != _layout(golden_partitions):
        raise CommunityR30NativeError("WEBI stage changed partition layout")
    candidate = bytearray(web_candidate)
    candidate[oslo.offset : oslo.offset + oslo.length] = rebuilt_oslo
    descriptor = inspector.DESCRIPTOR_OFFSET + oslo_index * inspector.DESCRIPTOR_SIZE
    oslo_sum = inspector.byte_sum(rebuilt_oslo)
    struct.pack_into("<I", header, descriptor + 0x10, oslo_sum)
    plaintext = bytes(header) + bytes(candidate[inspector.HEADER_SIZE :])
    global_sum = inspector.byte_sum(plaintext[0x20:])
    struct.pack_into("<I", header, 0x1C, global_sum)
    encrypted = base.encrypt_header(bytes(header), identity.key)
    candidate[: inspector.HEADER_SIZE] = (
        encrypted + bytes(header[inspector.ENCRYPTED_HEADER_SIZE : inspector.HEADER_SIZE])
    )
    result = bytes(candidate)
    if len(result) != base.EXPECTED_SIZE:
        raise CommunityR30NativeError("final image size changed")
    return result, {
        "schema": SCHEMA,
        "source_oslo_lzma": source_lzma,
        "native": native_report,
        "native_allowed_ranges": allowed_report,
        "rebuilt_oslo_lzma": lzma_report,
        "webui": web_report,
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
    golden_header, golden_parts = _partition_map(golden_raw, identity)
    candidate_header, candidate_parts = _partition_map(candidate, identity)
    web_candidate, _ = stage.build_stage_image(golden_raw, identity, PROFILE)
    web_header, web_parts = _partition_map(web_candidate, identity)
    conditions: list[dict[str, Any]] = [
        _condition("candidate_bytes", len(golden_raw), len(candidate)),
        _condition("partition_layout", _layout(golden_parts), _layout(candidate_parts)),
        _condition("web_stage_partition_layout", _layout(golden_parts), _layout(web_parts)),
    ]

    oslo_index = next(index for index, part in enumerate(golden_parts) if part.name == "OSLO")
    oslo = golden_parts[oslo_index]
    source_oslo, _ = decompress_oslo_partition(
        golden_raw[oslo.offset : oslo.offset + oslo.length],
        require_exact_source=True,
    )
    expected_oslo, native_report = ttl.build_payload(source_oslo, "full")
    actual_oslo, lzma_report = decompress_oslo_partition(
        candidate[oslo.offset : oslo.offset + oslo.length],
        require_exact_source=False,
    )
    conditions.extend(
        (
            _condition("decompressed_oslo_bytes", len(expected_oslo), len(actual_oslo)),
            _condition("decompressed_oslo_sha256", inspector.sha256(expected_oslo), inspector.sha256(actual_oslo)),
            _condition("decompressed_oslo_exact", True, actual_oslo == expected_oslo),
            _condition("native_hook_installed", True, native_report["hook"]["installed"]),
            _condition("native_boot_state", 0, native_report["state"]["boot_value"]),
            _condition("native_persistent", False, native_report["state"]["persistent"]),
        )
    )
    _allowed_native_changes(source_oslo, actual_oslo, native_report["changed_ranges"])

    for part in golden_parts:
        start, end = part.offset, part.offset + part.length
        if part.name == "OSLO":
            continue
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
    plaintext = bytes(candidate_header) + candidate[inspector.HEADER_SIZE :]
    conditions.extend(
        (
            _condition("header_unexpected_changed_bytes", 0, len(unexpected_header)),
            _condition("oslo_descriptor_sum", inspector.byte_sum(candidate[oslo.offset : oslo.offset + oslo.length]), candidate_parts[oslo_index].checksum),
            _condition("global_byte_sum", inspector.byte_sum(plaintext[0x20:]), inspector.u32(candidate_header, 0x1C)),
        )
    )
    _require(conditions, "final candidate verification")
    return {
        "schema": "mf885-community-r30-native-verification/v1",
        "status": "GREEN",
        "conditions": conditions,
        "oslo": lzma_report,
        "artifact": {"bytes": len(candidate), "sha256": inspector.sha256(candidate)},
    }


def write_exclusive(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    if path.exists() or temporary.exists():
        raise CommunityR30NativeError(f"refusing to overwrite {path.name}")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        temporary.unlink()
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise CommunityR30NativeError(f"could not publish {path.name} create-once") from exc


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Build exact-golden MF885 Community R3.0 native TTL image")
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
            raise CommunityR30NativeError("--confirm-native-ttl-risk is required")
        if not args.output.parent.is_dir() or not args.report.parent.is_dir():
            raise CommunityR30NativeError("output and report directories must already exist")
        if args.output.exists() or args.report.exists() or verification_path.exists():
            raise CommunityR30NativeError("output, report or verification temporary already exists")
        identity = inspector.load_identity(args.identity_xml)
        golden_raw = base.require_reviewed_golden(args.golden, identity)
        first, first_report = build_candidate(golden_raw, identity)
        second, second_report = build_candidate(golden_raw, identity)
        deterministic = first == second and first_report == second_report
        if not deterministic:
            raise CommunityR30NativeError("double build is not deterministic")
        verification = verify_candidate(golden_raw, first, identity)
        with verification_path.open("xb") as stream:
            stream.write(first)
            stream.flush()
            os.fsync(stream.fileno())
        independent = inspector.inspect_image(verification_path, identity, include_records=True)
        if independent.report["verification"]["status"] != "verified":
            raise CommunityR30NativeError("independent ZIMI/CAFE/LZMA inspection failed")
        report = {
            "schema": SCHEMA,
            "profile": PROFILE,
            "source": {
                "file": args.golden.name,
                "bytes": len(golden_raw),
                "sha256": inspector.sha256(golden_raw),
            },
            "artifact": {
                "file": args.output.name,
                "bytes": len(first),
                "sha256": inspector.sha256(first),
            },
            "build": first_report,
            "verification": {
                **verification,
                "double_build_equal": deterministic,
                "independent_container_status": independent.report["verification"]["status"],
                "changed_partitions": ["OSLO", "WEBI"],
                "other_partitions_byte_identical": True,
            },
            "qualification": {
                "flash_qualified": False,
                "live_ttl_qualified": False,
                "cold_boot_proven": False,
                "repeatability_proven": False,
                "rollback_proven": False,
                "reason": "offline deterministic build only; exact live approval and functional GL.iNet-to-VDS TTL proof remain required",
            },
        }
        verification_path.unlink()
        write_exclusive(args.output, first)
        write_exclusive(args.report, (json.dumps(report, indent=2, sort_keys=True) + "\n").encode())
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (
        CommunityR30NativeError,
        ttl.TtlPayloadError,
        inspector.InspectionError,
        base.BuildError,
        stage.StageBuildError,
        OSError,
        lzma.LZMAError,
    ) as exc:
        try:
            verification_path.unlink(missing_ok=True)
        except OSError:
            pass
        print(f"native build failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
