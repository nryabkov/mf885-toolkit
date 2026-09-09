"""Private dev15 AT and variable-USSD UI derivation; no firmware or deployment authority here."""
import hashlib,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf885_editor_dev6_source',HERE.parent/'community-0.4.7-dev.6/release.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
PROFILE='0.4.7-dev.15'
MARKER=b'MF885 Community 0.4.7-dev.15 - base 2.5.94'
ARTIFACT='MF885-Community-0.4.7-dev.15-base-2.5.94.bin'
class Error(RuntimeError):pass
once=previous.once

def revise(raw):
 return raw.replace(b'0.4.7-dev.6',b'0.4.7-dev.15').replace(b'047Dev6',b'047Dev15').replace(b'c047d6',b'c047d15')

def derive(records,root):
 replacements,assets,removed=previous.build_patch_set(records,root)
 replacements={p:revise(raw) for p,raw in replacements.items()}
 assets={p.replace('c047d6','c047d15'):revise(raw) for p,raw in assets.items()}
 entry_key=r'www\c047d15.html';app_key=r'www\js\c047d15app.js'
 entry=assets[entry_key];app=assets[app_key]
 entry=once(entry,b'</head>',b'  <link rel="icon" type="image/png" sizes="32x32" href="c047d15favicon.png">\n  <link rel="apple-touch-icon" sizes="180x180" href="c047d15touch.png">\n</head>')
 assets[r'www\c047d15favicon.png']=(HERE/'web/favicon.png').read_bytes()
 assets[r'www\c047d15touch.png']=(HERE/'web/apple-touch-icon.png').read_bytes()
 entry=once(entry,b'<button type="button" data-page="messages">Messages</button>',b'<button type="button" data-page="messages">Messages</button>\n        <button type="button" data-page="ussd">USSD</button>\n        <button type="button" data-page="at">AT</button>')
 entry=once(entry,b'      <section id="page-ttl"',(HERE/'web/console-panels.html').read_bytes()+b'\n      <section id="page-ttl"')
 entry=once(entry,b'  <script defer src="js/c047d15power.js"></script>',b'  <script defer src="js/c047d15power.js"></script>\n  <script defer src="js/c047d15console.js"></script>')
 entry=once(entry,b'!window.MF885Community047Dev15Power)',b'!window.MF885Community047Dev15Power||!window.MF885Community047Dev15Console)')
 app=once(app,b"dashboard|messages|diagnostics|modem|ttl",b"dashboard|messages|diagnostics|modem|ttl|ussd|at")
 app=once(app,b'if(power)power.syncControls()}',b'if(power)power.syncControls();var ussd=w.MF885Community047Dev15Console;if(ussd)ussd.syncControls()}')
 app=once(app,b'if(engineering)engineering.reset();messages=[];',b'if(engineering)engineering.reset();var ussd=w.MF885Community047Dev15Console;if(ussd)ussd.reset();messages=[];')
 helper=b'''  function ussdOwner(owner){if(owner!=='console'||routerOwner!==owner||!session)throw fault('E_USSD_SESSION','USSD requires a verified session and its operation lock.')}
  function ussdDocument(reply){if(!reply.body.length||reply.body.length>6144||/[^\\x09\\x0a\\x0d\\x20-\\x7e]/.test(reply.body)||/<!|&/.test(reply.body)||/<\\?/.test(reply.body.replace(/^\\s*<\\?xml\\s[^?]*\\?>/,'')))throw fault('E_USSD_RESPONSE','Invalid USSD response.',reply.requestId);return parseXml(reply.body,reply.requestId)}
'''
 app=once(app,b'  function engineeringExtension()',helper+b'  function engineeringExtension()')
 bridge=b'''consoleBridge:{begin:beginRouterOperation,end:endRouterOperation,sessionPresent:function(){return session!==null},routerBusy:function(){return routerOwner!==null},
    get:function(owner){ussdOwner(owner);return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=c047d15console',authorization:nextHeader('GET'),owner:owner}).then(ussdDocument)},
    network:function(owner){ussdOwner(owner);return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=status1',authorization:nextHeader('GET'),owner:owner}).then(ussdDocument)},
    post:function(value,owner){ussdOwner(owner);if(typeof value!=='string'||!/^[0-9a-f]{8}:[0-9a-f]{8}:[0-9a-f]{8}:[sau]:[0-9a-f]{0,448}$/.test(value))throw fault('E_USSD_VALUE','Invalid USSD request.');var body=XML_DECLARATION+'<RGW><diagnostic><console_v1>'+value+'</console_v1></diagnostic></RGW>';return request({method:'POST',url:'/xml_action.cgi?method=set&module=duster&file=c047d15console',authorization:nextHeader('POST'),body:body,owner:owner,timeoutMs:60000}).then(function(){return null})}
  },engineeringBridge:{'''
 app=once(app,b'engineeringBridge:{',bridge)
 # Bundle private architecture-independent modules into a classic same-origin
 # script. No module MIME support, CDN, runtime imports or generated evaluator.
 research=root/'research/ussd-observer-v19'
 snapshot=(research/'snapshot.mjs').read_text().replace('export function ','function ')
 session=(root/'research/console-session-v2/session.mjs').read_text().replace("import {decodeSessionSnapshot} from '../ussd-observer-v19/snapshot.mjs';",'').replace('export function ','function ')
 diagnostic=(root/'research/console-native-v6/diagnostic.mjs').read_text().replace('export function ','function ')
 bundle='(function(){\n'+diagnostic+'\n'+snapshot+'\n'+session+'\n'+(HERE/'web/console.js').read_text()+'\n})();\n'
 assets[entry_key]=entry;assets[app_key]=app
 assets[r'www\css\c047d15ui.css']+=b'\n.console-reply{white-space:pre-wrap;overflow-wrap:anywhere;margin:16px 0;padding:16px;border-radius:8px;background:var(--surface-soft,#f3f6fa)}\n'
 assets[r'www\js\c047d15console.js']=bundle.encode()
 assets[r'www\xmldata\c047d15console.xml']=b'<?xml version="1.0" encoding="US-ASCII"?><RGW><diagnostic><console_v1>pending</console_v1><ussd_v1>pending</ussd_v1><queue_v1>pending</queue_v1></diagnostic></RGW>\n'
 assets[r'www\css\c047d15ui.css']+=b'\n.console-actions{margin-top:20px;gap:12px;flex-wrap:wrap}.console-reply{max-height:28rem;overflow:auto}.console-history-item{padding:16px 0;border-bottom:1px solid var(--border,#dde3eb)}#ussdCode,#atCommand,#atPreset{width:100%;box-sizing:border-box}\n'
 return replacements,assets,removed

def build_patch_set(records,root):
 replacements,assets,removed=derive(records,root)
 actual={p:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for p,raw in {**replacements,**assets}.items()}
 if actual!=json.loads((HERE/'web-pins.json').read_bytes()):raise Error('USSD asset pin mismatch')
 return replacements,assets,removed
