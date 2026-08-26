#!/usr/bin/env python3
"""Build reviewed-golden, structural-only WebUI stage images.

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
import mf885_community_r2 as community_r2
import mf885_community_r21 as community_r21
import mf885_community_r22 as community_r22


ROOT = Path(__file__).resolve().parents[1]
STAGE_PROFILES: dict[str, dict[str, Any]] = {
    "0.2.2-community-r2": {
        "kind": "webui-community",
        "marker": community_r22.MARKER,
        "artifact": "MF885_Community_0.2.2-community-r2-cafe-r2.bin",
        "patcher": "community-r2.2",
        "files": {},
        "safety": {
            "routerRequestsOnPageLoad": [
                "GET locale/status for stock login",
                "at most one opt-in Digest resume attempt and one status1 proof",
                "semantic-read POST GET_RCV_SMS_LOCAL pages after opening Messages",
                "one each of status1, wan and Engineer_parameter after opening Diagnostics",
            ],
            "mutationContract": "one explicitly confirmed SMS send or inbox delete POST, no automatic retry, followed by bounded command status and complete folder readback",
            "mutationUnknownLocksPageSession": True,
            "automaticMutationRetries": 0,
            "tabAuthStoresPlaintextPassword": False,
            "tabAuthStoresPasswordEquivalentHA1": True,
            "languages": ["en"],
            "nativeDetailedLog": False,
            "backgroundDiagnosticsPolling": False,
            "cacheSafeCommunityAssets": True,
            "exactStatus1MutationGate": True,
            "exactStatus1AuthGate": True,
        },
    },
    "0.2.1-community-r2": {
        "kind": "webui-community",
        "marker": community_r21.MARKER,
        "artifact": "MF885_Community_0.2.1-community-r2-cafe-r2.bin",
        "patcher": "community-r2.1",
        "files": {},
        "safety": {
            "routerRequestsOnPageLoad": [
                "GET locale/status for stock login",
                "at most one opt-in Digest resume attempt and one status1 proof",
                "semantic-read POST GET_RCV_SMS_LOCAL pages after opening Messages",
                "one each of status1, wan and Engineer_parameter after opening Diagnostics",
            ],
            "mutationContract": "one explicitly confirmed SMS send or inbox delete POST, no automatic retry, followed by bounded command status and complete folder readback",
            "mutationUnknownLocksPageSession": True,
            "automaticMutationRetries": 0,
            "tabAuthStoresPlaintextPassword": False,
            "tabAuthStoresPasswordEquivalentHA1": True,
            "languages": ["en"],
            "nativeDetailedLog": False,
            "backgroundDiagnosticsPolling": False,
        },
    },
    "0.2-community-r2": {
        "kind": "webui-community",
        "marker": community_r2.MARKER,
        "artifact": "MF885_Community_0.2-community-r2-cafe-r2.bin",
        "patcher": "community-r2",
        "files": {},
        "safety": {
            "routerRequestsOnPageLoad": [
                "GET locale/status for stock login",
                "at most one opt-in Digest resume attempt and one status1 proof",
                "semantic-read POST GET_RCV_SMS_LOCAL pages after opening Messages",
            ],
            "mutationContract": "one explicitly confirmed inbox DELETE_SMS POST followed by bounded status reads and complete inbox readback",
            "mutationUnknownLocksPageSession": True,
            "automaticMutationRetries": 0,
            "tabAuthStoresPlaintextPassword": False,
            "tabAuthStoresPasswordEquivalentHA1": True,
            "languages": ["en"],
        },
    },
    "0.1-community-r1": {
        "kind": "webui-community",
        "marker": b"MF885 Community R1 SMS read-delete 0.1-community-r1",
        "artifact": "MF885_Community_0.1-community-r1-cafe-r2.bin",
        "files": {
            "www\\html\\SMS\\SMS.html": {
                "source": "firmware/community-r1/SMS.html",
                "size": 601,
                "sha256": "64b5dc600ff4aff228439168b4cad5b1a429ca055a11622bb03b3f418ca834a9",
            },
            "www\\js\\panel\\SMS\\SMS.js": {
                "source": "firmware/community-r1/SMS.js",
                "size": 11822,
                "sha256": "5102a7c29ff325d3d9481ceaa0069b273849986b9ef2c8fe9dcc6bff0a99b679",
            },
        },
        "forbidden": (b"SEND_SMS", b"detailed_log", b"canary_logs", b"mfSmsLog"),
        "safety": {
            "routerRequestsOnPageLoad": [
                "GET status1",
                "semantic-read POST GET_RCV_SMS_LOCAL pages",
            ],
            "mutationContract": "one explicitly confirmed inbox DELETE_SMS POST followed by bounded status reads and complete inbox readback",
            "mutationUnknownLocksPageSession": True,
            "automaticMutationRetries": 0,
        },
    },
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

DERIVED_PATCHERS = {
    "community-r2": (community_r2, community_r2.CommunityR2Error),
    "community-r2.1": (community_r21, community_r21.CommunityR21Error),
    "community-r2.2": (community_r22, community_r22.CommunityR22Error),
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
    if specification.get("patcher"):
        raise StageBuildError("derived profile sources require the reviewed golden image")
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
    if any(value.lower() in joined.lower() for value in specification.get("forbidden", ())):
        raise StageBuildError("stage source contains a forbidden profile capability")
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
    _, records, _ = base.parse_cafe_source(webi_payload)
    additions: dict[str, bytes] = {}
    removals: set[str] = set()
    patcher_name = specification.get("patcher")
    if patcher_name:
        if replacements is not None:
            raise StageBuildError("derived Community sources cannot be caller-supplied")
        try:
            patcher, patcher_error = DERIVED_PATCHERS[patcher_name]
        except KeyError as exc:
            raise StageBuildError("derived Community patcher is not reviewed") from exc
        try:
            replacements, additions, removals = patcher.build_patch_set(
                {record.path: record.logical_data for record in records}, ROOT
            )
        except patcher_error as exc:
            raise StageBuildError(str(exc)) from exc
    else:
        replacements = replacements or load_profile_sources(profile)
        for target, source_specification in specification["files"].items():
            if target not in replacements:
                raise StageBuildError("stage replacement set is incomplete")
            validate_profile_source(replacements[target], source_specification)
        if set(replacements) != set(specification["files"]):
            raise StageBuildError("stage replacement set contains an unreviewed path")
    joined = b"\n".join([*replacements.values(), *additions.values()])
    if specification["marker"] not in joined:
        raise StageBuildError("stage marker is absent from the derived sources")
    rebuilt_webi, cafe_report = base.rebuild_cafe(
        webi_payload, replacements, additions, removals
    )
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
        "profile_delta": {
            "replaced_paths": sorted(replacements),
            "added_paths": sorted(additions),
            "removed_paths": sorted(removals),
        },
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
        raise StageBuildError(f"could not write {path.name} atomically") from exc


def derived_source_records(patcher: object) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for target in sorted(patcher.CUSTOM_FILES):
        source, size, digest = patcher.CUSTOM_FILES[target]
        records.append(
            {"target": target, "source": source, "size": size, "sha256": digest}
        )
        seen.add(target)
    for target in sorted(patcher.OUTPUT_RECORDS):
        size, digest = patcher.OUTPUT_RECORDS[target]
        if target not in seen:
            records.append(
                {
                    "target": target,
                    "source": "derived from exact reviewed golden anchors",
                    "size": size,
                    "sha256": digest,
                }
            )
            seen.add(target)
    for target in sorted(getattr(patcher, "ADDITION_OUTPUT_RECORDS", {})):
        size, digest, source = patcher.ADDITION_OUTPUT_RECORDS[target]
        if target not in seen:
            records.append(
                {"target": target, "source": source, "size": size, "sha256": digest}
            )
            seen.add(target)
    return records


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
        identity = inspector.load_identity(args.identity_xml)
        golden_raw = base.require_reviewed_golden(args.golden, identity)
        golden = inspector.inspect_image(args.golden, identity, include_records=True)
        if golden.report["verification"]["status"] != "verified":
            raise StageBuildError("golden did not pass the full independent inspector")
        specification = STAGE_PROFILES[args.profile]
        replacements = (
            None if specification.get("patcher") else load_profile_sources(args.profile)
        )
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
        delta = build_report["profile_delta"]
        expected = delta["replaced_paths"]
        expected_added = delta["added_paths"]
        expected_removed = delta["removed_paths"]
        if (
            changed != expected
            or sorted(cafe.get("added_paths", [])) != expected_added
            or sorted(cafe.get("removed_paths", [])) != expected_removed
        ):
            raise StageBuildError("logical delta is not exactly the reviewed profile")
        source_records = []
        if specification.get("patcher"):
            patcher = DERIVED_PATCHERS[specification["patcher"]][0]
            source_records = derived_source_records(patcher)
        else:
            source_records = [
                {
                    "target": target,
                    "source": specification["files"][target]["source"],
                    "size": len(replacements[target]),
                    "sha256": inspector.sha256(replacements[target]),
                }
                for target in sorted(replacements)
            ]
        report = {
            "schema": "mf885-webui-stage-build/v2",
            "id": f"{args.profile}-cafe2",
            "logical_id": args.profile,
            "container_revision": 2,
            "kind": specification["kind"],
            "marker": specification["marker"].decode("ascii"),
            "source": {
                "size": len(golden_raw),
                "sha256": inspector.sha256(golden_raw),
                "raw_sha256": inspector.sha256(golden_raw),
                "reference_raw_sha256": base.GOLDEN_SHA256,
                "portable_plaintext_sha256": base.REVIEWED_PLAINTEXT_SHA256,
            },
            "artifact": {
                "file": args.output.name,
                "size": len(candidate),
                "sha256": inspector.sha256(candidate),
                "raw_sha256": inspector.sha256(candidate),
                "portable_plaintext_sha256": base.portable_plaintext_sha256(candidate, identity),
            },
            "identity_fingerprint_sha256": identity.fingerprint,
            "sources": source_records,
            "build": build_report,
            "verification": {
                "status": "verified",
                "structurally_verified": True,
                "changed_partitions": [
                    name for name, value in partition_diffs.items() if value
                ],
                "logical_changes": [f"WEBI:replace:{path}" for path in expected]
                + [f"WEBI:add:{path}" for path in expected_added]
                + [f"WEBI:remove:{path}" for path in expected_removed],
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
