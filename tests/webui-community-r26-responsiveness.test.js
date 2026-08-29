const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

let XMLDOMParser = null;
for (const candidate of ['linkedom', '/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']) {
  try { ({ DOMParser: XMLDOMParser } = require(candidate)); break; } catch (_) {}
}

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'firmware/community-r2.6/r26.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'firmware/community-r2.6/r26app.js'), 'utf8');
const css = fs.readFileSync(path.join(root, 'firmware/community-r2.6/r26ui.css'), 'utf8');

class TestNode {
  constructor(id = '', attributes = {}) {
    this.id = id;
    this.attributes = { ...attributes };
    this.listeners = {};
    this.children = [];
    this.hidden = false;
    this.disabled = false;
    this.value = '';
    this.textContent = '';
    this.className = attributes.class || '';
    this.style = {};
    this.classList = { toggle: (name, enabled) => {
      const values = this.className.split(/\s+/).filter(Boolean).filter(value => value !== name);
      if (enabled) values.push(name);
      this.className = values.join(' ');
    } };
  }
  addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
  dispatchEvent(event) { event.target = this; for (const callback of this.listeners[event.type] || []) callback.call(this, event); return !event.defaultPrevented; }
  appendChild(child) { this.children.push(child); return child; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  focus() {}
}

class TestEvent {
  constructor(type) { this.type = type; this.defaultPrevented = false; }
  preventDefault() { this.defaultPrevented = true; }
}

function testDocument() {
  const nodes = {};
  for (const match of html.matchAll(/id="([^"]+)"(?:\s+class="([^"]*)")?/g)) nodes[match[1]] = new TestNode(match[1], { class: match[2] || '' });
  for (const match of html.matchAll(/<[^>]+id="([^"]+)"[^>]*>([^<]*)/g)) if (nodes[match[1]]) nodes[match[1]].textContent = match[2].trim();
  nodes.boot.hidden = false;
  nodes.login.hidden = true;
  nodes.app.hidden = true;
  nodes['page-messages'].hidden = true;
  nodes['page-diagnostics'].hidden = true;
  nodes['page-modem'].hidden = true;
  nodes.folder.value = 'inbox';
  const pageLinks = [...html.matchAll(/data-page="([^"]+)"/g)].map(match => new TestNode('', { 'data-page': match[1] }));
  const listeners = {};
  return {
    readyState: 'loading',
    body: new TestNode('body'),
    getElementById(id) { return nodes[id] || null; },
    querySelectorAll(selector) {
      if (selector === '.page') return Object.values(nodes).filter(item => item.id.startsWith('page-'));
      if (selector === '[data-page]') return pageLinks;
      return [];
    },
    createElement() { return new TestNode(); },
    addEventListener(name, callback) { (listeners[name] ||= []).push(callback); },
    dispatchEvent(event) { for (const callback of listeners[event.type] || []) callback.call(this, event); },
    nodes,
    pageLinks
  };
}

function fixture() {
  const document = testDocument();
  const requests = [];
  const timers = [];
  class FakeXHR {
    constructor() { this.headers = {}; requests.push(this); }
    open(method, url, async) { this.method = method; this.url = url; this.async = async; }
    setRequestHeader(name, value) { this.headers[name] = value; }
    getResponseHeader(name) { return String(name).toLowerCase() === 'www-authenticate' ? this.challenge || '' : ''; }
    send(body) { this.body = body; }
    abort() { if (this.onabort) this.onabort(); }
  }
  const window = {
    window: null,
    document,
    location: { protocol: 'http:', host: '192.168.21.1', hash: '' },
    Event: TestEvent,
    XMLHttpRequest: FakeXHR,
    hex_md5(input) { return crypto.createHash('md5').update(String(input)).digest('hex'); },
    crypto: { getRandomValues(buffer) { buffer.fill(7); return buffer; } },
    setTimeout(callback, milliseconds) { timers.push({ callback, milliseconds }); return timers.length; },
    clearTimeout() {},
    confirm() { return true; },
    DOMParser: XMLDOMParser || class {}
  };
  window.window = window;
  const context = window;
  vm.createContext(context);
  vm.runInContext(script, context, { filename: 'r26app.js' });
  document.dispatchEvent(new TestEvent('DOMContentLoaded'));
  return { window, document, requests, timers };
}

test('R2.6 entry is a standalone shell and cannot start the legacy blocking stack', () => {
  assert.match(html, /<script defer src="js\/r26app\.js"><\/script>/);
  assert.match(html, /<script src="js\/library\/md5\.js"><\/script>/);
  for (const forbidden of ['initIndex', 'ajax_calls.js', 'r25auth.js', 'r25sms.js', 'r25diag.js', 'r25modem.js', 'callProductXML', 'PostSyncXML', 'GetSmsXML']) {
    assert.doesNotMatch(html, new RegExp(forbidden.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
});

test('R2.6 transport has no synchronous XHR and every request has one 10-second deadline', () => {
  assert.doesNotMatch(script, /async\s*:\s*false|\.open\([^\n]+,\s*false\s*\)/);
  assert.match(script, /REQUEST_TIMEOUT_MS=10000/);
  assert.match(script, /xhr\.open\(options\.method\|\|'GET',options\.url,true\)/);
  assert.match(script, /xhr\.timeout=options\.timeoutMs\|\|REQUEST_TIMEOUT_MS/);
  assert.match(script, /xhr\.ontimeout=/);
});

test('R2.6 paints the login shell without sending a router request', () => {
  const value = fixture();
  assert.equal(value.requests.length, 0);
  assert.equal(value.document.getElementById('boot').hidden, true);
  assert.equal(value.document.getElementById('login').hidden, false);
  assert.match(value.document.getElementById('loginStatus').textContent, /No router request/);
});

test('R2.6 leaves the page responsive while login is pending and reports the exact timeout', async () => {
  const value = fixture();
  value.document.getElementById('password').value = 'fixture-password';
  value.document.getElementById('loginForm').dispatchEvent(new value.window.Event('submit', { cancelable: true }));
  assert.equal(value.requests.length, 1);
  assert.equal(value.requests[0].async, true);
  assert.equal(value.requests[0].timeout, 10000);
  assert.equal(value.document.getElementById('login').hidden, false);
  assert.equal(value.document.getElementById('signIn').disabled, true);
  assert.match(value.document.getElementById('loginStatus').textContent, /Request 1 of 3/);
  value.requests[0].ontimeout();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(value.document.getElementById('signIn').disabled, false);
  assert.match(value.document.getElementById('loginStatus').textContent, /did not answer within 10 seconds/);
  assert.match(value.document.getElementById('loginStatus').className, /error/);
});

test('R2.6 parses the proven Digest envelope and rejects incomplete challenges', () => {
  const value = fixture();
  assert.deepEqual(
    JSON.parse(JSON.stringify(value.window.MF885CommunityR26.parseChallenge('Digest realm="Highwmg", nonce="abcdef", qop="auth"'))),
    { realm: 'Highwmg', nonce: 'abcdef', qop: 'auth', opaque: '' }
  );
  assert.throws(() => value.window.MF885CommunityR26.parseChallenge('Digest realm="Highwmg", qop="auth"'), /unsupported login challenge/);
});

test('R2.6 requires the exact direct status1 identity with no duplicate or nested decoy', { skip: !XMLDOMParser }, () => {
  const api = fixture().window.MF885CommunityR26;
  const exact = '<RGW><sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></sysinfo></RGW>';
  assert.equal(api.exactIdentity(api.parseXml(exact)), true);
  for (const invalid of [
    exact.replace('LV01', 'LV02'),
    exact.replace('Ver.D', 'Ver.C'),
    exact.replace('2.5.94_release_MF855_NZ_CP_2.129.003', '2.5.94'),
    exact.replace('</sysinfo>', '<model_name>LV01</model_name></sysinfo>'),
    '<RGW><decoy>' + exact + '</decoy></RGW>',
    exact.replace('</RGW>', '<login_status>KICKOFF</login_status></RGW>')
  ]) {
    let accepted = false;
    try { accepted = api.exactIdentity(api.parseXml(invalid)); } catch (_) {}
    assert.equal(accepted, false);
  }
});

test('R2.6 uses the exact browser Digest sequence and never mixes in the APP profile', async () => {
  const value = fixture();
  value.document.getElementById('password').value = 'fixture-password';
  value.document.getElementById('loginForm').dispatchEvent(new value.window.Event('submit'));
  const challenge = value.requests[0];
  challenge.status = 200;
  challenge.responseText = '';
  challenge.challenge = 'Digest realm="Highwmg", nonce="abcdef", qop="auth"';
  challenge.onload();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(value.requests.length, 2);
  const login = value.requests[1];
  assert.equal(login.method, 'GET');
  assert.match(login.url, /^\/login\.cgi\?realm=Highwmg&nonce=abcdef&response=[0-9a-f]{32}&qop=auth&cnonce=[0-9a-f]{16}&Action=Digest&username=admin&temp=marvell$/);
  assert.doesNotMatch(login.url, /client=APP/);
  assert.match(login.headers.Authorization, /uri="\/cgi\/xml_action\.cgi"/);
  assert.match(login.headers.Authorization, /nc=00000001/);
  login.status = 200;
  login.responseText = '';
  login.onload();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(value.requests.length, 3);
  assert.match(value.requests[2].url, /file=status1$/);
  assert.match(value.requests[2].headers.Authorization, /nc=00000002/);
});

test('R2.6 builds the stock Send/Delete XML once from validated values', () => {
  const api = fixture().window.MF885CommunityR26;
  const date = {getFullYear:()=>2026,getMonth:()=>7,getDate:()=>29,getHours:()=>9,getMinutes:()=>5,getSeconds:()=>6,getTimezoneOffset:()=>-300};
  assert.equal(api.smsTime(date), '26,8,29,9,5,6,%2B5');
  assert.equal(api.segments('x'.repeat(70)), 1);
  assert.equal(api.segments('x'.repeat(71)), 2);
  assert.equal(api.segments('x'.repeat(268)), 4);
  assert.equal(api.validPhone('+15551234567'), true);
  assert.equal(api.validPhone('+1+2'), false);
  assert.equal(api.validBody('Привет'), true);
  assert.equal(api.validBody('x'.repeat(269)), false);
  assert.equal(api.validBody('😀'), false);
  const send = api.sendXml('+15551234567', 'Hi <&', date);
  assert.match(send, /<message_flag>SEND_SMS<\/message_flag><sms_cmd>4<\/sms_cmd>/);
  assert.match(send, /<contacts>\+15551234567<\/contacts>/);
  assert.match(send, /<content>004800690020003C0026<\/content>/);
  assert.match(send, /<sms_time>26,8,29,9,5,6,%2B5<\/sms_time>/);
  assert.equal((send.match(/SEND_SMS/g) || []).length, 1);
  const deletion = api.deleteXml('LRCV42');
  assert.match(deletion, /<message_flag>DELETE_SMS<\/message_flag><sms_cmd>6<\/sms_cmd>/);
  assert.match(deletion, /<tags>12<\/tags><mem_store>1<\/mem_store>/);
  assert.match(deletion, /<delete_message_id>LRCV42,<\/delete_message_id>/);
  assert.equal((deletion.match(/DELETE_SMS/g) || []).length, 1);
});

test('R2.6 mutation completion is bounded, GET-only, and fail-closed after submission', () => {
  const api = fixture().window.MF885CommunityR26;
  assert.equal(api.statusPolls, 10);
  assert.match(script, /function pollCommand\(command,attempt\)\{return request\(\{method:'GET'/);
  assert.match(script, /if\(attempt>=STATUS_POLLS-1\)throw new Error\('Command completion was not proven\.'/);
  assert.match(script, /if\(submitted\)lockUnknown\(error\.message\|\|'Send verification failed\.'/);
  assert.match(script, /if\(submitted\)lockUnknown\(error\.message\|\|'Delete verification failed\.'/);
  assert.equal((script.match(/postMutation\(sendXml/g) || []).length, 1);
  assert.equal((script.match(/postMutation\(deleteXml/g) || []).length, 1);
});

test('R2.6 Messages is bounded, cancellable, progressively rendered, and never auto-polled', () => {
  assert.match(script, /MAX_MESSAGE_PAGES=20/);
  assert.match(script, /Loaded '\+all\.length\+' messages; completed page/);
  assert.match(script, /messagesCancel[^\n]+cancelCurrent/);
  assert.doesNotMatch(script, /setInterval|WATCH_KEY|watcher|automatic retry/i);
  assert.match(html, /Background polling is off/);
});

test('R2.6 exposes no unrelated mutation route or persistent credential store', () => {
  for (const forbidden of ['RestoreFw', 'MINI', 'status1?method=set', 'Engineering_mode=', 'SEND_USSD', 'WISP', 'IMEI', 'localStorage', 'sessionStorage']) {
    assert.doesNotMatch(script, new RegExp(forbidden, 'i'));
  }
});

test('R2.6 responsive layout keeps navigation and values inside a 720px breakpoint', () => {
  assert.match(css, /@media\(max-width:720px\)/);
  assert.match(css, /nav\{order:3;flex-basis:100%;display:grid;grid-template-columns:repeat\(4,1fr\)/);
  assert.match(css, /\.cards,\.values\{grid-template-columns:1fr\}/);
});
