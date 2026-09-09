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
