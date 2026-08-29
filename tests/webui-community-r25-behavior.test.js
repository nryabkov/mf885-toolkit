'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const child = require('node:child_process');
const path = require('node:path');
const vm = require('node:vm');

let parseHTML = null;
for (const candidate of ['linkedom', '/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']) {
  try { ({ parseHTML } = require(candidate)); break; } catch (_) {}
}

const root = path.resolve(__dirname, '..');
const generator = String.raw`
import json
from pathlib import Path
import mf885_community_r22 as r22
import mf885_community_r23 as r23
import mf885_community_r24 as r24
import mf885_community_r25 as r25

root = Path('.')
diag23 = r23._derive_diagnostics(r22._derive_diagnostics(root))
diag25 = r25._patch_diagnostics(r24._revise(diag23, 'test diagnostics'))
sms25 = r25._patch_sms(r24._patch_sms((root / 'firmware/community-r2.3/SMS.js').read_bytes()))
modem25 = r25._patch_modem((root / 'firmware/community-r2.4/modem_monitor.js').read_bytes())
diag_html = r25._patch_diagnostics_html(r24._revise((root / 'firmware/community-r2.3/Diagnostics.html').read_bytes(), 'test diagnostics html'))
sms_html = r25._revise(r24._revise((root / 'firmware/community-r2.3/SMS.html').read_bytes(), 'test sms html'), 'test sms html')
modem_html = r25._patch_modem_html((root / 'firmware/community-r2.4/Modem.html').read_bytes())
css24 = r24._revise((root / 'firmware/community-r2.3/community_ui.css').read_bytes(), 'test css') + b'\n' + (root / 'firmware/community-r2.4/community_ui_additions.css').read_bytes()
css25 = r25._patch_css(css24)
print(json.dumps({
  'diagnostics': diag25.decode(), 'diagnosticsHtml': diag_html.decode(),
  'sms': sms25.decode(), 'smsHtml': sms_html.decode(),
  'modem': modem25.decode(), 'modemHtml': modem_html.decode(), 'css': css25.decode(),
}))
`;
const generatedProcess = child.spawnSync('python3', ['-c', generator], {
  cwd: root,
  encoding: 'utf8',
  env: { ...process.env, PYTHONPATH: path.join(root, 'tools') }
});
if (generatedProcess.status !== 0) throw new Error(generatedProcess.stderr);
const generated = JSON.parse(generatedProcess.stdout);

const exactIdentity = '<sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num><serial_number>PRIVATE-SERIAL</serial_number></sysinfo>';
const status = `<RGW>${exactIdentity}<batteryinfo><Battery_percent>88</Battery_percent><Battery_status>1</Battery_status><Charger_status>4</Charger_status></batteryinfo><wan><sys_mode>17</sys_mode><cellular><sim_status>0</sim_status><rssi>36</rssi><roaming>0</roaming></cellular><network_name>Example Carrier</network_name></wan><message><content>PRIVATE-SMS</content></message></RGW>`;
const wan = mode => `<RGW><wan><Engineering_mode>${mode}</Engineering_mode><NW_register_status>1</NW_register_status><network_name>Example Carrier</network_name><connect_disconnect>cellular</connect_disconnect><cellular><sim_status>0</sim_status><roaming>0</roaming><imsi>PRIVATE-IMSI</imsi><password>PRIVATE-PASSWORD</password></cellular></wan><HA1>PRIVATE-HA1</HA1></RGW>`;
const nestedEngineer = '<RGW><Engi><LTE><tac>PRIVATE-TAC</tac><phyCellId>77</phyCellId><dlEuArfcn>2850</dlEuArfcn><ulEuArfcn>20850</ulEuArfcn><band>7</band><dlBandwidth>5</dlBandwidth><cellId>PRIVATE-CELL</cellId><rsrp>45</rsrp><rsrq>16</rsrq><sinr>8</sinr><mainRsrp>42</mainRsrp><diversityRsrp>47</diversityRsrp><mainRsrq>10</mainRsrq><diversityRsrq>19</diversityRsrq><rssi>64</rssi><cqi>0</cqi></LTE></Engi></RGW>';
const signedEngineer = '<RGW><Engineer_parameter><LTE_band>7</LTE_band><EARFCN>2850</EARFCN><PCI>77</PCI><RSRP>-94</RSRP><RSRQ>-10</RSRQ><SINR>16</SINR><RSSI>-66</RSSI></Engineer_parameter></RGW>';

function commonWindow(html) {
  const { window } = parseHTML('<html><head><title>Router</title></head><body><div id="Content"></div></body></html>');
  const document = window.document;
  function jquery() { return {}; }
  jquery.fn = {};
  jquery.i18n = { map: {} };
  Object.assign(window, {
    jQuery: jquery,
    $: jquery,
    location: { protocol: 'http:', host: '192.168.21.1' },
    callProductHTML: () => html,
    getAuthHeader: method => `Digest ${method}`,
    console,
    MF885CommunityR25: {
      markRoot() { document.documentElement.className += ' mfCommunityR25Root'; },
      exactStatus1Identity() { return true; }
    }
  });
  document.execCommand = () => false;
  return { window, document, jquery };
}

function diagnosticsFixture(options = {}) {
  const value = commonWindow(generated.diagnosticsHtml);
  const calls = [];
  const responses = {
    status1: options.status || status,
    wan: options.wan || wan('0'),
    Engineer_parameter: options.engineer || '<RGW/>'
  };
  value.jquery.ajax = config => {
    const name = (config.url.match(/file=([^&]+)/) || [])[1];
    const headers = {};
    calls.push({ name, config, headers });
    config.beforeSend({ setRequestHeader: (key, item) => { headers[key] = item; } });
    config.success(new value.window.DOMParser().parseFromString(responses[name], 'text/xml'));
    return { abort() {} };
  };
  const context = { window: value.window, document: value.document, console, Date, JSON, Array, Object, String, Number, Boolean, RegExp, Error, Promise, Map, Set };
  vm.createContext(context);
  vm.runInContext(generated.diagnostics, context, { filename: 'r25diag.js' });
  const controller = value.jquery.fn.objDiagnostics.call({});
  controller.setXMLName('status1');
  controller.onLoad();
  return { ...value, calls, controller };
}

function modemFixture(options = {}) {
  const value = commonWindow(generated.modemHtml);
  const calls = [];
  const timers = [];
  const storage = { ...(options.storage || {}) };
  const responses = {
    status1: options.status || status,
    wan: options.wan || wan('0'),
    Engineer_parameter: options.engineer || '<RGW/>'
  };
  value.jquery.ajax = config => {
    const name = (config.url.match(/file=([^&]+)/) || [])[1];
    const headers = {};
    calls.push({ name, config, headers });
    config.beforeSend({ setRequestHeader: (key, item) => { headers[key] = item; } });
    const request = { aborted: false, abort() { this.aborted = true; } };
    if (!request.aborted) config.success(new value.window.DOMParser().parseFromString(responses[name], 'text/xml'));
    return request;
  };
  Object.assign(value.window, {
    sessionStorage: {
      getItem(key) { if (options.storageThrows) throw new Error('storage'); return Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null; },
      setItem(key, item) { if (options.storageThrows) throw new Error('storage'); storage[key] = String(item); },
      removeItem(key) { delete storage[key]; }
    },
    setTimeout(fn, milliseconds) { timers.push({ fn, milliseconds, cancelled: false }); return timers.length; },
    clearTimeout(id) { if (timers[id - 1]) timers[id - 1].cancelled = true; }
  });
  const context = { window: value.window, document: value.document, console, Date, JSON, Array, Object, String, Number, Boolean, RegExp, Error, Promise, Map, Set };
  vm.createContext(context);
  vm.runInContext(generated.modem, context, { filename: 'r25modem.js' });
  const controller = value.jquery.fn.objModemMonitor.call({});
  controller.setXMLName('status1');
  controller.onLoad();
  return { ...value, calls, timers, storage, controller };
}

function smsXml() {
  return '<RGW><message><get_message><total_number>0</total_number><message_list/></get_message></message></RGW>';
}

function smsFixture(options = {}) {
  const value = commonWindow(generated.smsHtml);
  const timers = [];
  const storage = { ...(options.storage || {}) };
  let lastMap = [];
  let permissionCalls = 0;
  function FakeNotification() {}
  FakeNotification.permission = 'default';
  FakeNotification.requestPermission = () => { permissionCalls += 1; return Promise.resolve('default'); };
  Object.assign(value.window, {
    confirm: () => false,
    callProductXML: () => `<RGW>${exactIdentity}</RGW>`,
    putMapElement: (map, key, item) => map.push({ key, value: item }),
    g_objXML: { createXML: item => item, getXMLDocToString: item => item },
    PostSyncXML: (_name, map) => { lastMap = map; },
    GetSmsXML: () => { void lastMap; return smsXml(); },
    PostXMLWithResponse: () => { throw new Error('unexpected mutation'); },
    getData: () => '<RGW/>',
    isSecureContext: false,
    Notification: FakeNotification,
    sessionStorage: {
      getItem(key) { if (options.storageThrows) throw new Error('storage'); return Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null; },
      setItem(key, item) { if (options.storageThrows) throw new Error('storage'); storage[key] = String(item); },
      removeItem(key) { delete storage[key]; }
    },
    setTimeout(fn, milliseconds) { timers.push({ fn, milliseconds, cancelled: false }); return timers.length; },
    clearTimeout(id) { if (timers[id - 1]) timers[id - 1].cancelled = true; },
    UniDecode: item => item,
    UniEncode: item => item,
    GetSmsTime: () => 'fixture'
  });
  const context = value.window;
  vm.createContext(context);
  vm.runInContext(generated.sms, context, { filename: 'r25sms.js' });
  const controller = value.jquery.fn.objSms.call({}, 'mDeviceInbox');
  controller.setXMLName('message');
  controller.onLoad();
  return { ...value, timers, storage, controller, get permissionCalls() { return permissionCalls; } };
}

test('R2.5 Diagnostics explains Disabled Engineering mode and exposes the stock signal index honestly', { skip: !parseHTML }, () => {
  const value = diagnosticsFixture();
  assert.deepEqual(value.calls.map(item => item.name), ['status1', 'wan', 'Engineer_parameter']);
  for (const call of value.calls) {
    assert.equal(call.config.type, 'GET');
    assert.equal(call.config.timeout, 10000);
    assert.equal(call.config.cache, false);
    assert.equal(call.headers.Authorization, 'Digest GET');
  }
  const visible = value.document.getElementById('mfDiagValues').textContent;
  assert.match(visible, /Engineering modeDisabled/);
  assert.match(visible, /Signal quality \(vendor scale\)36/);
  assert.match(visible, /Detailed radio metricsNot returned/);
  assert.doesNotMatch(visible, /BandNot returned|RSRPNot returned|PCINot returned/);
  assert.match(value.document.getElementById('mfDiagStatus').textContent, /Engineering mode is Disabled; detailed radio metrics were not returned/);
  assert.match(value.document.documentElement.className, /mfCommunityR25Root/);

  const enabledEmpty = diagnosticsFixture({ wan: wan('1') });
  assert.match(enabledEmpty.document.getElementById('mfDiagStatus').textContent, /Engineering mode is Enabled; detailed radio metrics were not returned/);
});

test('R2.5 Diagnostics parses the nested stock schema and keeps its safe copy location-free', { skip: !parseHTML }, () => {
  const value = diagnosticsFixture({ wan: wan('0'), engineer: nestedEngineer });
  const visible = value.document.getElementById('mfDiagValues').textContent;
  for (const expected of ['Engineering modeDisabled', 'Band7', 'EARFCN2850', 'PCI77', 'RSRP-95 dBm · index 45', 'RSRQ-11.5 dB · index 16', 'SINRraw 8', 'RSSIraw 64']) assert.match(visible, new RegExp(expected));
  value.document.getElementById('mfDiagCopy').click();
  const report = value.document.getElementById('mfDiagReport').value;
  const parsed = JSON.parse(report);
  assert.equal(parsed.schema, 'mf885-community-safe-diagnostics/v1');
  assert.deepEqual(parsed.cellular.engineeringMode, { value: 'Disabled', stale: false });
  assert.deepEqual(parsed.cellular.signalQuality, { value: '36', stale: false });
  assert.deepEqual(parsed.cellular.rsrp, { value: '-95 dBm · index 45', stale: false });
  for (const secret of ['PRIVATE-', '2850', '20850', '77', '<RGW>', '192.168.21.1']) assert.doesNotMatch(report, new RegExp(secret.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
});

test('R2.5 keeps already signed flat radio values compatible without inventing SINR or RSSI units', { skip: !parseHTML }, () => {
  const value = diagnosticsFixture({ engineer: signedEngineer });
  const visible = value.document.getElementById('mfDiagValues').textContent;
  assert.match(visible, /RSRP-94 dBm/);
  assert.match(visible, /RSRQ-10 dB/);
  assert.match(visible, /SINRraw 16/);
  assert.match(visible, /RSSIraw -66/);
});

test('R2.5 Modem monitor is default-on, renders vendor signal bars, and persists an explicit opt-out', { skip: !parseHTML }, () => {
  const value = modemFixture();
  assert.deepEqual(value.calls.map(item => item.name), ['status1', 'wan', 'Engineer_parameter']);
  assert.equal(value.document.getElementById('mfModemWatch').checked, true);
  assert.equal(value.timers.filter(item => !item.cancelled && item.milliseconds === 30000).length, 1);
  const visible = value.document.getElementById('mfCommunityR25Modem').textContent;
  assert.match(visible, /Engineering modeDisabled/);
  assert.match(visible, /Signal level36 \/ 3\/4 bars \/ vendor scale/);
  assert.match(visible, /Detailed radio metricsNot returned/);
  assert.doesNotMatch(visible, /BandNot returned|RSRPNot returned/);
  assert.match(value.document.getElementById('mfModemStatus').textContent, /Engineering mode is Disabled; RSRP was not returned/);
  value.document.getElementById('mfModemCopy').click();
  const report = JSON.parse(value.document.getElementById('mfModemReport').value);
  assert.equal(report.samples[0].engineeringMode, 'Disabled');
  assert.equal(report.samples[0].signalIndex, '36');
  assert.equal(report.samples[0].signalBars, 3);

  const checkbox = value.document.getElementById('mfModemWatch');
  checkbox.checked = false;
  checkbox.dispatchEvent(new value.window.Event('change'));
  assert.equal(value.storage['mf885.community.r25.modem-watch.v1'], '0');
  assert.equal(value.timers.filter(item => !item.cancelled && item.milliseconds === 30000).length, 0);

  const restored = modemFixture({ storage: { 'mf885.community.r25.modem-watch.v1': '0' } });
  assert.equal(restored.document.getElementById('mfModemWatch').checked, false);
  assert.equal(restored.timers.filter(item => !item.cancelled && item.milliseconds === 30000).length, 0);
  const failClosed = modemFixture({ storageThrows: true });
  assert.equal(failClosed.document.getElementById('mfModemWatch').checked, false);
  assert.equal(failClosed.timers.length, 0);
});

test('R2.5 Modem maps proven LTE report indices, charts RSRP, and retains safe indices', { skip: !parseHTML }, () => {
  const value = modemFixture({ engineer: nestedEngineer });
  const visible = value.document.getElementById('mfModemSummary').textContent;
  for (const expected of ['RSRP-95 dBm · index 45', 'RSRQ-11.5 dB · index 16', 'SINRraw 8', 'RSSIraw 64', 'DL bandwidthraw 5', 'Main RSRP-98 dBm · index 42', 'Diversity RSRP-93 dBm · index 47']) assert.match(visible, new RegExp(expected));
  assert.match(value.document.getElementById('mfSignalNow').textContent, /-95 dBm · 1 sample/);
  assert.notEqual(value.document.getElementById('mfSignalLine').getAttribute('points'), '');
  value.document.getElementById('mfModemCopy').click();
  const report = JSON.parse(value.document.getElementById('mfModemReport').value);
  assert.equal(report.samples[0].rsrp, '-95');
  assert.equal(report.samples[0].rsrpIndex, 45);
  assert.equal(report.samples[0].rsrq, '-11.5');
  assert.equal(report.samples[0].rsrqIndex, 16);
  assert.equal(report.samples[0].sinr, '8');
  assert.equal(report.samples[0].rssi, '64');
  assert.equal(report.samples[0].bandwidth, '5');
  assert.equal(report.samples[0].mainRsrpIndex, 42);
  assert.equal(report.samples[0].diversityRsrqIndex, 19);
});

test('R2.5 radio-term help stays compact, toggles locally, and adds accessible label expansions', { skip: !parseHTML }, () => {
  const diagnostics = diagnosticsFixture({ engineer: nestedEngineer });
  const beforeDiagnosticsCalls = diagnostics.calls.length;
  const diagButton = diagnostics.document.getElementById('mfDiagTerms');
  const diagPanel = diagnostics.document.getElementById('mfDiagTermsPanel');
  assert.equal(diagPanel.hidden, true);
  assert.equal(diagButton.getAttribute('aria-expanded'), 'false');
  diagButton.click();
  assert.equal(diagPanel.hidden, false);
  assert.equal(diagButton.getAttribute('aria-expanded'), 'true');
  assert.match(diagPanel.textContent, /RSRPReference Signal Received Power/);
  assert.equal(diagnostics.calls.length, beforeDiagnosticsCalls);
  const diagRsrp = Array.from(diagnostics.document.querySelectorAll('.mfCommunityValueLabel')).find(node => node.textContent === 'RSRP');
  assert.equal(diagRsrp.getAttribute('title'), 'Reference Signal Received Power');

  const modem = modemFixture({ engineer: nestedEngineer });
  const beforeModemCalls = modem.calls.length;
  const modemButton = modem.document.getElementById('mfModemTerms');
  const modemPanel = modem.document.getElementById('mfModemTermsPanel');
  assert.equal(modemPanel.hidden, true);
  modemButton.click();
  assert.equal(modemPanel.hidden, false);
  assert.match(modemPanel.textContent, /EARFCNE-UTRA Absolute Radio Frequency Channel Number/);
  assert.equal(modem.calls.length, beforeModemCalls);
  const modemRsrp = Array.from(modem.document.querySelectorAll('.mfModemMetricLabel')).find(node => node.textContent === 'RSRP');
  assert.equal(modemRsrp.getAttribute('title'), 'Reference Signal Received Power');
});

test('R2.5 Messages checking is default-on but HTTP stays in-page-only and an explicit opt-out persists', { skip: !parseHTML }, () => {
  const value = smsFixture();
  assert.equal(value.document.getElementById('mfSmsAutoCheck').checked, true);
  assert.equal(value.timers.filter(item => !item.cancelled && item.milliseconds === 60000).length, 1);
  assert.equal(value.permissionCalls, 0);
  assert.match(value.document.getElementById('mfSmsWatchHint').textContent, /system alerts need HTTPS/i);
  const checkbox = value.document.getElementById('mfSmsAutoCheck');
  checkbox.checked = false;
  checkbox.dispatchEvent(new value.window.Event('change'));
  assert.equal(value.storage['mf885.community.r25.sms-watch.v1'], '0');
  assert.equal(value.timers.filter(item => !item.cancelled && item.milliseconds === 60000).length, 0);

  const restored = smsFixture({ storage: { 'mf885.community.r25.sms-watch.v1': '0' } });
  assert.equal(restored.document.getElementById('mfSmsAutoCheck').checked, false);
  assert.equal(restored.timers.filter(item => !item.cancelled && item.milliseconds === 60000).length, 0);
  const failClosed = smsFixture({ storageThrows: true });
  assert.equal(failClosed.document.getElementById('mfSmsAutoCheck').checked, false);
  assert.equal(failClosed.timers.filter(item => !item.cancelled && item.milliseconds === 60000).length, 0);
});

test('R2.5 read-only controllers keep text sinks, fixed endpoints, and no Engineering write path', { skip: !parseHTML }, () => {
  const combined = `${generated.diagnostics}\n${generated.modem}`;
  assert.match(generated.modem, /ENDPOINTS=\['status1','wan','Engineer_parameter'\]/);
  assert.match(generated.diagnostics, /ENDPOINTS=\['status1','wan','Engineer_parameter'\]/);
  assert.doesNotMatch(combined, /method=set|PostXML|setInterval|SEND_USSD|\+CUSD|wlan_cli_scan|Engineering_mode>1/i);
  assert.match(generated.sms, /preference===null\|\|preference==='1'/);
  assert.match(generated.modem, /preference===null\|\|preference==='1'/);
  assert.match(generated.sms, /setItem\(WATCH_KEY,value\?'1':'0'\)/);
  assert.match(generated.modem, /setItem\(WATCH_KEY,value\?'1':'0'\)/);
  assert.match(generated.css, /\.mfRadioTerms\[hidden\] \{ display:none !important; \}/);
  assert.match(generated.css, /\.mfCommunityValues \{[\s\S]*display:grid;[\s\S]*grid-template-columns:repeat\(2,minmax\(0,1fr\)\);/);
  assert.match(generated.css, /\.mfCommunityValue \{ float:none; width:auto; margin:0; \}/);
  assert.match(generated.css, /\.mfHasTerm \{ display:inline-block; width:auto;/);
  assert.match(generated.css, /\.mfHasTerm/);
});
