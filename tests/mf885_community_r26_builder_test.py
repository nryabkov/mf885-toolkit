import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mf885_community_r26 as community_r26  # noqa: E402
import mf885_firmware_inspect as inspector  # noqa: E402
import mf885_webui_stage_builder as stage  # noqa: E402


LOCAL_GOLDEN = Path(os.environ.get("MF885_TEST_GOLDEN", "__missing_golden_fixture__"))
LOCAL_IDENTITY = Path(os.environ.get("MF885_TEST_IDENTITY", "__missing_identity_fixture__"))


class CommunityR26BuilderTests(unittest.TestCase):
    def test_profile_is_registered_pinned_and_non_blocking(self):
        specification = stage.STAGE_PROFILES[community_r26.PROFILE]
        safety = specification["safety"]
        self.assertEqual(specification["patcher"], "community-r2.6")
        self.assertEqual(specification["marker"], community_r26.MARKER)
        self.assertEqual(safety["routerRequestsOnPageLoad"], [])
        self.assertEqual(safety["requestTimeoutSeconds"], 10)
        self.assertTrue(safety["expectedClientFailuresVisible"])
        self.assertTrue(safety["unexpectedClientFailuresVisible"])
        self.assertEqual(
            safety["clientErrorCorrelation"],
            "stable error code plus per-session request or JavaScript error ID",
        )
        self.assertFalse(safety["clientConsoleLogsQueryStrings"])
        self.assertFalse(safety["clientRawResponsesVisible"])
        self.assertFalse(safety["automaticReadPolling"])
        self.assertEqual(safety["automaticMutationRetries"], 0)
        self.assertTrue(safety["mutationUnknownLocksPageSession"])
        self.assertFalse(safety["tabAuthStoresPlaintextPassword"])
        self.assertFalse(safety["tabAuthStoresPasswordEquivalentHA1"])
        self.assertFalse(safety["legacyBlockingStackLoaded"])
        self.assertFalse(safety["engineeringModeMutationEnabled"])
        self.assertFalse(safety["firmwareControlEnabled"])
        self.assertTrue(safety["buildPinned"])
        self.assertEqual(len(community_r26.OUTPUT_RECORDS), 6)
        self.assertEqual(len(community_r26.ADDITION_OUTPUT_RECORDS), 3)
        self.assertEqual(len(community_r26.REMOVED_RECORDS), 18)
        self.assertEqual(
            {item["target"] for item in stage.derived_source_records(community_r26)},
            set(community_r26.OUTPUT_RECORDS) | set(community_r26.CUSTOM_FILES),
        )
        with self.assertRaisesRegex(stage.StageBuildError, "reviewed golden"):
            stage.load_profile_sources(community_r26.PROFILE)

    @unittest.skipUnless(
        LOCAL_GOLDEN.is_file() and LOCAL_IDENTITY.is_file(),
        "exact private golden and identity are optional in CI",
    )
    def test_exact_golden_build_is_deterministic_minimal_and_non_blocking(self):
        raw = LOCAL_GOLDEN.read_bytes()
        identity = inspector.load_identity(LOCAL_IDENTITY)
        first, first_report = stage.build_stage_image(raw, identity, community_r26.PROFILE)
        second, second_report = stage.build_stage_image(raw, identity, community_r26.PROFILE)
        self.assertEqual(first, second)
        self.assertEqual(first_report, second_report)
        self.assertEqual(len(first), 8_323_644)
        delta = first_report["profile_delta"]
        self.assertEqual(len(delta["replaced_paths"]), 6)
        self.assertEqual(delta["added_paths"], sorted(community_r26.CUSTOM_FILES))
        self.assertEqual(delta["removed_paths"], sorted(community_r26.REMOVED_RECORDS))
        self.assertGreaterEqual(first_report["cafe"]["padding_after"], 200_000)

        header = inspector.decrypt_header(first, identity)
        partitions, layout_errors = inspector.parse_partitions(header, len(first))
        self.assertEqual(layout_errors, [])
        for partition in partitions:
            if partition.name != "WEBI":
                start, end = partition.offset, partition.offset + partition.length
                self.assertEqual(first[start:end], raw[start:end], partition.name)
        webi = next(item for item in partitions if item.name == "WEBI")
        _, records, _ = stage.base.parse_cafe_source(
            first[webi.offset : webi.offset + webi.length]
        )
        logical = {record.path: record.logical_data for record in records}
        self.assertEqual(logical[community_r26.ENTRY_PATH], (ROOT / community_r26.CUSTOM_FILES[community_r26.ENTRY_PATH][0]).read_bytes())
        self.assertEqual(logical[community_r26.APP_PATH], (ROOT / community_r26.CUSTOM_FILES[community_r26.APP_PATH][0]).read_bytes())
        self.assertEqual(logical[community_r26.CSS_PATH], (ROOT / community_r26.CUSTOM_FILES[community_r26.CSS_PATH][0]).read_bytes())
        self.assertNotIn("www\\r25.html", logical)
        self.assertEqual(logical["www\\index.html"].count(b'href="/r26.html"'), 1)
        self.assertEqual(logical["www\\html\\adminApp.html"].count(b'href="/r26.html"'), 1)
        entry = logical[community_r26.ENTRY_PATH]
        app = logical[community_r26.APP_PATH]
        self.assertNotIn(b"initIndex", entry)
        self.assertNotIn(b"ajax_calls.js", entry)
        self.assertNotIn(b"async:false", app.replace(b" ", b""))
        self.assertNotIn(b"setInterval", app)
        self.assertNotIn(b"RestoreFw", app)


if __name__ == "__main__":
    unittest.main()
