"""Private WAN and power UI candidate; always derived from exact golden."""
import hashlib, importlib.util, json, re
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf885_editor_dev5_source',HERE.parent/'community-0.4.7-dev.5/release.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
PROFILE='0.4.7-dev.6'
MARKER=b'MF885 Community 0.4.7-dev.6 - base 2.5.94'
ARTIFACT='MF885-Community-0.4.7-dev.6-base-2.5.94.bin'
class Error(RuntimeError):pass
once=previous.once
def revise(raw):
    return raw.replace(b'0.4.7-dev.5',b'0.4.7-dev.6').replace(b'047Dev5',b'047Dev6').replace(b'c047d5',b'c047d6')
def derive(records,root):
    replacements,assets,removed=previous.build_patch_set(records,root)
    replacements={p:revise(raw) for p,raw in replacements.items()}
    assets={p.replace('c047d5','c047d6'):revise(raw) for p,raw in assets.items()}
    entry_key=r'www\c047d6.html'; app_key=r'www\js\c047d6app.js'
    entry=assets[entry_key];app=assets[app_key]
    entry,count=re.subn(rb'          <button type="button" data-page="(?:messages|diagnostics|modem|ttl)"[^>]*>[^<]*</button>\n',b'',entry)
    if count!=4:raise Error('Expected four duplicate dashboard links')
    entry=once(entry,b'        <div id="modemValues" class="values"></div>',b'        <div id="modemValues" class="values"></div>\n'+(HERE/'web/wan-panel.html').read_bytes())
    entry=once(entry,b'      </section>\n\n      <section id="page-messages"', (HERE/'web/power-panel.html').read_bytes()+b'      </section>\n\n      <section id="page-messages"')
    entry=once(entry,b'  <script defer src="js/c047d6engineering.js"></script>',b'  <script defer src="js/c047d6engineering.js"></script>\n  <script defer src="js/c047d6power.js"></script>')
    entry=once(entry,b'!window.MF885Community047Dev6Engineering)',b'!window.MF885Community047Dev6Engineering||!window.MF885Community047Dev6Power)')
    app=once(app,b'  function renderSources(', (HERE/'web/wan.js').read_bytes()+b'\n  function renderSources(')
    app=once(app,b"renderValues('modemValues',modemRows(snapshot));",b"renderValues('modemValues',modemRows(snapshot));renderWan(snapshot);")
    app=once(app,b'if(engineering)engineering.syncControls()}',b'if(engineering)engineering.syncControls();var power=w.MF885Community047Dev6Power;if(power)power.syncControls()}')
    app=once(app,b'engineeringBridge:{',b"powerBridge:{begin:beginRouterOperation,end:endRouterOperation,busy:function(){return routerOwner!==null},sessionPresent:function(){return session!==null},credentials:function(){if(routerOwner!=='power'||!session)throw fault('E_POWER_SESSION','Sign in first.');return {realm:session.challenge.realm,ha1:session.ha1}},proof:proof,parseChallenge:parseChallenge,parseXml:parseXml,exactIdentity:exactIdentity,stopLive:stopLive,finish:finishLocalLogout},wanRows:wanRows,engineeringBridge:{")
    assets[r'www\css\c047d6ui.css']+=(HERE/'web/layout.css').read_bytes()
    assets[entry_key]=entry;assets[app_key]=app
    assets[r'www\js\c047d6power.js']=(HERE/'web/power.js').read_bytes()
    return replacements,assets,removed
def build_patch_set(records,root):
    replacements,assets,removed=derive(records,root)
    actual={p:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for p,raw in {**replacements,**assets}.items()}
    if actual!=json.loads((HERE/'web-pins.json').read_bytes()):raise Error('WAN/power asset pin mismatch')
    return replacements,assets,removed
