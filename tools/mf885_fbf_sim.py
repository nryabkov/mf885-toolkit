#!/usr/bin/env python3
"""Deterministically model the reviewed WEBI FBF loop without writing anything.

This command reads two local artifacts and prints JSON.  It has no output-file,
router, Stage 0, publish, reset, or firmware-submission path.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import mf885_fbf as fbf


REVIEWED_FBF_BYTES = 1_843_200
REVIEWED_FBF_SHA256 = (
    "63e040d385b29d2732c06cabee81e3f85d6fd000e8661b22eb049627e91460a7"
)
SCENARIOS = ("success", "worker-return-minus-five")


class SimulationError(Exception):
    """Raised when the requested offline model is ambiguous or unreviewed."""


def _read(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise SimulationError(f"could not read {label}") from exc


def simulate_native_webi(
    parsed: fbf.ParsedFbf,
    initial_partition: bytes,
    *,
    scenario: str = "success",
    fail_record: int | None = None,
) -> dict[str, Any]:
    """Return a planned native-like trace while mutating only an in-memory copy.

    For ``worker-return-minus-five``, records before ``fail_record`` are modeled
    as complete.  The failing record and everything after it remain unknown;
    this deliberately does not invent a mid-erase or mid-write final image.
    """

    plan = fbf.webi_only_write_plan(parsed)
    if len(initial_partition) != fbf.WEBI_FLASH_BYTES:
        raise SimulationError("initial WEBI has the wrong partition size")
    if scenario not in SCENARIOS:
        raise SimulationError("unknown simulation scenario")
    if scenario == "success":
        if fail_record is not None:
            raise SimulationError("success scenario does not accept a failure record")
        completed_records = len(plan)
    else:
        if isinstance(fail_record, bool) or not isinstance(fail_record, int):
            raise SimulationError("worker failure requires an explicit record index")
        if fail_record < 0 or fail_record >= len(plan):
            raise SimulationError("failure record is outside the reviewed write plan")
        completed_records = fail_record

    state = bytearray(initial_partition)
    steps: list[dict[str, Any]] = []
    for record, entry in zip(parsed.records[:completed_records], plan):
        start = record.flash_address - fbf.WEBI_FLASH_ADDRESS
        end = start + record.extent_bytes
        if start < 0 or end > len(state):
            raise SimulationError("record escaped the modeled WEBI partition")
        before_sha = fbf.sha256(state[start:end])
        state[start:end] = b"\xFF" * record.extent_bytes
        erased_sha = fbf.sha256(state[start:end])
        payload = parsed.raw[
            record.data_offset : record.data_offset + record.stored_bytes
        ]
        state[start : start + record.stored_bytes] = payload
        steps.append(
            {
                **entry,
                "planned_only": True,
                "before_extent_sha256": before_sha,
                "erased_extent_sha256": erased_sha,
                "after_extent_sha256": fbf.sha256(state[start:end]),
                "partition_sha256_after_step": fbf.sha256(state),
            }
        )

    success = scenario == "success"
    known_state_sha = fbf.sha256(state)
    events: list[dict[str, Any]] = [
        {"phase": "strict-profile", "result": "pass", "planned_only": True},
        {"phase": "version-hardware-gate", "result": "not-evaluated", "modeled_assumption": "pass", "planned_only": True},
        {"phase": "battery-gate", "result": "not-evaluated", "modeled_assumption": "pass", "planned_only": True},
        {"phase": "pre-flash-hook", "result": "would-call", "planned_only": True},
    ]
    if success:
        events.extend(
            [
                {"phase": "upgrade-status", "value": 2, "planned_only": True},
                {"phase": "retained-selector", "value": "MAXS", "planned_only": True},
                {"phase": "reset-magic", "value": "0x12344321", "planned_only": True},
                {"phase": "upgrade-status", "value": 1, "planned_only": True},
                {"phase": "delay", "wait_units": 600, "planned_only": True},
                {"phase": "reset", "result": "would-call", "planned_only": True},
            ]
        )
    else:
        events.extend(
            [
                {
                    "phase": "record-failure",
                    "record_index": fail_record,
                    "result": "worker-return-minus-five",
                    "planned_only": True,
                },
                {"phase": "retained-selector", "value": "MINS", "planned_only": True},
                {"phase": "upgrade-status", "value": 3, "planned_only": True},
            ]
        )

    return {
        "schema": "mf885-webi-native-write-simulation/v1",
        "artifact": {
            "bytes": len(parsed.raw),
            "sha256": fbf.sha256(parsed.raw),
            "strict_webi_only_profile_verified": True,
        },
        "initial_partition": {
            "bytes": len(initial_partition),
            "sha256": fbf.sha256(initial_partition),
            "matches_reviewed_stock_webi": fbf.sha256(initial_partition)
            == fbf.OFFICIAL_C2_2589_WEBI_SHA256,
        },
        "model": {
            "scenario": scenario,
            "total_records": len(plan),
            "completed_records": completed_records,
            "failed_record": None if success else fail_record,
            "failed_record_and_remainder_state": "known" if success else "unknown",
            "native_would_erase_bytes": sum(item["erase_bytes"] for item in plan),
            "native_would_write_bytes": sum(item["write_bytes"] for item in plan),
            "known_prefix_state_sha256": known_state_sha,
            "modeled_final_partition_sha256": known_state_sha if success else None,
            "matches_reviewed_observer_webi": success
            and known_state_sha == fbf.CUSTOM_WEBI_SHA256,
            "steps": steps,
            "events": events,
        },
        "limitations": {
            "live_fbf_acceptance_proven": False,
            "mid_record_failure_state_known": False,
            "flash_hardware_behavior_proven": False,
            "native_partition_whitelist_identified": False,
            "native_readback_identified": False,
            "rollback_or_ab_fallback_identified": False,
            "post_reset_boot_proven": False,
            "qualified_mins_entry": False,
        },
        "safety": {
            "offline_only": True,
            "planned_operations_only": True,
            "filesystem_writes_attempted": 0,
            "router_requests_attempted": 0,
            "firmware_posts_attempted": 0,
            "flash_bytes_actually_written": 0,
            "reset_attempted": False,
            "flash_qualified": False,
        },
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Model the reviewed MF885 WEBI FBF path without writing anything"
    )
    value.add_argument("--image", type=Path, required=True)
    value.add_argument("--initial-webi", type=Path, required=True)
    value.add_argument("--scenario", choices=SCENARIOS, default="success")
    value.add_argument("--fail-record", type=int)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        raw = _read(args.image, "reviewed NOFLASH FBF")
        if len(raw) != REVIEWED_FBF_BYTES or fbf.sha256(raw) != REVIEWED_FBF_SHA256:
            raise SimulationError("image is not the exact reviewed NOFLASH FBF")
        initial = _read(args.initial_webi, "reviewed stock WEBI")
        if fbf.sha256(initial) != fbf.OFFICIAL_C2_2589_WEBI_SHA256:
            raise SimulationError("initial WEBI is not the exact reviewed stock partition")
        result = simulate_native_webi(
            fbf.parse_fbf(raw),
            initial,
            scenario=args.scenario,
            fail_record=args.fail_record,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (SimulationError, fbf.FbfError) as exc:
        print(f"simulation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
