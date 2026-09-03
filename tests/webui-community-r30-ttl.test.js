const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const childProcess = require('node:child_process');
const path = require('node:path');
const vm = require('node:vm');

let parseHTML = null;
for (const candidate of ['linkedom', '/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']) {
  try { ({ parseHTML } = require(candidate)); break; } catch (_) {}
}

const root = path.resolve(__dirname, '..');
const releaseName = process.env.MF885_TTL_TEST_RELEASE || 'r30';
const releaseConfig = Object.freeze({
  r30: Object.freeze({ module: 'mf885_community_r30', html: 'r30.html', js: 'r30app.js', namespace: 'MF885CommunityR30', label: 'R3.0' }),
  r32: Object.freeze({ module: 'mf885_community_r32', html: 'r32.html', js: 'r32app.js', namespace: 'MF885CommunityR32', label: 'R3.2' }),
  r33: Object.freeze({ module: 'mf885_community_r33', html: 'r33.html', js: 'r33app.js', namespace: 'MF885CommunityR33', label: 'R3.3', bridge: true, setFile: 'ttl_set' }),
  r35: Object.freeze({ module: 'mf885_community_r35', html: 'r35.html', js: 'r35app.js', namespace: 'MF885CommunityR35', label: 'R3.5', sameModel: true, setFile: 'ttl_set' })
});
const selectedRelease = releaseConfig[releaseName];
if (!selectedRelease) throw new Error(`Unsupported MF885_TTL_TEST_RELEASE ${releaseName}`);
let derived;
if (process.env.MF885_R30_TEST_ASSET_DIR) {
  const fs = require('node:fs');
  derived = {
    html: fs.readFileSync(path.join(process.env.MF885_R30_TEST_ASSET_DIR, selectedRelease.html), 'utf8'),
    js: fs.readFileSync(path.join(process.env.MF885_R30_TEST_ASSET_DIR, selectedRelease.js), 'utf8')
  };
} else {
  derived = JSON.parse(childProcess.execFileSync('python3', ['-c', [
    "import json,sys",
    "from pathlib import Path",
    "sys.path.insert(0,'tools')",
    `import ${selectedRelease.module} as r`,
    "a=r.derive_assets(Path('.').resolve())",
    "print(json.dumps({'html':a[r.ENTRY_PATH].decode('utf-8'),'js':a[r.APP_PATH].decode('utf-8')}))"
  ].join(';')], { cwd: root, encoding: 'utf8' }));
}
const html = derived.html;
const source = derived.js;
const declaration = '<?xml version="1.0" encoding="US-ASCII"?> ';
const identity = '<RGW><sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></sysinfo><batteryinfo><Battery_percent>83</Battery_percent></batteryinfo><wan><NW_register_status>1</NW_register_status><network_name>Example Carrier</network_name><sys_mode>6</sys_mode><cellular><sim_status>0</sim_status></cellular></wan><lan><run_days>0</run_days><run_hours>0</run_hours><run_minutes>1</run_minutes><run_seconds>0</run_seconds></lan></RGW>';
const wan = '<RGW><wan><Engineering_mode>0</Engineering_mode><NW_register_status>1</NW_register_status><network_name>Example Carrier</network_name><sys_mode>6</sys_mode><cellular><sim_status>0</sim_status></cellular></wan></RGW>';
const engineer = '<RGW><Engi><LTE><band>7</band><rsrp>45</rsrp><rsrq>16</rsrq></LTE></Engi></RGW>';

function ttlXml(value, output = value === 'off' ? 'TTL_OFF' : 'TTL_VALUE') {
  if (selectedRelease.bridge) return `<RGW><diagnostic/><SystemChannelName><PRODUCT_CHANNEL>${value}</PRODUCT_CHANNEL></SystemChannelName></RGW>`;
  if (selectedRelease.sameModel) return `<RGW><diagnostic><output>${value}</output></diagnostic></RGW>`;
  return `<RGW><diagnostic><command>ttl</command><arg>${value}</arg><output>${output}</output></diagnostic></RGW>`;
}

function fixture() {
  const { window } = parseHTML(html);
  const document = window.document;
  Object.defineProperty(document.getElementById('folder'), 'value', { value: 'inbox', writable: true, configurable: true });
  let visibility = 'visible';
  Object.defineProperty(document, 'visibilityState', { get() { return visibility; }, configurable: true });
  const requests = [];
  const consoleEntries = [];
  const timers = new Map();
  const diagnosticQueue = [];
  let timerSequence = 0;
  let ttlState = 'off';

  function responseFor(xhr) {
    if (xhr.url === '/login.cgi') return { body: '', auth: 'Digest realm="Highwmg", nonce="abcdef", qop="auth"' };
    if (xhr.url.startsWith('/login.cgi?')) return { body: '' };
    if (/file=status1$/.test(xhr.url)) return { body: identity };
    if (/file=wan$/.test(xhr.url)) return { body: wan };
    if (/file=Engineer_parameter$/.test(xhr.url)) return { body: engineer };
    if (/file=ttl_set$/.test(xhr.url)) {
      assert.equal(Boolean(selectedRelease.setFile), true, 'isolated TTL setter must be selected');
      assert.equal(xhr.method, 'POST');
      assert.equal(String(xhr.body).startsWith(declaration), true);
      const selected = (String(xhr.body).match(/<arg>(off|[1-9][0-9]{0,2})<\/arg>/) || [])[1];
      assert.ok(selected, 'exact TTL argument');
      assert.equal(selected === 'off' || Number(selected) <= 255, true, 'TTL argument is in range');
      ttlState = selected;
      return { body: '<RGW/>' };
    }
    if (/file=diagnostic$/.test(xhr.url)) {
      if (xhr.method === 'POST') {
        assert.equal(selectedRelease.bridge, undefined, 'R3.3 must not POST through the read template');
        assert.equal(String(xhr.body).startsWith(declaration), true);
        const selected = (String(xhr.body).match(/<arg>(off|[1-9][0-9]{0,2})<\/arg>/) || [])[1];
        assert.ok(selected, 'exact TTL argument');
        assert.equal(selected === 'off' || Number(selected) <= 255, true, 'TTL argument is in range');
        ttlState = selected;
        return { body: '<RGW/>' };
      }
      return diagnosticQueue.length ? diagnosticQueue.shift() : { body: ttlXml(ttlState) };
    }
    if (/file=message$/.test(xhr.url)) {
      if (xhr.method === 'POST') return { body: '<RGW/>' };
      return { body: '<RGW><message><get_message><total_number>0</total_number><message_list></message_list></get_message></message></RGW>' };
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
      this.status = reply.status || 200;
      this.responseText = reply.body;
      this.auth = reply.auth || '';
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
  window.console = {
    debug(...values) { consoleEntries.push(['debug', ...values]); },
    error(...values) { consoleEntries.push(['error', ...values]); }
  };
  const context = { window, document, console: window.console, Date, JSON, Array, Object, String, Number, Boolean, RegExp, Error, Promise, Map, Set, Uint8Array };
  vm.createContext(context);
  vm.runInContext(source, context, { filename: selectedRelease.js });
  return {
    window, document, requests, consoleEntries, timers, diagnosticQueue,
    community: window[selectedRelease.namespace],
    currentTtl() { return ttlState; },
    setVisibility(value) { visibility = value; document.dispatchEvent(new window.Event('visibilitychange')); },
    fireNextTimer(predicate = () => true) {
      const entry = [...timers.entries()].find(([, timer]) => !timer.cleared && predicate(timer));
      assert.ok(entry, 'expected pending timer');
      entry[1].cleared = true;
      entry[1].callback();
      return entry[1].delay;
    }
  };
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
  await waitFor(() => /TTL state Off/.test(value.document.getElementById('ttlStatus').textContent), 'TTL bootstrap');
}

async function rejectedSameModelBody(body, failedCondition) {
  const value = fixture();
  value.diagnosticQueue.push({ body });
  value.document.getElementById('password').value = 'fixture-password';
  value.document.getElementById('loginForm').dispatchEvent(new value.window.Event('submit'));
  await waitFor(() => !value.document.getElementById('app').hidden, 'authenticated shell');
  await waitFor(() => value.community.ttlRuntime.locked, 'fail-closed TTL read');
  assert.equal([...value.document.querySelectorAll('button[data-ttl-value]')].every(button => button.disabled), true);
  assert.match(value.document.getElementById('ttlStatus').textContent, /writes are locked/i);
  if (failedCondition) {
    assert.equal(value.consoleEntries.some(entry => entry.some(item => item && item.id === failedCondition && item.passed === false)), true, failedCondition);
  }
  return value;
}

test(`${selectedRelease.label} is the existing extension plus one immediate-loading TTL page`, { skip: !parseHTML }, async () => {
  const value = fixture();
  assert.equal(value.document.querySelectorAll('nav [data-page]').length, 5);
  assert.equal(value.document.querySelectorAll('#page-ttl').length, 1);
  assert.match(value.document.getElementById('page-ttl').textContent, /returns to Off after every restart/);
  assert.equal([...value.document.querySelectorAll('button[data-ttl-value]')].every(button => button.disabled), true);
  assert.equal(value.document.getElementById('ttlCustomApply').disabled, true);
  await login(value);
  assert.deepEqual(value.requests.slice(0, 8).map(request => { const match = request.url.match(/file=([^&]+)/); return [request.method, match ? match[1] : request.url.split('?')[0]]; }), [
    ['GET', '/login.cgi'], ['GET', '/login.cgi'], ['GET', 'status1'], ['GET', 'wan'], ['GET', 'Engineer_parameter'], ['POST', 'message'], ['GET', 'message'], ['GET', 'diagnostic']
  ]);
  assert.equal(value.document.getElementById('ttlCurrent').textContent, 'Off');
  assert.equal([...value.document.querySelectorAll('button[data-ttl-value]')].every(button => !button.disabled), true);
  assert.equal(value.document.getElementById('ttlCustomApply').disabled, false);
});

test('each preset change is exactly one POST and one GET with no retry', { skip: !parseHTML }, async () => {
  const value = fixture();
  await login(value);
  for (const selected of ['64', '65', 'off']) {
    const before = value.requests.length;
    value.document.querySelector(`button[data-ttl-value="${selected}"]`).click();
    await waitFor(() => value.currentTtl() === selected && value.requests.length === before + 2 && /no retry was sent/i.test(value.document.getElementById('ttlStatus').textContent), `TTL ${selected} readback`);
    assert.deepEqual(value.requests.slice(before).map(request => request.method), ['POST', 'GET']);
    assert.equal(value.requests[before].url.endsWith(`file=${selectedRelease.setFile || 'diagnostic'}`), true);
    assert.match(String(value.requests[before].body), new RegExp(`<command>ttl</command><arg>${selected}</arg>`));
    assert.equal(value.community.ttlRuntime.locked, false);
  }
});

test('custom TTL accepts every boundary shape and rejects invalid values before transport', { skip: !parseHTML }, async () => {
  const value = fixture();
  await login(value);
  for (const selected of ['1', '37', '255']) {
    const before = value.requests.length;
    value.document.getElementById('ttlCustom').value = selected;
    value.document.getElementById('ttlCustomApply').click();
    await waitFor(() => value.currentTtl() === selected && value.requests.length === before + 2, `custom TTL ${selected}`);
    assert.deepEqual(value.requests.slice(before).map(request => request.method), ['POST', 'GET']);
    assert.match(String(value.requests[before].body), new RegExp(`<arg>${selected}</arg>`));
    assert.equal(value.document.querySelector('[data-ttl-card="custom"]').classList.contains('active'), true);
  }
  for (const selected of ['0', '01', '256', '-1']) {
    const before = value.requests.length;
    value.document.getElementById('ttlCustom').value = selected;
    value.document.getElementById('ttlCustomApply').click();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(value.requests.length, before, `invalid ${selected} must not reach transport`);
    assert.match(value.document.getElementById('ttlStatus').textContent, /1 to 255/);
  }
});

test('ambiguous readback locks mutation and one later fresh GET unlocks it', { skip: !parseHTML }, async () => {
  const value = fixture();
  await login(value);
  value.diagnosticQueue.push({ body: selectedRelease.setFile ? ttlXml('65') : ttlXml('64', 'TTL_OFF') });
  const before = value.requests.length;
  value.document.querySelector('button[data-ttl-value="64"]').click();
  await waitFor(() => value.community.ttlRuntime.locked, 'TTL mutation lock');
  assert.equal(value.requests.length, before + 2);
  assert.match(value.document.getElementById('ttlStatus').textContent, /outcome is unknown/i);
  assert.equal([...value.document.querySelectorAll('button[data-ttl-value]')].every(button => button.disabled), true);
  value.document.getElementById('ttlRefresh').click();
  await waitFor(() => !value.community.ttlRuntime.locked, 'TTL fresh read unlock');
  assert.equal(value.requests.length, before + 3);
  assert.equal(value.document.getElementById('ttlCurrent').textContent, '64 · Recommended');
  const failedCondition = selectedRelease.setFile ? 'readback_matches_request' : 'output_matches_state';
  assert.equal(value.consoleEntries.some(entry => entry.some(item => item && item.id === failedCondition && item.passed === false)), true);
});

test('same-model read rejects extra or duplicate fields and keeps writes locked', { skip: !parseHTML || !selectedRelease.sameModel }, async () => {
  const value = await rejectedSameModelBody('<RGW><diagnostic><output>off</output><arg>off</arg></diagnostic></RGW>', 'diagnostic_extra_field_count');
  assert.equal(value.consoleEntries.some(entry => entry.some(item => item && item.id === 'diagnostic_extra_field_count' && item.passed === false)), true);
});

test('same-model read rejects wrong root and attributes at every XML level', { skip: !parseHTML || !selectedRelease.sameModel }, async () => {
  const cases = [
    ['<rgw><diagnostic><output>off</output></diagnostic></rgw>', 'root_tag'],
    ['<RGW source="fixture"><diagnostic><output>off</output></diagnostic></RGW>', 'root_attribute_count'],
    ['<RGW><diagnostic source="fixture"><output>off</output></diagnostic></RGW>', 'diagnostic_attribute_count'],
    ['<RGW><diagnostic><output source="fixture">off</output></diagnostic></RGW>', 'output_attribute_count']
  ];
  for (const [body, condition] of cases) await rejectedSameModelBody(body, condition);
});

test('same-model read rejects nested output and significant surrounding text', { skip: !parseHTML || !selectedRelease.sameModel }, async () => {
  await rejectedSameModelBody('<RGW><diagnostic><output><value>off</value></output></diagnostic></RGW>', 'output_element_count');
  await rejectedSameModelBody('<RGW>unexpected<diagnostic><output>off</output></diagnostic></RGW>', 'root_significant_text');
  await rejectedSameModelBody('<RGW><diagnostic>unexpected<output>off</output></diagnostic></RGW>', 'diagnostic_significant_text');
});

test('same-model read never trims a noncanonical TTL value', { skip: !parseHTML || !selectedRelease.sameModel }, async () => {
  await rejectedSameModelBody('<RGW><diagnostic><output> off </output></diagnostic></RGW>', 'output_is_off_or_canonical_decimal');
});

test('universal polling includes TTL on every page and logout forgets RAM state', { skip: !parseHTML }, async () => {
  const value = fixture();
  await login(value);
  value.document.querySelector('nav [data-page="messages"]').click();
  value.document.getElementById('liveToggle').click();
  value.document.getElementById('liveToggle').click();
  const before = value.requests.length;
  value.fireNextTimer(timer => timer.delay === 0);
  await waitFor(() => value.requests.length === before + 6, 'universal TTL refresh');
  assert.deepEqual(value.requests.slice(before).map(request => [request.method, (request.url.match(/file=([^&]+)/) || [])[1]]), [
    ['GET', 'status1'], ['GET', 'wan'], ['GET', 'Engineer_parameter'], ['POST', 'message'], ['GET', 'message'], ['GET', 'diagnostic']
  ]);
  value.document.getElementById('logout').click();
  assert.equal(value.community.ttlRuntime.current, null);
  assert.equal(value.community.ttlRuntime.locked, false);
  assert.equal(value.document.getElementById('ttlCurrent').textContent, 'Loading...');
});
