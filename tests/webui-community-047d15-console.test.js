const test=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');
const root=path.resolve(__dirname,'..');
const assets=path.join(root,'webui/0.4.7-dev.15');
const derived={html:fs.readFileSync(path.join(assets,'c047d15.html'),'utf8'),core:fs.readFileSync(path.join(assets,'js/c047d15app.js'),'utf8'),ttl:fs.readFileSync(path.join(assets,'js/c047d15ttl.js'),'utf8'),engineering:fs.readFileSync(path.join(assets,'js/c047d15engineering.js'),'utf8'),capability:fs.readFileSync(path.join(assets,'c047d15ttl.json'),'utf8')};
const output=(g,t)=>`<RGW><diagnostic><command>retained-untrusted</command><arg>stale</arg><output>r47:${(g>>>0).toString(16).padStart(8,'0')}:${t.toString(16).padStart(2,'0')}</output></diagnostic></RGW>`;
const options={};
const ack=(g,t,arg)=>output(g,t).replace('<command>retained-untrusted</command><arg>stale</arg>',`<command>ttl</command><arg>${arg}</arg>`);
const identity = '<RGW><sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></sysinfo><batteryinfo><Battery_percent>83</Battery_percent></batteryinfo><wan><NW_register_status>1</NW_register_status><network_name>Example Carrier</network_name><sys_mode>6</sys_mode><cellular><sim_status>0</sim_status></cellular></wan><lan><run_days>0</run_days><run_hours>0</run_hours><run_minutes>1</run_minutes><run_seconds>0</run_seconds></lan></RGW>';
const wan = '<RGW><wan><Engineering_mode>0</Engineering_mode><query_time_interval>1</query_time_interval><NW_register_status>1</NW_register_status><network_name>Example Carrier</network_name><sys_mode>6</sys_mode><cellular><sim_status>0</sim_status></cellular></wan></RGW>';
const engineer = '<RGW><Engi><LTE><band>7</band><rsrp>45</rsrp><rsrq>16</rsrq></LTE></Engi></RGW>';
const stockEmpty = '<RGW><diagnostic><command/><arg/><output/></diagnostic></RGW>';
const retained = value => `<RGW><diagnostic><command>ttl</command><arg>${value}</arg><output/></diagnostic></RGW>`;

function fixture() {
  const dom = parseHTML(derived.html);
  // Keep browser globals off linkedom's globalThis-backed window proxy.
  const document = dom.document;
  const window = {document,DOMParser:dom.DOMParser,Event:dom.Event,addEventListener:dom.addEventListener.bind(dom)};
  Object.defineProperty(document.getElementById('folder'), 'value', { value: 'inbox', writable: true, configurable: true });
  Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
  const requests = [];const powerRequests=[];const powerQueue=[];let confirms=0;
  const consoleEntries = [];
  const timers = new Map();
  const diagnosticQueue = [];
  let timerSequence = 0;
  let requested = null, applied=64, generation=0;
  let nextCommandError=0;const ussdGetQueue=[],ussdPostQueue=[];let ussdNonce=[0,0],ussdSequence=0,ussdStatus=0,ussdSends=0,commandKind=0,commandText='',commandOutput='',consolePhase=0,ussdEvent=null;
  let queueHex="00".repeat(120);
  function ussdWire(){
    const raw=Buffer.alloc(1044),c=Buffer.alloc(996);
    raw.writeUInt32LE(ussdNonce[0],1028);raw.writeUInt32LE(ussdNonce[1],1032);raw.writeUInt32LE(ussdSequence,1036);raw.writeInt32LE(ussdStatus,1040);
    if(ussdEvent){raw[16]=1;raw[17]=1;raw.writeUInt32LE(1,4);raw.writeUInt32LE(1,20);raw.writeUInt32LE(ussdEvent.sequence,24);raw[32]=33;raw[33]=ussdEvent.path??1;raw[36]=ussdEvent.status??0;raw[37]=ussdEvent.selector??5;raw.writeUInt16LE(ussdEvent.details?.[0]??0,268);raw.writeUInt16LE(ussdEvent.details?.[1]??0,270);const body=ussdEvent.raw?Buffer.from(ussdEvent.raw,'hex'):Buffer.from(ussdEvent.text,'utf16le');if(!ussdEvent.raw)body.swap16();raw[38]=body.length;body.copy(raw,39);}
    [ussdNonce[0],ussdNonce[1],ussdSequence,consolePhase,commandKind,ussdStatus>>>0,0,Buffer.byteLength(commandOutput),0].forEach((v,i)=>c.writeUInt32LE(v,i*4));c.write(commandOutput,36);
    return '<RGW><diagnostic><console_v1>c1:'+c.toString('hex')+'</console_v1><ussd_v1>u4:'+raw.toString('hex')+'</ussd_v1><queue_v1>q2:'+queueHex+'</queue_v1></diagnostic></RGW>';
  }
  const networkQueue=[];
  const postQueue=[], capabilityQueue=[],wanQueue=[],wanPostQueue=[];let engineeringMode='0';
  function wanBody(){return wan.replace('<Engineering_mode>0</Engineering_mode>','<Engineering_mode>'+engineeringMode+'</Engineering_mode>')}
  Object.defineProperty(document.getElementById('engineeringMode'),'value',{value:'0',writable:true,configurable:true});
  Object.defineProperty(document.getElementById('ttlMode'),'value',{value:'64',writable:true,configurable:true});

  function responseFor(xhr) {
    if (xhr.url === '/c047d15ttl.json') return capabilityQueue.length?capabilityQueue.shift():{body:derived.capability};
    if (xhr.url === '/login.cgi') return { body: '', auth: 'Digest realm="Highwmg", nonce="abcdef", qop="auth"' };
    if (xhr.url.startsWith('/login.cgi?')) return { body: '' };
    if (/file=status1$/.test(xhr.url)) {const next=networkQueue.length?networkQueue.shift():{body:identity};if(next.before)next.before();return next;}
    if (/file=c047d15console$/.test(xhr.url)) {
      if(xhr.method==='POST'){
        const match=xhr.body.match(/^<\?xml version="1.0" encoding="US-ASCII"\?> <RGW><diagnostic><console_v1>([0-9a-f]{8}):([0-9a-f]{8}):([0-9a-f]{8}):([sau]):([0-9a-f]{0,448})<\/console_v1><\/diagnostic><\/RGW>$/);assert.ok(match,'exact console POST envelope');
        const fields=match.slice(1,4).map(x=>parseInt(x,16)),kind=match[4],command=Buffer.from(match[5],'hex').toString('ascii');
        if(!(ussdNonce[0]||ussdNonce[1])&&fields[2]===0&&kind==='s')ussdNonce=fields.slice(0,2);
        else if(fields[0]===ussdNonce[0]&&fields[1]===ussdNonce[1]&&fields[2]===ussdSequence+1){ussdSequence=fields[2];ussdSends++;commandKind=kind.charCodeAt(0);commandText=command;consolePhase=5;commandOutput=kind==='a'?'+CSQ: 15,99\r\nOK\r\n':'';}
        if(nextCommandError && kind!=='s'){ussdStatus=nextCommandError;consolePhase=6;commandOutput='';nextCommandError=0;}
        return ussdPostQueue.length?ussdPostQueue.shift():{body:'<RGW/>'};
      }
      return ussdGetQueue.length?ussdGetQueue.shift():{body:ussdWire()};
    }
    if (/file=wan$/.test(xhr.url)) {
      if(xhr.method==='POST'){
        const match=/^<\?xml version="1.0" encoding="US-ASCII"\?> <RGW><wan><Engineering_mode>([01])<\/Engineering_mode>(<query_time_interval>1<\/query_time_interval>)?<\/wan><\/RGW>$/.exec(xhr.body);
        assert.ok(match,'exact Engineering wire envelope');assert.equal(!!match[2],match[1]==='1');engineeringMode=match[1];
        return wanPostQueue.length?wanPostQueue.shift():{body:'<RGW/>'};
      }
      return wanQueue.length?wanQueue.shift():{body:wanBody()};
    }
    if (/file=Engineer_parameter$/.test(xhr.url)) return { body: engineer };
    if (/file=message$/.test(xhr.url)) return xhr.method === 'POST' ? { body: '<RGW/>' } : { body: '<RGW><message><get_message><total_number>0</total_number><message_list/></get_message></message></RGW>' };
    if (/file=diagnostic$/.test(xhr.url)) {
      if (xhr.method === 'POST') {
        assert.match(xhr.body, /^<\?xml version="1.0" encoding="US-ASCII"\?> <RGW><diagnostic><command>ttl<\/command><arg>(off|[1-9][0-9]{0,2})<\/arg><\/diagnostic><\/RGW>$/);
        const match = xhr.body.match(/<arg>([^<]+)<\/arg>/);
        requested=match[1]; applied=requested==='off'?0:Number(requested);
        generation=generation===0xffffff?1:generation+1;
        return postQueue.length?postQueue.shift():{body:ack(generation,applied,requested)};
      }
      return diagnosticQueue.length ? (typeof diagnosticQueue[0]==='string'?{body:diagnosticQueue.shift()}:diagnosticQueue.shift()) : {body:output(generation,applied)};
    }
    throw new Error(`Unexpected route ${xhr.method} ${xhr.url}`);
  }

  class FakeXHR {
    constructor() { this.headers = {}; this.status = 0; this.responseText = ''; requests.push(this); }
    open(method, url, async) { this.method = method; this.url = url; this.async = async; }
    setRequestHeader(name, value) { this.headers[name] = value; }
    getResponseHeader(name) { return String(name).toLowerCase() === 'www-authenticate' ? (this.auth || '') : ''; }
    send(body) {
      this.body = body;
      let reply;
      try { reply = responseFor(this); } catch (error) { queueMicrotask(() => this.onerror && this.onerror(error)); return; }
      this.status = reply.status || 200; this.responseText = reply.body || ''; this.auth = reply.auth || '';
      if(reply.timeout){queueMicrotask(() => this.ontimeout());return;}
      if(reply.hold){this.release=()=>this.onload();return;}
      queueMicrotask(() => this.onload && this.onload());
    }
    abort() { queueMicrotask(() => this.onabort && this.onabort()); }
  }

  window.crypto=crypto.webcrypto;
  window.XMLHttpRequest = FakeXHR;
  window.location = { protocol: 'http:', host: '192.168.21.1', hash: '' };
  window.hex_md5 = input => crypto.createHash('md5').update(String(input)).digest('hex');
  window.confirm = () => {confirms++;return true};
  window.AbortController=class{constructor(){this.signal={}}abort(){}};
  window.fetch=async(url,options)=>{
    powerRequests.push({url,options});if(powerQueue.length){const response=powerQueue.shift();if(response.error)throw Error('network');if(response.body!==undefined)return {status:response.status||200,headers:{get:()=>response.auth||''},text:async()=>response.body};}
    const body=/file=status1$/.test(url)?identity:/file=reset$/.test(url)?'<RGW><reboot/></RGW>':/file=poweroff$/.test(url)?'<RGW><shutdown/></RGW>':'';
    return {status:url==='/login.cgi'?401:200,headers:{get:()=>url==='/login.cgi'?'Digest realm="Highwmg", nonce="abcdef", qop="auth"':''},text:async()=>body};
  };
  window.sessionStorage = { getItem() { return null; }, setItem() {} };
  window.setTimeout = (callback, delay) => { const id = ++timerSequence; timers.set(id, { callback, delay: Number(delay) || 0, cleared: false }); return id; };
  window.clearTimeout = id => { const timer = timers.get(id); if (timer) timer.cleared = true; };
  window.console = { debug(...values) { consoleEntries.push(['debug', ...values]); }, error(...values) { consoleEntries.push(['error', ...values]); } };
  const context = { window, document, console: window.console, Date, JSON, Array, Object, String, Number, Boolean, RegExp, Error, Promise, Map, Set, Uint8Array,Uint32Array,DataView,TextDecoder };
  vm.createContext(context);
  vm.runInContext(derived.core, context, { filename: 'c047d15app.js' });
  vm.runInContext(derived.ttl, context, { filename: 'c047d15ttl.js' });
  vm.runInContext(derived.engineering, context, { filename: 'c047d15engineering.js' });
  vm.runInContext(fs.readFileSync(path.join(assets,'js/c047d15power.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(assets,'js/c047d15console.js'),'utf8'),context);
  return { networkQueue,setUssdEvent(e){ussdEvent={sequence:ussdSequence,text:'',...e}},failNextCommand(code){nextCommandError=code},setQueue(raw){queueHex=raw.toString("hex")},ussd:window.MF885Community047Dev15Console,ussdGetQueue,ussdPostQueue,get ussdSends(){return ussdSends},ussdReboot(){ussdNonce=[0,0];ussdSequence=0;ussdStatus=0;consolePhase=0;commandKind=0;commandOutput='';ussdEvent=null},setUssdReply(text){ussdEvent={sequence:ussdSequence,text}},get commandText(){return commandText},powerRequests,powerQueue, window, document, requests, consoleEntries, timers, wanQueue,wanPostQueue,setEngineeringMode(value){engineeringMode=value},engineering:window.MF885Community047Dev15Engineering,diagnosticQueue, postQueue, capabilityQueue, setRemote(g,v){generation=g;applied=v;}, ttl: window.MF885Community047Dev15TTL, get requested() { return requested; } };
}

async function waitFor(predicate, label) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (predicate()) return;
    await new Promise(resolve => setImmediate(resolve));
  }
  throw new Error(`Timed out waiting for ${label}`);
}

async function login(value) {
  value.document.getElementById('password').value = 'fixture-password';
  value.document.getElementById('loginForm').dispatchEvent(new value.window.Event('submit'));
  await waitFor(() => !value.document.getElementById('app').hidden, 'authenticated shell');
  await waitFor(() => !value.document.getElementById('refreshAll').disabled, 'bootstrap finished');
}




test('USSD follows Messages, AT follows USSD, and all existing pages survive',async()=>{
  const f=fixture();const nav=Array.from(f.document.querySelectorAll('button[data-page]'),n=>n.getAttribute('data-page'));
  assert.equal(nav[nav.indexOf('messages')+1],'ussd');assert.equal(nav[nav.indexOf('ussd')+1],'at');
  for(const page of ['dashboard','messages','diagnostics','modem','ttl','ussd','at'])assert.ok(f.document.getElementById('page-'+page));
  assert.equal(f.document.getElementById('ussdCode').value,'');assert.equal(f.ussdSends,0);
});
test('arbitrary entered USSD reaches authenticated POST, refresh never resends',async()=>{
  const f=fixture();await login(f);await f.ussd.run('prepare','u');assert.equal(f.ussdSends,0);
  f.document.getElementById('ussdCode').value='*123*456#';await f.ussd.run('submit','u');
  assert.equal(f.ussdSends,1);assert.equal(f.commandText,'*123*456#');assert.match(f.document.getElementById('ussdAttempt').textContent,/\*123\*456#/);
  f.setUssdReply('Test reply');await f.ussd.run('refresh','u');assert.equal(f.ussdSends,1);assert.equal(f.document.getElementById('ussdReply').textContent,'Test reply');
  assert.match(f.document.getElementById('ussdStatus').textContent,/matched/);
});
test('balance shortcut only fills the input',async()=>{
  const f=fixture();await login(f);await f.ussd.run('prepare','u');f.document.getElementById('ussdBalance').click();
  assert.equal(f.document.getElementById('ussdCode').value,'*100#');assert.equal(f.ussdSends,0);
});
test('manual AT and setting commands share response and history',async()=>{
  const f=fixture();await login(f);await f.ussd.run('prepare','a');
  f.document.getElementById('atCommand').value='AT+CSQ';await f.ussd.run('submit','a');
  assert.equal(f.commandText,'AT+CSQ');assert.match(f.document.getElementById('atReply').textContent,/CSQ: 15,99/);
  f.document.getElementById('atCommand').value='ATE0';await f.ussd.run('submit','a');
  assert.equal(f.commandText,'ATE0');assert.equal(f.ussdSends,2);assert.match(f.document.getElementById('atHistory').textContent,/AT\+CSQ/);
});
test('reboot between preparation and sending does not send or reclaim',async()=>{
  const f=fixture();await login(f);await f.ussd.run('prepare','u');const count=f.requests.filter(r=>r.method==='POST'&&/file=c047d15console$/.test(r.url)).length;
  f.ussdReboot();f.document.getElementById('ussdCode').value='*101#';await f.ussd.run('submit','u');assert.equal(f.ussdSends,0);
  assert.equal(f.requests.filter(r=>r.method==='POST'&&/file=c047d15console$/.test(r.url)).length,count);
});
test('a lost POST reply is read back without another send',async()=>{
  const f=fixture();await login(f);await f.ussd.run('prepare','u');f.ussdPostQueue.push({timeout:true});
  f.document.getElementById('ussdCode').value='*102#';await f.ussd.run('submit','u');await f.ussd.run('refresh','u');assert.equal(f.ussdSends,1);
});
test('empty and injected input never reach POST; carrier markup stays text',async()=>{
  const f=fixture();await login(f);await f.ussd.run('prepare','u');
  for(const code of ['', '*100#\r*101#']){f.document.getElementById('ussdCode').value=code;await f.ussd.run('submit','u');}
  assert.equal(f.ussdSends,0);f.document.getElementById('ussdCode').value='*101#';await f.ussd.run('submit','u');
  f.setUssdReply('<img src=x onerror=alert(1)>');await f.ussd.run('refresh','u');assert.equal(f.document.getElementById('ussdReply').querySelector('img'),null);assert.match(f.document.getElementById('ussdReply').textContent,/<img/);
});

test('queue diagnostics refreshes stored counters without a command',async()=>{
 const f=fixture();await login(f);await f.ussd.run('prepare','a');
 const raw=Buffer.alloc(120);[3,2,1,1,1,1,1,0xc000b,0,0,1,1,0xc000b].forEach((v,i)=>raw.writeUInt32LE(v,4*i));raw.write('AT+CSQ',80);[0x07100000,0x060957c1,0x07100590,0x060957a5].forEach((v,i)=>raw.writeUInt32LE(v,104+4*i));f.setQueue(raw);
 const before=f.requests.filter(r=>r.method==='POST').length;await f.ussd.run('refresh','a');
 assert.match(f.document.getElementById('atQueueState').textContent,/Pending records: 1 \/ 8/);
 assert.match(f.document.getElementById('atQueueState').textContent,/Last external command: AT\+CSQ/);
 assert.match(f.document.getElementById('atQueueState').textContent,/not a live queue/);
 assert.match(f.document.getElementById('atQueueState').textContent,/object 0x7100000; callback 0x60957c1; head 0x7100590; caller 0x60957a5/);
 assert.equal(f.requests.filter(r=>r.method==='POST').length,before);assert.equal(f.ussdSends,0);
});
test('invalid diagnostic bounds stop before any command',async()=>{
 const f=fixture();await login(f);await f.ussd.run('prepare','a');
 const raw=Buffer.alloc(120);raw.writeUInt32LE(9,20);f.setQueue(raw);
 const before=f.requests.filter(r=>r.method==='POST').length;const stopped=await f.ussd.run('refresh','a');assert.equal(stopped.phase,'unavailable');assert.equal(stopped.canSubmit,false);
 assert.equal(f.requests.filter(r=>r.method==='POST').length,before);assert.equal(f.ussdSends,0);
});

test('missing AT parser explains non-execution and never retries',async()=>{
 const f=fixture();await login(f);await f.ussd.run('prepare','a');f.failNextCommand(-2021);
 f.document.getElementById('atCommand').value='AT+CSQ';await f.ussd.run('submit','a');
 assert.match(f.document.getElementById('atStatus').textContent,/channel is unavailable/);
 assert.match(f.document.getElementById('atStatus').textContent,/not executed/);
 await f.ussd.run('refresh','a');assert.equal(f.ussdSends,1);
});


test('actual dev14 empty error is an error in current result, events and history',async()=>{
 const f=fixture();await login(f);await f.ussd.run('prepare','u');
 f.document.getElementById('ussdCode').value='*100#';await f.ussd.run('submit','u');
 f.setUssdEvent({path:2,status:2,selector:1,details:[4,12808]});
 const state=await f.ussd.run('refresh','u');assert.equal(state.action.outcome,'ussd-error');
 assert.match(f.document.getElementById('ussdStatus').textContent,/USSD error/);
 assert.match(f.document.getElementById('ussdReply').textContent,/No reply text/);
 assert.match(f.document.getElementById('ussdReply').textContent,/details 4, 12808/);
 assert.doesNotMatch(f.document.getElementById('ussdStatus').textContent,/reply matched/);
 assert.match(f.document.getElementById('ussdEvents').textContent,/ussd-error/);
 assert.equal(f.ussdSends,1);
 f.document.getElementById('ussdCode').value='*101#';await f.ussd.run('submit','u');
 assert.match(f.document.getElementById('ussdHistory').textContent,/USSD error/);
});
test('text-bearing errors, empty results and binary events cannot become successful text',async()=>{
 const f=fixture();await login(f);await f.ussd.run('prepare','u');
 f.document.getElementById('ussdCode').value='*100#';await f.ussd.run('submit','u');
 for(const [event,outcome] of [
  [{path:2,text:'Failure'},'ussd-error'],[{path:1,text:''},'ussd-empty'],
  [{path:1,selector:2,raw:'ff'},'ussd-raw'],[{path:4,text:'Unknown'},'ussd-event']]){
  f.setUssdEvent(event);const s=await f.ussd.run('refresh','u');assert.equal(s.action.outcome,outcome);
  assert.doesNotMatch(f.document.getElementById('ussdStatus').textContent,/reply matched/);
 }
 assert.equal(f.ussdSends,1);
});
test('unready, missing, duplicate, nested and unreadable registration prevent command POST',async()=>{
 const f=fixture();await login(f);await f.ussd.run('prepare','u');
 f.document.getElementById('ussdCode').value='*100#';
 const before=f.requests.filter(r=>r.method==='POST').length;
 for(const response of [
  {body:identity.replace('<NW_register_status>1','<NW_register_status>11')},
  {body:identity.replace('<sim_status>0','<sim_status>1')},
  {body:identity.replace('<NW_register_status>1</NW_register_status>','')},
  {body:identity.replace('<NW_register_status>1</NW_register_status>','<NW_register_status>1</NW_register_status><NW_register_status>1</NW_register_status>')},
  {body:identity.replace('<NW_register_status>1</NW_register_status>','<NW_register_status><x>1</x></NW_register_status>')},
  {timeout:true}]){
  f.networkQueue.push(response);await f.ussd.run('submit','u');
  assert.equal(f.ussdSends,0);assert.match(f.document.getElementById('ussdStatus').textContent,/Nothing was sent/);
 }
 assert.equal(f.requests.filter(r=>r.method==='POST').length,before);
 // Recovery alone does not send; the next explicit submit rechecks the network.
 await f.ussd.run('refresh','u');assert.equal(f.ussdSends,0);
 f.networkQueue.push({body:identity.replace('<NW_register_status>1','<NW_register_status>5')});
 await f.ussd.run('submit','u');assert.equal(f.ussdSends,1);
});
test('network check is fresh for every USSD and does not gate offline AT diagnostics',async()=>{
 const f=fixture();await login(f);await f.ussd.run('prepare','u');
 f.document.getElementById('ussdCode').value='*100#';await f.ussd.run('submit','u');assert.equal(f.ussdSends,1);
 f.networkQueue.push({body:identity.replace('<NW_register_status>1','<NW_register_status>11')});
 await f.ussd.run('submit','u');assert.equal(f.ussdSends,1);
 const before=f.requests.filter(r=>/file=status1$/.test(r.url)).length;
 f.document.getElementById('atCommand').value='AT+CSQ';await f.ussd.run('submit','a');
 assert.equal(f.ussdSends,2);assert.equal(f.requests.filter(r=>/file=status1$/.test(r.url)).length,before);
});
test('restart while network status is loading prevents sending into the new session',async()=>{
 const f=fixture();await login(f);await f.ussd.run('prepare','u');
 f.networkQueue.push({body:identity,before:()=>f.ussdReboot()});
 const before=f.requests.filter(r=>r.method==='POST').length;
 f.document.getElementById('ussdCode').value='*100#';await f.ussd.run('submit','u');
 assert.equal(f.ussdSends,0);assert.equal(f.requests.filter(r=>r.method==='POST').length,before);
});
