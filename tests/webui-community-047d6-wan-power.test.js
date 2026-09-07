const test=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');
const root=path.resolve(__dirname,'..');
const assets=path.join(root,fs.existsSync(path.join(root,'public-export.json'))?'public/webui/0.4.7-dev.6':'webui/0.4.7-dev.6');
const derived={html:fs.readFileSync(path.join(assets,'c047d6.html'),'utf8'),core:fs.readFileSync(path.join(assets,'js/c047d6app.js'),'utf8'),ttl:fs.readFileSync(path.join(assets,'js/c047d6ttl.js'),'utf8'),engineering:fs.readFileSync(path.join(assets,'js/c047d6engineering.js'),'utf8'),capability:fs.readFileSync(path.join(assets,'c047d6ttl.json'),'utf8')};
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
  const postQueue=[], capabilityQueue=[],wanQueue=[],wanPostQueue=[];let engineeringMode='0';
  function wanBody(){return wan.replace('<Engineering_mode>0</Engineering_mode>','<Engineering_mode>'+engineeringMode+'</Engineering_mode>')}
  Object.defineProperty(document.getElementById('engineeringMode'),'value',{value:'0',writable:true,configurable:true});
  Object.defineProperty(document.getElementById('ttlMode'),'value',{value:'64',writable:true,configurable:true});

  function responseFor(xhr) {
    if (xhr.url === '/c047d6ttl.json') return capabilityQueue.length?capabilityQueue.shift():{body:derived.capability};
    if (xhr.url === '/login.cgi') return { body: '', auth: 'Digest realm="Highwmg", nonce="abcdef", qop="auth"' };
    if (xhr.url.startsWith('/login.cgi?')) return { body: '' };
    if (/file=status1$/.test(xhr.url)) return { body: identity };
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
  const context = { window, document, console: window.console, Date, JSON, Array, Object, String, Number, Boolean, RegExp, Error, Promise, Map, Set, Uint8Array };
  vm.createContext(context);
  vm.runInContext(derived.core, context, { filename: 'c047d6app.js' });
  vm.runInContext(derived.ttl, context, { filename: 'c047d6ttl.js' });
  vm.runInContext(derived.engineering, context, { filename: 'c047d6engineering.js' });
  vm.runInContext(fs.readFileSync(path.join(assets,'js/c047d6power.js'),'utf8'),context);
  return { powerRequests,powerQueue, window, document, requests, consoleEntries, timers, wanQueue,wanPostQueue,setEngineeringMode(value){engineeringMode=value},engineering:window.MF885Community047Dev6Engineering,diagnosticQueue, postQueue, capabilityQueue, setRemote(g,v){generation=g;applied=v;}, ttl: window.MF885Community047Dev6TTL, get requested() { return requested; } };
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



function diag(f, method) {return f.requests.filter(r=>/file=diagnostic$/.test(r.url)&&(!method||r.method===method));}
function phase(f) {return f.document.getElementById('ttlStatus').getAttribute('data-phase');}
async function ready() {const f=fixture();await login(f);await f.ttl.read();assert.equal(phase(f),'ready');return f;}


function writes(f){return f.requests.filter(x=>x.method==='POST'&&/file=wan$/.test(x.url))}

test('Engineering reads, applies Enabled/Disabled with exact body and readback; TTL still works',async()=>{
  const f=await ready();await f.engineering.read();
  assert.equal(f.engineering.state.current.mode,'0');
  await f.engineering.apply('1');assert.equal(f.engineering.state.current.mode,'1');assert.equal(writes(f).length,1);
  await f.engineering.apply('0');assert.equal(f.engineering.state.current.mode,'0');assert.equal(writes(f).length,2);
  assert.equal(f.engineering.state.locked,false);
  assert.ok(writes(f).every(r=>r.timeout===60000));
  await f.ttl.setValue('off');assert.equal(f.ttl.state.current.value,0);
  assert.doesNotMatch(derived.html,/produced an empty immediate response|does not offer a switch/);
});
test('Timed out Engineering POST is never replayed; readback resolves it, and shared lock excludes TTL',async()=>{
  const f=await ready();await f.engineering.read();f.wanPostQueue.push({timeout:true});
  await f.engineering.apply('1');assert.equal(writes(f).length,1);assert.equal(f.engineering.state.current.mode,'1');
  assert.match(f.document.getElementById('engineeringStatus').textContent,/separate read confirmed/);
  const bridge=f.window.MF885Community047Dev6.engineeringBridge;
  assert.equal(bridge.begin('engineering-write','engineeringStatus'),true);
  const before=diag(f).length;await f.ttl.read();assert.equal(diag(f).length,before);bridge.end('engineering-write');
});
test('Changed remote state, malformed fields and expired local epoch cannot unlock a write',async()=>{
  const f=await ready();await f.engineering.read();f.setEngineeringMode('1');
  await f.engineering.apply('1');assert.equal(writes(f).length,0);assert.equal(f.engineering.state.locked,true);
  const bad=new f.window.DOMParser().parseFromString('<RGW><wan><Engineering_mode>0</Engineering_mode><Engineering_mode>1</Engineering_mode><query_time_interval>1</query_time_interval></wan></RGW>','text/xml');
  assert.throws(()=>f.engineering.parseState(bad),/E_ENGINEERING_RESPONSE/);
  f.wanQueue.push({body:wan,hold:true});const pending=f.engineering.read();
  await waitFor(()=>f.requests.some(x=>x.release),'held read');f.engineering.reset();f.requests.find(x=>x.release).release();await pending;
  assert.equal(f.engineering.state.current,null);assert.equal(f.engineering.state.locked,true);assert.equal(writes(f).length,0);
});

test('WAN output keeps personal addresses, separates PDPs, excludes credentials and duplicate navigation',async()=>{
 const f=await ready(),xml='<RGW><wan><ip>100.64.0.2</ip><dns1>1.1.1.1</dns1><password>SECRET</password><cellular><pdp_context_list><Item><apn>example.apn</apn><ipv4>10.0.0.1</ipv4><password>SECRET</password></Item><Item><ipv4>10.0.0.2</ipv4></Item></pdp_context_list></cellular></wan><lan><ip>192.168.21.1</ip></lan></RGW>';
 const rows=f.window.MF885Community047Dev6.wanRows({endpoints:{status1:{ok:true,doc:new f.window.DOMParser().parseFromString(xml,'text/xml')}}});
 assert.match(JSON.stringify(rows),/100.64.0.2/);assert.match(JSON.stringify(rows),/PDP 2/);assert.match(JSON.stringify(rows),/example.apn/);assert.doesNotMatch(JSON.stringify(rows),/SECRET|192.168.21.1/);
 assert.equal(f.document.querySelectorAll('#page-dashboard button[data-page]').length,0);assert.equal(f.document.querySelectorAll('nav button[data-page]').length,5);
 assert.ok(f.document.querySelector('#page-dashboard #routerReboot'));
});
test('Power uses APP nc2/3, same header for fresh identity and one command, no POST, no redirect, and local logout',async()=>{
 for(const action of ['reboot','poweroff']){const f=await ready();assert.equal(await f.window.MF885Community047Dev6Power.apply(action),true);
 assert.equal(f.powerRequests.length,4);const [challenge,login,identity,command]=f.powerRequests;
 assert.equal(challenge.url,'/login.cgi');assert.match(login.url,/client=APP/);assert.match(login.options.headers.Authorization,/nc=00000003.*client=APP$/);
 const params=new URLSearchParams(login.url.split('?')[1]);const expected=crypto.createHash('md5').update(crypto.createHash('md5').update('admin:Highwmg:fixture-password').digest('hex')+':abcdef:00000002:'+params.get('cnonce')+':auth:'+crypto.createHash('md5').update('GET:/cgi/protected.cgi').digest('hex')).digest('hex');assert.equal(params.get('response'),expected);
 assert.equal(identity.options.headers.Authorization,login.options.headers.Authorization);assert.equal(command.options.headers.Authorization,login.options.headers.Authorization);
 assert.ok(command.url.endsWith('file='+(action==='reboot'?'reset':'poweroff')));assert.ok(f.powerRequests.every(x=>x.options.method==='GET'&&x.options.redirect==='error'&&!x.options.body));
 assert.equal(f.document.getElementById('app').hidden,true);assert.match(f.document.getElementById('loginStatus').textContent,/physical effect is not yet confirmed/);
 await f.window.MF885Community047Dev6Power.apply(action);assert.equal(f.powerRequests.length,4);
 }
});
test('Power cancel, changed identity, concurrency and delivery failure never trigger another command',async()=>{
 const f=await ready();f.window.confirm=()=>false;await f.window.MF885Community047Dev6Power.apply('reboot');assert.equal(f.powerRequests.length,0);f.window.confirm=()=>true;
 const bridge=f.window.MF885Community047Dev6.engineeringBridge;bridge.begin('engineering-read','engineeringStatus');await f.window.MF885Community047Dev6Power.apply('reboot');assert.equal(f.powerRequests.length,0);bridge.end('engineering-read');
 f.powerQueue.push({body:'',auth:'Digest realm="Highwmg", nonce="abcdef", qop="auth"'},{body:''},{body:identity.replace('MF96 Ver.D','MF96 Ver.X')});
 await f.window.MF885Community047Dev6Power.apply('reboot');assert.equal(f.powerRequests.length,3);assert.doesNotMatch(f.powerRequests.map(x=>x.url).join(' '),/file=reset/);
 const g=await ready();g.powerQueue.push({body:'',auth:'Digest realm="Highwmg", nonce="abcdef", qop="auth"'},{body:''},{body:identity},{error:true});await g.window.MF885Community047Dev6Power.apply('reboot');assert.equal(g.powerRequests.length,4);assert.match(g.document.getElementById('loginStatus').textContent,/result is unknown/);
});

test('Power accepts the exact captured APP envelope and rejects arbitrary HTML before the command',async()=>{
 for(const valid of [true,false]){const f=await ready();f.powerQueue.push({body:'',auth:'Digest realm="Highwmg", nonce="abcdef", qop="auth"'},{body:valid?'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nServer: Mongoose/3.0\r\n\r\n':'<html>OK</html>'});const result=await f.window.MF885Community047Dev6Power.apply('reboot');assert.equal(result,valid);assert.equal(f.powerRequests.length,valid?4:2);}
});
