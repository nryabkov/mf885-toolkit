const test=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
let parseHTML=null;try{({parseHTML}=require('linkedom'));}catch(_){}
const root=path.resolve(__dirname,'..');
const assets=path.join(root,fs.existsSync(path.join(root,'public-export.json'))?'public/webui/r4.6':'webui/r4.6');
const derived={html:fs.readFileSync(path.join(assets,'r46.html'),'utf8'),core:fs.readFileSync(path.join(assets,'js/r46app.js'),'utf8'),ttl:fs.readFileSync(path.join(assets,'js/r46ttl.js'),'utf8')};
const output=(g,t)=>`<RGW><diagnostic><command>retained-untrusted</command><arg>stale</arg><output>r46:${(g>>>0).toString(16).padStart(8,'0')}:${t.toString(16).padStart(2,'0')}</output></diagnostic></RGW>`;
const options={skip:!parseHTML};
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
  const postQueue=[];

  function responseFor(xhr) {
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
        return postQueue.length?postQueue.shift():{body:'<RGW/>'};
      }
      generation=(generation+1)>>>0;
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
  vm.runInContext(derived.core, context, { filename: 'r46app.js' });
  vm.runInContext(derived.ttl, context, { filename: 'r46ttl.js' });
  return { window, document, requests, consoleEntries, timers, diagnosticQueue, postQueue, ttl: window.MF885CommunityR46TTL, get requested() { return requested; } };
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
  await waitFor(() => !value.window.MF885CommunityR46.ttlBridge.routerBusy(), 'bootstrap finished');
}


const phase=f=>f.document.getElementById('ttlStatus').getAttribute('data-phase');
const diagnostic=f=>f.requests.filter(r=>/file=diagnostic$/.test(r.url));
async function ready(){const f=fixture();await login(f);await f.ttl.read();assert.equal(phase(f),'ready');return f;}

test('login and global refresh issue zero TTL requests; explicit read unlocks',options,async()=>{
 const f=fixture();assert.equal(f.document.getElementById('ttlApply').disabled,true);
 await login(f);assert.equal(diagnostic(f).length,0);assert.equal(f.document.getElementById('ttlApply').disabled,true);
 await f.window.MF885CommunityR46.refreshAll();assert.equal(diagnostic(f).length,0);
 await f.ttl.read();assert.deepEqual(diagnostic(f).map(r=>r.method),['GET','GET']);
 assert.equal(f.ttl.state.current.value,64);assert.equal(f.document.getElementById('ttlApply').disabled,false);
 assert.match(f.document.getElementById('page-ttl').textContent,/IPv6/);assert.match(f.document.getElementById('page-ttl').textContent,/оперативной памяти/);
});
test('all native states and generations parse independently of retained request',options,()=>{
 const f=fixture();for(let t=0;t<256;t++)for(const g of [0,1,0x7fffffff,0xffffffff]){const s=f.ttl.strictState(f.window.MF885CommunityR46.parseXml(output(g,t)));assert.equal(s.value,t);assert.equal(s.generation,g);}
 for(let t=1;t<256;t++)assert.equal(f.ttl.valueInfo(String(t)).accepted,true);
 for(const v of ['',null,64,'0','00','01','256','+64','-1',' 64','64 ','64.0','6e1','0x40','OFF','64\n'])assert.equal(f.ttl.valueInfo(v).accepted,false,String(v));
 assert.equal(f.ttl.valueInfo('off').accepted,true);
});
test('strict readback rejects retained-only, duplicate, nested, extra and malformed states',options,()=>{
 const f=fixture(),parse=s=>f.window.MF885CommunityR46.parseXml(s);
 for(const s of [stockEmpty,retained('65'),output(1,64).replace('r46:','r45:'),output(1,64).replace(':40',':400'),output(1,64).replace(':40',':4A'),output(1,64).replace('<output>','<output x="1">'),output(1,64).replace('</diagnostic>','<output>r46:00000002:41</output></diagnostic>'),output(1,64).replace('</RGW>','<other/></RGW>'),output(1,64).replace('<arg>stale</arg>','<arg><x/></arg>'),output(1,64).replace('</arg>','</arg>text')])assert.throws(()=>f.ttl.strictState(parse(s)));
});
test('freshness handles wrap and rejects equal, backwards or ambiguous half-range',options,()=>{
 const f=fixture();for(const [a,b,want] of [[0,1,true],[0xffffffff,0,true],[3,3,false],[4,3,false],[0,0x80000000,false],[0,0x7fffffff,true]])assert.equal(f.ttl.advancing({generation:a},{generation:b}),want);
});
test('two identical cached outputs never unlock mutations',options,async()=>{
 const f=fixture();await login(f);f.diagnosticQueue.push(output(42,64),output(42,64));await f.ttl.read();assert.equal(phase(f),'unavailable');assert.equal(f.ttl.state.locked,true);
 const n=diagnostic(f).length;await f.ttl.setValue('65');assert.equal(diagnostic(f).length,n);
});
test('a change is GET, one POST, GET with native readback; Off uses same path',options,async()=>{
 const f=await ready();let n=diagnostic(f).length;await f.ttl.setValue('65');let flow=diagnostic(f).slice(n);
 assert.deepEqual(flow.map(r=>r.method),['GET','POST','GET']);assert.equal(phase(f),'applied');assert.equal(f.ttl.state.current.value,65);assert.ok(flow.every(r=>/^Digest /.test(r.headers.Authorization)));
 n=diagnostic(f).length;await f.ttl.setValue('off');assert.deepEqual(diagnostic(f).slice(n).map(r=>r.method),['GET','POST','GET']);assert.equal(f.ttl.state.current.value,0);assert.equal(phase(f),'applied');
});
test('already-applied value is freshly read with zero writes',options,async()=>{
 const f=await ready(),n=diagnostic(f).length;await f.ttl.setValue('64');assert.deepEqual(diagnostic(f).slice(n).map(r=>r.method),['GET']);assert.equal(phase(f),'ready');
});
test('invalid values never reach transport and display input help',options,async()=>{
 const f=await ready(),n=diagnostic(f).length;for(const v of ['','0','01','256','64.0',' 64','+64'])await f.ttl.setValue(v);assert.equal(diagnostic(f).length,n);
 const input=f.document.getElementById('ttlValue');input.value='1';input.dispatchEvent(new f.window.Event('input'));assert.match(f.document.getElementById('ttlInputHint').textContent,/Малое значение/);
 input.value='01';input.dispatchEvent(new f.window.Event('input'));assert.equal(input.getAttribute('aria-invalid'),'true');
});
test('dirty input survives global refresh, manual TTL read and Off',options,async()=>{
 const f=await ready(),input=f.document.getElementById('ttlValue');input.value='96';input.dispatchEvent(new f.window.Event('input'));
 await f.window.MF885CommunityR46.refreshAll();await f.ttl.read();await f.ttl.setValue('off');assert.equal(input.value,'96');assert.equal(f.ttl.state.dirty,true);
});
test('stale baseline blocks POST; manual read recovers',options,async()=>{
 const f=await ready(),n=diagnostic(f).length;f.diagnosticQueue.push(output(f.ttl.state.current.generation,64));await f.ttl.setValue('65');assert.deepEqual(diagnostic(f).slice(n).map(r=>r.method),['GET']);assert.equal(phase(f),'unavailable');await f.ttl.read();assert.equal(f.ttl.state.locked,false);
});
test('POST timeout is unknown with no retry or automatic readback',options,async()=>{
 const f=await ready(),n=diagnostic(f).length;f.postQueue.push({timeout:true});await f.ttl.setValue('65');assert.deepEqual(diagnostic(f).slice(n).map(r=>r.method),['GET','POST']);assert.equal(phase(f),'unknown');assert.equal(f.ttl.state.locked,true);
 await f.ttl.setValue('65');assert.equal(diagnostic(f).length,n+2);await f.ttl.read();assert.equal(f.ttl.state.current.value,65);assert.equal(f.ttl.state.locked,false);
});
test('HTTP 200 cannot hide failed native setter or stale publication',options,async()=>{
 for(const stale of [false,true]){const f=await ready(),g=f.ttl.state.current.generation;f.diagnosticQueue.push(output(g+1,64),output(stale?g+1:g+2,64));await f.ttl.setValue('65');assert.equal(phase(f),stale?'unknown':'rejected');assert.equal(f.ttl.state.locked,true);assert.equal(diagnostic(f).filter(r=>r.method==='POST').length,1);}
});
test('POST envelope authentication failure and oversized/DTD GET lock writes',options,async()=>{
 const f=await ready();f.postQueue.push({body:'<RGW><login_status>TIMEOUT</login_status></RGW>'});await f.ttl.setValue('65');assert.equal(phase(f),'unknown');
 for(const body of ['x'.repeat(4097),'<!DOCTYPE RGW>'+output(100,64)]){f.diagnosticQueue.push(body);await f.ttl.read();assert.equal(phase(f),'unavailable');assert.equal(f.ttl.state.locked,true);}
});
test('double click and global refresh cannot interleave with TTL transaction',options,async()=>{
 const f=await ready();f.diagnosticQueue.push({body:output(3,64),hold:true});const pending=f.ttl.setValue('65');await waitFor(()=>diagnostic(f).at(-1).release,'held GET');
 const n=f.requests.length;await f.ttl.setValue('96');await f.window.MF885CommunityR46.refreshAll();assert.equal(f.requests.length,n);assert.equal(f.document.getElementById('ttlRead').disabled,true);diagnostic(f).at(-1).release();await pending;assert.equal(f.ttl.state.current.value,65);
});
test('console receives no response bodies, password, challenge, retained fields or unexpected exception text',options,async()=>{
 const f=await ready();f.window.MF885CommunityR46.reportUnexpected('private-marker',new Error('private-error-secret'));await f.ttl.setValue('65');
 const log=JSON.stringify(f.consoleEntries);for(const secret of ['fixture-password','abcdef','Highwmg','retained-untrusted','private-error-secret','private-marker','<RGW','Battery_percent','network_name'])assert.equal(log.includes(secret),false,secret);
 assert.ok(f.consoleEntries.length>0);assert.ok(f.consoleEntries.every(row=>row.length===3&&row[2].bodyRedacted===true));
});
test('logout clears observed state, edits and mutation eligibility',options,async()=>{
 const f=await ready();f.document.getElementById('ttlValue').value='96';f.document.getElementById('logout').click();assert.equal(f.ttl.state.current,null);assert.equal(f.document.getElementById('ttlValue').value,'');assert.equal(f.document.getElementById('ttlApply').disabled,true);
});
