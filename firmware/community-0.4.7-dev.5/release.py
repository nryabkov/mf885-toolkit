"""Private Engineering editor over the qualified dev.4 native component."""
import hashlib
import importlib.util
import json
import re
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf885_editor_dev4_source',HERE.parent/'community-0.4.7-dev.4/release.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
PROFILE='0.4.7-dev.5'
MARKER=b'MF885 Community 0.4.7-dev.5 - base 2.5.94'
ARTIFACT='MF885-Community-0.4.7-dev.5-base-2.5.94.bin'
class Error(RuntimeError):pass

def once(raw,old,new):
    if raw.count(old)!=1:raise Error('Inherited structure mismatch: '+repr(old[:80]))
    return raw.replace(old,new)

def revise(raw):
    return raw.replace(b'0.4.7-dev.4',b'0.4.7-dev.5').replace(b'047Dev4',b'047Dev5').replace(b'c047d4',b'c047d5')

def derive(records,root):
    replacements,assets,removed=previous.build_patch_set(records,root)
    replacements={p:revise(raw) for p,raw in replacements.items()}
    assets={p.replace('c047d4','c047d5'):revise(raw) for p,raw in assets.items()}
    entry=assets['www\\c047d5.html'];app=assets['www\\js\\c047d5app.js']
    entry=once(entry,b'  <script defer src="js/c047d5ttl.js"></script>',b'  <script defer src="js/c047d5ttl.js"></script>\n  <script defer src="js/c047d5engineering.js"></script>')
    entry=once(entry,b'!window.MF885Community047Dev5TTL)',b'!window.MF885Community047Dev5TTL||!window.MF885Community047Dev5Engineering)')
    entry=once(entry,b'        <div id="modemValues" class="values"></div>',b'        <div id="modemValues" class="values"></div>\n'+(HERE/'web/engineering-panel.html').read_bytes().rstrip())
    entry=entry.replace(b'Cellular radio \xc2\xb7 read only',b'Cellular radio and readings')
    entry,count=re.subn(rb'<section><h3>Engineering mode</h3><p>.*?</p></section>',b'<section><h3>Engineering readings</h3><p>Enable collection to populate detailed LTE fields. The first readings can take about a minute. Disabling collection can briefly interrupt mobile registration. The time shown is when the interface read the router; the radio measurement time is unknown.</p></section>',entry)
    if count!=1:raise Error('Engineering help structure')
    entry=entry.replace(b'USSD, modem write, Engineering toggle, debug-profile change',b'USSD, other modem writes, debug-profile change')
    entry=entry.replace(b'This screen uses the router\'s existing read-only status models only.',b'Signal measurements are read from the router. Collection changes only when you apply the Engineering setting above.')
    app=once(app,b'if(ttl)ttl.syncControls()}',b'if(ttl)ttl.syncControls();var engineering=engineeringExtension();if(engineering)engineering.syncControls()}')
    app=once(app,b'if(ttl)ttl.reset();messages=[];',b'if(ttl)ttl.reset();var engineering=engineeringExtension();if(engineering)engineering.reset();messages=[];')
    helper=b'''  function engineeringExtension(){return w.MF885Community047Dev5Engineering||null}
  function engineeringOwner(owner){if(!session||routerOwner!==owner||(owner!=='engineering-read'&&owner!=='engineering-write'))throw fault('E_ENGINEERING_SESSION','Engineering operation requires a verified session and its operation lock.')}
  function engineeringDocument(reply){if(!reply.body.length||reply.body.length>32768||/<!DOCTYPE|<!ENTITY/i.test(reply.body))throw fault('E_ENGINEERING_RESPONSE','Invalid Engineering response.',reply.requestId);return parseXml(reply.body,reply.requestId)}
'''
    app=once(app,b'  function ttlExtension()',helper+b'  function ttlExtension()')
    bridge=b'''engineeringBridge:{
    begin:beginRouterOperation,end:endRouterOperation,
    sessionPresent:function(){return session!==null},routerBusy:function(){return routerOwner!==null},
    get:function(owner){engineeringOwner(owner);return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=wan',authorization:nextHeader('GET'),owner:owner}).then(engineeringDocument)},
    post:function(value,owner){engineeringOwner(owner);if(owner!=='engineering-write'||(value!=='0'&&value!=='1'))throw fault('E_ENGINEERING_VALUE','Invalid Engineering setting.');var body=XML_DECLARATION+'<RGW><wan><Engineering_mode>'+value+'</Engineering_mode>'+(value==='1'?'<query_time_interval>1</query_time_interval>':'')+'</wan></RGW>';return request({method:'POST',url:'/xml_action.cgi?method=set&module=duster&file=wan',authorization:nextHeader('POST'),body:body,owner:owner,timeoutMs:60000}).then(function(reply){return reply.body?engineeringDocument(reply):null})}
  },ttlBridge:{'''
    app=once(app,b'ttlBridge:{',bridge)
    app=app.replace(b'Engineering mode \xc2\xb7 read only',b'Engineering collection')
    app=app.replace(b"+'s old'",b"+'s since HTTP read'")
    app=app.replace(b"' \xc2\xb7 captured '",b"' \xc2\xb7 read at '")
    app=app.replace(b"' \xc2\xb7 source details are shown in Diagnostics.'",b"' \xc2\xb7 radio measurement time unknown. Source details are in Diagnostics.'")
    assets['www\\c047d5.html']=entry;assets['www\\js\\c047d5app.js']=app
    assets['www\\js\\c047d5engineering.js']=(HERE/'web/engineering.js').read_bytes()
    return replacements,assets,removed

def build_patch_set(records,root):
    replacements,assets,removed=derive(records,root)
    actual={p:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for p,raw in {**replacements,**assets}.items()}
    if actual!=json.loads((HERE/'web-pins.json').read_bytes()):raise Error('Engineering editor asset pin mismatch')
    return replacements,assets,removed
