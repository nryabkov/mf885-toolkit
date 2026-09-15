"""Private cumulative dev18 container builder; installation requires operator approval for this exact candidate.

dev18 inherits the dev17 native component unchanged (see native_payload.py), so
the native conditions and architecture checks are the reviewed dev17 ones. Only
the browser TTL capability record changes: the editor now truthfully reports
off or a manual 1..255 with the boot default 64.
"""
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
release=module('mf885_047d18_release','release.py')
native=module('mf885_047d18_native','native_payload.py')
PROFILE=release.PROFILE;ARTIFACT=release.ARTIFACT
stage.STAGE_PROFILES[PROFILE]={**stage.STAGE_PROFILES['0.4.5-community-r2'],
 'marker':release.MARKER,'artifact':'MF885-Community-0.4.7-dev.18-base-2.5.94-web-only.bin','patcher':'private-047d18',
 'safety':{**stage.STAGE_PROFILES['0.4.5-community-r2']['safety'],
   'ttlAvailable':True,'ttlBrowserModes':['off','manual'],'ttlBrowserRange':[1,255],'ttlBrowserDefault':64,
   'ttlAutomaticRetries':0,'themeChoices':['system','light','dark'],'themeDefault':'system','themeRouterWrites':0,
   'ussdAvailable':True,'ussdNativeProtocol':'u4','ussdUserInput':True,'consoleNativeProtocol':'c1','atPanel':True,
   'ussdPostRetryCeiling':0,'ussdCarrierResultAttribution':True,
   'cpuAvailable':True,'cpuNativeProtocol':'cpu2','cpuHardwareQualified':False,
   'sessionExpiryLogout':True,'sessionExpiryRelogin':True,'sessionExpiryAutoRetry':0,
   'hardwareQualified':False,'buildPinned':True,
   'externalQualificationContract':'Reference dev18 installed on one MF96 Ver.D/base2.5.94: assets, theme and bounded TTL packet observations checked. CPU accuracy and long-term USB stability remain unqualified. Each rebuilt output requires its own qualification; see docs/TTL_THEME_047D18_RU.md.'}}
stage.DERIVED_PATCHERS['private-047d18']=(release,release.Error)

def native_conditions(report,safety):
 c=comparator.condition;u=report['ussd'];t=report['contract'];n=report['console']
 return [c('theme_choices',['system','light','dark'],safety['themeChoices']),c('theme_default','system',safety['themeDefault']),c('theme_router_writes',0,safety['themeRouterWrites']),c('ttl_browser_range',[1,255],safety['ttlBrowserRange']),c('ttl_browser_default',64,safety['ttlBrowserDefault']),c('native_unchanged',True,report['native_unchanged_from_dev17']),c('native_exact',native.COMPONENT_SHA,n['component_sha256']),c('native_architecture_elf',native.ELF_SHA,n['inspection']['elf_sha256']),
  c('native_page_leaves_veneers',True,u['payload_bytes']<=4080),c('console_window_fits',True,n['inspection']['bytes']<=8192),c('variable_ussd',True,safety['ussdUserInput']),c('console_protocol','c1',safety['consoleNativeProtocol']),c('ttl_bytes_preserved',True,u['ttl_preserved']),
  c('ussd_post_consumed_before_PSM',True,u['http_consume_v18']),c('ussd_session_claim',True,u['http_session_v17']),
  c('boot_ttl',64,t['boot_ttl']),c('one_word_ttl_store',1,t['set_global_stores']),c('ttl_get_no_store',0,t['get_global_stores']),
  c('ussd_no_retry',0,safety['ussdPostRetryCeiling']),c('ussd_protocol','u4',safety['ussdNativeProtocol']),
  c('session_expiry_no_retry',0,safety['sessionExpiryAutoRetry']),
  c('cpu_protocol','cpu2',safety['cpuNativeProtocol']),c('cpu_arena_size',3676,n['arena_bytes']['v7_with_cpu']),
  c('cpu_hook_names',['cpu-idle-begin','cpu-idle-end','cpu-irq-exit'],n['extra_patch_allowlist']),
  c('cpu_hook_widths',[4,4,4],[x['bytes'] for x in n['patches'] if x['name'] in n['extra_patch_allowlist']])]

def verify_candidate(golden,image,identity):
 return comparator.verify_candidate(golden,image,identity,profile=PROFILE,
  verification_schema='mf885-047d18-private-verify/v1',label=PROFILE,
  native_build=native.build_payload,native_conditions=native_conditions,error=release.Error)
