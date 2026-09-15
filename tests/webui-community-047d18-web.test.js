/* Community 0.4.7-dev.18: manual TTL input 1..255 with retained Off.
 *
 * Runs against the real derived dev18 assets (assembled by
 * firmware/community-0.4.7-dev.18/fixtures/assemble_assets.js) with the same linkedom
 * DOM used by the dev15/dev16/dev17 suites. The fixture models the router, not
 * the implementation, and the TTL flows drive real DOM events (mode change,
 * numeric input, form submit).
 *
 * Run:
 *   NODE_PATH=/tmp/mf885-node-deps/node_modules \
 *   MF885_DEV18_ASSETS=<assembled dir> \
 *   node --test firmware/community-0.4.7-dev.18/web.test.js
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { parseHTML } = require('linkedom');

const assets = process.env.MF885_DEV18_ASSETS || path.join(__dirname, '../webui/0.4.7-dev.18');
if (!assets) throw new Error('MF885_DEV18_ASSETS must point at the assembled dev18 asset directory');
const read = name => fs.readFileSync(path.join(assets, name), 'utf8');
const derived = {
  html: read('c047d18.html'),
  core: read('js/c047d18app.js'),
  ttl: read('js/c047d18ttl.js'),
  engineering: read('js/c047d18engineering.js'),
  power: read('js/c047d18power.js'),
  console: read('js/c047d18console.js'),
  cpu: read('js/c047d18cpu.js'),
  capability: read('c047d18ttl.json'),
};

const identity = '<RGW><sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></sysinfo><batteryinfo><Battery_percent>83</Battery_percent></batteryinfo><wan><NW_register_status>1</NW_register_status><network_name>Example Carrier</network_name><sys_mode>6</sys_mode><cellular><sim_status>0</sim_status></cellular></wan><lan><run_days>0</run_days><run_hours>0</run_hours><run_minutes>1</run_minutes><run_seconds>0</run_seconds></lan></RGW>';
const expired = kind => `<RGW><login_status>${kind}</login_status></RGW>`;
const wan = '<RGW><wan><Engineering_mode>0</Engineering_mode><query_time_interval>1</query_time_interval><NW_register_status>1</NW_register_status><network_name>Example Carrier</network_name><sys_mode>6</sys_mode><cellular><sim_status>0</sim_status></cellular></wan></RGW>';
const engineer = '<RGW><Engi><LTE><band>7</band><rsrp>45</rsrp><rsrq>16</rsrq></LTE></Engi></RGW>';
const challenge = 'Digest realm="Highwmg", nonce="abcdef", qop="auth"';
const consoleBody = '<RGW><diagnostic><console_v1>c1:' + '00'.repeat(996) + '</console_v1><ussd_v1>u4:' + '00'.repeat(1044) + '</ussd_v1><queue_v1>q2:' + '00'.repeat(120) + '</queue_v1></diagnostic></RGW>';
const cpuBody = wire => `<RGW><diagnostic><console_v1>c1:${'00'.repeat(996)}</console_v1><cpu_v1>${wire}</cpu_v1></diagnostic></RGW>`;
/* The r47 word: revision in the high 24 bits, TTL in the low byte. */
const word = (generation, value) => `r47:${generation.toString(16).padStart(8, '0').slice(-8)}:${value.toString(16).padStart(2, '0')}`;
const diagnostic = (generation, value, arg) => `<RGW><diagnostic><command>ttl</command><arg>${arg === undefined ? (value === 0 ? 'off' : String(value)) : arg}</arg><output>${word(generation, value)}</output></diagnostic></RGW>`;

function cpuFrame({ version = 1, flags = 2, epoch = 1, frequency = 32768, total = 0n, idle = 0n, errors = 0, transitions = 0 } = {}) {
  const low = v => Number(v & 0xffffffffn) >>> 0;
  const high = v => Number((v >> 32n) & 0xffffffffn) >>> 0;
  const words = [version, flags, epoch, frequency, low(total), high(total), low(idle), high(idle), errors, transitions];
  return 'cpu2:' + words.map(w => [0,8,16,24].map(shift => ((w>>>shift)&255).toString(16).padStart(2,'0')).join('')).join('');
}

function fixture() {
  const dom = parseHTML(derived.html);
  const document = dom.document;
  const window = { document, DOMParser: dom.DOMParser, Event: dom.Event, addEventListener: dom.addEventListener.bind(dom) };
  // linkedom has no real form state; seed the select/input values the core app
  // reads during bootstrap, exactly like the dev15/dev16/dev17 suites.
  Object.defineProperty(document.getElementById('ttlMode'), 'value', { value: 'manual', writable: true, configurable: true });
  for (const [id, value] of [['folder', 'inbox'], ['engineeringMode', '0'], ['atPreset', 'AT+CSQ']]) {
    Object.defineProperty(document.getElementById(id), 'value', { value, writable: true, configurable: true });
  }
  Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });

  const requests = [], powerRequests = [], timers = new Map();
  const queue = [], postQueue = [], consoleGetQueue = [], cpuQueue = [], diagnosticQueue = [], capabilityQueue = [];
  let timerSequence = 0, engineeringMode = '0', applied = 64, generation = 0;
  let loginChallengeStatus = 200;

  function route(xhr) {
    const url = xhr.url;
    if (url === '/login.cgi') return { status: loginChallengeStatus, body: '', auth: challenge };
    if (url.startsWith('/login.cgi?')) return { body: '' };
    if (/file=status1$/.test(url)) return queue.length ? queue.shift() : { body: identity };
    if (/file=Engineer_parameter$/.test(url)) return { body: engineer };
    if (/file=wan$/.test(url)) {
      if (xhr.method === 'POST') {
        const match = /<Engineering_mode>([01])<\/Engineering_mode>/.exec(xhr.body);
        if (postQueue.length) return postQueue.shift();
        engineeringMode = match[1];
        return { body: '<RGW/>' };
      }
      return { body: wan.replace('<Engineering_mode>0</Engineering_mode>', '<Engineering_mode>' + engineeringMode + '</Engineering_mode>') };
    }
    if (/file=message$/.test(url)) {
      if (xhr.method === 'POST') return postQueue.length ? postQueue.shift() : { body: '<RGW/>' };
      return { body: '<RGW><message><get_message><total_number>0</total_number><message_list/></get_message></message></RGW>' };
    }
    if (/file=diagnostic$/.test(url)) {
      if (xhr.method === 'POST') {
        if (postQueue.length) return postQueue.shift();
        const arg = /<arg>([^<]*)<\/arg>/.exec(xhr.body)[1];
        applied = arg === 'off' ? 0 : Number(arg);
        generation = generation === 0xffffff ? 1 : generation + 1;
        return { body: diagnostic(generation, applied, arg) };
      }
      if (diagnosticQueue.length) return diagnosticQueue.shift();
      return { body: diagnostic(generation, applied) };
    }
    if (/file=c047d18cpu$/.test(url)) {
      if (xhr.method !== 'GET') throw new Error('the CPU file is GET only');
      if (cpuQueue.length) return cpuQueue.shift();
      return { body: cpuBody(cpuFrame({ flags: 1, epoch: 1 })) };
    }
    if (/file=c047d18console$/.test(url)) {
      if (xhr.method === 'POST' && postQueue.length) return postQueue.shift();
      if (xhr.method === 'GET' && consoleGetQueue.length) return consoleGetQueue.shift();
      return { body: consoleBody };
    }
    if (url === '/c047d18ttl.json') return capabilityQueue.length ? capabilityQueue.shift() : { body: derived.capability };
    throw new Error('Unexpected route ' + xhr.method + ' ' + url);
  }

  class FakeXHR {
    constructor() { this.headers = {}; this.status = 0; this.responseText = ''; this.auth = ''; requests.push(this); }
    open(method, url) { this.method = method; this.url = url; }
    setRequestHeader(name, value) { this.headers[name] = value; }
    getResponseHeader(name) { return String(name).toLowerCase() === 'www-authenticate' ? this.auth : ''; }
    send(body) {
      this.body = body;
      let reply;
      try { reply = route(this); } catch (error) { queueMicrotask(() => this.onerror && this.onerror()); return; }
      if (reply.hold) { this.release = (override) => { const final = override || reply; this.status = final.status || 200; this.responseText = final.body || ''; this.auth = final.auth || ''; this.onload && this.onload(); }; return; }
      if (reply.timeout) { queueMicrotask(() => this.ontimeout && this.ontimeout()); return; }
      if (reply.network) { queueMicrotask(() => this.onerror && this.onerror()); return; }
      this.status = reply.status || 200; this.responseText = reply.body || ''; this.auth = reply.auth || '';
      queueMicrotask(() => this.onload && this.onload());
    }
    abort() { if (this.release) return; queueMicrotask(() => this.onabort && this.onabort()); }
  }

  window.crypto = crypto.webcrypto;
  window.XMLHttpRequest = FakeXHR;
  window.location = { protocol: 'http:', host: '192.0.2.1', hash: '' };
  window.hex_md5 = input => crypto.createHash('md5').update(String(input)).digest('hex');
  window.confirm = () => true;
  window.AbortController = class { constructor() { this.signal = {}; } abort() {} };
  window.fetch = async (url) => {
    powerRequests.push({ url });
    if (/\/login\.cgi$/.test(url)) return { status: 401, headers: { get: () => challenge }, text: async () => '' };
    if (/\/login\.cgi\?/.test(url)) return { status: 200, headers: { get: () => '' }, text: async () => '' };
    if (/file=status1$/.test(url)) return { status: 200, headers: { get: () => '' }, text: async () => identity };
    if (/file=reset$/.test(url)) return { status: 200, headers: { get: () => '' }, text: async () => '<RGW><reboot/></RGW>' };
    return { status: 200, headers: { get: () => '' }, text: async () => '' };
  };
  window.sessionStorage = { getItem() { return null; }, setItem() {} };
  window.setTimeout = (callback, delay) => { const id = ++timerSequence; timers.set(id, { callback, delay: Number(delay) || 0 }); return id; };
  window.clearTimeout = id => { timers.delete(id); };
  window.console = { debug() {}, error() {} };

  const context = { window, document, console: window.console, Date, JSON, Array, Object, String, Number, Boolean, RegExp, Error, Promise, Map, Set, Uint8Array, Uint32Array, DataView, TextDecoder, BigInt, isFinite, parseInt };
  vm.createContext(context);
  vm.runInContext(derived.cpu, context, { filename: 'c047d18cpu.js' });
  vm.runInContext(derived.core, context, { filename: 'c047d18app.js' });
  vm.runInContext(derived.ttl, context, { filename: 'c047d18ttl.js' });
  vm.runInContext(derived.engineering, context, { filename: 'c047d18engineering.js' });
  vm.runInContext(derived.power, context, { filename: 'c047d18power.js' });
  vm.runInContext(derived.console, context, { filename: 'c047d18console.js' });

  return {
    window, document, requests, powerRequests, timers, queue, postQueue, cpuQueue, diagnosticQueue, capabilityQueue,
    signInVisible() { return !document.getElementById('login').hidden; },
    appVisible() { return !document.getElementById('app').hidden; },
    cpuHome() { return document.getElementById('dashboardCpu').textContent; },
    ttlStatus() { return document.getElementById('ttlStatus').textContent; },
    ttlPhase() { return document.getElementById('ttlStatus').getAttribute('data-phase'); },
    ttlCurrent() { return document.getElementById('ttlCurrent').textContent; },
    ttlApplyDisabled() { return document.getElementById('ttlApply').disabled; },
    ttlValueDisabled() { return document.getElementById('ttlValue').disabled; },
    setApplyDisabled(v) { Object.defineProperty(document.getElementById('ttlApply'), 'disabled', { value: v, writable: true, configurable: true }); },
    diag(kind) { return requests.filter(r => r.method === kind && /file=diagnostic$/.test(r.url)); },
    setRemote(g, v) { generation = g; applied = v; },
    posts(pattern) { return requests.filter(r => r.method === 'POST' && pattern.test(r.url)); },
    authenticated(pattern) { return requests.filter(r => r.headers.Authorization && pattern.test(r.url)); },
    cpuGets() { return requests.filter(r => /file=c047d18cpu$/.test(r.url)); },
    submitTtl(mode, value) {
      const modeNode = document.getElementById('ttlMode');
      modeNode.value = mode;
      modeNode.dispatchEvent(new window.Event('change'));
      const valueNode = document.getElementById('ttlValue');
      valueNode.value = value;
      valueNode.dispatchEvent(new window.Event('input'));
      document.getElementById('ttlForm').dispatchEvent(new window.Event('submit', { cancelable: true }));
    },
    holdNext(matcher) {
      const reply = { hold: true, body: identity };
      (matcher === 'ttl' ? diagnosticQueue : queue).push(reply);
      return reply;
    },
    app: window.MF885Community047Dev18,
    ttl: window.MF885Community047Dev18TTL,
    codec: window.MF885Dev18Cpu,
  };
}

const settle = async () => { for (let i = 0; i < 80; i++) await new Promise(r => setImmediate(r)); };
async function waitFor(predicate, label) { for (let i = 0; i < 200; i++) { if (predicate()) return; await new Promise(r => setImmediate(r)); } throw new Error('Timed out waiting for ' + label); }

async function login(f, password = 'fixture-password') {
  f.document.getElementById('password').value = password;
  f.document.getElementById('loginForm').dispatchEvent(new f.window.Event('submit'));
  await waitFor(() => f.appVisible(), 'authenticated shell');
  await waitFor(() => !f.document.getElementById('refreshAll').disabled, 'bootstrap finished');
}

async function readTtl(f) { await f.ttl.read(); await settle(); }

// ---------------------------------------------------------------------------
// Real-DOM TTL editor: modes, canonical values and preserved behaviour.
// ---------------------------------------------------------------------------

test('the derived HTML exposes an explicit mode select and a labelled numeric TTL input', () => {
  const f = fixture();
  const mode = f.document.getElementById('ttlMode');
  const input = f.document.getElementById('ttlValue');
  assert.ok(mode && input, 'both TTL controls exist');
  assert.deepEqual([...mode.options].map(o => o.value), ['manual', 'off'], 'Off is retained and manual is the other explicit mode');
  assert.equal(input.getAttribute('type'), 'number');
  assert.equal(input.getAttribute('min'), '1');
  assert.equal(input.getAttribute('max'), '255');
  assert.equal(input.getAttribute('step'), '1');
  assert.equal(input.value, '64', 'the explicit fresh default is 64');
  assert.equal(f.document.querySelector('label[for="ttlValue"]').textContent, 'TTL');
});

test('the shipped parseManual accepts only canonical decimal 1..255', () => {
  const ttl = fixture().ttl;
  for (const good of ['1', '64', '255']) assert.equal(ttl.parseManual(good), Number(good), good);
  for (const bad of ['', ' 64', '64 ', ' 64 ', '+64', '-64', '0', '00', '064', '1.0', '1e2', '0x40', 'NaN', 'Infinity', '256', '999', '١٢', null, 64, '64a']) {
    assert.equal(ttl.parseManual(bad), null, JSON.stringify(bad) + ' must be rejected');
  }
});

test('a manual 1, 64 and 255 each trigger exactly one POST, one ACK and a separate readback', async () => {
  for (const value of ['1', '64', '255']) {
    const f = fixture(); await login(f);
    // Start from a different confirmed value so each case really writes.
    f.setRemote(3, 128);
    await readTtl(f);
    assert.equal(f.ttlPhase(), 'ready', 'the setting was read first');
    assert.equal(f.ttlCurrent(), '128');
    const baseline = f.diag('GET').length;
    f.submitTtl('manual', value);
    await waitFor(() => f.ttlPhase() === 'applied' || f.ttlPhase() === 'unavailable' || f.ttlPhase() === 'unknown', 'apply finished');
    await settle();
    assert.equal(f.ttlPhase(), 'applied', 'canonical ' + value + ' applies');
    assert.equal(f.ttlCurrent(), value);
    assert.equal(f.diag('POST').length, 1, 'exactly one POST');
    assert.match(f.diag('POST')[0].body, new RegExp('<arg>' + value + '</arg>'), 'the exact canonical argument is sent');
    assert.ok(f.diag('GET').length >= baseline + 2, 'a baseline read and a separate readback both ran');
    assert.equal(f.ttlValueDisabled(), false);
  }
});

test('applying the already-current 64 is a no-op and sends nothing', async () => {
  const f = fixture(); await login(f); await readTtl(f);
  assert.equal(f.ttlCurrent(), '64');
  f.submitTtl('manual', '64');
  await waitFor(() => f.ttlPhase() === 'ready', 'no-op reported');
  assert.equal(f.diag('POST').length, 0, 'no write when the value already matches');
  assert.match(f.ttlStatus(), /Already set to 64/);
});

test('rejected values never reach the wire and never round or clamp', async () => {
  const cases = [['bogus', '64'], ['manual', '0'], ['manual', '256'], ['manual', ''], ['manual', ' 64'], ['manual', '64 '], ['manual', '+64'], ['manual', '-1'], ['manual', '064'], ['manual', '1.5'], ['manual', '1e2'], ['manual', 'NaN'], ['manual', 'Infinity']];
  for (const [mode, value] of cases) {
    const f = fixture(); await login(f); await readTtl(f);
    f.submitTtl(mode, value);
    await settle();
    assert.equal(f.diag('POST').length, 0, mode + ' ' + JSON.stringify(value) + ' must not POST');
    assert.equal(f.ttlPhase(), 'rejected');
    assert.match(f.ttlStatus(), /whole number from 1 to 255/i);
  }
});

test('retained Off mode sends the off argument and reports it', async () => {
  const f = fixture(); await login(f); await readTtl(f);
  f.submitTtl('off', '64');
  await waitFor(() => f.ttlPhase() === 'applied', 'off applied');
  assert.equal(f.ttlCurrent(), 'Off');
  assert.equal(f.diag('POST').length, 1);
  assert.match(f.diag('POST')[0].body, /<arg>off<\/arg>/);
  assert.equal(f.ttlValueDisabled(), true, 'the numeric input is disabled while the mode is Off');
});

test('reading an existing 1..255 setting renders it and preloads the draft', async () => {
  for (const [generation, value] of [[1, 1], [7, 128], [0xffffff, 255]]) {
    const f = fixture(); await login(f);
    f.diagnosticQueue.push({ body: diagnostic(generation, value) });
    await readTtl(f);
    assert.equal(f.ttlPhase(), 'ready');
    assert.equal(f.ttlCurrent(), String(value), 'the reported value is rendered verbatim');
    assert.equal(f.document.getElementById('ttlMode').value, 'manual');
    assert.equal(f.document.getElementById('ttlValue').value, String(value), 'the draft shows the read value');
    assert.equal(f.ttlApplyDisabled(), false, 'a confirmed current value unlocks Apply');
    assert.equal(f.diag('POST').length, 0, 'reading never writes');
  }
});

test('a changed baseline blocks the write and sends nothing', async () => {
  const f = fixture(); await login(f); await readTtl(f);
  // The router moved on between the first read and the pre-write check.
  f.diagnosticQueue.push({ body: diagnostic(5, 100) });
  f.submitTtl('manual', '200');
  await waitFor(() => f.ttlPhase() === 'changed', 'changed detected');
  assert.equal(f.diag('POST').length, 0, 'no write after a changed baseline');
  assert.equal(f.ttlApplyDisabled(), true, 'Apply is locked until a fresh read');
  assert.equal(f.ttlCurrent(), '100', 'the newly observed value is shown');
});

test('an ACK with the wrong revision is rejected without a readback', async () => {
  const f = fixture(); await login(f); await readTtl(f);
  const baseline = f.diag('GET').length;
  f.postQueue.push({ body: diagnostic(99, 200, '200') });
  f.submitTtl('manual', '200');
  await waitFor(() => f.ttlPhase() === 'unknown', 'mismatched ack reported unknown');
  assert.equal(f.diag('POST').length, 1, 'the single POST was already sent');
  assert.equal(f.diag('GET').length, baseline + 1, 'no readback follows a bad ACK');
  assert.equal(f.ttlApplyDisabled(), true);
});

test('an ACK that differs from the separate readback leaves the setting unconfirmed', async () => {
  const f = fixture(); await login(f); await readTtl(f);
  // The pre-write baseline still matches, the ACK agrees, but the independent
  // readback reports a different value.
  f.diagnosticQueue.push({ body: diagnostic(0, 64) });
  f.postQueue.push({ body: diagnostic(1, 200, '200') });
  f.diagnosticQueue.push({ body: diagnostic(1, 100) });
  f.submitTtl('manual', '200');
  await waitFor(() => f.ttlPhase() === 'unknown', 'readback mismatch reported unknown');
  assert.equal(f.diag('POST').length, 1, 'nothing is retried');
  assert.equal(f.ttlApplyDisabled(), true);
  assert.equal(f.ttlCurrent(), 'Not confirmed');
});

test('logout resets the draft to the fresh default and disables the controls', async () => {
  const f = fixture(); await login(f); await readTtl(f);
  f.submitTtl('manual', '255');
  await waitFor(() => f.ttlPhase() === 'applied', 'applied');
  assert.equal(f.document.getElementById('ttlValue').value, '255');
  f.document.getElementById('logout').dispatchEvent(new f.window.Event('click'));
  await settle();
  assert.equal(f.appVisible(), false, 'the session ended');
  assert.equal(f.document.getElementById('ttlValue').value, '64', 'a fresh editor is back to the explicit default');
  assert.equal(f.document.getElementById('ttlMode').value, 'manual');
  assert.equal(f.ttlValueDisabled(), true, 'the input is disabled while signed out');
  assert.equal(f.ttlApplyDisabled(), true);
});

test('input stays disabled while signed out and while a router operation is busy', async () => {
  const f = fixture();
  assert.equal(f.ttlValueDisabled(), true, 'disabled before sign-in');
  await login(f); await readTtl(f);
  assert.equal(f.ttlValueDisabled(), false, 'enabled after sign-in for manual mode');
  // A held snapshot keeps the shared router lock; both TTL controls must lock.
  f.queue.push({ hold: true, body: identity });
  const pending = f.app.refreshAll('manual').catch(() => null);
  await settle();
  assert.equal(f.ttlValueDisabled(), true, 'a busy router operation disables the input');
  assert.equal(f.document.getElementById('ttlMode').disabled, true);
  const held = f.requests.find(r => r.release && !r._released);
  held._released = true; held.release();
  await pending; await settle();
  assert.equal(f.ttlValueDisabled(), false, 'the input recovers when the lock is free');
});

test('a late read cannot overwrite a manual draft typed after it started', async () => {
  const f = fixture(); await login(f);
  f.holdNext('ttl');
  const pending = f.ttl.read();
  await waitFor(() => f.requests.some(r => r.release && !r._released), 'the read held in flight');
  const held = f.requests.find(r => r.release && !r._released);
  assert.ok(held, 'the read is held in flight');
  // The user types a newer draft while the read is still open.
  const valueNode = f.document.getElementById('ttlValue');
  valueNode.value = '200';
  valueNode.dispatchEvent(new f.window.Event('input'));
  held._released = true; held.release({ body: diagnostic(4, 64) });
  await pending; await settle();
  assert.equal(f.document.getElementById('ttlCurrent').textContent, '64', 'the read result is still rendered');
  assert.equal(f.document.getElementById('ttlValue').value, '200', 'but the newer manual draft survives');
});

test('a definitive session expiry during a write stops the flow and cannot revive it', async () => {
  const f = fixture(); await login(f, 'password-A'); await readTtl(f);
  f.postQueue.push({ body: expired('TIMEOUT') });
  f.submitTtl('manual', '100');
  await waitFor(() => !f.appVisible(), 'session ended locally');
  assert.equal(f.ttlValueDisabled(), true, 'the TTL input is locked after expiry');
  assert.equal(f.diag('POST').length, 1, 'the single POST was not retried');
});

test('a late write completion from an expired session cannot unlock the next session', async () => {
  const f = fixture(); await login(f, 'password-A'); await readTtl(f);
  f.postQueue.push({ hold: true, body: diagnostic(1, 100, '100') });
  f.submitTtl('manual', '100');
  await waitFor(() => f.diag('POST').length === 1, 'write in flight');
  const held = f.requests.find(r => r.release && !r._released);
  f.app.powerBridge.expire(f.app.powerBridge.currentEpoch(), new Error('Session expired'));
  await settle(); assert.equal(f.appVisible(), false);
  await login(f, 'password-B');
  held._released = true; held.release();
  await settle();
  assert.equal(f.appVisible(), true, 'a stale write reply must not tear down the new session');
  assert.equal(f.ttlValueDisabled(), false, 'session B keeps its own control state');
  assert.equal(f.diag('POST').length, 1, 'no automatic retry for session B');
});

test('a capability document that is not the exact dev18 contract fails closed', async () => {
  const f = fixture(); await login(f);
  f.capabilityQueue.push({ body: '{"schema":"mf885-ttl-editor/v1","communityVersion":"0.4.7-dev.17","nativeApi":"r47-revision24-ttl8"}' });
  await readTtl(f);
  assert.equal(f.ttlPhase(), 'unavailable');
  assert.equal(f.diag('POST').length, 0);
  assert.equal(f.ttlApplyDisabled(), true);
});

test('the derived capability asset is the exact widened dev18 contract', () => {
  assert.equal(derived.capability.trimEnd(), '{"schema":"mf885-ttl-editor/v1","communityVersion":"0.4.7-dev.18","vendorBase":"2.5.94","nativeApi":"r47-revision24-ttl8","modes":["off","manual"],"manualRange":{"min":1,"max":255,"step":1,"canonical":"decimal"},"settings":["off","1-255"],"default":64,"persistence":"ram","bootTtl":64}');
});

test('the app transport guard rejects every non-canonical argument before building bytes', async () => {
  const f = fixture(); await login(f); await readTtl(f);
  const bridge = f.app.ttlBridge;
  for (const bad of ['0', '256', ' 64', '64 ', '+64', '-1', '064', '1.5', '1e2', 'NaN', 'Infinity', 64, null, undefined]) {
    bridge.begin('ttl-write', 'ttlStatus');
    assert.throws(() => bridge.post(bad, 'ttl-write'), /Invalid TTL/, JSON.stringify(bad));
    bridge.end('ttl-write');
  }
  for (const good of ['off', '1', '64', '255']) {
    bridge.begin('ttl-write', 'ttlStatus');
    const request = bridge.post(good, 'ttl-write');
    assert.ok(request && typeof request.then === 'function', good + ' is accepted by the guard');
    request.catch(() => null);
    bridge.end('ttl-write');
  }
  await settle();
  assert.equal(f.diag('POST').length, 4, 'only the four canonical arguments reached the wire');
});

// ---------------------------------------------------------------------------
// Preserved dev17 behaviour: CPU, console icons and console page.
// ---------------------------------------------------------------------------

test('the dev17 CPU card, console page and favicon/touch icons are preserved', () => {
  const f = fixture();
  assert.ok(f.document.getElementById('dashboardCpu'), 'Home CPU card exists');
  assert.ok(f.document.getElementById('diagnosticsCpu'), 'Diagnostics CPU status exists');
  for (const page of ['dashboard', 'messages', 'diagnostics', 'modem', 'ttl', 'ussd', 'at']) assert.ok(f.document.getElementById('page-' + page), 'page ' + page);
  const head = f.document.head.innerHTML;
  assert.match(head, /c047d18favicon\.png/);
  assert.match(head, /c047d18touch\.png/);
  assert.ok(f.document.getElementById('ussdConsole') || f.document.getElementById('page-ussd'), 'console UI preserved');
});

test('the unchanged CPU read still runs inside the shared snapshot lock', async () => {
  const f = fixture(); await login(f);
  // Warming baseline, then a valid 50% interval on the next snapshot.
  f.cpuQueue.push({ body: cpuBody(cpuFrame({ flags: 1, epoch: 3 })) });
  f.queue.push({ body: identity });
  await f.app.refreshAll('manual').catch(() => null);
  await settle();
  assert.equal(f.cpuHome(), 'Warming up');
  f.cpuQueue.push({ body: cpuBody(cpuFrame({ flags: 2, epoch: 3, total: 32768n, idle: 16384n })) });
  f.queue.push({ body: identity });
  await f.app.refreshAll('manual').catch(() => null);
  await settle();
  assert.equal(f.cpuHome(), '50.0%');
  assert.equal(f.cpuGets().length > 0, true);
  assert.equal(f.requests.filter(r => r.method === 'POST' && /c047d18cpu$/.test(r.url)).length, 0, 'the CPU file stays GET only');
});

test('an existing TTL setting is never written on load or on refresh', async () => {
  const f = fixture(); await login(f);
  const before = f.diag('POST').length;
  await f.app.refreshAll('manual').catch(() => null);
  await settle();
  assert.equal(f.diag('POST').length, before, 'no automatic TTL write from a refresh');
  assert.equal(f.diag('GET').length, 0, 'no automatic TTL read either');
});
