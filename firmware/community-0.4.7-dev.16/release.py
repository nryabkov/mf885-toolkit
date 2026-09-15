"""Private dev16: automatic local logout when the router session expires.

Derived from the dev15 derivation, which already carries manual AT and
arbitrary initial USSD. This module rewrites browser JS/HTML bytes only. It does
not touch the native component, the stock/golden inputs, dev15 assets, or any
previously released pin file.

The dev15 -> dev16 rewrite is a pure function of the dev15 asset mapping, so the
regression suite can exercise the real production transform against the pinned
dev15 export without the private golden. Final pin generation still requires the
golden-record derivation through build_stages.py `webpins` (reviewer step).
"""
import hashlib,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf885_047d15_source',HERE.parent/'community-0.4.7-dev.15/release.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
PROFILE='0.4.7-dev.16'
MARKER=b'MF885 Community 0.4.7-dev.16 - base 2.5.94'
ARTIFACT='MF885-Community-0.4.7-dev.16-base-2.5.94.bin'
class Error(RuntimeError):pass
once=previous.once
# apply_session_expiry() operates on the *dev16-named* mapping that derive()
# produces from dev15, so its input key is the dev16 app key. APP_IN is kept as
# an alias of APP_OUT for callers that still speak in "input asset" terms; the
# production mapping never contains two copies of the app.
APP_OUT=r'www\js\c047d16app.js'
APP_IN=APP_OUT

def revise(raw):
 return raw.replace(b'0.4.7-dev.15',b'0.4.7-dev.16').replace(b'047Dev15',b'047Dev16').replace(b'c047d15',b'c047d16')

# --- Session-expiry contract -------------------------------------------------
# A definitive router session end is exactly one of:
#   * an XML reply whose login_status is TIMEOUT / KICKOFF / UNAUTHORIZED, or
#   * an authenticated (digest Authorization header present) HTTP 401.
# NOT definitive: request onerror, request ontimeout, HTTP 5xx/403, malformed
# unrelated bodies, and the expected initial /login.cgi 401 challenge that has
# no authenticated Authorization header.
#
# Epoch identity is captured once, at request creation, and travels with the
# request. A callback whose captured epoch no longer equals the live
# `requestEpoch` is *stale*: it is discarded without touching the current
# session, its locks, its DOM or its timers. This is the only place stale
# outcomes are decided, so a late chain from an expired login cannot revive,
# clear or mutate a later login. `expireSessionOnce(epoch,error)` is likewise
# epoch-scoped: it refuses to tear down a session it does not own.

# Injected just before ussdOwner(); uses only w, session, requestEpoch,
# expiryHandled, finishLocalLogout, normalizeError and fault.
GATE=b'''  function xmlExpiry(body){if(!body||String(body).length>32768||/<!DOCTYPE|<!ENTITY/i.test(body)||!/login_status/i.test(String(body)))return false;try{var doc=new w.DOMParser().parseFromString(String(body),'text/xml');if(!doc.documentElement||doc.documentElement.nodeName!=='RGW'||doc.getElementsByTagName('parsererror').length)return false;var list=doc.getElementsByTagName('login_status');if(list.length!==1||list[0].parentNode!==doc.documentElement)return false;return /^(?:TIMEOUT|KICKOFF|UNAUTHORIZED)$/i.test(String(list[0].textContent||'').trim())}catch(error){return false}}
  function staleFault(requestId,meta){return fault('E_STALE_SESSION','A response from an earlier router session was discarded.',requestId,meta)}
  function expireSessionOnce(epoch,error,requestId,meta){if(epoch!==requestEpoch)return staleFault(requestId,meta);if(expiryHandled)return normalizeError(error);expiryHandled=1;finishLocalLogout('Your router session expired. Sign in again. Any command already submitted may have an unknown result. Nothing was retried.',true);return normalizeError(error)}
  function classifyReply(epoch,status,authorizationSent,body,requestId,meta){if(epoch!==requestEpoch)return staleFault(requestId,meta);if(authorizationSent&&status===401)return expireSessionOnce(epoch,fault('E_SESSION_EXPIRED','The router session expired. Sign in again.',requestId,meta),requestId,meta);if(xmlExpiry(body))return expireSessionOnce(epoch,fault('E_SESSION_EXPIRED','The router session expired. Sign in again.',requestId,meta),requestId,meta);return null}
'''
ANCHOR_OWNER=b'  function ussdOwner(owner){'

# Each step is an exact single-occurrence replacement over the dev15 app bytes.
def _epoch_declare(app):
 # requestEpoch identifies the live session; each request captures it on entry.
 # operationToken scopes the single router-operation lock to one acquisition so
 # a finalizer from an expired chain cannot release a newer same-owner lock.
 return once(app,b"var session=null,currentRequest=null,routerOwner=null,",
  b"var session=null,requestEpoch=1,expiryHandled=0,operationToken=0,currentRequest=null,routerOwner=null,")

def _inject_gate(app):
 return once(app,ANCHOR_OWNER,GATE+ANCHOR_OWNER)

def _request_epoch_capture(app):
 # Capture the session identity with the request and route *every* completion
 # through classifyReply(). A stale request never resolves as valid data and
 # never runs the expiry teardown for a session it does not own.
 return once(app,b"var xhr=new w.XMLHttpRequest(),settled=false,requestId=nextRequestId(),method=options.method||'GET',requestOwner=options.owner||'direct',meta={method:method,route:safeRoute(options.url),owner:requestOwner},started=Date.now();",
  b"var xhr=new w.XMLHttpRequest(),settled=false,requestId=nextRequestId(),method=options.method||'GET',requestOwner=options.owner||'direct',requestEpochAtStart=requestEpoch,meta={method:method,route:safeRoute(options.url),owner:requestOwner},started=Date.now();")

def _authenticated_401(app):
 # An authenticated 401 and an expiry XML body are definitive, but only for the
 # epoch that issued the request; owner 'login' is excluded because a rejected
 # password must stay "Sign in failed." and never tear down an unopened session.
 return once(app,b"xhr.onload=function(){if(xhr.status===200||(options.acceptStatuses&&options.acceptStatuses.indexOf(xhr.status)>=0))finish();else finish(fault('E_HTTP','Router HTTP '+xhr.status+'.',requestId,meta))};",
  b"xhr.onload=function(){if(requestEpochAtStart!==requestEpoch){finish(staleFault(requestId,meta));return}if(xhr.status===200||(options.acceptStatuses&&options.acceptStatuses.indexOf(xhr.status)>=0)){if(currentRequest&&currentRequest.xhr===xhr)currentRequest=null;var expired=options.authorization&&requestOwner!=='login'?classifyReply(requestEpochAtStart,xhr.status,!!options.authorization,xhr.responseText,requestId,meta):null;finish(expired||undefined)}else if(xhr.status===401&&options.authorization&&requestOwner!=='login'){if(currentRequest&&currentRequest.xhr===xhr)currentRequest=null;finish(classifyReply(requestEpochAtStart,401,true,xhr.responseText,requestId,meta))}else finish(fault('E_HTTP','Router HTTP '+xhr.status+'.',requestId,meta))};")

def _request_finish_epoch(app):
 # finish() drops stale outcomes centrally: an old chain cannot resolve, clear
 # locks, mutate panels or blank the DOM after a newer login took over.
 return once(app,b"function finish(error){if(settled)return;settled=true;if(currentRequest&&currentRequest.xhr===xhr)currentRequest=null;",
  b"function finish(error){if(settled)return;settled=true;var stale=requestEpochAtStart!==requestEpoch;if(currentRequest&&currentRequest.xhr===xhr)currentRequest=null;if(stale&&(!error||error.mfCode!=='E_SESSION_EXPIRED'))error=staleFault(requestId,meta);")

def _gate_transports(app):
 # Read/document transports only carry the expiry classification flag now; the
 # epoch guard lives in request(), so there is no second mutable-global compare.
 return once(app,b"function modelGet(name,owner){return request({method:'GET',url:modelUrl(name),authorization:nextHeader('GET'),owner:owner})",
  b"function modelGet(name,owner){return request({method:'GET',url:modelUrl(name),authorization:nextHeader('GET'),owner:owner,expiryCheck:true})")

def _sms_page(app):
 return once(app,b"function smsPage(folder,page,owner){var body=smsRequestXml(folder,page);return request({method:'POST',url:'/xml_action.cgi?method=set&module=duster&file=message',authorization:nextHeader('POST'),body:body,owner:owner}).then(function(){return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=message',authorization:nextHeader('GET'),owner:owner})})",
  b"function smsPage(folder,page,owner){var body=smsRequestXml(folder,page);return request({method:'POST',url:'/xml_action.cgi?method=set&module=duster&file=message',authorization:nextHeader('POST'),body:body,owner:owner,expiryCheck:true}).then(function(){return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=message',authorization:nextHeader('GET'),owner:owner,expiryCheck:true})})")

def _poll_command(app):
 return once(app,b"function pollCommand(command,attempt,owner){return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=message',authorization:nextHeader('GET'),owner:owner})",
  b"function pollCommand(command,attempt,owner){return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=message',authorization:nextHeader('GET'),owner:owner,expiryCheck:true})")

def _post_mutation(app):
 return once(app,b"function postMutation(body,command,owner){return request({method:'POST',url:'/xml_action.cgi?method=set&module=duster&file=message',authorization:nextHeader('POST'),body:body,owner:owner})",
  b"function postMutation(body,command,owner){return request({method:'POST',url:'/xml_action.cgi?method=set&module=duster&file=message',authorization:nextHeader('POST'),body:body,owner:owner,expiryCheck:true})")

def _engineering_write(app):
 # Previously `reply.body ? engineeringDocument(reply) : null` silently ignored
 # an empty write reply. dev16 inspects every write reply centrally through
 # request(...expiryCheck:true), so the write body is never dropped.
 return once(app,b"return request({method:'POST',url:'/xml_action.cgi?method=set&module=duster&file=wan',authorization:nextHeader('POST'),body:body,owner:owner,timeoutMs:60000}).then(function(reply){return reply.body?engineeringDocument(reply):null})",
  b"return request({method:'POST',url:'/xml_action.cgi?method=set&module=duster&file=wan',authorization:nextHeader('POST'),body:body,owner:owner,timeoutMs:60000,expiryCheck:true}).then(function(reply){return reply.body?engineeringDocument(reply):null})")

def _console_write(app):
 return once(app,b"return request({method:'POST',url:'/xml_action.cgi?method=set&module=duster&file=c047d16console',authorization:nextHeader('POST'),body:body,owner:owner,timeoutMs:60000}).then(function(){return null})",
  b"return request({method:'POST',url:'/xml_action.cgi?method=set&module=duster&file=c047d16console',authorization:nextHeader('POST'),body:body,owner:owner,timeoutMs:60000,expiryCheck:true}).then(function(){return null})")

def _ttl_get(app):
 return once(app,b"get:function(owner){ttlTransportOwner(owner);return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=diagnostic',authorization:nextHeader('GET'),owner:owner}).then(ttlDocument)}",
  b"get:function(owner){ttlTransportOwner(owner);return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=diagnostic',authorization:nextHeader('GET'),owner:owner,expiryCheck:true}).then(ttlDocument)}")

def _ttl_post(app):
 return once(app,b"post:function(value,owner){ttlTransportOwner(owner);if(owner!=='ttl-write'||!(value==='off'||value==='64'))throw fault('E_TTL_VALUE','Invalid TTL.');var body=XML_DECLARATION+'<RGW><diagnostic><command>ttl</command><arg>'+value+'</arg></diagnostic></RGW>';return request({method:'POST',url:'/xml_action.cgi?method=set&module=duster&file=diagnostic',authorization:nextHeader('POST'),body:body,owner:owner}).then(ttlDocument)}",
  b"post:function(value,owner){ttlTransportOwner(owner);if(owner!=='ttl-write'||!(value==='off'||value==='64'))throw fault('E_TTL_VALUE','Invalid TTL.');var body=XML_DECLARATION+'<RGW><diagnostic><command>ttl</command><arg>'+value+'</arg></diagnostic></RGW>';return request({method:'POST',url:'/xml_action.cgi?method=set&module=duster&file=diagnostic',authorization:nextHeader('POST'),body:body,owner:owner,expiryCheck:true}).then(ttlDocument)}")

def _console_get(app):
 return once(app,b"get:function(owner){ussdOwner(owner);return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=c047d16console',authorization:nextHeader('GET'),owner:owner}).then(ussdDocument)}",
  b"get:function(owner){ussdOwner(owner);return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=c047d16console',authorization:nextHeader('GET'),owner:owner,expiryCheck:true}).then(ussdDocument)}")

def _console_network(app):
 return once(app,b"network:function(owner){ussdOwner(owner);return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=status1',authorization:nextHeader('GET'),owner:owner}).then(ussdDocument)}",
  b"network:function(owner){ussdOwner(owner);return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=status1',authorization:nextHeader('GET'),owner:owner,expiryCheck:true}).then(ussdDocument)}")

def _engineering_get(app):
 return once(app,b"get:function(owner){engineeringOwner(owner);return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=wan',authorization:nextHeader('GET'),owner:owner}).then(engineeringDocument)}",
  b"get:function(owner){engineeringOwner(owner);return request({method:'GET',url:'/xml_action.cgi?method=get&module=duster&file=wan',authorization:nextHeader('GET'),owner:owner,expiryCheck:true}).then(engineeringDocument)}")

def _login_epoch(app):
 # Only a successful authenticated login opens a new session epoch. The initial
 # /login.cgi GET challenge keeps its dev15 handling unchanged. The challenge and
 # the password exchange both run under owner 'login', whose requests never
 # classify as expiry, so a rejected password stays "Sign in failed.".
 return once(app,b"if(!beginRouterOperation('login','loginStatus'))return Promise.resolve(null);var acceptedIdentity=null;",
  b"if(!beginRouterOperation('login','loginStatus'))return Promise.resolve(null);var acceptedIdentity=null;var loginEpoch=requestEpoch;")

def _login_commit_epoch(app):
 # The epoch advances only after the identity is proven, so a failed/rejected
 # login never increments it and never invalidates a previously live session.
 return once(app,b"password='';acceptedIdentity=identity;node('login').hidden=true;node('app').hidden=false;",
  b"password='';acceptedIdentity=identity;requestEpoch=loginEpoch+1;expiryHandled=0;node('login').hidden=true;node('app').hidden=false;")

def _refresh_all(app):
 # After a local expiry the session is gone, so follow-on steps must stop
 # quietly without an unhandled rejection and without replaying anything.
 return once(app,b"return readSnapshot(null,(trigger||'manual')+':'+id).catch(function(error){logFailure(error,'Universal device refresh failed.');return null}).then(function(){if(!messageAllowed)return null;return loadMessagesPreview((trigger||'manual')+':'+id)}).finally(function(){scheduleLive()})}",
  b"return readSnapshot(null,(trigger||'manual')+':'+id).catch(function(error){logFailure(error,'Universal device refresh failed.');return null}).then(function(){if(!messageAllowed||!session)return null;return loadMessagesPreview((trigger||'manual')+':'+id)}).catch(function(error){logFailure(error,'Universal device refresh stopped.');return null}).finally(function(){scheduleLive()})}")

def _live_tick(app):
 # The live scheduler already checks session; make its message dispatch fail
 # closed after expiry instead of raising out of the timer.
 return once(app,b"if(messageDue&&messageAllowed){dispatchCount++;nextMessagesAt=now+MESSAGES_POLL_MS;liveLog(id,'dispatch',{kind:'messages-preview',semanticPostCeiling:1,resultGetCeiling:1});flow=flow.then(function(){return loadMessagesPreview('live:'+id)})}",
  b"if(messageDue&&messageAllowed){dispatchCount++;nextMessagesAt=now+MESSAGES_POLL_MS;liveLog(id,'dispatch',{kind:'messages-preview',semanticPostCeiling:1,resultGetCeiling:1});flow=flow.then(function(){return session?loadMessagesPreview('live:'+id):null})}")

def _end_operation_token(app):
 # endRouterOperation(owner) was string-only: a finalizer from an expired chain
 # could release a newer operation that happened to share the owner string. It
 # now requires the exact acquisition token, so a stale finalizer is refused.
 return once(app,b"function endRouterOperation(owner){if(routerOwner!==owner){reportUnexpected('router-operation-owner',{expected:owner,actual:routerOwner});return false}",
  b"function endRouterOperation(owner,token){if(routerOwner!==owner){reportUnexpected('router-operation-owner',{expected:owner,actual:routerOwner});return false}if(token!==operationToken){if(w.console&&typeof w.console.debug==='function')privateLog('debug','[MF885] stale router operation finalizer ignored',{owner:owner});return false}")

def _begin_operation_token(app):
 # Every acquisition mints a token and returns it; each operation captures its
 # own token and must pass it back, so a finalizer can only release the lock it
 # actually acquired.
 return once(app,b"routerOwner=owner;syncRouterControls();",
  b"routerOwner=owner;operationToken++;syncRouterControls();")

def _thread_operation_tokens(app):
 # Capture the acquisition token at each operation's begin and pass it to the
 # matching finalizer. Owner strings alone are not an identity.
 pairs=(
  (b"if(!beginRouterOperation('snapshot','diagnosticsStatus'))return Promise.resolve(diagnosticsSnapshot);",
   b"var snapshotToken=beginRouterOperation('snapshot','diagnosticsStatus');if(!snapshotToken)return Promise.resolve(diagnosticsSnapshot);"),
  (b"endRouterOperation('snapshot')",b"endRouterOperation('snapshot',snapshotToken)"),
  (b"if(!beginRouterOperation('messages-preview','messagesStatus'))return Promise.resolve(null);",
   b"var previewToken=beginRouterOperation('messages-preview','messagesStatus');if(!previewToken)return Promise.resolve(null);"),
  (b"endRouterOperation('messages-preview')",b"endRouterOperation('messages-preview',previewToken)"),
  (b"if(!beginRouterOperation('messages-read','messagesStatus'))return Promise.resolve();",
   b"var readToken=beginRouterOperation('messages-read','messagesStatus');if(!readToken)return Promise.resolve();"),
  (b"endRouterOperation('messages-read')",b"endRouterOperation('messages-read',readToken)"),
  (b"if(!beginRouterOperation('messages-send','messagesStatus'))return;",
   b"var sendToken=beginRouterOperation('messages-send','messagesStatus');if(!sendToken)return;"),
  (b"endRouterOperation('messages-send')",b"endRouterOperation('messages-send',sendToken)"),
  (b"if(!beginRouterOperation('messages-delete','messagesStatus'))return;",
   b"var deleteToken=beginRouterOperation('messages-delete','messagesStatus');if(!deleteToken)return;"),
  (b"endRouterOperation('messages-delete')",b"endRouterOperation('messages-delete',deleteToken)"),
  (b"if(!beginRouterOperation('login','loginStatus'))return Promise.resolve(null);",
   b"var loginToken=beginRouterOperation('login','loginStatus');if(!loginToken)return Promise.resolve(null);"),
  (b"endRouterOperation('login')",b"endRouterOperation('login',loginToken)"),
  # beginRouterOperation returns the token instead of a bare boolean.
  (b"return true}\n  function endRouterOperation(owner,token){",b"return operationToken}\n  function endRouterOperation(owner,token){"),
 )
 for old,new in pairs:app=once(app,old,new)
 return app

def _finish_logout(app):
 # Teardown stops polling, cancels the active request, releases the operation
 # lock, resets every extension and DOM region and shows the login form. The
 # request/session state is cleared so a fresh login starts cleanly.
 return once(app,b"function finishLocalLogout(message,error){cancelCurrent();session=null;stopLive();",
  b"function finishLocalLogout(message,error){requestEpoch++;expiryHandled=1;operationToken++;routerOwner=null;cancelCurrent();session=null;stopLive();syncRouterControls();")

def _lock_unknown(app):
 # A write whose session ended locally must not lock the *next* session's
 # message writes. The unknown outcome is still reported, but the local lock
 # belongs to the expired epoch only.
 return once(app,b"function lockUnknown(error){var value=logFailure(error,'Mutation verification failed.');mutationLocked=true;mutationBusy=false;",
  b"function lockUnknown(error){var value=logFailure(error,'Mutation verification failed.');if(value.mfCode==='E_SESSION_EXPIRED'||value.mfCode==='E_STALE_SESSION'){return}mutationLocked=true;mutationBusy=false;")

def _power_bridge_epoch(app):
 # power.js uses fetch and its own flow/auth, not request(); it must reuse the
 # same local teardown and must not leak an expiry callback into a new session.
 return once(app,b"stopLive:stopLive,finish:finishLocalLogout}",
  b"stopLive:stopLive,finish:finishLocalLogout,currentEpoch:function(){return requestEpoch},expire:function(epoch,error){return expireSessionOnce(epoch,error)},release:function(owner,token){return endRouterOperation(owner,token)},classifyReply:classifyReply}")

POWER_KEY=r'www\js\c047d16power.js'
CONSOLE_KEY=r'www\js\c047d16console.js'

def _console_extension_token(assets):
 # The c1 console extension is bundled by the dev15 derivation, so it is only
 # reachable through the derived asset. It holds the same router operation lock
 # and must thread the acquisition token exactly like the other extensions.
 if CONSOLE_KEY not in assets:return assets
 raw=once(assets[CONSOLE_KEY],
  b"if(!bridge.begin('console',prefix+'Status'))return null;",
  b"var token=bridge.begin('console',prefix+'Status');if(!token)return null;")
 raw=once(raw,b"finally{busy=false;bridge.end('console');syncControls()}",
  b"finally{busy=false;bridge.end('console',token);syncControls()}")
 out=dict(assets);out[CONSOLE_KEY]=raw
 return out

def _power_extension_expiry(assets):
 if POWER_KEY not in assets:return assets
 # power.js keeps its own fetch flow, so it needs its own epoch identity. The
 # epoch is captured before the first request and every completion (including
 # the finally) is discarded once the session moved on; an authenticated 401
 # uses the same local teardown as the core app. The initial /login.cgi 401
 # challenge is passed `challenge=true` and still accepted, and nothing is
 # replayed: the promise chain simply stops.
 raw=assets[POWER_KEY]
 raw=once(raw,b"  function get(url,authorization,challenge){\n    var controller=new w.AbortController(),timer=w.setTimeout(function(){controller.abort()},10000);\n    var headers={'Cache-Control':'no-store','Pragma':'no-cache'};if(authorization)headers.Authorization=authorization;\n    return w.fetch(url,{method:'GET',headers:headers,credentials:'same-origin',cache:'no-store',redirect:'error',signal:controller.signal}).then(function(reply){\n      if(reply.status!==200&&!(challenge&&reply.status===401))throw Error('Router rejected the request (HTTP '+reply.status+').');\n      return reply.text().then(function(body){if(body.length>32768)throw Error('Oversized router response.');return {body:body,auth:reply.headers.get('WWW-Authenticate')||''}});\n    }).finally(function(){w.clearTimeout(timer)});\n  }",
  b"  function powerFault(code,message){var error=Error(message);error.mfCode=code;return error}\n  function get(url,authorization,challenge,epoch){\n    if(epoch!==b.currentEpoch())return Promise.reject(powerFault('E_STALE_SESSION','Earlier session ended.'));\n    var controller=new w.AbortController(),timer=w.setTimeout(function(){controller.abort()},10000);\n    var headers={'Cache-Control':'no-store','Pragma':'no-cache'};if(authorization)headers.Authorization=authorization;\n    return w.fetch(url,{method:'GET',headers:headers,credentials:'same-origin',cache:'no-store',redirect:'error',signal:controller.signal}).then(function(reply){\n      if(epoch!==b.currentEpoch())throw powerFault('E_STALE_SESSION','A response from an earlier router session was discarded.');\n      if(reply.status===401&&authorization&&!challenge)throw b.expire(epoch,powerFault('E_SESSION_EXPIRED','The router session expired. Sign in again.'));\n      if(reply.status!==200&&!(challenge&&reply.status===401))throw Error('Router rejected the request (HTTP '+reply.status+').');\n      return reply.text().then(function(body){if(epoch!==b.currentEpoch())throw powerFault('E_STALE_SESSION','Earlier session ended.');var ended=authorization?b.classifyReply(epoch,reply.status,true,body):null;if(ended)throw ended;if(body.length>32768)throw Error('Oversized router response.');return {body:body,auth:reply.headers.get('WWW-Authenticate')||''}});\n    }).finally(function(){w.clearTimeout(timer)});\n  }")
 raw=once(raw,b"if(!b.begin('power','powerStatus'))return Promise.resolve(false);\n    busy=true;consumed=false;b.stopLive();syncControls();",
  b"var token=b.begin('power','powerStatus');if(!token)return Promise.resolve(false);\n    var epoch=b.currentEpoch();busy=true;consumed=false;b.stopLive();syncControls();")
 raw=raw.replace(b"return get('/login.cgi','',true).then(",b"return get('/login.cgi','',true,epoch).then(")
 raw=once(raw,b"return get('/login.cgi?'+query,header);",b"return get('/login.cgi?'+query,header,false,epoch);")
 raw=raw.replace(b"return get('/xml_action.cgi?method=get&module=duster&file=status1',header);",
  b"return get('/xml_action.cgi?method=get&module=duster&file=status1',header,false,epoch);")
 raw=once(raw,b"return get('/xml_action.cgi?method=get&module=duster&file='+(action==='reboot'?'reset':'poweroff'),header);",
  b"return get('/xml_action.cgi?method=get&module=duster&file='+(action==='reboot'?'reset':'poweroff'),header,false,epoch);")
 # A late finalizer from an expired epoch must neither blank the new session's
 # UI nor release the newer operation lock.
 raw=once(raw,b"    }).finally(function(){\n      auth=null;header='';busy=false;b.end('power');b.finish(finalMessage,!accepted);syncControls();\n    });",
  b"    }).finally(function(){\n      auth=null;header='';busy=false;if(epoch!==b.currentEpoch())return;b.release('power',token);b.finish(finalMessage,!accepted);syncControls();\n    });")
 out=dict(assets);out[POWER_KEY]=raw
 return out

# Extension assets are part of the same derive() mapping. They hold the router
# operation lock through the shared bridge, so they must thread the acquisition
# token exactly like the core app does; otherwise their finalizer could release
# a newer operation or be refused after a local expiry.
TTL_KEY=r'www\js\c047d16ttl.js'
ENGINEERING_KEY=r'www\js\c047d16engineering.js'

def _ttl_extension_token(assets):
 if TTL_KEY not in assets:return assets
 raw=assets[TTL_KEY]
 # begin() returns the acquisition token; each operation keeps it and end()
 # requires it, so a stale finalizer cannot release a newer console/ttl lock.
 raw=once(raw,b"if (!bridge || !bridge.sessionPresent() || state.busy || !bridge.begin(owner, 'ttlStatus')) return false;\n    state.busy = true; syncControls(); return true;\n  }\n  function end(owner) { state.busy = false; bridge.end(owner); syncControls(); }",
  b"if (!bridge || !bridge.sessionPresent() || state.busy) return false;\n    var token = bridge.begin(owner, 'ttlStatus'); if (!token) return false;\n    state.busy = true; syncControls(); return token;\n  }\n  function end(owner, token) { state.busy = false; bridge.end(owner, token); syncControls(); }")
 raw=raw.replace(b"if (!begin(owner)) return Promise.resolve(null);",
  b"var token = begin(owner); if (!token) return Promise.resolve(null);")
 raw=raw.replace(b"end(owner); });",b"end(owner, token); });")
 out=dict(assets);out[TTL_KEY]=raw
 return out

def _engineering_extension_token(assets):
 if ENGINEERING_KEY not in assets:return assets
 raw=assets[ENGINEERING_KEY]
 raw=once(raw,b"function begin(owner){if(!bridge||!bridge.sessionPresent()||state.busy||!bridge.begin(owner,'engineeringStatus'))return false;state.busy=true;syncControls();return true}\n  function end(owner){state.busy=false;bridge.end(owner);syncControls()}",
  b"function begin(owner){if(!bridge||!bridge.sessionPresent()||state.busy)return false;var token=bridge.begin(owner,'engineeringStatus');if(!token)return false;state.busy=true;syncControls();return token}\n  function end(owner,token){state.busy=false;bridge.end(owner,token);syncControls()}")
 raw=raw.replace(b"if(!begin(owner))return Promise.resolve(null);",
  b"var token=begin(owner);if(!token)return Promise.resolve(null);")
 raw=raw.replace(b"finally(function(){end(owner)})",b"finally(function(){end(owner,token)})")
 out=dict(assets);out[ENGINEERING_KEY]=raw
 return out


def _continuation_fences(app):
 """Fence whole asynchronous operations, including work between requests.

 A transport rejection alone is insufficient: snapshot recovery and timer
 continuations can otherwise borrow the next login's credentials. Exact pinned
 dev15 inputs bound these small source transformations; browser tests exercise
 the resulting full assets rather than these replacement expressions.
 """
 import re
 names=('modelGet','smsPage','readSnapshot','readFolderData','loadMessagesPreview','loadMessages',
        'sendMessage','deleteMessage','pollCommand','postMutation','refreshAll',
        'runLiveTick','startAuthenticatedUi')
 for name in names:
  start=app.index(('  function '+name+'(').encode())
  end=app.find(b'\n  function ',start+1)
  if end<0:raise Error('operation boundary missing: '+name)
  part=app[start:end]
  opening=part.index(b'{')+1
  part=part[:opening]+b'var operationEpoch=requestEpoch;'+part[opening:]
  part=re.sub(rb'(\.then\(function\([^)]*\)\{)',rb'\1if(operationEpoch!==requestEpoch)throw staleFault();',part)
  part=part.replace(b'},function(error){',b'},function(error){if(operationEpoch!==requestEpoch)throw staleFault();')
  part=re.sub(rb'(\.catch\(function\([^)]*\)\{)',rb'\1if(operationEpoch!==requestEpoch)return null;',part)
  part=re.sub(rb'(\.finally\(function\([^)]*\)\{)',rb'\1if(operationEpoch!==requestEpoch)return;',part)
  part=part.replace(b'.then(second)',b'.then(function(){if(operationEpoch!==requestEpoch)return null;return second()})')
  part=part.replace(b'function next(){',b'function next(){if(operationEpoch!==requestEpoch)throw staleFault();')
  if name=='runLiveTick':
   part=part.replace(b'return flow.finally(',b"return flow.catch(function(error){if(operationEpoch===requestEpoch)logFailure(error,'Live refresh stopped.');return null}).finally(")
  app=app[:start]+part+app[end:]
 # Explicitly clear rendered data and drafts, not merely the hidden flag.
 clear=b"['diagnosticsValues','modemValues','wanValues','wanMissingValues','diagnosticsSources','messagesList','dashboardNetwork','dashboardBattery','dashboardMessages','modemFreshness'].forEach(function(id){var element=node(id);if(element)element.textContent=''});['password','messageNumber','messageBody','ussdCode','atCommand'].forEach(function(id){var element=node(id);if(element)element.value=''});messagesBusy=false;messagesCancelError=null;node('messageComposer').hidden=true;"
 return once(app,b"node('app').hidden=true;node('login').hidden=false;status('loginStatus',message",clear+b"node('app').hidden=true;node('login').hidden=false;status('loginStatus',message")

STEPS=(_epoch_declare,_inject_gate,_request_epoch_capture,_request_finish_epoch,_authenticated_401,_gate_transports,_sms_page,_poll_command,_post_mutation,_engineering_write,_console_write,_ttl_get,_ttl_post,_console_get,_console_network,_engineering_get,_login_epoch,_login_commit_epoch,_begin_operation_token,_end_operation_token,_thread_operation_tokens,_refresh_all,_live_tick,_lock_unknown,_power_bridge_epoch,_finish_logout,_continuation_fences)

def apply_session_expiry(assets):
 """Pure dev16-asset -> dev16-asset transform used by derive() and the tests.

 Input keys and app bytes must already carry the dev16 names, exactly as
 derive() produces them from dev15 before this step runs. The mapping keeps a
 single app entry: the transform replaces APP_OUT in place.
 """
 if APP_OUT not in assets:raise Error('dev16 app asset missing')
 app=assets[APP_OUT]
 if b'0.4.7-dev.15' in app:raise Error('apply_session_expiry expects dev16-revised bytes')
 for step in STEPS:app=step(app)
 out=dict(assets);out[APP_OUT]=app
 out=_ttl_extension_token(out)
 out=_engineering_extension_token(out)
 out=_console_extension_token(out)
 out=_power_extension_expiry(out)
 return out

def derive(records,root):
 replacements,assets,removed=previous.build_patch_set(records,root)
 replacements={p:revise(raw) for p,raw in replacements.items()}
 # Rename dev15 -> dev16 first, then run the session-expiry rewrite in place on
 # the already-revised dev16 app bytes. The mapping never holds two app copies.
 assets={p.replace('c047d15','c047d16'):revise(raw) for p,raw in assets.items()}
 assets=apply_session_expiry(assets)
 return replacements,assets,removed

def build_patch_set(records,root):
 replacements,assets,removed=derive(records,root)
 actual={p:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for p,raw in {**replacements,**assets}.items()}
 pins=HERE/'web-pins.json'
 if not pins.exists():raise Error('dev16 web-pins.json is absent; run build_stages.py webpins with the golden inputs')
 if actual!=json.loads(pins.read_bytes()):raise Error('dev16 asset pin mismatch')
 return replacements,assets,removed
