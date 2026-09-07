const test=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');
const root=path.resolve(__dirname,'..');
const assets=path.join(root,fs.existsSync(path.join(root,'public-export.json'))?'public/webui/0.4.7-dev.5':'webui/0.4.7-dev.5');
const derived={html:fs.readFileSync(path.join(assets,'c047d5.html'),'utf8'),core:fs.readFileSync(path.join(assets,'js/c047d5app.js'),'utf8'),ttl:fs.readFileSync(path.join(assets,'js/c047d5ttl.js'),'utf8'),engineering:fs.readFileSync(path.join(assets,'js/c047d5engineering.js'),'utf8'),capability:fs.readFileSync(path.join(assets,'c047d5ttl.json'),'utf8')};
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
  const requests = [];
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
    if (xhr.url === '/c047d5ttl.json') return capabilityQueue.length?capabilityQueue.shift():{body:derived.capability};
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
  window.confirm = () => true;
  window.sessionStorage = { getItem() { return null; }, setItem() {} };
  window.setTimeout = (callback, delay) => { const id = ++timerSequence; timers.set(id, { callback, delay: Number(delay) || 0, cleared: false }); return id; };
  window.clearTimeout = id => { const timer = timers.get(id); if (timer) timer.cleared = true; };
  window.console = { debug(...values) { consoleEntries.push(['debug', ...values]); }, error(...values) { consoleEntries.push(['error', ...values]); } };
  const context = { window, document, console: window.console, Date, JSON, Array, Object, String, Number, Boolean, RegExp, Error, Promise, Map, Set, Uint8Array };
  vm.createContext(context);
  vm.runInContext(derived.core, context, { filename: 'c047d5app.js' });
  vm.runInContext(derived.ttl, context, { filename: 'c047d5ttl.js' });
  vm.runInContext(derived.engineering, context, { filename: 'c047d5engineering.js' });
  return { window, document, requests, consoleEntries, timers, wanQueue,wanPostQueue,setEngineeringMode(value){engineeringMode=value},engineering:window.MF885Community047Dev5Engineering,diagnosticQueue, postQueue, capabilityQueue, setRemote(g,v){generation=g;applied=v;}, ttl: window.MF885Community047Dev5TTL, get requested() { return requested; } };
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
  const bridge=f.window.MF885Community047Dev5.engineeringBridge;
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
