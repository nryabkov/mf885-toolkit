const test=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');
const root=path.resolve(__dirname,'..');
const assets=path.join(root,fs.existsSync(path.join(root,'public-export.json'))?'public/webui/0.4.7-dev.4':'webui/0.4.7-dev.4');
const derived={html:fs.readFileSync(path.join(assets,'c047d4.html'),'utf8'),core:fs.readFileSync(path.join(assets,'js/c047d4app.js'),'utf8'),ttl:fs.readFileSync(path.join(assets,'js/c047d4ttl.js'),'utf8'),capability:fs.readFileSync(path.join(assets,'c047d4ttl.json'),'utf8')};
const output=(g,t)=>`<RGW><diagnostic><command>retained-untrusted</command><arg>stale</arg><output>r47:${(g>>>0).toString(16).padStart(8,'0')}:${t.toString(16).padStart(2,'0')}</output></diagnostic></RGW>`;
const options={};
const ack=(g,t,arg)=>output(g,t).replace('<command>retained-untrusted</command><arg>stale</arg>',`<command>ttl</command><arg>${arg}</arg>`);
const identity = '<RGW><sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></sysinfo><batteryinfo><Battery_percent>83</Battery_percent></batteryinfo><wan><NW_register_status>1</NW_register_status><network_name>Example Carrier</network_name><sys_mode>6</sys_mode><cellular><sim_status>0</sim_status></cellular></wan><lan><run_days>0</run_days><run_hours>0</run_hours><run_minutes>1</run_minutes><run_seconds>0</run_seconds></lan></RGW>';
const wan = '<RGW><wan><Engineering_mode>0</Engineering_mode><NW_register_status>1</NW_register_status><network_name>Example Carrier</network_name><sys_mode>6</sys_mode><cellular><sim_status>0</sim_status></cellular></wan></RGW>';
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
  const postQueue=[], capabilityQueue=[];
  Object.defineProperty(document.getElementById('ttlMode'),'value',{value:'64',writable:true,configurable:true});

  function responseFor(xhr) {
    if (xhr.url === '/c047d4ttl.json') return capabilityQueue.length?capabilityQueue.shift():{body:derived.capability};
    if (xhr.url === '/login.cgi') return { body: '', auth: 'Digest realm="Highwmg", nonce="abcdef", qop="auth"' };
    if (xhr.url.startsWith('/login.cgi?')) return { body: '' };
    if (/file=status1$/.test(xhr.url)) return { body: identity };
    if (/file=wan$/.test(xhr.url)) return { body: wan };
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
  vm.runInContext(derived.core, context, { filename: 'c047d4app.js' });
  vm.runInContext(derived.ttl, context, { filename: 'c047d4ttl.js' });
  return { window, document, requests, consoleEntries, timers, diagnosticQueue, postQueue, capabilityQueue, setRemote(g,v){generation=g;applied=v;}, ttl: window.MF885Community047Dev4TTL, get requested() { return requested; } };
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

test('generated entry binds the new core/module/capability and contains English guided controls',()=>{
 new vm.Script(derived.core);new vm.Script(derived.ttl);
 assert.match(derived.html,/0\.4\.7-dev\.4 - base 2\.5\.94/);assert.match(derived.html,/c047d4ttl.js/);
 assert.match(derived.html,/After a restart, TTL returns to/);assert.doesNotMatch(derived.html,/[А-Яа-я]/);
 assert.deepEqual(JSON.parse(derived.capability).settings,['64','off']);
});
test('login, navigation, manual refresh and live tick never read or set TTL',async()=>{
 const f=fixture();await login(f);
 f.document.querySelector('[data-page="ttl"]').dispatchEvent(new f.window.Event('click'));
 await f.window.MF885Community047Dev4.refreshAll();await f.window.MF885Community047Dev4.runLiveTick();
 assert.equal(diag(f).length,0);assert.equal(f.requests.filter(r=>r.url==='/c047d4ttl.json').length,0);
 assert.equal(f.document.getElementById('ttlApply').disabled,true);
 for(const r of f.requests.filter(r=>r.method==='POST')){assert.match(r.url,/file=message$/);assert.match(r.body,/<get_message>/);}
});
test('repeated identical GET revisions are valid, with one native GET per manual read',async()=>{
 const f=await ready();assert.equal(f.ttl.state.current.generation,0);assert.equal(f.ttl.state.current.value,64);
 await f.ttl.read();assert.equal(phase(f),'ready');assert.equal(diag(f,'GET').length,2);assert.equal(diag(f,'POST').length,0);
 assert.equal(f.document.getElementById('ttlApply').disabled,false);
});
test('form applies Off once with exact ACK and independent read, then restores64',async()=>{
 const f=await ready();f.document.getElementById('ttlMode').value='off';
 f.document.getElementById('ttlForm').dispatchEvent(new f.window.Event('submit',{cancelable:true}));
 await waitFor(()=>!f.ttl.state.busy,'Off transaction');
 assert.equal(phase(f),'applied');assert.equal(f.ttl.state.current.value,0);assert.equal(f.ttl.state.current.generation,1);
 assert.equal(diag(f,'POST').length,1);assert.equal(diag(f,'GET').length,3);
 await f.ttl.setValue('64');assert.equal(phase(f),'applied');assert.equal(f.ttl.state.current.value,64);assert.equal(f.ttl.state.current.generation,2);
 assert.equal(diag(f,'POST').length,2);assert.equal(diag(f,'GET').length,5);
 for(const r of diag(f)){assert.match(r.headers.Authorization,/uri="\/cgi\/xml_action.cgi"/);assert.equal(r.url.startsWith('/xml_action.cgi?'),true);assert.match(r.headers['Cache-Control'],/no-store/);}
});
test('already selected setting sends no POST and preserves revision',async()=>{
 const f=await ready();await f.ttl.setValue('64');assert.equal(diag(f,'POST').length,0);assert.equal(f.ttl.state.current.generation,0);assert.match(f.document.getElementById('ttlStatus').textContent,/No change was sent/);
});
test('revision wraps from ffffff to1 only for SET',async()=>{
 const f=fixture();f.setRemote(0xffffff,64);await login(f);await f.ttl.read();await f.ttl.setValue('off');assert.equal(phase(f),'applied');assert.equal(f.ttl.state.current.generation,1);
});
test('changed baseline or restart blocks POST and requires manual review',async()=>{
 for(const [g,v] of [[1,0],[1,64]]){const f=await ready();f.setRemote(g,v);await f.ttl.setValue('off');assert.equal(phase(f),'changed');assert.equal(diag(f,'POST').length,0);assert.equal(f.ttl.state.locked,true);await f.ttl.read();assert.equal(f.ttl.state.locked,false);}
 const f=fixture();f.setRemote(5,64);await login(f);await f.ttl.read();f.setRemote(0,64);await f.ttl.setValue('off');assert.equal(phase(f),'changed');assert.equal(diag(f,'POST').length,0);
});
test('custom/native values can be displayed but only64/Off can be submitted',async()=>{
 const f=fixture();f.setRemote(2,65);await login(f);await f.ttl.read();assert.equal(f.document.getElementById('ttlCurrent').textContent,'65');
 for(const v of ['65','1','255','0','064','64 ',' 64','+64','64.0',64,null,'<x/>']){await f.ttl.setValue(v);assert.equal(diag(f,'POST').length,0);}
 await f.ttl.setValue('64');assert.equal(phase(f),'applied');assert.equal(f.ttl.state.current.value,64);
});
test('unknown capability or core version blocks before any native GET/POST',async()=>{
 for(const reply of [{body:'{}'},{body:derived.capability.replace('dev.4','dev.2')},{body:derived.capability+' '},{body:derived.capability,status:404}]){const f=fixture();await login(f);f.capabilityQueue.push(reply);await f.ttl.read();assert.equal(phase(f),'unavailable');assert.equal(diag(f).length,0);assert.equal(f.ttl.state.busy,false);}
 const f=fixture();await login(f);f.window.MF885Community047Dev4.version='unknown';await f.ttl.read();assert.equal(phase(f),'unavailable');assert.equal(f.ttl.state.busy,false);assert.equal(diag(f).length,0);
});
test('malformed, old, nested and ambiguous state envelopes never unlock',async()=>{
 const good=output(3,64);
 const bad=[good.replace('</output>','\n</output>'),good.replace('</output>','\r</output>'),good.replace('</output>','\r\n</output>'),'', '<RGW/>',good.replace('r47:','r46:'),good.replace('00000003','01000003'),good.replace(':40',':4A'),output(0,0),good.replace('<output>','<output x="1">'),good.replace('</output>','</output><output>r47:00000003:40</output>'),good.replace('r47:00000003:40','<x>r47:00000003:40</x>'),good.replace('<RGW>','<RGW a="1">'),good.replace('<diagnostic>','bad<diagnostic>'),good.replace('</diagnostic>','</diagnostic>bad'),good.replace('stale','&amp;'),good.replace('stale','\u0000'),good.replace('stale','рус'),good.replace('<RGW>','<!DOCTYPE RGW><RGW>'),good.replace('<diagnostic>','<?x y?><diagnostic>'),good.replace('<diagnostic>','<!--x--><diagnostic>'),good.replace('stale','<![CDATA[x]]>'),'<html>login</html>','x'.repeat(4097)];
 for(const body of bad){const f=fixture();await login(f);f.diagnosticQueue.push(body);await f.ttl.read();assert.equal(phase(f),'unavailable',body.slice(0,100));assert.equal(f.document.getElementById('ttlApply').disabled,true);assert.equal(diag(f,'POST').length,0);}
});
test('typed ACK is mandatory; invalid ACK leaves unknown and sends no result GET/retry',async()=>{
 const good=ack(1,0,'off');
 const bad=[good.replace('</output>','\n</output>'),good.replace('</output>','\r</output>'),good.replace('</output>','\r\n</output>'),'<RGW/>',output(1,0),good.replace('<command>ttl','<command>x'),good.replace('<arg>off','<arg>64'),ack(2,0,'off'),ack(1,64,'off'),good.replace('r47:','r46:'),good.replace('</output>','</output><arg>off</arg>')];
 for(const body of bad){const f=await ready();f.postQueue.push({body});await f.ttl.setValue('off');assert.equal(phase(f),'unknown');assert.equal(diag(f,'POST').length,1);assert.equal(diag(f,'GET').length,2);assert.equal(f.ttl.state.locked,true);}
});
test('mismatched readback locks the editor without retry',async()=>{
 const f=await ready();f.diagnosticQueue.push(output(0,64),output(2,64));await f.ttl.setValue('off');assert.equal(phase(f),'unknown');assert.equal(diag(f,'POST').length,1);assert.equal(diag(f,'GET').length,3);assert.equal(f.document.getElementById('ttlCurrent').textContent,'Not confirmed');
});
test('timeout after device applies a POST requires a manual read, never a retry',async()=>{
 const f=await ready();f.postQueue.push({timeout:true});await f.ttl.setValue('off');assert.equal(phase(f),'unknown');assert.match(f.document.getElementById('ttlCurrentHelp').textContent,/unknown/);assert.equal(diag(f,'POST').length,1);await f.ttl.setValue('64');assert.equal(diag(f,'POST').length,1);await f.ttl.read();assert.equal(f.ttl.state.current.value,0);assert.equal(f.ttl.state.locked,false);assert.equal(diag(f,'POST').length,1);
});
test('held POST blocks duplicate click, refresh, logout and competing request',async()=>{
 const f=await ready();f.postQueue.push({hold:true,body:ack(1,0,'off')});const pending=f.ttl.setValue('off');await waitFor(()=>diag(f,'POST').length===1&&diag(f,'POST')[0].release,'held POST');
 const n=f.requests.length;await f.ttl.setValue('off');await f.window.MF885Community047Dev4.refreshAll();
 f.document.getElementById('logout').dispatchEvent(new f.window.Event('click'));
 assert.equal(f.document.getElementById('refreshAll').disabled,true);assert.equal(f.document.getElementById('logout').disabled,true);assert.equal(f.document.getElementById('messageSend').disabled,true);assert.equal(f.requests.length,n);
 await assert.rejects(f.window.MF885Community047Dev4.request({url:'/blocked',owner:'other'}),/Another router operation/);
 diag(f,'POST')[0].release();await pending;assert.equal(phase(f),'applied');assert.equal(diag(f,'POST').length,1);assert.equal(f.document.getElementById('refreshAll').disabled,false);
});
test('late callback after reset cannot publish success or send a readback',async()=>{
 const f=await ready();f.postQueue.push({hold:true,body:ack(1,0,'off')});const pending=f.ttl.setValue('off');await waitFor(()=>diag(f,'POST').length===1&&diag(f,'POST')[0].release,'held');f.ttl.reset();diag(f,'POST')[0].release();await pending;assert.equal(f.ttl.state.current,null);assert.equal(f.ttl.state.locked,true);assert.equal(diag(f,'GET').length,2);assert.equal(phase(f),'unavailable');
});
test('bridge independently rejects unexposed values and invalid owners',async()=>{
 const f=await ready(),b=f.window.MF885Community047Dev4.ttlBridge;
 assert.throws(()=>b.post('off','ttl-write'),/operation lock/);assert.equal(b.begin('ttl-write','ttlStatus'),true);
 for(const x of ['65','1','255','064',64])assert.throws(()=>b.post(x,'ttl-write'),/Invalid TTL/);
 b.end('ttl-write');assert.equal(diag(f,'POST').length,0);
});
test('valid XML declaration and ignored retained fields do not require fake freshness',async()=>{
 const f=fixture();await login(f);f.diagnosticQueue.push('<?xml version="1.0" encoding="US-ASCII"?> '+output(3,64));await f.ttl.read();assert.equal(phase(f),'ready');assert.equal(f.ttl.state.current.generation,3);
});
test('logs preserve metadata while hiding response XML and credentials',async()=>{
 const f=await ready();await f.ttl.setValue('off');const logs=JSON.stringify(f.consoleEntries);
 assert.ok(f.consoleEntries.length>0);assert.match(logs,/bodyRedacted/);assert.doesNotMatch(logs,/fixture-password|abcdef|Example Carrier|<RGW>|r47:|Digest realm/);
});

test('HTTP/session rejection at every native phase never causes a retry',async()=>{
 const errors=[{status:401},{status:403},{body:'<RGW><login_status>TIMEOUT</login_status></RGW>'},{body:'<RGW><login_status>KICKOFF</login_status></RGW>'},{body:'<RGW><login_status>UNAUTHORIZED</login_status></RGW>'}];
 for(const err of errors){
  const f=fixture();await login(f);f.diagnosticQueue.push(err);await f.ttl.read();assert.equal(phase(f),'unavailable');assert.equal(diag(f,'POST').length,0);
  const p=await ready();p.postQueue.push(err);await p.ttl.setValue('off');assert.equal(phase(p),'unknown');assert.equal(diag(p,'POST').length,1);assert.equal(diag(p,'GET').length,2);
  const a=await ready();a.diagnosticQueue.push(output(0,64),err);await a.ttl.setValue('off');assert.equal(phase(a),'unknown');assert.equal(diag(a,'POST').length,1);assert.equal(diag(a,'GET').length,3);
 }
});
test('explicit POST abort yields unknown and manual read can recover the setting',async()=>{
 const f=await ready();f.postQueue.push({hold:true,body:ack(1,0,'off')});const p=f.ttl.setValue('off');await waitFor(()=>diag(f,'POST').length===1&&diag(f,'POST')[0].release,'held POST');
 assert.equal(f.window.MF885Community047Dev4.cancel('ttl-write'),true);await p;assert.equal(phase(f),'unknown');assert.equal(diag(f,'GET').length,2);assert.equal(diag(f,'POST').length,1);
 await f.ttl.read();assert.equal(f.ttl.state.current.value,0);assert.equal(f.ttl.state.locked,false);assert.equal(diag(f,'POST').length,1);
});
test('readback timeout after valid ACK stays unknown with no additional request',async()=>{
 const f=await ready();f.diagnosticQueue.push(output(0,64),{timeout:true});await f.ttl.setValue('off');assert.equal(phase(f),'unknown');assert.equal(diag(f,'POST').length,1);assert.equal(diag(f,'GET').length,3);assert.equal(f.ttl.state.locked,true);
});
test('capability is checked again before Apply and prevents stale-page writes',async()=>{
 const f=await ready();f.capabilityQueue.push({body:'{}'});await f.ttl.setValue('off');assert.equal(phase(f),'unavailable');assert.equal(diag(f,'GET').length,1);assert.equal(diag(f,'POST').length,0);
});
test('held prewrite GET blocks repeated Apply/refresh without extra requests',async()=>{
 const f=await ready();f.diagnosticQueue.push({hold:true,body:output(0,64)});const p=f.ttl.setValue('off');await waitFor(()=>diag(f,'GET').length===2&&diag(f,'GET')[1].release,'held prewrite');
 const n=f.requests.length;await f.ttl.setValue('off');await f.window.MF885Community047Dev4.refreshAll();assert.equal(f.requests.length,n);assert.equal(diag(f,'POST').length,0);
 diag(f,'GET')[1].release();await p;assert.equal(phase(f),'applied');assert.equal(diag(f,'POST').length,1);
});
