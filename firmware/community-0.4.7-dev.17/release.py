"""Private dev17: browser CPU load UI derived from the dev16 browser candidate.

Derived from the dev16 derivation, which already carries automatic local logout
on definitive session expiry (and, through dev15/dev6, manual AT and arbitrary
initial USSD). This module rewrites browser JS/HTML bytes and adds one new
diagnostic XML request file only. It does not touch the native component, the
stock/golden inputs, any earlier release's assets, or any released pin file.

The dev16 -> dev17 rewrite is a pure function of the dev16 asset mapping, so the
regression suite can exercise the real production transform against the pinned
dev16-derived export without the private golden. Final pin generation still
requires the golden-record derivation through build_stages.py `webpins`
(reviewer step).

The CPU measurement itself is native v7 (already compiled and reviewed); this
module only consumes its `cpu2:` wire frame through the pure `cpu.js` module.
It never re-declares the native contract and it makes no hardware claim.
"""
import hashlib,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf885_047d17_source',HERE.parent/'community-0.4.7-dev.16/release.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
PROFILE='0.4.7-dev.17'
MARKER=b'MF885 Community 0.4.7-dev.17 - base 2.5.94'
ARTIFACT='MF885-Community-0.4.7-dev.17-base-2.5.94.bin'
class Error(RuntimeError):pass
once=previous.once
# The pin file path is a separate constant so the fail-closed check can be
# exercised against a temporary directory without relocating the module's own
# read-only inputs (cpu.js is read from HERE and must stay beside release.py).
PINS_FILE=HERE/'web-pins.json'
# apply_cpu_load() operates on the *dev17-named* mapping that derive() produces
# from dev16, so its input key is the dev17 app key. APP_IN is kept as an alias
# of APP_OUT for callers that still speak in "input asset" terms; the production
# mapping never contains two copies of the app.
APP_OUT=r'www\js\c047d17app.js'
APP_IN=APP_OUT
CPU_KEY=r'www\js\c047d17cpu.js'
CPU_XML_KEY=r'www\xmldata\c047d17cpu.xml'
ENTRY_KEY=r'www\c047d17.html'
# Separate diagnostic file: the existing console XML is decoded by a strict
# three-field parser (console_v1, ussd_v1, queue_v1), so cpu_v1 must never be
# added there. Native cc_http_read reads CPU only when console_v1 exists, so
# this file carries console_v1 plus cpu_v1 and nothing else.
CPU_XML=b'<?xml version="1.0" encoding="US-ASCII"?><RGW><diagnostic><console_v1>pending</console_v1><cpu_v1>pending</cpu_v1></diagnostic></RGW>\n'

def revise(raw):
 return raw.replace(b'0.4.7-dev.16',b'0.4.7-dev.17').replace(b'047Dev16',b'047Dev17').replace(b'c047d16',b'c047d17')

# --- CPU load contract -------------------------------------------------------
# One additional sequential GET is appended to the existing shared snapshot
# after the three model reads. It runs under the same snapshot operation lock,
# reuses request()/nextHeader('GET') with expiryCheck:true, captures the
# operation epoch and rejects a late result before decoding, rendering or
# changing the retained baseline. There is no second timer: the existing
# universal refresh (live tick or manual button) drives it every 30 seconds.
#
# A CPU failure clears the CPU value and baseline and shows "unavailable" but
# never blocks the other three valid device reads from rendering. No retry is
# issued. Logout clears the baseline so a previous session's completion cannot
# revive a percentage.

# Injected next to the other transport helpers. cpuDocument validates the wire
# envelope and returns the raw cpu_v1 text; the pure codec validates the frame.
CPU_HELPERS=b'''  function cpuExtension(){return w.MF885Dev17Cpu||null}
  function cpuTransportOwner(owner){if(!session||routerOwner!==owner||owner!=='snapshot')throw fault('E_CPU_SESSION','The CPU read requires the shared snapshot operation lock.')}
  function cpuDocument(reply){if(!reply.body.length||reply.body.length>4096||/[^\\x09\\x0a\\x0d\\x20-\\x7e]/.test(reply.body)||/<!|&/.test(reply.body)||/<\\?/.test(reply.body.replace(/^\\s*<\\?xml\\s[^?]*\\?>/,'')))throw fault('E_CPU_RESPONSE','Invalid CPU response.',reply.requestId);var doc=parseXml(reply.body,reply.requestId),root=doc.documentElement;function children(n){return Array.prototype.filter.call(n.childNodes||[],function(c){return c.nodeType===1})}if(!root||root.nodeName!=='RGW'||root.attributes.length)throw fault('E_CPU_RESPONSE','Invalid CPU root.');var modules=children(root);if(modules.length!==1||modules[0].nodeName!=='diagnostic'||modules[0].attributes.length)throw fault('E_CPU_RESPONSE','Invalid CPU module.');var fields=children(modules[0]),values={};if(fields.length!==2)throw fault('E_CPU_RESPONSE','Invalid CPU fields.');fields.forEach(function(field){if(!/^(console_v1|cpu_v1)$/.test(field.nodeName)||values[field.nodeName]!==undefined||field.attributes.length||Array.prototype.some.call(field.childNodes,function(n){return n.nodeType!==3}))throw fault('E_CPU_RESPONSE','Invalid CPU field.');values[field.nodeName]=field.textContent});return values.cpu_v1}
  function cpuTrackerInstance(){var codec=cpuExtension();if(!codec)return null;if(!cpuTracker)cpuTracker=codec.createTracker();return cpuTracker}
  function cpuReset(){cpuTracker=null;cpuSnapshot=null;cpuReadState=null;renderCpu(null)}
  function cpuLabel(value){return value===null||value===undefined?'Unavailable':value}
  function cpuSummaryText(){if(!cpuSnapshot)return 'CPU load unavailable.';if(cpuSnapshot.state==='valid')return 'CPU load '+cpuSnapshot.percentage.toFixed(1)+'% over '+cpuSnapshot.intervalSeconds.toFixed(1)+'s.';if(cpuSnapshot.state==='warming')return 'CPU load warming up (no complete sampling interval yet).';return 'CPU load unavailable.'}
  function renderCpu(state){var home=node('dashboardCpu'),detail=node('diagnosticsCpu');if(!home||!detail)return;if(state&&state.state==='valid'){home.textContent=state.percentage.toFixed(1)+'%';detail.textContent='Last CPU measurement: '+state.percentage.toFixed(1)+'%, measured over '+state.intervalSeconds.toFixed(1)+' seconds at '+capturedTime(state.capturedAt)+'. Experimental measurement; awaiting verification on the router.'}else if(state&&state.state==='warming'){home.textContent='Warming up';detail.textContent='Waiting for the next CPU sample. The measurement updates with device data.'}else{home.textContent='Unavailable';detail.textContent='CPU measurement is unavailable. Refresh device data to try again.'}}

'''
ANCHOR_OWNER=b'  function ussdOwner(owner){'

def _cpu_helpers(app):
 return once(app,ANCHOR_OWNER,CPU_HELPERS+ANCHOR_OWNER)

def _cpu_tracker_state(app):
 # The tracker is a module-level singleton so its baseline survives across
 # snapshots; it is reset (never re-created) on logout.
 return once(app,b"var session=null,requestEpoch=1,expiryHandled=0,operationToken=0,currentRequest=null,routerOwner=null,",
  b"var session=null,requestEpoch=1,expiryHandled=0,operationToken=0,currentRequest=null,routerOwner=null,cpuTracker=null,cpuSnapshot=null,cpuReadState=null,")

# dev16 already fences next(); the CPU read is chained after next() resolves and
# before the snapshot is published, still on the same sequential flow and lock.
NEXT_TAIL_ANCHOR=b"    return next().then(function(){if(operationEpoch!==requestEpoch)throw staleFault();snapshot.completedAt=Date.now();"

CPU_READ=b"""    function readCpu(){cpuTransportOwner('snapshot');var codec=cpuExtension();if(!codec){cpuReadState='module-unavailable';cpuSnapshot={state:'unavailable'};return Promise.resolve(null)}status('diagnosticsStatus','Snapshot '+snapshot.id+' \xc2\xb7 reading CPU load\xe2\x80\xa6');return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=c047d17cpu',authorization:nextHeader('GET'),owner:'snapshot',expiryCheck:true}).then(function(reply){if(operationEpoch!==requestEpoch)throw staleFault();return cpuDocument(reply)}).then(function(wire){if(operationEpoch!==requestEpoch)throw staleFault();var tracker=cpuTrackerInstance();if(!tracker){cpuReadState='module-unavailable';cpuSnapshot={state:'unavailable'};return null}var state=tracker.observe(wire);cpuReadState=state.state;cpuSnapshot=state;return null},function(error){if(operationEpoch!==requestEpoch)throw staleFault();if(cpuTracker)cpuTracker.reset();cpuReadState='unavailable';cpuSnapshot={state:'unavailable'};if(w.console&&typeof w.console.debug==='function')privateLog('debug','[MF885]['+snapshot.id+'] CPU read failed',{endpoint:'cpu',errorCode:error&&error.mfCode||'E_CPU_UNAVAILABLE'});return null})}
"""

def _cpu_snapshot_read(app):
 # CPU runs strictly after all three model reads and shares the snapshot lock.
 # A CPU failure resolves to null here; it never rejects or blocks the three
 # already-collected model endpoints from rendering.
 return once(app,NEXT_TAIL_ANCHOR,
  CPU_READ+b"    return next().then(function(){if(operationEpoch!==requestEpoch)throw staleFault();return readCpu()}).then(function(){if(operationEpoch!==requestEpoch)throw staleFault();snapshot.cpu=cpuSnapshot;snapshot.completedAt=Date.now();")

def _cpu_summary(app):
 # Summary text states the CPU state next to the three device endpoints; a CPU
 # failure is never reported as a device-endpoint failure.
 return once(app,b"var summary='Snapshot '+snapshot.id+' \xc2\xb7 '+successes+'/3 endpoints \xc2\xb7 '+capturedTime(snapshot.completedAt)+'.';if(failures.length)summary+=' '+failures.join(' \xc2\xb7 ');if(liveEnabled)summary+=' Next universal device refresh in 30 seconds.';",
  b"var summary='Snapshot '+snapshot.id+' \xc2\xb7 '+successes+'/3 device endpoints \xc2\xb7 '+capturedTime(snapshot.completedAt)+'.';if(failures.length)summary+=' '+failures.join(' \xc2\xb7 ');summary+=' '+cpuSummaryText();if(liveEnabled)summary+=' Next universal device refresh in 30 seconds.';")

def _cpu_render(app):
 # Rendering happens inside renderSnapshot, after the publish guard, so a
 # failed or stale CPU read shows unavailable without hiding valid device data.
 return once(app,b"renderValues('diagnosticsValues',diagnosticsRows(snapshot));renderValues('modemValues',modemRows(snapshot));renderWan(snapshot);renderSources('diagnosticsSources',snapshot);",
  b"renderValues('diagnosticsValues',diagnosticsRows(snapshot));renderValues('modemValues',modemRows(snapshot));renderWan(snapshot);renderSources('diagnosticsSources',snapshot);renderCpu(snapshot.cpu||null);")

def _cpu_logout_reset(app):
 # Logout clears the retained baseline and every rendered CPU value. Because
 # requestEpoch advances inside finishLocalLogout, a completion from the ended
 # session is rejected by the epoch guards and cannot revive a percentage.
 return once(app,b"messages=[];messagesComplete=false;messagesMutationSafe=false;mutationBusy=false;mutationLocked=false;diagnosticsSnapshot=null;snapshotBusy=false;bootstrapBusy=false;nextSnapshotAt=0;nextMessagesAt=0;lastMessagesAt=null;",
  b"messages=[];messagesComplete=false;messagesMutationSafe=false;mutationBusy=false;mutationLocked=false;diagnosticsSnapshot=null;snapshotBusy=false;bootstrapBusy=false;nextSnapshotAt=0;nextMessagesAt=0;lastMessagesAt=null;cpuReset();")

def _cpu_get_ceiling(app):
 # The shared snapshot now performs four GETs instead of three; the live log
 # must state the true ceiling. Endpoint safety is unchanged (same lock, same
 # sequential ordering, no retry).
 return once(app,b"liveLog(id,'dispatch',{kind:'shared-snapshot',getCeiling:3})",
  b"liveLog(id,'dispatch',{kind:'shared-snapshot',getCeiling:4,cpuGetCeiling:1})")

STEPS=(_cpu_helpers,_cpu_tracker_state,_cpu_snapshot_read,_cpu_summary,_cpu_render,_cpu_logout_reset,_cpu_get_ceiling)

def app_transform(app):
 """Apply the dev17 CPU-load rewrite to already dev17-revised app bytes."""
 if b'0.4.7-dev.16' in app:raise Error('apply_cpu_load expects dev17-revised bytes')
 for step in STEPS:app=step(app)
 return app

def _entry_cpu_card(entry):
 # Home card in the dashboard grid and a Diagnostics status block, plus the
 # cpu.js script tag. Favicon/touch icons and their head references are kept.
 entry=once(entry,b'<article><strong id="dashboardMessages">Loading\xe2\x80\xa6</strong><span>Latest messages</span></article>',
  b'<article><strong id="dashboardMessages">Loading\xe2\x80\xa6</strong><span>Latest messages</span></article>\n          <article><strong id="dashboardCpu">Loading\xe2\x80\xa6</strong><span>CPU load - last measurement</span></article>')
 entry=once(entry,b'<div id="diagnosticsSources" class="source-grid" aria-label="Diagnostics source health"></div>',
  b'<div id="diagnosticsSources" class="source-grid" aria-label="Diagnostics source health"></div>\n        <h2 class="subheading">CPU load</h2>\n        <p id="diagnosticsCpu" class="status" role="status" aria-live="polite">CPU load is read with the shared device snapshot. Experimental measurement; awaiting verification on the router.</p>')
 entry=once(entry,b'  <script defer src="js/c047d17console.js"></script>',
  b'  <script defer src="js/c047d17console.js"></script>\n  <script defer src="js/c047d17cpu.js"></script>')
 return entry

def apply_cpu_load(assets):
 """Pure dev17-asset -> dev17-asset transform used by derive() and the tests.

 Input keys and app bytes must already carry the dev17 names, exactly as
 derive() produces them from dev16 before this step runs.
 """
 if APP_OUT not in assets:raise Error('dev17 app asset missing')
 if ENTRY_KEY not in assets:raise Error('dev17 entry asset missing')
 out=dict(assets)
 out[APP_OUT]=app_transform(assets[APP_OUT])
 out[ENTRY_KEY]=_entry_cpu_card(assets[ENTRY_KEY])
 out[CPU_KEY]=(HERE/'cpu.js').read_bytes()
 out[CPU_XML_KEY]=CPU_XML
 css=r'www\css\c047d17ui.css'
 out[css]=once(out[css],b'.cards{display:grid;grid-template-columns:repeat(3,1fr)',b'.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))')
 return out

def derive(records,root):
 replacements,assets,removed=previous.build_patch_set(records,root)
 replacements={p:revise(raw) for p,raw in replacements.items()}
 # Rename dev16 -> dev17 first, then run the CPU rewrite in place on the
 # already-revised dev17 app and entry bytes. No two copies are ever held.
 assets={p.replace('c047d16','c047d17'):revise(raw) for p,raw in assets.items()}
 assets=apply_cpu_load(assets)
 return replacements,assets,removed

def build_patch_set(records,root):
 replacements,assets,removed=derive(records,root)
 actual={p:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for p,raw in {**replacements,**assets}.items()}
 pins=PINS_FILE
 if not pins.exists():raise Error('dev17 web-pins.json is absent; run build_stages.py webpins with the golden inputs')
 if actual!=json.loads(pins.read_bytes()):raise Error('dev17 asset pin mismatch')
 return replacements,assets,removed
