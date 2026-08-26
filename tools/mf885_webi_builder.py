#!/usr/bin/env python3
"""Build a deterministic WEBI-only MF885 canary from a reviewed golden image.

The tool never contacts a router. It patches one fixed-size CAFE record, appends
one record inside existing padding, recalculates the
CAFE Adler-32 and both ZIMI additive byte sums, re-encrypts the device-bound
header, and requires the independent inspector to verify the result before the
output is published. The output remains structural-only and is not flash
qualified or added to the Stage 0 restore allowlist.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mf885_firmware_inspect as inspector


GOLDEN_SHA256 = "2b5880fc26805918bb574d07341ea9b863f8261be34c3bf9766fac0929204531"
EXPECTED_SIZE = 8_323_644
REVIEWED_PLAINTEXT_SHA256 = "2bf4151a6e209845fd8d30f576577f6a66fe4cdf6d770c8bb45f0204c3486850"
REVIEWED_HEADER_SHA256 = "9bcd77127729bb225cc8bb688c858cd4a0b909b0f9923b9af484668a9ac493e9"
REVIEWED_BODY_SHA256 = "cca8c01b80651abaf7c53dbcab26976ab2bce349f8f7c121d195d172e9a234ab"
REVIEWED_PARTITIONS = (
    ("OSLO", 0x00023C, 0x460000, 0x232C9A1E, "8b3da09d8d1aa4c8dbc493b8b1ceaeaabb51746744515dc8cdf66d65461260ca"),
    ("GRBI", 0x46023C, 0x0C0000, 0x06CB4BB8, "e2f0e115ae091bc018c6c2bac6560368dbdf1d4b66a3334450f113548f244de0"),
    ("WEBI", 0x52023C, 0x1C0000, 0x097C3A03, "86fda63366438a166c7ef334042af410e55289e7591a0743c47797404c08bb56"),
    ("WIFI", 0x6E023C, 0x080000, 0x05AD8FBA, "db5a098ae78ed29206b97afaa9329d743d934290df53eab6e4feec75e3b448cd"),
    ("WCAL", 0x76023C, 0x080000, 0x06736250, "aab1c19f4ec1f5c9da3099d1041754ab9dfa9e7daa22fcc02a3b4db74d618eeb"),
    ("RFBN", 0x7E023C, 0x010000, 0x00CCE703, "644d300771c71b193030066a52ae1ff0723bfb84b218861a60de4ce3f5202902"),
)
INDEX_PATH = "www\\index.html"
SCRIPT_PATH = "www\\js\\canary_logs.js"
INDEX_LOADER = b'<script src="js/canary_logs.js"></script>'
CANARY_MARKER = b"MF885 Community Canary Logs 0.0-logs-r1"
CANARY_PROFILES = {
    "0.0-logs-r1": {
        "marker": CANARY_MARKER,
        "size": 12_561,
        "sha256": "60405789b8bab668f69e3152b8bca23245fa4df76052a2a6b3f203f9e9e7b28e",
    },
    "0.0-logs-r2": {
        "marker": b"MF885 Community Canary Logs 0.0-logs-r2",
        "size": 13_402,
        "sha256": "9d6016a1f7b8e779a70826dc9a4607cf72d7ecb37301f1f831501461fc4c3540",
    },
}


class BuildError(Exception):
    pass


@dataclass(frozen=True)
class CafeSourceRecord:
    path: str
    header: bytes
    stored_data: bytes
    logical_data: bytes
    padding_bytes: int


def encode_cafe_data(logical_data: bytes) -> tuple[bytes, int, int]:
    """Return canonical stored bytes, padding count and size_flags for logical data."""
    padding_bytes = (-len(logical_data)) % 4
    stored_data = logical_data + b"\xFF" * padding_bytes
    if len(stored_data) > 0x00FFFFFF:
        raise BuildError("CAFE logical data exceeds the 24-bit stored-size field")
    return stored_data, padding_bytes, (padding_bytes << 24) | len(stored_data)


def portable_plaintext_sha256(data: bytes, identity: inspector.IdentityMaterial) -> str:
    """Hash the decrypted ZIMI header plus the unchanged partition bytes."""
    header = inspector.decrypt_header(data, identity)
    return inspector.sha256(header + data[inspector.HEADER_SIZE :])


def require_reviewed_golden(path: Path, identity: inspector.IdentityMaterial) -> bytes:
    """Accept only the reviewed 2.5.94/Ver.D image, independent of unit encryption."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise BuildError("could not read the golden image") from exc
    if len(data) != EXPECTED_SIZE:
        raise BuildError(f"golden must be exactly {EXPECTED_SIZE} bytes")

    parsed = inspector.inspect_image(path, identity, include_records=True)
    if parsed.report["verification"]["status"] != "verified":
        raise BuildError("golden did not pass the full independent inspector")
    header = inspector.decrypt_header(data, identity)
    if inspector.sha256(header) != REVIEWED_HEADER_SHA256:
        raise BuildError("golden decrypted header is not the reviewed 2.5.94/Ver.D base")
    if inspector.sha256(data[inspector.HEADER_SIZE :]) != REVIEWED_BODY_SHA256:
        raise BuildError("golden partition body is not the reviewed base")
    if portable_plaintext_sha256(data, identity) != REVIEWED_PLAINTEXT_SHA256:
        raise BuildError("golden portable plaintext fingerprint does not match")

    actual_partitions = tuple(
        (
            part.name,
            part.offset,
            part.length,
            part.checksum,
            inspector.sha256(data[part.offset : part.offset + part.length]),
        )
        for part in parsed.partitions
    )
    if actual_partitions != REVIEWED_PARTITIONS:
        raise BuildError("golden partition layout or payload fingerprints do not match")
    return data


def parse_cafe_source(payload: bytes) -> tuple[bytes, list[CafeSourceRecord], int]:
    report, _ = inspector.parse_cafe(payload, include_records=False)
    if (
        not report["adler32_valid"]
        or report["duplicate_paths"]
        or not report["record_padding_valid"]
        or not report["stored_sizes_aligned_4"]
    ):
        raise BuildError("source WEBI CAFE archive is not internally valid")
    position = inspector.CAFE_HEADER_SIZE
    records: list[CafeSourceRecord] = []
    while inspector.u32(payload, position) != 0xDADADADA:
        header = payload[position : position + inspector.CAFE_RECORD_HEADER_SIZE]
        size_flags = inspector.u32(header, 4)
        size = size_flags & 0x00FFFFFF
        padding_bytes = size_flags >> 24
        path = header[8:].split(b"\0", 1)[0].decode("ascii")
        start = position + inspector.CAFE_RECORD_HEADER_SIZE
        stored_data = payload[start : start + size]
        logical_data = stored_data[:-padding_bytes] if padding_bytes else stored_data
        records.append(
            CafeSourceRecord(path, header, stored_data, logical_data, padding_bytes)
        )
        position = start + size
    return payload[: inspector.CAFE_HEADER_SIZE], records, position


def patch_index_loader(stock: bytes) -> bytes:
    """Patch the reviewed slot in the logical (padding-free) index body."""
    if INDEX_LOADER in stock or any(profile["marker"] in stock for profile in CANARY_PROFILES.values()):
        raise BuildError("golden index already contains Canary material")
    match = re.search(br"(\s+)</body>", stock, re.IGNORECASE)
    if not match or len(match.group(1)) != len(INDEX_LOADER):
        raise BuildError("stock index no longer has the reviewed 41-byte pre-body whitespace slot")
    patched = stock[: match.start(1)] + INDEX_LOADER + stock[match.end(1) :]
    if len(patched) != len(stock):
        raise BuildError("index loader patch changed the record size")
    return patched


def require_exact_canary_script(script: bytes, profile: str) -> bytes:
    specification = CANARY_PROFILES.get(profile)
    if specification is None:
        raise BuildError("unknown Canary build profile")
    marker = specification["marker"]
    if (
        len(script) != specification["size"]
        or inspector.sha256(script) != specification["sha256"]
    ):
        raise BuildError("Canary script does not match the exact profile size and SHA-256")
    if marker not in script:
        raise BuildError("Canary script does not contain the exact marker")
    if any(
        other["marker"] in script
        for key, other in CANARY_PROFILES.items()
        if key != profile
    ):
        raise BuildError("Canary script contains a marker from another build profile")
    return marker


def rebuild_cafe(
    payload: bytes,
    replacements: dict[str, bytes],
    additions: dict[str, bytes] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    cafe_header, records, old_sentinel = parse_cafe_source(payload)
    paths = {record.path for record in records}
    additions = additions or {}
    missing = sorted(set(replacements) - paths)
    if missing:
        raise BuildError("replacement paths are absent from WEBI: " + ", ".join(missing))
    duplicate_additions = sorted(set(additions) & paths)
    if duplicate_additions:
        raise BuildError("added paths already exist in WEBI: " + ", ".join(duplicate_additions))
    rebuilt = bytearray(cafe_header)
    changes = []
    for record in records:
        if record.path not in replacements:
            rebuilt.extend(record.header)
            rebuilt.extend(record.stored_data)
            continue
        logical_data = replacements[record.path]
        stored_data, padding_bytes, size_flags = encode_cafe_data(logical_data)
        header = bytearray(record.header)
        struct.pack_into("<I", header, 4, size_flags)
        rebuilt.extend(header)
        rebuilt.extend(stored_data)
        if bytes(header) != record.header or stored_data != record.stored_data:
            changes.append(
                {
                    "path": record.path,
                    "size_before": len(record.logical_data),
                    "size_after": len(logical_data),
                    "sha256_before": inspector.sha256(record.logical_data),
                    "sha256_after": inspector.sha256(logical_data),
                    "stored_size_before": len(record.stored_data),
                    "stored_size_after": len(stored_data),
                    "padding_before": record.padding_bytes,
                    "padding_after": padding_bytes,
                }
            )
    added = []
    for path in sorted(additions):
        logical_data = additions[path]
        encoded_path = path.encode("ascii")
        if not encoded_path or len(encoded_path) >= 128:
            raise BuildError(f"invalid added CAFE record {path}")
        stored_data, padding_bytes, size_flags = encode_cafe_data(logical_data)
        header = bytearray(inspector.CAFE_RECORD_HEADER_SIZE)
        struct.pack_into("<I", header, 0, 0xCAFE1000)
        struct.pack_into("<I", header, 4, size_flags)
        header[8 : 8 + len(encoded_path)] = encoded_path
        rebuilt.extend(header)
        rebuilt.extend(stored_data)
        added.append(
            {
                "path": path,
                "size": len(logical_data),
                "sha256": inspector.sha256(logical_data),
                "stored_size": len(stored_data),
                "padding": padding_bytes,
                "size_flags": inspector.hex32(size_flags),
            }
        )
    sentinel = len(rebuilt)
    rebuilt.extend(struct.pack("<I", 0xDADADADA))
    if len(rebuilt) > len(payload):
        raise BuildError(
            f"rebuilt WEBI exceeds its fixed slot by {len(rebuilt) - len(payload)} bytes"
        )
    rebuilt.extend(b"\xFF" * (len(payload) - len(rebuilt)))
    adler = zlib.adler32(rebuilt[8:sentinel]) & 0xFFFFFFFF
    struct.pack_into("<I", rebuilt, 4, adler)
    report, _ = inspector.parse_cafe(bytes(rebuilt), include_records=False)
    if (
        not report["adler32_valid"]
        or not report["record_padding_valid"]
        or not report["stored_sizes_aligned_4"]
    ):
        raise BuildError("rebuilt WEBI CAFE verification failed")
    return bytes(rebuilt), {
        "changes": changes,
        "additions": added,
        "sentinel_before": f"0x{old_sentinel:x}",
        "sentinel_after": f"0x{sentinel:x}",
        "padding_before": len(payload) - old_sentinel - 4,
        "padding_after": len(payload) - sentinel - 4,
        "adler32": inspector.hex32(adler),
    }


def encrypt_header(header: bytes, key: bytes) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError as exc:
        raise BuildError("header rebuilding needs the Python cryptography package") from exc
    encryptor = Cipher(algorithms.AES(key), modes.CBC(bytes(16))).encryptor()
    return encryptor.update(header[: inspector.ENCRYPTED_HEADER_SIZE]) + encryptor.finalize()


def build_image(
    golden_raw: bytes,
    identity: inspector.IdentityMaterial,
    script: bytes,
    profile: str = "0.0-logs-r1",
) -> tuple[bytes, dict[str, Any]]:
    marker = require_exact_canary_script(script, profile)
    if b"</script>" in script.lower():
        raise BuildError("standalone Canary script unexpectedly contains an HTML script terminator")
    header = bytearray(inspector.decrypt_header(golden_raw, identity))
    partitions, layout_errors = inspector.parse_partitions(header, len(golden_raw))
    if layout_errors:
        raise BuildError("golden partition layout is not the expected contiguous layout")
    try:
        webi_index, webi = next(
            (index, part) for index, part in enumerate(partitions) if part.name == "WEBI"
        )
    except StopIteration as exc:
        raise BuildError("golden image has no WEBI partition") from exc
    webi_payload = golden_raw[webi.offset : webi.offset + webi.length]
    _, records, _ = parse_cafe_source(webi_payload)
    stock_index = next(
        (record.logical_data for record in records if record.path == INDEX_PATH), None
    )
    if stock_index is None:
        raise BuildError("golden WEBI has no www/index.html record")
    canary_index = patch_index_loader(stock_index)
    rebuilt_webi, cafe_report = rebuild_cafe(
        webi_payload,
        {INDEX_PATH: canary_index},
        {SCRIPT_PATH: script},
    )
    candidate = bytearray(golden_raw)
    candidate[webi.offset : webi.offset + webi.length] = rebuilt_webi

    descriptor = inspector.DESCRIPTOR_OFFSET + webi_index * inspector.DESCRIPTOR_SIZE
    webi_sum = inspector.byte_sum(rebuilt_webi)
    struct.pack_into("<I", header, descriptor + 0x10, webi_sum)
    plaintext_image = bytes(header) + bytes(candidate[inspector.HEADER_SIZE :])
    global_sum = inspector.byte_sum(plaintext_image[0x20:])
    struct.pack_into("<I", header, 0x1C, global_sum)
    encrypted_prefix = encrypt_header(bytes(header), identity.key)
    candidate[: inspector.HEADER_SIZE] = (
        encrypted_prefix + bytes(header[inspector.ENCRYPTED_HEADER_SIZE : inspector.HEADER_SIZE])
    )
    if len(candidate) != EXPECTED_SIZE:
        raise BuildError("candidate image size changed")
    return bytes(candidate), {
        "cafe": cafe_report,
        "index": {
            "path": INDEX_PATH,
            "size_before": len(stock_index),
            "size_after": len(canary_index),
            "sha256_before": inspector.sha256(stock_index),
            "sha256_after": inspector.sha256(canary_index),
        },
        "script": {
            "path": SCRIPT_PATH,
            "size": len(script),
            "sha256": inspector.sha256(script),
        },
        "checksums": {
            "webi_byte_sum": inspector.hex32(webi_sum),
            "global_byte_sum": inspector.hex32(global_sum),
        },
    }


def write_exclusive(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    if path.exists() or temporary.exists():
        raise BuildError(f"refusing to overwrite {path.name}")
    try:
        with temporary.open("xb") as stream:
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
        raise BuildError(f"could not write {path.name} atomically") from exc


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Build a structural-only MF885 WEBI log Canary")
    value.add_argument("--golden", type=Path, required=True)
    value.add_argument("--identity-xml", type=Path, required=True)
    value.add_argument("--script", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--report", type=Path, required=True)
    value.add_argument("--profile", choices=tuple(CANARY_PROFILES), default="0.0-logs-r1")
    value.add_argument("--confirm-structural-only", action="store_true")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    temporary = args.output.with_name(args.output.name + ".verify.tmp")
    try:
        if not args.confirm_structural_only:
            raise BuildError("--confirm-structural-only is required; this does not qualify a flash")
        if not args.output.parent.is_dir() or not args.report.parent.is_dir():
            raise BuildError("output and report directories must already exist")
        if args.output.exists() or args.report.exists() or temporary.exists():
            raise BuildError("output, report, or verification temporary already exists")
        identity = inspector.load_identity(args.identity_xml)
        golden_raw = require_reviewed_golden(args.golden, identity)
        script = args.script.read_bytes()
        golden = inspector.inspect_image(args.golden, identity, include_records=True)
        if golden.report["verification"]["status"] != "verified":
            raise BuildError("golden did not pass the full independent inspector")
        candidate, build_report = build_image(golden_raw, identity, script, args.profile)
        with temporary.open("xb") as stream:
            stream.write(candidate)
            stream.flush()
            os.fsync(stream.fileno())
        parsed = inspector.inspect_image(temporary, identity, include_records=True)
        comparison = inspector.compare_images(golden, parsed)
        if parsed.report["verification"]["status"] != "verified":
            raise BuildError("candidate failed the full independent inspector")
        partition_diffs = {item["name"]: item.get("diff_bytes") for item in comparison["partitions"]}
        if any(value for name, value in partition_diffs.items() if name != "WEBI"):
            raise BuildError("a non-WEBI partition changed")
        cafe = comparison["cafe"].get("WEBI", {})
        changed = [item.get("path") for item in cafe.get("changed_records", [])]
        if changed != [INDEX_PATH] or cafe.get("added_paths") != [SCRIPT_PATH] or cafe.get("removed_paths"):
            raise BuildError("logical delta is not exactly the fixed-size index loader plus canary_logs.js")
        report = {
            "schema": "mf885-webi-canary-build/v2",
            "id": f"{args.profile}-cafe2",
            "logical_id": args.profile,
            "container_revision": 2,
            "marker": CANARY_PROFILES[args.profile]["marker"].decode("ascii"),
            "source": {
                "size": len(golden_raw),
                "sha256": inspector.sha256(golden_raw),
                "raw_sha256": inspector.sha256(golden_raw),
                "reference_raw_sha256": GOLDEN_SHA256,
                "portable_plaintext_sha256": REVIEWED_PLAINTEXT_SHA256,
            },
            "artifact": {
                "file": args.output.name,
                "size": len(candidate),
                "sha256": inspector.sha256(candidate),
                "raw_sha256": inspector.sha256(candidate),
                "portable_plaintext_sha256": portable_plaintext_sha256(candidate, identity),
            },
            "identity_fingerprint_sha256": identity.fingerprint,
            "script_sha256": inspector.sha256(script),
            "build": build_report,
            "verification": {
                "status": "verified",
                "structurally_verified": True,
                "changed_partitions": [name for name, value in partition_diffs.items() if value],
                "logical_changes": ["WEBI:www/index.html", "WEBI:www/js/canary_logs.js"],
                "non_webi_partitions_byte_identical": True,
            },
            "qualification": {
                "flash_qualified": False,
                "live_tested": False,
                "restore_allowlisted": False,
                "reason": "structural build only; normal ZMIFI RestoreFw is rejected before parsing and stock FBF live acceptance/recovery remain unproved",
                "stable": False,
            },
        }
        temporary.unlink()
        write_exclusive(args.output, candidate)
        write_exclusive(args.report, (json.dumps(report, indent=2, sort_keys=True) + "\n").encode())
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (BuildError, inspector.InspectionError, OSError) as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        print(f"build failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
