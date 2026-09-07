"""Private exact-golden registration for the TTL and Engineering editor."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(ROOT / 'firmware/community-0.4.7-dev.2'), str(ROOT / 'tools')]
import release
import native_payload
import mf885_webui_stage_builder as stage
import mf885_exact_golden_comparator_builder as comparator
import mf885_firmware_inspect as inspector
import mf885_webi_builder as webi
import mf885_community_r30_native_builder as shared
PROFILE = release.PROFILE
ARTIFACT = release.ARTIFACT
stage.STAGE_PROFILES[PROFILE] = {
    **stage.STAGE_PROFILES['0.4.5-community-r2'],
    'marker': release.MARKER,
    'artifact': 'MF885-Community-0.4.7-dev.5-base-2.5.94-web-only.bin',
    'patcher': 'private-047d5',
    'safety': {
        **stage.STAGE_PROFILES['0.4.5-community-r2']['safety'],
        'diagnosticGetCallbacks': 1, 'diagnosticSetCallbacks': 1,
        'ttlAvailable': True, 'ttlMode': 'private-guided-64-off-editor',
        'ttlGenerationFreshness': False, 'ttlAutomaticReads': 0,
        'ttlReadGetCeiling': 2, 'ttlWriteGetCeiling': 3,
        'ttlWritePostCeiling': 1, 'ttlAutomaticRetries': 0,
        'ttlBrowserValues': ['64', 'off'],
        'engineeringAvailable': True, 'engineeringInterval': '1',
        'engineeringWriteGetCeiling': 2, 'engineeringWritePostCeiling': 1,
        'engineeringAutomaticRetries': 0, 'engineeringPostTimeoutMs': 60000, 'rawResponseBodiesLogged': False,
        'buildPinned': True,
        'externalQualificationContract': 'Native bytes identical to tested dev.2; changed UI requires its own hardware qualification before publication.',
    },
}
stage.DERIVED_PATCHERS['private-047d5'] = (release, release.Error)

def native_conditions(report, safety):
    c = comparator.condition
    x = report['contract']
    return [c('boot_ttl', 64, x['boot_ttl']), c('one_word_state_store', 1, x['set_global_stores']), c('get_no_state_store', 0, x['get_global_stores']), c('packet_no_state_store', 0, x['forward_global_stores']), c('own_ram_start', 0x070ad234, x['state_runtime']), c('own_ram_bytes', 4, x['state_bytes']), c('no_generation_freshness', False, x['revision_freshness']), c('browser_values', ['64', 'off'], safety['ttlBrowserValues']), c('no_browser_retry', 0, safety['ttlAutomaticRetries']), c('no_automatic_ttl_reads', 0, safety['ttlAutomaticReads'])]

def build_candidate(golden, identity):
    return comparator.build_candidate(golden, identity, profile=PROFILE, schema='mf885-047d5-private-build/v1', label=PROFILE, native_build=native_payload.build_payload, error=release.Error)

def verify_candidate(golden, image, identity):
    return comparator.verify_candidate(golden, image, identity, profile=PROFILE, verification_schema='mf885-047d5-private-verify/v1', label=PROFILE, native_build=native_payload.build_payload, native_conditions=native_conditions, error=release.Error)
