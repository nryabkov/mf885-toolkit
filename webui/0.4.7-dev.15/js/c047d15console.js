(function(){
/* Read-only decoder of the last borrowed-parser observation. */
function decodeQueueDiagnostic(value){
 if(typeof value!=='string'||!(/^(?:q1:[0-9a-f]{208}|q2:[0-9a-f]{240})$/.test(value)))throw Error('Invalid AT queue snapshot');
 const hasContext=value.startsWith('q2:');const bytes=new Uint8Array(hasContext?120:104);for(let i=0;i<bytes.length;i++)bytes[i]=parseInt(value.slice(3+2*i,5+2*i),16);
 const view=new DataView(bytes.buffer),words=Array.from({length:20},(_,i)=>view.getUint32(i*4,true));
 const [flags,samples,foreignCalls,ownedCalls,busyRejections,pendingCount,pendingMask,responseTag,responseCode,responseError,responses,callbackClass]=words;
 const tags=words.slice(12);let bits=0;for(let m=pendingMask;m;m>>>=1)bits+=m&1;
 if(flags>31||pendingCount>8||pendingMask>255||bits!==pendingCount||callbackClass>2||tags.slice(pendingCount).some(x=>x!==0))throw Error('Invalid AT queue bounds');
 if((flags===0&&(samples||pendingCount))||((flags&2)&&flags!==3))throw Error('Invalid AT queue flags');
 const tail=bytes.slice(80,104),zero=tail.indexOf(0);if(zero<0||tail.slice(zero).some(x=>x!==0))throw Error('Invalid AT command label');
 const verb=String.fromCharCode(...tail.slice(0,zero));if(verb!==''&&!/^AT[A-Za-z+]{0,21}$/.test(verb))throw Error('Invalid AT command label');
 const context=hasContext?{parserAddress:view.getUint32(104,true),callbackAddress:view.getUint32(108,true),pendingAddress:view.getUint32(112,true),callerAddress:view.getUint32(116,true)}:null;
 if(context&&flags===0&&Object.values(context).some(x=>x!==0))throw Error('Unobserved AT context');
 return {context,flags,samples,foreignCalls,ownedCalls,busyRejections,pendingCount,pendingMask,tags:tags.slice(0,pendingCount),responseTag,responseCode,responseError,responses,callbackClass,verb,sampled:Boolean(flags&1),valid:Boolean(flags&2),liveQueue:false};
}

/* Private u4 snapshot reader: strict HTTP-origin ownership and text decoding.
 * No transport or DOM mutation. Native firmware owns the association proof. */
const BYTES = 1044;
const EVENT_BYTES = 252;
const invalid = () => { throw new Error('Invalid MF885 u4 snapshot'); };
function decodeSessionSnapshot(wire) {
  if (typeof wire !== 'string' || wire.length !== 3 + 2 * BYTES ||
      !/^u4:[0-9a-f]+$/.test(wire)) invalid();
  const raw = new Uint8Array(BYTES);
  for (let i = 0; i < BYTES; i++) raw[i] = parseInt(wire.slice(3 + 2*i, 5 + 2*i), 16);
  const view = new DataView(raw.buffer);
  const u16 = at => view.getUint16(at, true);
  const u32 = at => view.getUint32(at, true);
  const zero = (start, end) => { for (let i = start; i < end; i++) if (raw[i]) invalid(); };
  const count = raw[17], newest = u32(4);
  if (raw[16] > 1 || count > 4 || count !== Math.min(newest, 4)) invalid();
  zero(18, 20);
  const events = [];
  for (let i = 0; i < count; i++) {
    const at = 20 + i * EVENT_BYTES;
    const sequence = u32(at), transaction = u32(at + 4), confirmation = u16(at + 10);
    const flags = raw[at + 12], path = raw[at + 13], linked = !!(flags & 1);
    if (sequence !== newest - count + i + 1 || flags & ~63 || path < 1 || path > 4) invalid();
    if (linked ? !!(flags & (4 | 8 | 16)) : !(flags & 16)) invalid();
    if (!linked && (transaction || confirmation || flags & 2)) invalid();
    if (linked !== !!(flags & 32) || (linked && !transaction) || confirmation || (flags & 2)) invalid();
    zero(at + 14, at + 16);
    const body = at + 16, size = raw[body + 2], selector = raw[body + 1];
    if (size > 229) invalid();
    zero(body + 3 + size, body + 232);
    events.push({sequence, nativeTransactionRaw: transaction, localIdRaw: u16(at + 8),
      confirmationRaw: confirmation, flagsRaw: flags, pathRaw: path,
      statusRaw: raw[body], codingSelectorRaw: selector,
      stockRenderedDcs: ({2: 4, 4: 16, 5: 17})[selector] ?? 0,
      payloadBytes: size, payloadHex: wire.slice(3 + 2*(body + 3), 3 + 2*(body + 3 + size)),
      detailWordsRaw: [u16(body + 232), u16(body + 234)],
      requestSequence: linked ? transaction : null, ownership: linked ? 'http-request' : 'unattributed'});
  }
  zero(20 + count * EVENT_BYTES, 1028);
  const low = u32(1028), high = u32(1032), sequence = u32(1036), status = view.getInt32(1040, true);
  const initialized = !!(low || high), pending = status === -2147483648;
  if ((!initialized && (sequence || status)) || (pending && !sequence)) invalid();
  const hex = n => n.toString(16).padStart(8, '0');
  const nonceRaw = hex(low) + ':' + hex(high);
  for (const event of events) {
    if (event.requestSequence !== null && (!initialized || event.requestSequence > sequence)) invalid();
    Object.assign(event, decodeUssdText(event));
  }
  const next = initialized && !pending && sequence < 0xffffffff ? sequence + 1 : null;
  return {schema: 'mf885-ussd-snapshot/u4', sessionContract: 'http-request-link/v20',
    submission: {nonceRaw, nonceInitialized: initialized, sequence, status, pending,
      nextArgument: next === null ? null : nonceRaw + ':' + hex(next)}, bootEpochRaw: u32(0),
    bootIdentityQualified: false, newestSequence: newest, overwritten: u32(8),
    rejected: u32(12), coverageComplete: !!raw[16], events};
}


/* Stock selector5 contains big-endian UCS2/UTF16 code units. Selector4
 * contains unpacked GSM default-alphabet septets, not packed network bytes.
 * Selector2 is arbitrary 8-bit data: retain hex without guessing a charset. */
function decodeUssdText(event) {
  const bytes = Uint8Array.from(event.payloadHex.match(/../g) || [], x => parseInt(x, 16));
  const raw = reason => ({text: null, textEncoding: null, textIssue: reason});
  if (event.codingSelectorRaw === 5) {
    if (bytes.length % 2) return raw('Odd UTF-16BE byte count');
    let text = '';
    for (let i = 0; i < bytes.length; i += 2) {
      const unit = (bytes[i] << 8) | bytes[i+1];
      if (unit >= 0xd800 && unit <= 0xdbff) {
        if (i+3 >= bytes.length) return raw('Incomplete UTF-16BE surrogate');
        const next = (bytes[i+2] << 8) | bytes[i+3];
        if (next < 0xdc00 || next > 0xdfff) return raw('Invalid UTF-16BE surrogate');
        text += String.fromCharCode(unit, next); i += 2;
      } else if (unit >= 0xdc00 && unit <= 0xdfff) return raw('Unexpected UTF-16BE surrogate');
      else text += String.fromCharCode(unit);
    }
    return {text, textEncoding: 'UTF-16BE', textIssue: null};
  }
  if (event.codingSelectorRaw === 4) {
    const alphabet = '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\u001bÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà';
    const extension = {10:'\f',20:'^',40:'{',41:'}',47:'\\',60:'[',61:'~',62:']',64:'|',101:'€'};
    let text = '';
    for (let i = 0; i < bytes.length; i++) {
      const value = bytes[i];
      if (value > 127) return raw('Invalid GSM alphabet byte');
      if (value === 27) {
        const extra = extension[bytes[++i]];
        if (extra === undefined) return raw('Invalid GSM extension');
        text += extra;
      } else text += alphabet[value];
    }
    return {text, textEncoding: 'GSM default alphabet', textIssue: null};
  }
  return raw('Unsupported or binary coding selector');
}

/* Private c1 command session successor v2. Explicit sends, GET-only recovery, bounded RAM history. */

const wordHex = n => n.toString(16).padStart(8,'0');
function encodeConsoleCommand(kind,command) {
  if(!['a','u'].includes(kind)||typeof command!=='string'||!command.length||command.length>224||/[^\x20-\x7e]/.test(command))throw Error('Enter 1–224 printable ASCII characters.');
  if(kind==='a'&&(!/^at/i.test(command)||command.includes(';')))throw Error('Enter one AT command, without a command batch.');
  if(kind==='u'&&/[$@\[\]\\^_`{|}~]/.test(command))throw Error('This USSD sender accepts codes and ASCII characters shared with the GSM alphabet.');
  return Array.from(command,c=>c.charCodeAt(0).toString(16).padStart(2,'0')).join('');
}
function decodeConsoleSnapshot(wire) {
  if(typeof wire!=='string'||wire.length!==1995||!/^c1:[0-9a-f]+$/.test(wire))throw Error('Invalid console snapshot');
  const raw=Uint8Array.from(wire.slice(3).match(/../g),x=>parseInt(x,16)),v=new DataView(raw.buffer);
  const w=Array.from({length:9},(_,i)=>v.getUint32(i*4,true));
  const [low,high,sequence,phase,kind,,tag,count,flags]=w,status=v.getInt32(20,true);
  if(phase>7||![0,97,117].includes(kind)||count>960||flags&~3||(!sequence&&(phase||kind||status||tag||count||flags))||(!(low||high)&&sequence)||((phase>=1&&phase<=4)!==(status===-2147483648)))throw Error('Inconsistent console snapshot');
  for(let i=36+count;i<raw.length;i++)if(raw[i])throw Error('Nonzero output padding');
  const outputBytes=raw.slice(36,36+count);let output=null;
  try {output=new TextDecoder('utf-8',{fatal:true}).decode(outputBytes);}catch{}
  return {nonce:wordHex(low)+':'+wordHex(high),initialized:!!(low||high),sequence,phase,kind:String.fromCharCode(kind),status,tag,
    pending:phase>=1&&phase<=4,quarantined:!!(flags&2),truncated:!!(flags&1),output,
    outputHex:wire.slice(75,75+2*count)};
}
function createConsoleSession({read,post,readNetwork,random=words=>globalThis.crypto.getRandomValues(words)}) {
  let busy=false,phase='unavailable',joined=null,current=null,action=null,history=[],network=null;
  const copy=a=>a?{...a,reply:a.reply?{...a.reply}:null}:null;
  const state=()=>({busy,phase,canSubmit:!busy&&phase==='ready',snapshot:current,network:network?{...network}:null,action:copy(action),history:history.map(copy)});
  async function readState(){
    const wire=await read(),c=decodeConsoleSnapshot(wire.console),u=decodeSessionSnapshot(wire.ussd);
    if(c.nonce!==u.submission.nonceRaw||c.sequence!==u.submission.sequence||c.status!==u.submission.status)throw Error('Snapshot changed while being read');
    current={console:c,ussd:u};return c;
  }
  function reconcile(c){
    if(action){
      if(!c.initialized||c.nonce!==action.nonce){action.outcome='session-lost';action.reply=null;}
      else {
        if(action.kind==='u'){
          const matches=current.ussd.events.filter(e=>e.requestSequence===action.sequence);
          if(matches.length){action.reply={...matches[matches.length-1]};action.outcome=classifyUssdEvent(action.reply);}
        }
        if(c.sequence===action.sequence){
          action.status=c.status;
          if(action.kind==='a'){action.output=c.output;action.outputHex=c.outputHex;action.truncated=c.truncated;}
          if(!action.reply)action.outcome=c.pending?'pending':c.phase===5?(action.kind==='u'?'accepted-awaiting-reply':'success'):c.phase===6?'error':'unknown';
        } else if(!action.reply)action.outcome=c.sequence>action.sequence?'superseded':'not-observed';
      }
    }
    phase=c.initialized&&c.nonce===joined?(c.quarantined?'quarantined':c.pending?'pending':c.sequence<0xffffffff?'ready':'unavailable'):'session-changed';
  }
  async function run(fn){if(busy)throw Error('Command operation in progress');busy=true;try{await fn();}finally{busy=false;}return state();}
  async function refresh(){try{reconcile(await readState());}catch{current=null;phase='unavailable';}}
  return {state,
    prepare:()=>run(async()=>{
      joined=null;phase='preparing';
      try{
        let c=await readState();
        if(!c.initialized){
          let words=new Uint32Array(2);for(let i=0;i<8&&!words.some(Boolean);i++)random(words);
          if(!words.some(Boolean))throw Error('No random session identity');
          try{await post(wordHex(words[0])+':'+wordHex(words[1])+':00000000:s:');}catch{}
          c=await readState();
        }
        if(!c.initialized){phase='unavailable';return;}
        joined=c.nonce;reconcile(c);
      }catch{current=null;phase='unavailable';}
    }),
    submit:(kind,command)=>run(async()=>{
      const payload=encodeConsoleCommand(kind,command);
      if(phase!=='ready'||!joined)throw Error('Connect the command session first');
      await refresh();if(phase!=='ready')return;
      if(kind==='u'){
        try{network=networkReadiness(await readNetwork());}
        catch{network={ready:false,reason:'Network readiness could not be read. Nothing was sent.'};}
        if(!network.ready)return;
        // Network I/O may span a restart or another producer. Recheck ownership.
        await refresh();if(phase!=='ready')return;
      }
      const c=current.console;
      if(action){history.unshift(copy(action));history=history.slice(0,20);}
      action={nonce:c.nonce,sequence:c.sequence+1,kind,command,outcome:'unknown',status:null,output:'',outputHex:'',truncated:false,reply:null};
      phase='sending';
      try{await post(c.nonce+':'+wordHex(action.sequence)+':'+kind+':'+payload);}catch{}
      await refresh();
    }),
    refresh:()=>run(refresh)
  };
}

// Path values come from observer.h, not from the carrier status byte.
function classifyUssdEvent(event){
  if(event.pathRaw===2)return 'ussd-error';
  if(![1,3].includes(event.pathRaw))return 'ussd-event';
  if(!event.payloadBytes)return 'ussd-empty';
  return typeof event.text==='string'&&event.text.length?'ussd-reply':'ussd-raw';
}
function networkReadiness(fields){
  if(!fields||!['1','5'].includes(fields.registration)||fields.sim!=='0')return {
    ready:false,reason:'SIM and network registration are not ready or could not be verified. Nothing was sent.'};
  return {ready:true,registration:fields.registration,sim:fields.sim,
    reason:'Registered. USSD availability still depends on the modem and network.'};
}
// Stock status1 direct paths only. Missing, duplicate or structured fields fail closed.
function decodeConsoleNetwork(doc){
  const children=n=>Array.from(n?.childNodes||[]).filter(c=>c.nodeType===1);
  const child=(n,name)=>{const all=children(n).filter(c=>c.nodeName===name);if(all.length!==1||all[0].attributes.length)throw Error('Invalid network field');return all[0];};
  const leaf=(n,name)=>{const v=child(n,name);if(Array.from(v.childNodes).some(c=>c.nodeType!==3)||!/^\d+$/.test(v.textContent))throw Error('Invalid network value');return v.textContent;};
  const root=doc?.documentElement;if(!root||root.nodeName!=='RGW'||root.attributes.length)throw Error('Invalid network root');
  const wan=child(root,'wan');return {registration:leaf(wan,'NW_register_status'),sim:leaf(child(wan,'cellular'),'sim_status')};
}

(function(w){
  'use strict';
  var bridge=w.MF885Community047Dev15.consoleBridge,client=null,busy=false,epoch=0,activeEpoch=0,lastQueue=null;
  var help={
    'AT+CSQ':'Reads the modem signal report. A value of 99 means unknown or unavailable.',
    'AT+CREG?':'Reads network registration. Status 1 is the home network; 5 is roaming.',
    'AT+CGATT?':'Reads packet service attachment: 1 means attached, 0 means detached.',
    'AT+CGDCONT?':'Lists data contexts, including configured APNs. It does not change them.',
    'ATE0':'Turns command echo off for this AT channel.',
    'ATE1':'Turns command echo on for this AT channel.',
    'AT+CMEE=2':'Requests descriptive modem errors on this AT channel.',
    manual:'Enter one complete AT command. Unsupported commands return a modem error.'
  };
  function el(id){return w.document.getElementById(id)}
  function check(){if(epoch!==activeEpoch||!bridge.sessionPresent())throw Error('Session expired')}
  function wire(doc){
    function children(n){return Array.prototype.filter.call(n.childNodes||[],function(c){return c.nodeType===1})}
    var root=doc&&doc.documentElement;
    if(!root||root.nodeName!=='RGW'||root.attributes.length)throw Error('Invalid response root');
    var modules=children(root);
    if(modules.length!==1||modules[0].nodeName!=='diagnostic'||modules[0].attributes.length)throw Error('Invalid response module');
    var fields=children(modules[0]),values={};
    if(fields.length!==3)throw Error('Missing console state');
    fields.forEach(function(field){
      if(!/^(console_v1|ussd_v1|queue_v1)$/.test(field.nodeName)||values[field.nodeName]!==undefined||field.attributes.length||Array.prototype.some.call(field.childNodes,function(n){return n.nodeType!==3}))throw Error('Invalid response field');
      values[field.nodeName]=field.textContent;
    });
    lastQueue=decodeQueueDiagnostic(values.queue_v1);
    return {console:values.console_v1,ussd:values.ussd_v1};
  }
  function newClient(){return createConsoleSession({
    read:async function(){check();var doc=await bridge.get('console');check();return wire(doc)},
    readNetwork:async function(){check();var doc=await bridge.network('console');check();return decodeConsoleNetwork(doc)},
    post:async function(value){check();await bridge.post(value,'console');check()},
    random:function(words){w.crypto.getRandomValues(words)}
  })}
  function input(kind){return el(kind==='u'?'ussdCode':'atCommand').value}
  function valid(kind){try{encodeConsoleCommand(kind,input(kind));return true}catch{return false}}
  function syncControls(){
    var blocked=busy||bridge.routerBusy()||!bridge.sessionPresent(),ready=client&&client.state().canSubmit;
    ['ussd','at'].forEach(function(prefix){
      el(prefix+'Prepare').disabled=blocked||!w.crypto||typeof w.crypto.getRandomValues!=='function';
      el(prefix+'Refresh').disabled=blocked;
      el(prefix+'Send').disabled=blocked||!ready||!valid(prefix==='ussd'?'u':'a');
    });
    el('ussdCode').disabled=busy;el('atCommand').disabled=busy;el('atPreset').disabled=busy;el('ussdBalance').disabled=busy;
  }
  var diagnosticReasons={
    '-2010':'The modem worker context could not be verified.',
    '-2011':'The command buffer was released through an unexpected path.',
    '-2012':'The copied command length did not match.',
    '-2013':'The copied command did not match.',
    '-2014':'The copied command terminator did not match.',
    '-2015':'The AT channel already had another pending response.',
    '-2016':'Another command producer used the AT channel.',
    '-2017':'The response identifier was reused or out of order.',
    '-2018':'The pending response record could not be verified.',
    '-2019':'The response could not be associated with this command.',
    '-2020':'No final response or pending record was observed.'
  };
  function status(action){
    if(!action)return '';
    return ({pending:'The modem is processing this command. Check result to read its status.',
      success:'Command completed.',error:action.status===-2021?'The AT channel is unavailable. This command was not executed. No automatic retry was sent.':action.status===-2015?'The AT channel is busy. This command was not executed. Wait, then submit a new command explicitly; no automatic retry was sent.':'The modem returned an error ('+action.status+').',
      'ussd-reply':'USSD text reply matched to this request.',
      'ussd-error':'The modem reported a USSD error. No automatic retry was sent.',
      'ussd-empty':'USSD completed without reply text. This is not a confirmed text response.',
      'ussd-raw':'USSD data received; its text encoding could not be decoded.',
      'ussd-event':'A USSD event was recorded; a reply is not confirmed.',
      'accepted-awaiting-reply':'The modem accepted the code. Waiting for a matching USSD reply.',
      'session-lost':'The router session changed. The previous result is unknown.',
      superseded:'A later command replaced the modem status. This result is unknown.',
      'not-observed':'The request has not been observed in modem state. It was not retried.',
      unknown:(diagnosticReasons[String(action.status)]||'The result is unknown.')+' New sends are disabled for this router session. No retry was sent. Diagnostic code: '+action.status})[action.outcome]||'Result unavailable.';
  }
  function eventText(event){
    var label=classifyUssdEvent(event),body=event.payloadBytes?(event.text!==null?event.text:'Raw data: '+event.payloadHex):'No reply text.';
    if(label==='ussd-reply')return body;
    return body+'\nDiagnostics: path '+event.pathRaw+'; status '+event.statusRaw+'; encoding selector '+event.codingSelectorRaw+'; details '+event.detailWordsRaw.join(', ');
  }
  function reply(action){
    if(!action)return '';
    if(action.kind==='u')return action.reply?(eventText(action.reply)):'';
    return (action.output===null?'Raw response: '+action.outputHex:action.output)+(action.truncated?'\n[Response exceeds the 960-byte display buffer]':'');
  }
  function renderQueue(){
    var q=lastQueue;
    el('atQueueState').textContent=!q?'No observation read.':!q.sampled?'No parser invocation observed yet. Responses observed: '+q.responses:
      'Last parser observation (not a live queue): '+(q.valid?'valid':'incomplete or invalid')+'\nPending records: '+q.pendingCount+' / 8'+
      '\nPending tags: '+(q.tags.map(function(x){return x.toString(16)}).join(', ')||'none')+
      '\nParser observations: '+q.samples+'; external: '+q.foreignCalls+'; ours: '+q.ownedCalls+
      '\nLast external command: '+(q.verb||'not recorded')+' (parameters omitted)'+
      '\nResponses observed: '+q.responses+'; last tag: '+q.responseTag.toString(16)+'; code: '+q.responseCode+'; error: '+q.responseError+
      '\nBusy rejections: '+q.busyRejections+'; diagnostic flags: '+q.flags+
      (q.context?'\nBorrowed context: object 0x'+q.context.parserAddress.toString(16)+'; callback 0x'+q.context.callbackAddress.toString(16)+'; head 0x'+q.context.pendingAddress.toString(16)+'; caller 0x'+q.context.callerAddress.toString(16):'\nPointer context not available in this snapshot version.');
  }
  function render(state){
    renderQueue();
    var all=state.action?[state.action].concat(state.history):state.history;
    ['ussd','at'].forEach(function(prefix){
      var kind=prefix==='ussd'?'u':'a',items=all.filter(function(a){return a.kind===kind}),latest=items[0];
      var availability=state.phase==='quarantined'?'Command ownership was lost. New sends are disabled for this router session.':state.canSubmit?'Connected. Enter a command and press Send.':state.phase==='pending'?'Another modem command is pending. Use Check result.':'Sign in and connect to read the modem session.';
      el(prefix+'Status').textContent=prefix==='ussd'&&state.network&&!state.network.ready?state.network.reason:latest?status(latest):availability;
      el(prefix+'Attempt').textContent=latest?'Request '+latest.sequence+' · '+latest.command:'';
      el(prefix+'Reply').textContent=reply(latest);el(prefix+'Reply').hidden=!reply(latest);
      var container=el(prefix+'History');container.textContent='';
      items.slice(1).forEach(function(a){var section=w.document.createElement('div'),title=w.document.createElement('strong'),body=w.document.createElement('pre');section.className='console-history-item';title.textContent='Request '+a.sequence+' · '+a.command;body.className='console-reply';body.textContent=status(a)+'\n'+reply(a);section.appendChild(title);section.appendChild(body);container.appendChild(section)});
    });
    var events=state.snapshot?state.snapshot.ussd.events:[];
    el('ussdEvents').textContent=events.length?events.map(function(e){return 'Event '+e.sequence+' · '+(e.requestSequence!==null?'request '+e.requestSequence:'unmatched')+'\n'+classifyUssdEvent(e)+'\n'+eventText(e)}).join('\n\n'):'No events read.';
  }
  async function run(operation,kind){
    var prefix=kind==='a'?'at':'ussd',command;
    if(busy||bridge.routerBusy()||!bridge.sessionPresent())return null;
    if(operation==='submit'){
      if(!client||!client.state().canSubmit)return null;
      command=input(kind);
      try{encodeConsoleCommand(kind,command)}catch(error){el(prefix+'Status').textContent=error.message;return null;}
      if(!w.confirm('Send '+command+' once?'))return null;
    }
    if(!bridge.begin('console',prefix+'Status'))return null;
    busy=true;activeEpoch=epoch;var started=epoch;syncControls();
    el(prefix+'Status').textContent=operation==='submit'?'Checking the session and sending once…':'Reading modem state…';
    try{
      if(!client)client=newClient();
      var result=operation==='submit'?await client.submit(kind,command):await client[operation]();
      if(started===epoch)render(result);return result;
    }catch(error){if(started===epoch)el(prefix+'Status').textContent='Operation stopped. No request was retried.';return null;}
    finally{busy=false;bridge.end('console');syncControls()}
  }
  function reset(){epoch++;client=null;lastQueue=null;renderQueue();['ussd','at'].forEach(function(p){el(p+'Status').textContent='Sign in and connect. No command is sent automatically.';el(p+'Attempt').textContent='';el(p+'Reply').textContent='';el(p+'Reply').hidden=true;el(p+'History').textContent=''});el('ussdEvents').textContent='No events read.';syncControls()}
  ['ussd','at'].forEach(function(prefix){var kind=prefix==='ussd'?'u':'a';['Prepare','Send','Refresh'].forEach(function(suffix){var operation={Prepare:'prepare',Send:'submit',Refresh:'refresh'}[suffix];el(prefix+suffix).addEventListener('click',function(){run(operation,kind)})})});
  el('ussdCode').addEventListener('input',syncControls);el('atCommand').addEventListener('input',function(){el('atPreset').value='manual';el('atHelp').textContent=help.manual;syncControls()});
  el('ussdBalance').addEventListener('click',function(){el('ussdCode').value='*100#';syncControls()});
  el('atPreset').addEventListener('change',function(){var preset=el('atPreset').value;el('atHelp').textContent=help[preset]||help.manual;if(preset!=='manual')el('atCommand').value=preset;syncControls()});
  w.MF885Community047Dev15Console={run:run,reset:reset,syncControls:syncControls,wire:wire};syncControls();
})(window);

})();
