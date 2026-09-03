const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

let parseHTML = null;
for (const candidate of ['linkedom', '/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']) {
  try { ({ parseHTML } = require(candidate)); break; } catch (_) {}
}

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'firmware/community-r2.6/r26.html'), 'utf8');
const source = fs.readFileSync(path.join(root, 'firmware/community-r2.6/r26app.js'), 'utf8');
const identity = '<RGW><sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></sysinfo></RGW>';

function decodeUcs2(value) {
  let output = '';
  for (let index = 0; index < value.length; index += 4) output += String.fromCharCode(parseInt(value.slice(index, index + 4), 16));
  return output;
}

function xmlItem(item) {
  const encode = value => String(value).replace(/[&<>]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[character]);
  return `<Item><index>${encode(item.id)}</index><from>${encode(item.from || item.to)}</from><contacts>${encode(item.to || item.from)}</contacts><subject>${encode(item.body)}</subject><received>${encode(item.date || '26,8,29,9,0,0,+0')}</received></Item>`;
}

function fixture(options = {}) {
  const { window } = parseHTML(html);
  const document = window.document;
  Object.defineProperty(document.getElementById('folder'), 'value', { value: 'inbox', writable: true, configurable: true });
  const requests = [];
  const consoleEntries = [];
  const counters = { semanticReads: 0, sendPosts: 0, deletePosts: 0, statusGets: 0 };
  const state = {
    inbox: Array.from({ length: 12 }, (_, index) => ({ id: `LRCV${index + 1}`, from: `+155500000${String(index + 1).padStart(2, '0')}`, body: `Inbox ${index + 1}` })),
    sent: [],
    sim: [],
    drafts: [],
    pendingFolder: null,
    pendingPage: 1,
    pendingCommand: null
  };

  function responseFor(xhr) {
    if (xhr.url === '/login.cgi') return { body: '', auth: 'Digest realm="Highwmg", nonce="abcdef", qop="auth"' };
    if (xhr.url.startsWith('/login.cgi?')) return { body: '' };
    if (/file=status1$/.test(xhr.url)) return { body: identity };
    if (/file=(?:wan|Engineer_parameter)$/.test(xhr.url)) return { body: '<RGW><wan><Engineering_mode>0</Engineering_mode></wan></RGW>' };
    if (!/file=message$/.test(xhr.url)) throw new Error(`Unexpected route ${xhr.method} ${xhr.url}`);
    if (xhr.method === 'POST') {
      const flag = (String(xhr.body || '').match(/<message_flag>([^<]+)<\/message_flag>/) || [])[1] || '';
      if (/^GET_/.test(flag)) {
        counters.semanticReads++;
        state.pendingFolder = flag === 'GET_RCV_SMS_LOCAL' ? 'inbox' : flag === 'GET_SENT_SMS_LOCAL' ? 'sent' : flag === 'GET_SIM_SMS' ? 'sim' : 'drafts';
        state.pendingPage = Number((String(xhr.body).match(/<page_number>(\d+)<\/page_number>/) || [])[1] || 1);
      } else if (flag === 'SEND_SMS') {
        counters.sendPosts++;
        const to = (String(xhr.body).match(/<contacts>([^<]+)<\/contacts>/) || [])[1] || '';
        const encoded = (String(xhr.body).match(/<content>([0-9A-F]+)<\/content>/) || [])[1] || '';
        if (!options.unknownSend) state.sent.unshift({ id: `LSENT${state.sent.length + 1}`, to, body: decodeUcs2(encoded) });
        state.pendingCommand = '4';
      } else if (flag === 'DELETE_SMS') {
        counters.deletePosts++;
        const id = (String(xhr.body).match(/<delete_message_id>([^,<]+),<\/delete_message_id>/) || [])[1] || '';
        state.inbox = state.inbox.filter(item => item.id !== id);
        state.pendingCommand = '6';
      } else throw new Error(`Unexpected message flag ${flag}`);
      return { body: '<RGW/>' };
    }
    if (state.pendingCommand) {
      counters.statusGets++;
      const command = state.pendingCommand;
      if (!options.unknownSend || command !== '4') state.pendingCommand = null;
      return { body: `<RGW><message><sms_cmd>${command}</sms_cmd><sms_cmd_status_result>${options.unknownSend && command === '4' ? '1' : '3'}</sms_cmd_status_result></message></RGW>` };
    }
    const items = state[state.pendingFolder || 'inbox'];
    const totalPages = Math.max(1, Math.ceil(items.length / 10));
    const start = (state.pendingPage - 1) * 10;
    const page = items.slice(start, start + 10);
    state.pendingFolder = null;
    return { body: `<RGW><message><get_message><total_number>${totalPages}</total_number><message_list>${page.map(xmlItem).join('')}</message_list></get_message></message></RGW>` };
  }

  class FakeXHR {
    constructor() { this.headers = {}; this.status = 0; this.responseText = ''; requests.push(this); }
    open(method, url, async) { this.method = method; this.url = url; this.async = async; }
    setRequestHeader(name, value) { this.headers[name] = value; }
    getResponseHeader(name) { return String(name).toLowerCase() === 'www-authenticate' ? this.auth || '' : ''; }
    send(body) {
      this.body = body;
      let reply;
      try { reply = responseFor(this); } catch (error) { queueMicrotask(() => this.onerror && this.onerror(error)); return; }
      this.status = 200; this.responseText = reply.body; this.auth = reply.auth || '';
      queueMicrotask(() => this.onload && this.onload());
    }
    abort() { queueMicrotask(() => this.onabort && this.onabort()); }
  }

  window.XMLHttpRequest = FakeXHR;
  window.location = { protocol: 'http:', host: '192.168.21.1', hash: '' };
  window.hex_md5 = input => crypto.createHash('md5').update(String(input)).digest('hex');
  window.confirm = () => true;
  window.setTimeout = callback => { queueMicrotask(callback); return 1; };
  window.clearTimeout = () => {};
  window.console = {
    debug(...values) { consoleEntries.push(['debug', ...values]); },
    error(...values) { consoleEntries.push(['error', ...values]); }
  };
  const context = { window, document, console: window.console, Date, JSON, Array, Object, String, Number, Boolean, RegExp, Error, Promise, Map, Set, Uint8Array };
  vm.createContext(context);
  vm.runInContext(source, context, { filename: 'r26app.js' });
  return { window, document, requests, counters, state, consoleEntries };
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
  await waitFor(() => !value.document.getElementById('app').hidden, 'authenticated app');
}

test('R2.6 fake-router E2E logs in with exactly three requests', { skip: !parseHTML }, async () => {
  const value = fixture();
  assert.equal(value.requests.length, 0);
  await login(value);
  assert.equal(value.requests.length, 3);
  assert.deepEqual(value.requests.map(item => [item.method, item.url.split('?')[0]]), [['GET', '/login.cgi'], ['GET', '/login.cgi'], ['GET', '/xml_action.cgi']]);
  assert.match(value.requests[1].headers.Authorization, /nc=00000001/);
  assert.match(value.requests[2].headers.Authorization, /nc=00000002/);
});

test('R2.6 reads two router pages progressively and paginates locally', { skip: !parseHTML }, async () => {
  const value = fixture(); await login(value);
  value.document.querySelector('[data-page="messages"]').click();
  value.document.getElementById('messagesRefresh').click();
  await waitFor(() => /12 messages/.test(value.document.getElementById('messagesStatus').textContent), 'complete inbox read');
  assert.equal(value.counters.semanticReads, 2);
  assert.equal(value.document.querySelectorAll('#messagesList article').length, 10);
  const requestCount = value.requests.length;
  value.document.getElementById('messagesNext').click();
  assert.equal(value.document.querySelectorAll('#messagesList article').length, 2);
  assert.equal(value.requests.length, requestCount);
});

test('R2.6 sends exactly once and proves one matching new Sent record', { skip: !parseHTML }, async () => {
  const value = fixture(); await login(value);
  value.document.querySelector('[data-page="messages"]').click();
  value.document.getElementById('messagesNew').click();
  value.document.getElementById('messageNumber').value = '+15551234567';
  value.document.getElementById('messageBody').value = 'hello';
  const submit = new value.window.Event('submit');
  value.document.getElementById('messageComposer').dispatchEvent(submit);
  value.document.getElementById('messageComposer').dispatchEvent(new value.window.Event('submit'));
  await waitFor(() => /Recorded in Sent/.test(value.document.getElementById('messagesStatus').textContent), 'Sent readback');
  assert.equal(value.counters.sendPosts, 1);
  assert.equal(value.counters.statusGets, 1);
  assert.deepEqual(value.state.sent.map(item => [item.to, item.body]), [['+15551234567', 'hello']]);
});

test('R2.6 deletes exactly once and proves the unique inbox ID absent', { skip: !parseHTML }, async () => {
  const value = fixture(); await login(value);
  value.document.querySelector('[data-page="messages"]').click();
  value.document.getElementById('messagesRefresh').click();
  await waitFor(() => /12 messages/.test(value.document.getElementById('messagesStatus').textContent), 'complete inbox read');
  const button = value.document.querySelector('button[data-delete-id="LRCV1"]');
  button.click(); button.click();
  await waitFor(() => /Deleted and verified absent/.test(value.document.getElementById('messagesStatus').textContent), 'delete readback');
  assert.equal(value.counters.deletePosts, 1);
  assert.equal(value.counters.statusGets, 1);
  assert.equal(value.state.inbox.some(item => item.id === 'LRCV1'), false);
});

test('R2.6 never retries an ambiguous Send and locks further writes', { skip: !parseHTML }, async () => {
  const value = fixture({ unknownSend: true }); await login(value);
  value.document.querySelector('[data-page="messages"]').click();
  value.document.getElementById('messagesNew').click();
  value.document.getElementById('messageNumber').value = '+15551234567';
  value.document.getElementById('messageBody').value = 'unknown';
  value.document.getElementById('messageComposer').dispatchEvent(new value.window.Event('submit'));
  await waitFor(() => /Outcome unknown/.test(value.document.getElementById('messagesStatus').textContent), 'locked unknown outcome');
  assert.equal(value.counters.sendPosts, 1);
  assert.equal(value.counters.statusGets, 10);
  assert.equal(value.document.getElementById('messagesNew').disabled, true);
  assert.equal(value.document.getElementById('messageSend').disabled, true);
  assert.match(value.document.getElementById('messagesStatus').textContent, /\[E_COMMAND_UNPROVEN · R26-[0-9]{4}\]/);
  assert.equal(value.consoleEntries.some(entry => entry[0] === 'error' && /\[E_COMMAND_UNPROVEN\]/.test(entry[1])), true);
});
