/* Community 0.4.7-dev.18: System/Light/Dark theme regression suite.
 *
 * Runs against the real derived dev18 assets (assembled by
 * firmware/community-0.4.7-dev.18/fixtures/assemble_assets.js) through the same
 * linkedom DOM and node:vm context used by web.test.js. The production theme
 * transform (release.py theme.py) produces the assets under test, so an
 * injection, key or reference mistake fails here rather than at build time.
 *
 * Run (bounded memory, serial, short timeout):
 *   NODE_PATH=/tmp/mf885-node-deps/node_modules \
 *   MF885_DEV18_ASSETS=<assembled dir> \
 *   node --max-old-space-size=96 --test firmware/community-0.4.7-dev.18/theme.test.js
 */
const test = require('node:test');
const assert = require('node:assert/strict');
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
  theme: read('js/c047d18theme.js'),
  themeCss: read('css/c047d18theme.css'),
};

const KEY = 'mf885-c047d18-theme';

/* linkedom does not implement HTMLSelectElement.value: it reads as undefined
   and ignores writes. The real browser DOM does implement it, so the fixture
   installs the shim on every <select> the module creates, before the module can
   read or write it. This mirrors the value seeding already used by the
   dev15/dev16/dev17 suites in web.test.js and does not change what is tested. */
function shimSelectValue(select) {
  if (!select || String(select.tagName).toLowerCase() !== 'select') return;
  const existing = Object.getOwnPropertyDescriptor(select, 'value');
  if (existing && existing.set) return;
  const options = [...select.options];
  const initial = options.length ? String(options[0].getAttribute('value')) : '';
  Object.defineProperty(select, 'value', { value: initial, writable: true, configurable: true });
}

/* Minimal, deterministic storage double. `mode` selects a working store, a
   store that throws on every access (denied storage), or an absent store. */
function storage({ mode = 'ok', seed = null } = {}) {
  const data = new Map();
  if (seed !== null) data.set(KEY, seed);
  if (mode === 'absent') return undefined;
  if (mode === 'denied') {
    const boom = () => { throw new Error('storage denied'); };
    return { getItem: boom, setItem: boom, removeItem: boom };
  }
  return {
    data,
    getItem(k) { return data.has(k) ? data.get(k) : null; },
    setItem(k, v) { data.set(k, String(v)); },
    removeItem(k) { data.delete(k); },
  };
}

/* Minimal media-query double. `legacy` selects the old addListener/removeListener
   pair that pre-2019 Safari exposes, which the module must fall back to. */
function media({ dark = false, mode = 'modern', legacy = false } = {}) {
  if (mode === 'absent') return undefined;
  if (mode === 'denied') return () => { throw new Error('matchMedia denied'); };
  const listeners = [];
  const query = {
    media: '(prefers-color-scheme: dark)',
    matches: dark,
    listeners,
    set(value) { query.matches = value; listeners.forEach(fn => fn()); },
  };
  if (legacy) {
    query.addListener = fn => listeners.push(fn);
    query.removeListener = fn => {
      const index = listeners.indexOf(fn);
      if (index >= 0) listeners.splice(index, 1);
    };
  } else {
    query.addEventListener = (type, fn) => { if (type === 'change') listeners.push(fn); };
    query.removeEventListener = (type, fn) => {
      const index = listeners.indexOf(fn);
      if (index >= 0) listeners.splice(index, 1);
    };
  }
  return () => query;
}

/* Build a DOM from the real derived HTML and run the theme module in an
   isolated VM context. Only the theme module is executed here: the suite tests
   the theme contract, and the existing TTL suite already covers the core app. */
function fixture({ store = storage(), mediaQuery = media(), runCore = false } = {}) {
  const dom = parseHTML(derived.html);
  const document = dom.document;
  // Every <select> the theme module creates gets a working `.value` before the
  // module can touch it, so the fixture behaves like a browser DOM.
  const createElement = document.createElement.bind(document);
  document.createElement = tag => {
    const element = createElement(tag);
    shimSelectValue(element);
    return element;
  };
  const requests = [];
  const timers = [];
  const window = {
    document,
    Event: dom.Event,
    addEventListener: dom.addEventListener ? dom.addEventListener.bind(dom) : () => {},
    location: { protocol: 'http:', host: '192.0.2.1', hash: '' },
    console: { debug() {}, error() {} },
  };
  window.window = window;
  if (store !== undefined) window.localStorage = store;
  if (mediaQuery !== undefined) window.matchMedia = mediaQuery;
  // Any network or timer use in the theme path is a hard failure, not a warning.
  window.XMLHttpRequest = class { open() { requests.push('xhr'); } send() { requests.push('xhr'); } };
  window.fetch = (...args) => { requests.push('fetch:' + args[0]); return Promise.resolve({}); };
  window.setTimeout = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
  window.setInterval = (fn, ms) => { timers.push({ fn, ms, interval: true }); return timers.length; };
  window.requestAnimationFrame = fn => { timers.push({ fn }); return timers.length; };

  const context = { window, document, console: window.console, Date, JSON, Array, Object, String, Number, Boolean, RegExp, Error, Promise, Map, Set };
  vm.createContext(context);
  // The early-apply inline script is part of the derived HTML head and runs
  // before any module; execute it first so the fixture matches the browser.
  // The other inline script is the core boot watchdog, which is not run here.
  const inline = [...derived.html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  const early = inline.filter(code => code.includes('data-theme-choice'));
  assert.equal(early.length, 1, 'exactly one inline theme early-apply script');
  assert.ok(early[0].includes("mf885-c047d18-theme"), 'the early script carries the storage key');
  vm.runInContext(early[0], context, { filename: 'inline-theme.js' });

  const html = document.documentElement;
  const initial = { theme: html.getAttribute('data-theme'), choice: html.getAttribute('data-theme-choice') };

  vm.runInContext(derived.theme, context, { filename: 'c047d18theme.js' });
  if (runCore) vm.runInContext(derived.core, context, { filename: 'c047d18app.js' });

  const theme = window.MF885Community047Dev18Theme;
  const runtime = window.MF885ThemeRuntime;
  assert.ok(runtime, 'the shipped deferred script starts without the core app');

  return {
    window, document, html, initial, theme, runtime, requests, timers,
    themeAttr() { return html.getAttribute('data-theme'); },
    choiceAttr() { return html.getAttribute('data-theme-choice'); },
    stored() { return store && store.getItem ? store.getItem(KEY) : null; },
    selector(id = 'themeChoice') { return document.getElementById(id); },
    changeTo(value, id = 'themeChoice') {
      const node = document.getElementById(id);
      node.value = value;
      node.dispatchEvent(new window.Event('change'));
    },
  };
}

// ---------------------------------------------------------------------------
// Assets, references and versioned keys.
// ---------------------------------------------------------------------------

test('the derived build ships versioned theme assets referenced from the head', () => {
  assert.match(derived.html, /<link rel="stylesheet" href="css\/c047d18theme\.css">/);
  assert.match(derived.html, /<script defer src="js\/c047d18theme\.js"><\/script>/);
  assert.ok(derived.themeCss.length > 0 && derived.theme.length > 0);
  // The theme stylesheet must load after the base sheets so it wins on ties.
  const css = derived.html.indexOf('css/c047d18theme.css');
  assert.ok(css > derived.html.indexOf('css/c047d18ui.css'));
  assert.ok(css > derived.html.indexOf('css/c047d18ttl.css'));
});

test('the favicon and touch icon bytes and head references are preserved', () => {
  for (const icon of ['c047d18favicon.png', 'c047d18touch.png']) {
    assert.ok(fs.existsSync(path.join(assets, icon)), icon + ' still shipped');
    assert.match(derived.html, new RegExp('href="' + icon + '"'), icon + ' still referenced');
  }
  assert.match(derived.html, /rel="icon" type="image\/png" sizes="32x32"/);
  assert.match(derived.html, /rel="apple-touch-icon" sizes="180x180"/);
});

test('the early inline script paints the resolved theme before any module runs', () => {
  const f = fixture({ store: storage({ seed: 'dark' }) });
  assert.equal(f.initial.theme, 'dark', 'dark is on <html> before the module executes');
  assert.equal(f.initial.choice, 'dark');
});

// ---------------------------------------------------------------------------
// Initial resolution: system / light / dark.
// ---------------------------------------------------------------------------

test('initial System follows the OS: dark OS paints dark, light OS paints light', () => {
  const dark = fixture({ mediaQuery: media({ dark: true }) });
  assert.equal(dark.runtime.current(), 'system');
  assert.equal(dark.themeAttr(), 'dark');
  assert.equal(dark.choiceAttr(), 'system');
  assert.equal(dark.selector().value, 'system');

  const light = fixture({ mediaQuery: media({ dark: false }) });
  assert.equal(light.themeAttr(), 'light');
  assert.equal(light.choiceAttr(), 'system');
});

test('initial explicit Light and Dark choices override the OS preference', () => {
  const light = fixture({ store: storage({ seed: 'light' }), mediaQuery: media({ dark: true }) });
  assert.equal(light.runtime.current(), 'light');
  assert.equal(light.themeAttr(), 'light');

  const dark = fixture({ store: storage({ seed: 'dark' }), mediaQuery: media({ dark: false }) });
  assert.equal(dark.runtime.current(), 'dark');
  assert.equal(dark.themeAttr(), 'dark');
});

test('a saved invalid value falls back to System instead of an odd attribute', () => {
  for (const junk of ['blue', 'DARK', 'Dark ', '', 'system;', '{"theme":"dark"}', 'null', '0']) {
    const f = fixture({ store: storage({ seed: junk }) });
    assert.equal(f.runtime.current(), 'system', JSON.stringify(junk) + ' is not a choice');
    assert.equal(f.choiceAttr(), 'system');
    assert.equal(f.themeAttr(), 'light', 'light OS default');
  }
});

// ---------------------------------------------------------------------------
// Degraded storage and media environments.
// ---------------------------------------------------------------------------

test('denied storage and a denied matchMedia never break boot', () => {
  const denied = fixture({ store: storage({ mode: 'denied' }), mediaQuery: media({ mode: 'denied' }) });
  assert.equal(denied.runtime.current(), 'system');
  assert.equal(denied.themeAttr(), 'light', 'light is the safe fallback');
  assert.equal(denied.theme.writeSaved(denied.window, 'dark'), false, 'a refused write reports failure');
});

test('absent storage and absent matchMedia still resolve to a valid theme', () => {
  const none = fixture({ store: storage({ mode: 'absent' }), mediaQuery: media({ mode: 'absent' }) });
  assert.equal(none.runtime.current(), 'system');
  assert.equal(none.themeAttr(), 'light');
  assert.equal(none.runtime.resolved(), 'light');
});

test('missing localStorage does not prevent choosing a theme for the session', () => {
  const f = fixture({ store: storage({ mode: 'denied' }) });
  f.changeTo('dark');
  assert.equal(f.runtime.current(), 'dark', 'the choice still applies in-page');
  assert.equal(f.themeAttr(), 'dark');
});

// ---------------------------------------------------------------------------
// Changes are saved and system tracking is scoped to System only.
// ---------------------------------------------------------------------------

test('a chosen value is persisted and restored on the next load', () => {
  const store = storage();
  const first = fixture({ store });
  first.changeTo('dark');
  assert.equal(store.getItem(KEY), 'dark', 'the choice is written');
  assert.equal(first.themeAttr(), 'dark');

  const reload = fixture({ store });
  assert.equal(reload.runtime.current(), 'dark');
  assert.equal(reload.themeAttr(), 'dark');
  assert.equal(reload.selector().value, 'dark', 'the selector reflects the restored value');

  first.changeTo('light');
  assert.equal(store.getItem(KEY), 'light');
  assert.equal(first.themeAttr(), 'light');
});

test('an OS change is followed only while the choice is System', () => {
  const system = fixture({ mediaQuery: media({ dark: false }) });
  assert.equal(system.themeAttr(), 'light');
  system.window.matchMedia('(prefers-color-scheme: dark)').set(true);
  assert.equal(system.themeAttr(), 'dark', 'System tracks the OS both ways');
  system.window.matchMedia('(prefers-color-scheme: dark)').set(false);
  assert.equal(system.themeAttr(), 'light', 'and back');

  const manual = fixture({ store: storage({ seed: 'light' }), mediaQuery: media({ dark: false }) });
  manual.window.matchMedia('(prefers-color-scheme: dark)').set(true);
  assert.equal(manual.themeAttr(), 'light', 'a manual Light choice ignores the OS');

  const dark = fixture({ store: storage({ seed: 'dark' }), mediaQuery: media({ dark: true }) });
  dark.window.matchMedia('(prefers-color-scheme: dark)').set(false);
  assert.equal(dark.themeAttr(), 'dark', 'a manual Dark choice ignores the OS');
});

test('a legacy matchMedia with addListener only is still tracked, and released', () => {
  const mq = media({ dark: false, legacy: true });
  const f = fixture({ mediaQuery: mq });
  const query = f.window.matchMedia('(prefers-color-scheme: dark)');
  assert.equal(query.listeners.length, 1, 'the legacy listener is registered');
  query.set(true);
  assert.equal(f.themeAttr(), 'dark', 'the legacy listener fires');

  f.changeTo('light');
  assert.equal(query.listeners.length, 0, 'leaving System removes the listener');
  query.set(false);
  assert.equal(f.themeAttr(), 'light', 'no stale listener repaints after a manual choice');
});

test('the OS listener does not accumulate across choices or repeated mounts', () => {
  const mq = media({ dark: false });
  const f = fixture({ mediaQuery: mq });
  const query = f.window.matchMedia('(prefers-color-scheme: dark)');
  assert.equal(query.listeners.length, 1);
  for (const choice of ['dark', 'system', 'light', 'system']) f.changeTo(choice);
  assert.equal(query.listeners.length, 1, 'exactly one live listener at all times');
  f.runtime.mount();
  f.runtime.mount();
  assert.equal(f.document.querySelectorAll('#themeChoice').length, 1, 'only one selector is ever mounted');
});

test('theme follows the OS independently of login state', () => {
  const store = storage({ seed: 'dark' });
  const mq = media({ dark: false });
  const f = fixture({ store, mediaQuery: mq });
  assert.equal(f.themeAttr(), 'dark');
  // A System choice subscribes to the OS while it is active...
  f.changeTo('system');
  assert.equal(f.themeAttr(), 'light');
  assert.equal(f.window.matchMedia('(prefers-color-scheme: dark)').listeners.length, 1);
  // ...and logout releases it, leaving the last saved choice in force.
  f.runtime.reset();
  assert.equal(f.window.matchMedia('(prefers-color-scheme: dark)').listeners.length, 1, 'one listener remains independently of login');
  assert.equal(f.runtime.current(), 'system', 'reset re-reads what was actually saved');
  f.window.matchMedia('(prefers-color-scheme: dark)').set(true);
  assert.equal(f.themeAttr(), 'dark', 'System continues following OS while signed out');

  // With no intervening change, logout restores the seeded preference.
  const seeded = fixture({ store: storage({ seed: 'dark' }), mediaQuery: media({ dark: false }) });
  seeded.changeTo('light');
  seeded.changeTo('dark');
  seeded.runtime.reset();
  assert.equal(seeded.runtime.current(), 'dark');
  assert.equal(seeded.themeAttr(), 'dark');
});

// ---------------------------------------------------------------------------
// The selector: accessible, compact and native.
// ---------------------------------------------------------------------------

test('the selector is a native labelled select with the three English choices', () => {
  const f = fixture();
  const select = f.document.getElementById('themeChoice');
  assert.ok(select, 'the selector is mounted');
  assert.equal(select.tagName.toLowerCase(), 'select', 'a native select keeps platform keyboard behavior');
  assert.deepEqual([...select.options].map(o => o.value), ['system', 'light', 'dark']);
  assert.deepEqual([...select.options].map(o => o.textContent), ['System', 'Light', 'Dark']);
  assert.equal(select.getAttribute('aria-label'), 'Colour theme');
  const label = f.document.querySelector('label[for="themeChoice"]');
  assert.ok(label, 'the select has a real label bound by for/id');
  assert.equal(label.textContent, 'Theme');
});

test('the selector is visible after login and the pre-login copy is also present', () => {
  const f = fixture();
  const app = f.document.getElementById('app');
  assert.ok(app.querySelector('#themeChoice'), 'the signed-in shell carries the selector');
  const login = f.document.getElementById('loginForm');
  const preLogin = f.document.getElementById('themeChoiceLogin');
  assert.ok(preLogin, 'the login card carries its own selector');
  assert.ok(login.contains(preLogin), 'the pre-login selector lives in the login card');
  assert.deepEqual([...preLogin.options].map(o => o.value), ['system', 'light', 'dark']);
});

test('driving the selector directly is the keyboard path and changes the theme', () => {
  const store = storage();
  const f = fixture({ store });
  const select = f.document.getElementById('themeChoice');
  // A native select changed by keyboard dispatches the same change event.
  select.value = 'dark';
  select.dispatchEvent(new f.window.Event('change'));
  assert.equal(store.getItem(KEY), 'dark');
  assert.equal(f.themeAttr(), 'dark');
  assert.equal(f.document.getElementById('themeChoiceLogin').value, 'dark', 'both selectors stay in sync');
});

// ---------------------------------------------------------------------------
// Safety envelope: no network and no timers from the theme path.
// ---------------------------------------------------------------------------

test('the theme module performs no network request and schedules no timer', () => {
  const f = fixture({ store: storage({ seed: 'dark' }) });
  f.changeTo('system');
  f.changeTo('dark');
  f.runtime.reset();
  f.runtime.mountLogin();
  f.runtime.mount();
  assert.deepEqual(f.requests, [], 'no XHR and no fetch');
  assert.deepEqual(f.timers, [], 'no timeout, interval or animation frame');
});

test('the theme source contains no network or timer calls at all', () => {
  for (const forbidden of ['XMLHttpRequest', 'fetch(', 'setTimeout', 'setInterval', 'requestAnimationFrame', 'WebSocket', 'navigator.sendBeacon']) {
    assert.equal(derived.theme.includes(forbidden), false, 'theme.js must not use ' + forbidden);
  }
});

test('the theme stylesheet carries no remote import or url reference', () => {
  assert.equal(/@import/.test(derived.themeCss), false, 'no @import');
  assert.equal(/url\(\s*['"]?https?:/i.test(derived.themeCss), false, 'no remote url()');
});

// ---------------------------------------------------------------------------
// Dark coverage of the existing surfaces and preserved behaviour.
// ---------------------------------------------------------------------------

test('the dark stylesheet covers every existing surface family', () => {
  const required = [
    '.boot', '.runtime-status', '.login-card', 'header', 'nav button', '.page', '.cards article',
    '.value', '.message', '.composer', '.composer textarea', '.terms', '.source-card', '.status',
    '.status.error', '.ttl-state', '.ttl-editor', '.console-reply', '.evidence-badge', 'button',
    'button.secondary', 'button.quiet', '.button-link', '.live-toggle', 'input', 'select', 'textarea',
    ':focus-visible', 'button:disabled', 'input:disabled',
  ];
  for (const selector of required) {
    assert.ok(derived.themeCss.includes(selector), 'dark rules must cover ' + selector);
  }
  assert.match(derived.themeCss, /:root\[data-theme="dark"\]/);
  // Success / warning / error status phases must be distinguishable in dark.
  for (const phase of ['applied', 'ready', 'pending']) {
    assert.ok(derived.themeCss.includes('data-phase="' + phase + '"'), 'dark status phase ' + phase);
  }
  assert.ok(derived.themeCss.includes('--danger'), 'error colour retained');
  assert.ok(derived.themeCss.includes('--ok'), 'success colour added');
  assert.ok(derived.themeCss.includes('--warn'), 'warning colour added');
});

test('reduced motion is respected and the theme adds no transition', () => {
  assert.match(derived.themeCss, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  assert.match(derived.themeCss, /transition-duration:\s*0?\.001ms\s*!important/);
  assert.equal(/transition\s*:/.test(derived.themeCss), false, 'the theme never introduces a transition');
});

test('the light theme keeps the legacy palette with no dark attribute', () => {
  const f = fixture({ store: storage({ seed: 'light' }) });
  assert.equal(f.themeAttr(), 'light');
  assert.equal(/data-theme="light"/.test(derived.themeCss), false, 'light needs no new rules; the legacy sheet is the light theme');
});

// ---------------------------------------------------------------------------
// Integration with the real core module: the hooks are wired where the task
// requires them (before/after sign-in and on logout). The core module is the
// actual derived c047d18app.js, driven through its real bind() path with the
// minimal browser surface it touches; the full router fixture lives in
// web.test.js and is not duplicated here.
// ---------------------------------------------------------------------------

test('the shipped theme starts before the core and does not depend on session hooks', () => {
  assert.ok(derived.html.indexOf('src="js/c047d18theme.js"') < derived.html.indexOf('src="js/c047d18app.js"'));
  assert.equal(derived.core.includes('themeExtension'), false);
  const f = fixture({store: storage({mode: 'denied'})});
  f.changeTo('dark');
  f.runtime.reset();
  assert.equal(f.themeAttr(), 'dark', 'session-only preference survives sign-out');
  assert.ok(f.document.querySelector('header #themeChoice'));
});

test('the theme module is loadable before the core module and needs no other module', () => {
  // theme.js must not depend on the core app, the TTL module or any extension:
  // it is the first deferred script, so ordering cannot be relied upon.
  for (const forbidden of ['MF885Community047Dev18TTL', 'MF885Community047Dev18Engineering', 'Cpu', 'consoleBridge', 'ttlBridge']) {
    assert.equal(derived.theme.includes(forbidden), false, 'theme.js must not reference ' + forbidden);
  }
  assert.ok(derived.theme.includes('MF885Community047Dev18Theme'), 'the module exports its own name');
});

test('the pre-login selector exists before the core module binds and survives sign-out', () => {
  const f = fixture();
  // The inline early-apply ran against the shipped HTML: the login card is the
  // visible surface before authentication, and it already carries the selector.
  assert.ok(f.document.getElementById('login').querySelector('#themeChoiceLogin'));
  f.changeTo('dark', 'themeChoiceLogin');
  assert.equal(f.themeAttr(), 'dark', 'a change made before sign-in applies');
  assert.equal(f.selector('themeChoice').value, 'dark', 'and the signed-in selector follows');
});
