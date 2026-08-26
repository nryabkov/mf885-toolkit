#!/usr/bin/env python3
"""Build exact-golden, structural-only WebUI stage images.

This builder replaces only reviewed CAFE records. It has no router transport,
no FBF publisher and no flash action. Every source byte is pinned by profile,
and the independent ZIMI/CAFE inspector must accept the completed image before
the output is published.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import mf885_firmware_inspect as inspector
import mf885_webi_builder as base


ROOT = Path(__file__).resolve().parents[1]
STAGE_PROFILES: dict[str, dict[str, Any]] = {
    "0.0-sms-r1": {
        "kind": "webui-sms",
        "marker": b"MF885 Community WebUI SMS 0.0-sms-r1",
        "artifact": "MF885_Community_0.0-sms-r1-cafe-r2.bin",
        "files": {
            "www\\html\\SMS\\SMS.html": {
                "source": "firmware/webui-sms-r1/SMS.html",
                "size": 1549,
                "sha256": "ae9c42ba80436addf5c5bbadbf87fa91199630f41110870278ac8e65aa16faa2",
            },
            "www\\js\\panel\\SMS\\SMS.js": {
                "source": "firmware/webui-sms-r1/SMS.js",
                "size": 12746,
                "sha256": "bb53c958e50805aede7152081f7d08b2325c9cfa2f7b30204e10bf39e0db84d0",
            },
        },
        "safety": {
            "routerRequestsOnPageLoad": ["GET status1", "semantic-read POST message pages"],
            "mutationContract": "one explicit stock message POST followed by bounded status reads",
            "mutationUnknownLocksPageSession": True,
        },
    },
}


class StageBuildError(Exception):
    pass


def validate_profile_source(data: bytes, specification: dict[str, Any]) -> None:
    if len(data) != specification["size"]:
        raise StageBuildError("stage source size does not match its exact profile")
    if inspector.sha256(data) != specification["sha256"]:
        raise StageBuildError("stage source SHA-256 does not match its exact profile")


def load_profile_sources(profile: str, root: Path = ROOT) -> dict[str, bytes]:
    specification = STAGE_PROFILES.get(profile)
    if specification is None:
        raise StageBuildError("unknown or intentionally unbuildable WebUI stage")
    replacements: dict[str, bytes] = {}
    for target, source_specification in specification["files"].items():
        try:
            data = (root / source_specification["source"]).read_bytes()
        except OSError as exc:
            raise StageBuildError("could not read an exact stage source") from exc
        validate_profile_source(data, source_specification)
        replacements[target] = data
    if specification["marker"] not in b"\n".join(replacements.values()):
        raise StageBuildError("stage marker is absent from the reviewed sources")
    joined = b"\n".join(replacements.values())
    forbidden = (b"RestoreFw", b"file=reset", b"file=poweroff", b"debugmodeon")
    if any(value.lower() in joined.lower() for value in forbidden):
        raise StageBuildError("stage source contains a forbidden firmware/power/debug route")
    return replacements


def build_stage_image(
    golden_raw: bytes,
    identity: inspector.IdentityMaterial,
    profile: str,
    replacements: dict[str, bytes] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    specification = STAGE_PROFILES.get(profile)
    if specification is None:
        raise StageBuildError("unknown or intentionally unbuildable WebUI stage")
    replacements = replacements or load_profile_sources(profile)
    for target, source_specification in specification["files"].items():
        if target not in replacements:
            raise StageBuildError("stage replacement set is incomplete")
        validate_profile_source(replacements[target], source_specification)
    if set(replacements) != set(specification["files"]):
        raise StageBuildError("stage replacement set contains an unreviewed path")

    header = bytearray(inspector.decrypt_header(golden_raw, identity))
    partitions, layout_errors = inspector.parse_partitions(header, len(golden_raw))
    if layout_errors:
        raise StageBuildError("golden partition layout is not the reviewed contiguous layout")
    try:
        webi_index, webi = next(
            (index, part) for index, part in enumerate(partitions) if part.name == "WEBI"
        )
    except StopIteration as exc:
        raise StageBuildError("golden image has no WEBI partition") from exc

    webi_payload = golden_raw[webi.offset : webi.offset + webi.length]
    rebuilt_webi, cafe_report = base.rebuild_cafe(webi_payload, replacements)
    candidate = bytearray(golden_raw)
    candidate[webi.offset : webi.offset + webi.length] = rebuilt_webi

    descriptor = inspector.DESCRIPTOR_OFFSET + webi_index * inspector.DESCRIPTOR_SIZE
    webi_sum = inspector.byte_sum(rebuilt_webi)
    import struct

    struct.pack_into("<I", header, descriptor + 0x10, webi_sum)
    plaintext_image = bytes(header) + bytes(candidate[inspector.HEADER_SIZE :])
    global_sum = inspector.byte_sum(plaintext_image[0x20:])
    struct.pack_into("<I", header, 0x1C, global_sum)
    encrypted_prefix = base.encrypt_header(bytes(header), identity.key)
    candidate[: inspector.HEADER_SIZE] = (
        encrypted_prefix
        + bytes(header[inspector.ENCRYPTED_HEADER_SIZE : inspector.HEADER_SIZE])
    )
    if len(candidate) != base.EXPECTED_SIZE:
        raise StageBuildError("candidate image size changed")
    return bytes(candidate), {
        "cafe": cafe_report,
        "checksums": {
            "webi_byte_sum": inspector.hex32(webi_sum),
            "global_byte_sum": inspector.hex32(global_sum),
        },
    }


def write_exclusive(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    if path.exists() or temporary.exists():
        raise StageBuildError(f"refusing to overwrite {path.name}")
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
        raise StageBuildError(f"could not write {path.name} atomically") from exc


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Build an exact-golden, structural-only MF885 WebUI stage"
    )
    value.add_argument("--golden", type=Path, required=True)
    value.add_argument("--identity-xml", type=Path, required=True)
    value.add_argument("--profile", choices=tuple(STAGE_PROFILES), required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--report", type=Path, required=True)
    value.add_argument("--confirm-structural-only", action="store_true")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    temporary = args.output.with_name(args.output.name + ".verify.tmp")
    try:
        if not args.confirm_structural_only:
            raise StageBuildError("--confirm-structural-only is required")
        if not args.output.parent.is_dir() or not args.report.parent.is_dir():
            raise StageBuildError("output and report directories must already exist")
        if args.output.exists() or args.report.exists() or temporary.exists():
            raise StageBuildError("output, report, or verification temporary already exists")
        golden_raw = base.require_exact_golden(args.golden)
        identity = inspector.load_identity(args.identity_xml)
        golden = inspector.inspect_image(args.golden, identity, include_records=True)
        if golden.report["verification"]["status"] != "verified":
            raise StageBuildError("golden did not pass the full independent inspector")
        replacements = load_profile_sources(args.profile)
        candidate, build_report = build_stage_image(
            golden_raw, identity, args.profile, replacements
        )
        with temporary.open("xb") as stream:
            stream.write(candidate)
            stream.flush()
            os.fsync(stream.fileno())
        parsed = inspector.inspect_image(temporary, identity, include_records=True)
        comparison = inspector.compare_images(golden, parsed)
        if parsed.report["verification"]["status"] != "verified":
            raise StageBuildError("candidate failed the full independent inspector")
        partition_diffs = {
            item["name"]: item.get("diff_bytes") for item in comparison["partitions"]
        }
        if any(value for name, value in partition_diffs.items() if name != "WEBI"):
            raise StageBuildError("a non-WEBI partition changed")
        cafe = comparison["cafe"].get("WEBI", {})
        changed = sorted(item.get("path") for item in cafe.get("changed_records", []))
        expected = sorted(replacements)
        if changed != expected or cafe.get("added_paths") or cafe.get("removed_paths"):
            raise StageBuildError("logical delta is not exactly the reviewed replacements")
        specification = STAGE_PROFILES[args.profile]
        report = {
            "schema": "mf885-webui-stage-build/v2",
            "id": f"{args.profile}-cafe2",
            "logical_id": args.profile,
            "container_revision": 2,
            "kind": specification["kind"],
            "marker": specification["marker"].decode("ascii"),
            "source": {"size": len(golden_raw), "sha256": base.GOLDEN_SHA256},
            "artifact": {
                "file": args.output.name,
                "size": len(candidate),
                "sha256": inspector.sha256(candidate),
            },
            "identity_fingerprint_sha256": identity.fingerprint,
            "sources": [
                {
                    "target": target,
                    "source": specification["files"][target]["source"],
                    "size": len(replacements[target]),
                    "sha256": inspector.sha256(replacements[target]),
                }
                for target in sorted(replacements)
            ],
            "build": build_report,
            "verification": {
                "status": "verified",
                "structurally_verified": True,
                "changed_partitions": [
                    name for name, value in partition_diffs.items() if value
                ],
                "logical_changes": [f"WEBI:{path}" for path in expected],
                "non_webi_partitions_byte_identical": True,
            },
            "runtime_safety": specification["safety"],
            "qualification": {
                "flash_qualified": False,
                "live_tested": False,
                "restore_allowlisted": False,
                "fbf_wrapper_available": False,
                "reason": "structural build only; delivery, rollback and live WebUI behavior remain unproved",
                "stable": False,
            },
        }
        temporary.unlink()
        write_exclusive(args.output, candidate)
        write_exclusive(
            args.report,
            (json.dumps(report, indent=2, sort_keys=True) + "\n").encode(),
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (StageBuildError, base.BuildError, inspector.InspectionError, OSError) as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        print(f"build failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
