"""Offline dev15 container builder. Reference hardware results are documented separately; no device access."""
import importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
import mf885_webui_stage_builder as stage
import mf885_exact_golden_comparator_builder as comparator
import mf885_firmware_inspect as inspector
import mf885_webi_builder as webi
import mf885_community_r30_native_builder as shared

def module(name,file):
 spec=importlib.util.spec_from_file_location(name,HERE/file);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
release=module('mf885_047d15_release','release.py')
native=module('mf885_047d15_native','native_payload.py')
PROFILE=release.PROFILE;ARTIFACT=release.ARTIFACT
stage.STAGE_PROFILES[PROFILE]={**stage.STAGE_PROFILES['0.4.5-community-r2'],
 'marker':release.MARKER,'artifact':'MF885-Community-0.4.7-dev.15-base-2.5.94-web-only.bin','patcher':'private-047d15',
 'safety':{**stage.STAGE_PROFILES['0.4.5-community-r2']['safety'],
   'ttlAvailable':True,'ttlBrowserValues':['64','off'],'ttlAutomaticRetries':0,
   'ussdAvailable':True,'ussdNativeProtocol':'u4','ussdUserInput':True,'consoleNativeProtocol':'c1','atPanel':True,
   'ussdPostRetryCeiling':0,'ussdCarrierResultAttribution':True,
   'hardwareQualified':False,'buildPinned':True,
   'externalQualificationContract':'Private candidate; USSD association is conditional on complete native ID observation; hardware and recovery test required before publication.'}}
stage.DERIVED_PATCHERS['private-047d15']=(release,release.Error)

def native_conditions(report,safety):
 c=comparator.condition;u=report['ussd'];t=report['contract'];n=report['console']
 return [c('native_exact',native.COMPONENT_SHA,n['component_sha256']),c('native_architecture_elf',native.ELF_SHA,n['inspection']['elf_sha256']),
  c('native_page_leaves_veneers',True,u['payload_bytes']<=4080),c('console_window_fits',True,n['inspection']['bytes']<=8192),c('variable_ussd',True,safety['ussdUserInput']),c('console_protocol','c1',safety['consoleNativeProtocol']),c('ttl_bytes_preserved',True,u['ttl_preserved']),
  c('ussd_post_consumed_before_PSM',True,u['http_consume_v18']),c('ussd_session_claim',True,u['http_session_v17']),
  c('boot_ttl',64,t['boot_ttl']),c('one_word_ttl_store',1,t['set_global_stores']),c('ttl_get_no_store',0,t['get_global_stores']),
  c('ussd_no_retry',0,safety['ussdPostRetryCeiling']),c('ussd_protocol','u4',safety['ussdNativeProtocol'])]

def verify_candidate(golden,image,identity):
 return comparator.verify_candidate(golden,image,identity,profile=PROFILE,
  verification_schema='mf885-047d15-private-verify/v1',label=PROFILE,native_build=native.build_payload,native_conditions=native_conditions,error=release.Error)
