"""Private dev18: user-authorized manual TTL input 1..255 with retained Off.

Derived from the dev17 derivation, which already carries native console v7 CPU
accounting, automatic local logout on definitive session expiry, manual AT and
arbitrary initial USSD. This module rewrites browser JS/HTML/JSON/CSS bytes only.
It does not touch the native component, the stock/golden inputs, any earlier
release's assets, or any released pin file.

The dev18 TTL editor keeps the exact dev17 transport shape (one explicit read,
one baseline revision check, a single POST, strict ACK, a separate readback, no
retry, RAM-only state) and only widens the accepted canonical argument from
{off,64} to {off} plus decimal 1..255. That is exactly the native dev2 TTL
contract (r47-revision24-ttl8), so the native component is reused unchanged;
dev18 ships no native change and requires no native compile.

The dev17 -> dev18 rewrite is a pure function of the dev17 asset mapping, so the
regression suite can exercise the real production transform against the pinned
dev17-derived export without the private golden. Final pin generation still
requires the golden-record derivation through build_stages.py `webpins`
(reviewer step).
"""
import hashlib,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf885_047d18_source',HERE.parent/'community-0.4.7-dev.17/release.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
# The theme step lives in its own module beside this file. The import is late
# (after `previous`) because theme.py re-enters this module for `once`, the
# shared keys and the dev18 Error class.
_theme_spec=importlib.util.spec_from_file_location('mf885_047d18_theme',HERE/'theme.py')
theme=importlib.util.module_from_spec(_theme_spec)
PROFILE='0.4.7-dev.18'
MARKER=b'MF885 Community 0.4.7-dev.18 - base 2.5.94'
ARTIFACT='MF885-Community-0.4.7-dev.18-base-2.5.94.bin'
class Error(RuntimeError):pass
once=previous.once
# Split so the fail-closed check can run against a temporary directory without
# relocating the module's own read-only inputs (release.py stays beside HERE).
PINS_FILE=HERE/'web-pins.json'
APP_OUT=r'www\js\c047d18app.js'
APP_IN=APP_OUT
TTL_KEY=r'www\js\c047d18ttl.js'
TTL_JSON_KEY=r'www\c047d18ttl.json'
ENTRY_KEY=r'www\c047d18.html'
TTL_CSS_KEY=r'www\css\c047d18ttl.css'
THEME_CSS_KEY=r'www\css\c047d18theme.css'
THEME_JS_KEY=r'www\js\c047d18theme.js'
# theme.py needs the shared names from this module (`once`, the dev18 Error
# class, the asset keys). It cannot import this file back, so the executing
# module object is handed to it instead. Callers that load this module through
# spec_from_file_location (the fixture generator, the webpin stage) do not
# register it in sys.modules, so the frame globals are the reliable reference.
_theme_spec.loader.exec_module(theme)
theme.bind(sys.modules.get(__name__) or globals())

def revise(raw):
 return raw.replace(b'0.4.7-dev.17',b'0.4.7-dev.18').replace(b'047Dev17',b'047Dev18').replace(b'c047d17',b'c047d18')

# --- Capability contract -----------------------------------------------------
# The exact capability document is compared byte-for-byte by the editor, so the
# JSON asset and the literal inside ttl.js must stay identical. It truthfully
# describes the retained modes (off or manual) and the inclusive manual range.
CAPABILITY=b'{"schema":"mf885-ttl-editor/v1","communityVersion":"0.4.7-dev.18","vendorBase":"2.5.94","nativeApi":"r47-revision24-ttl8","modes":["off","manual"],"manualRange":{"min":1,"max":255,"step":1,"canonical":"decimal"},"settings":["off","1-255"],"default":64,"persistence":"ram","bootTtl":64}\n'
CAPABILITY_LITERAL_OLD=b"  var capabilityText = '{\"schema\":\"mf885-ttl-editor/v1\",\"communityVersion\":\"0.4.7-dev.18\",\"vendorBase\":\"2.5.94\",\"nativeApi\":\"r47-revision24-ttl8\",\"settings\":[\"64\",\"off\"],\"persistence\":\"ram\",\"bootTtl\":64}\\n';\n"
CAPABILITY_LITERAL_NEW=b"  var capabilityText = '"+CAPABILITY.rstrip(b'\n')+b"\\n';\n"

# --- TTL value guard ---------------------------------------------------------
# The app-side transport is the last line of defence: it validates the canonical
# argument before any bytes are built. Only `off` or a canonical decimal 1..255
# is accepted; whitespace, sign, zero, leading zero, fraction, exponent,
# NaN/Infinity and out-of-range are all refused. Nothing is clamped or rounded.
POST_GUARD_OLD=b"post:function(value,owner){ttlTransportOwner(owner);if(owner!=='ttl-write'||!(value==='off'||value==='64'))throw fault('E_TTL_VALUE','Invalid TTL.');"
POST_GUARD_NEW=b"post:function(value,owner){ttlTransportOwner(owner);if(owner!=='ttl-write'||typeof value!=='string'||!/^(?:off|[1-9][0-9]{0,2})$/.test(value)||(value!=='off'&&(Number(value)<1||Number(value)>255)))throw fault('E_TTL_VALUE','Invalid TTL.');"

def _ttl_post_guard(app):
 return once(app,POST_GUARD_OLD,POST_GUARD_NEW)

# --- TTL editor UI -----------------------------------------------------------
# The select only chooses the mode now; the numeric input carries the manual
# TTL. A fresh editor always starts in manual mode with the explicit default 64.
TTL_HELPERS_OLD=(b"  var state = {current: null, locked: true, busy: false, epoch: 0, bound: false};\n"
 b"  function node(id) { return w.document.getElementById(id); }\n"
 b"  function problem(code) { var e = new Error(code); e.mfCode = code; return e; }\n"
 b"  function label(value) { return value === 0 ? 'Off' : String(value); }\n")
TTL_HELPERS_NEW=(b"  var state = {current: null, locked: true, busy: false, epoch: 0, bound: false, draftSerial: 0};\n"
 b"  function node(id) { return w.document.getElementById(id); }\n"
 b"  function problem(code) { var e = new Error(code); e.mfCode = code; return e; }\n"
 b"  function label(value) { return value === 0 ? 'Off' : String(value); }\n"
 b"  function parseManual(raw) { if (typeof raw !== 'string' || !/^[1-9][0-9]{0,2}$/.test(raw)) return null; var n = Number(raw); return n >= 1 && n <= 255 ? n : null; }\n"
 b"  function draft() {\n"
 b"    var mode = node('ttlMode') ? node('ttlMode').value : 'manual';\n"
 b"    if (mode === 'off') return 'off';\n"
 b"    if (mode !== 'manual') return null;\n"
 b"    var value = node('ttlValue') ? String(node('ttlValue').value == null ? '' : node('ttlValue').value) : '';\n"
 b"    var parsed = parseManual(value);\n"
 b"    return parsed === null ? null : String(parsed);\n"
 b"  }\n"
 b"  function showDraft(value) {\n"
 b"    if (node('ttlMode')) node('ttlMode').value = value === 0 ? 'off' : 'manual';\n"
 b"    if (node('ttlValue')) node('ttlValue').value = value === 0 ? '64' : String(value);\n"
 b"    hint();\n"
 b"  }\n")
def _ttl_helpers(app):
 return once(app,TTL_HELPERS_OLD,TTL_HELPERS_NEW)

TTL_RENDER_OLD=b"    node('ttlCurrentHelp').textContent = value.value === 0 ? 'TTL replacement is off.' : value.value === 64 ? 'TTL replacement is set to 64.' : 'The router reports another value. This editor can apply 64 or Off.';\n  }\n"
TTL_RENDER_NEW=b"    node('ttlCurrentHelp').textContent = value.value === 0 ? 'TTL replacement is off.' : value.value === 64 ? 'TTL replacement is set to 64.' : 'The router reports TTL ' + label(value.value) + '.';\n  }\n"
def _ttl_render_text(app):
 return once(app,TTL_RENDER_OLD,TTL_RENDER_NEW)

TTL_SYNC_OLD=b"    node('ttlRead').disabled = !signed || busy;\n    node('ttlMode').disabled = !signed || busy;\n    node('ttlApply').disabled = !signed || busy || state.locked || state.current === null;\n"
TTL_SYNC_NEW=b"    node('ttlRead').disabled = !signed || busy;\n    node('ttlMode').disabled = !signed || busy;\n    if (node('ttlValue')) node('ttlValue').disabled = !signed || busy || node('ttlMode').value === 'off';\n    node('ttlApply').disabled = !signed || busy || state.locked || state.current === null;\n"
def _ttl_sync(app):
 return once(app,TTL_SYNC_OLD,TTL_SYNC_NEW)

TTL_HINT_OLD=b"    node('ttlChoiceHint').textContent = node('ttlMode').value === 'off' ? 'Stop replacing TTL. Packets keep their normal TTL behavior along the route.' : 'Set eligible IPv4 packets to TTL 64. Later routers can reduce the value received at the destination.';\n"
TTL_HINT_NEW=b"    node('ttlChoiceHint').textContent = node('ttlMode').value === 'off' ? 'Stop replacing TTL. Packets keep their normal TTL behavior along the route.' : 'Set eligible IPv4 packets to TTL 1-255. Later routers can reduce the value received at the destination.';\n"
def _ttl_hint(app):
 return once(app,TTL_HINT_OLD,TTL_HINT_NEW)

# render() must never overwrite a manual draft the user typed after the read or
# write began. The serial is captured when an operation starts and the controls
# are only re-synced while it is unchanged.
TTL_READ_RENDER_OLD=b"    return capability(owner, epoch).then(function () { return get(owner, epoch); }).then(function (value) {\n      render(value); state.locked = false;\n"
TTL_READ_RENDER_NEW=b"    var serial = state.draftSerial;\n    return capability(owner, epoch).then(function () { return get(owner, epoch); }).then(function (value) {\n      render(value); if (serial === state.draftSerial) showDraft(value.value); state.locked = false;\n"
def _ttl_read_draft(app):
 return once(app,TTL_READ_RENDER_OLD,TTL_READ_RENDER_NEW)

TTL_SET_OLD=b"  function setValue(value) {\n    if (value !== '64' && value !== 'off') { status('rejected', 'Choose 64 or Off. Other values are not available in this version.'); return Promise.resolve(null); }\n    if (state.locked || !state.current) { status('unavailable', 'Read the router setting first.'); return Promise.resolve(null); }\n"
TTL_SET_NEW=b"  function setValue(explicit) {\n    var asked = explicit === undefined ? draft() : explicit;\n    if (asked === null) { status('rejected', 'Enter a whole number from 1 to 255, or choose Off.'); return Promise.resolve(null); }\n    if (asked !== 'off' && parseManual(asked) === null) { status('rejected', 'Enter a whole number from 1 to 255, or choose Off.'); return Promise.resolve(null); }\n    var value = asked;\n    if (state.locked || !state.current) { status('unavailable', 'Read the router setting first.'); return Promise.resolve(null); }\n"
def _ttl_set_value(app):
 return once(app,TTL_SET_OLD,TTL_SET_NEW)

TTL_SET_WANTED_OLD=b"      render(baseline);\n      var wanted = value === 'off' ? 0 : 64;\n      if (baseline.value === wanted) { status('ready', 'Already set to ' + label(wanted) + '. No change was sent.'); return baseline; }\n      check(epoch); submitted = true; status('pending', 'Applying once, then checking the result\xe2\x80\xa6');\n"
TTL_SET_WANTED_NEW=b"      render(baseline);\n      var wanted = value === 'off' ? 0 : Number(value);\n      if (baseline.value === wanted) { status('ready', 'Already set to ' + label(wanted) + '. No change was sent.'); return baseline; }\n      check(epoch); submitted = true; status('pending', 'Applying once, then checking the result\xe2\x80\xa6');\n"
def _ttl_set_wanted(app):
 return once(app,TTL_SET_WANTED_OLD,TTL_SET_WANTED_NEW)

# reset() is the fresh-editor state (login/logout): explicit manual mode with the
# documented default 64. Off mode is retained, never removed.
TTL_RESET_OLD=b"    node('ttlCurrentHelp').textContent = 'The current setting is not read automatically.';\n    node('ttlMode').value = '64';\n    status('unavailable', 'Sign in and read the router setting.'); hint(); syncControls();\n"
TTL_RESET_NEW=b"    node('ttlCurrentHelp').textContent = 'The current setting is not read automatically.';\n    showDraft(64);\n    status('unavailable', 'Sign in and read the router setting.'); syncControls();\n"
def _ttl_reset(app):
 return once(app,TTL_RESET_OLD,TTL_RESET_NEW)

TTL_BIND_OLD=b"    node('ttlMode').addEventListener('change', hint);\n    node('ttlForm').addEventListener('submit', function (event) { event.preventDefault(); setValue(node('ttlMode').value); });\n"
TTL_BIND_NEW=b"    node('ttlMode').addEventListener('change', function () { state.draftSerial++; hint(); syncControls(); });\n    if (node('ttlValue')) node('ttlValue').addEventListener('input', function () { state.draftSerial++; });\n    node('ttlForm').addEventListener('submit', function (event) { event.preventDefault(); setValue(); });\n"
def _ttl_bind(app):
 return once(app,TTL_BIND_OLD,TTL_BIND_NEW)

TTL_EXPORT_OLD=b"  w.MF885Community047Dev18TTL = {version: '0.4.7-dev.18', state: state, strictState: strictState, nextRevision: nextRevision, read: read, setValue: setValue, reset: reset, syncControls: syncControls, bind: bind};\n"
TTL_EXPORT_NEW=b"  w.MF885Community047Dev18TTL = {version: '0.4.7-dev.18', state: state, strictState: strictState, nextRevision: nextRevision, parseManual: parseManual, draft: draft, read: read, setValue: setValue, reset: reset, syncControls: syncControls, bind: bind};\n"
def _ttl_export(app):
 return once(app,TTL_EXPORT_OLD,TTL_EXPORT_NEW)

def _ttl_capability_literal(app):
 return once(app,CAPABILITY_LITERAL_OLD,CAPABILITY_LITERAL_NEW)

TTL_STEPS=(_ttl_capability_literal,_ttl_helpers,_ttl_render_text,_ttl_sync,_ttl_hint,_ttl_read_draft,_ttl_set_value,_ttl_set_wanted,_ttl_reset,_ttl_bind,_ttl_export)

def ttl_transform(raw):
 """Apply the dev18 TTL editor widening to already dev18-revised ttl.js bytes."""
 if b'0.4.7-dev.17' in raw:raise Error('ttl_transform expects dev18-revised bytes')
 for step in TTL_STEPS:raw=step(raw)
 return raw

# --- TTL markup --------------------------------------------------------------
# Mode select (off/manual) plus a labelled numeric TTL input. min1 max255 step1
# default64. The existing favicon/touch head references are untouched.
ENTRY_SELECT_OLD=b'            <label for="ttlMode">Choose a mode</label>\n            <select id="ttlMode" aria-describedby="ttlChoiceHint ttlPersistence" disabled>\n              <option value="64">64 \xc2\xb7 replace TTL</option>\n              <option value="off">Off \xc2\xb7 stop replacing TTL</option>\n            </select>\n'
ENTRY_SELECT_NEW=b'            <label for="ttlMode">Mode</label>\n            <select id="ttlMode" aria-describedby="ttlChoiceHint ttlPersistence" disabled>\n              <option value="manual">Manual \xc2\xb7 replace TTL</option>\n              <option value="off">Off \xc2\xb7 stop replacing TTL</option>\n            </select>\n            <label for="ttlValue">TTL</label>\n            <input id="ttlValue" type="number" inputmode="numeric" min="1" max="255" step="1" value="64" aria-describedby="ttlChoiceHint ttlPersistence" disabled>\n'
def _entry_mode_input(entry):
 return once(entry,ENTRY_SELECT_OLD,ENTRY_SELECT_NEW)

ENTRY_HINT_OLD=b'            <p id="ttlChoiceHint" class="ttl-hint">Set eligible IPv4 packets to TTL 64. Later routers can reduce the value received at the destination.</p>\n'
ENTRY_HINT_NEW=b'            <p id="ttlChoiceHint" class="ttl-hint">Set eligible IPv4 packets to TTL 1-255. Later routers can reduce the value received at the destination.</p>\n'
def _entry_hint(entry):
 return once(entry,ENTRY_HINT_OLD,ENTRY_HINT_NEW)

ENTRY_APPLY_OLD=b'            <button id="ttlApply" type="submit" disabled>Apply mode</button>\n'
ENTRY_APPLY_NEW=b'            <button id="ttlApply" type="submit" disabled>Apply TTL</button>\n'
def _entry_apply(entry):
 return once(entry,ENTRY_APPLY_OLD,ENTRY_APPLY_NEW)

def entry_transform(entry):
 if b'0.4.7-dev.17' in entry:raise Error('entry_transform expects dev18-revised bytes')
 for step in (_entry_mode_input,_entry_hint,_entry_apply):entry=step(entry)
 return entry

# --- TTL stylesheet ----------------------------------------------------------
# The editor now contains a select and a numeric input, so both share the
# existing width/height treatment. No other rule is changed.
CSS_SELECT_OLD=b'.ttl-editor select{width:100%;max-width:400px;box-sizing:border-box;font-size:17px;min-height:48px}'
CSS_SELECT_NEW=b'.ttl-editor select,.ttl-editor input[type=number]{width:100%;max-width:400px;box-sizing:border-box;font-size:17px;min-height:48px}\n.ttl-editor input[type=number]{margin-bottom:8px}'
def _css_input(assets):
 raw=assets[TTL_CSS_KEY]
 out=dict(assets);out[TTL_CSS_KEY]=once(raw,CSS_SELECT_OLD,CSS_SELECT_NEW)
 return out

def apply_ttl_editor(assets):
 """Pure dev18-asset -> dev18-asset transform used by derive() and the tests.

 Input keys and app bytes must already carry the dev18 names, exactly as
 derive() produces them from dev17 before this step runs.
 """
 for key in (APP_OUT,ENTRY_KEY,TTL_KEY,TTL_JSON_KEY,TTL_CSS_KEY):
  if key not in assets:raise Error('dev18 TTL asset missing: '+key)
 out=dict(assets)
 out[APP_OUT]=ttl_post_guard_transform(assets[APP_OUT])
 out[TTL_KEY]=ttl_transform(assets[TTL_KEY])
 out[ENTRY_KEY]=entry_transform(assets[ENTRY_KEY])
 out[TTL_JSON_KEY]=CAPABILITY
 out=_css_input(out)
 return out

def ttl_post_guard_transform(app):
 if b'0.4.7-dev.17' in app:raise Error('ttl_post_guard_transform expects dev18-revised bytes')
 return _ttl_post_guard(app)

def derive(records,root):
 replacements,assets,removed=previous.build_patch_set(records,root)
 replacements={p:revise(raw) for p,raw in replacements.items()}
 # Rename dev17 -> dev18 first, then run the TTL editor widening in place on the
 # already-revised dev18 assets. No two copies are ever held.
 assets={p.replace('c047d17','c047d18'):revise(raw) for p,raw in assets.items()}
 assets=apply_ttl_editor(assets)
 # The theme step runs last: it consumes the TTL-applied dev18 entry/app bytes
 # and adds the versioned theme CSS/JS keys. It is a pure transform, so the
 # regression suite can drive it directly and build_stages.py `webpins` still
 # produces the final pins from the golden-record derivation.
 assets=theme.apply_theme(assets)
 return replacements,assets,removed

def build_patch_set(records,root):
 replacements,assets,removed=derive(records,root)
 actual={p:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for p,raw in {**replacements,**assets}.items()}
 pins=PINS_FILE
 if not pins.exists():raise Error('dev18 web-pins.json is absent; run build_stages.py webpins with the golden inputs')
 if actual!=json.loads(pins.read_bytes()):raise Error('dev18 asset pin mismatch')
 return replacements,assets,removed
