/* Community 0.4.7-dev.18 theme module.
 *
 * Local browser source asset, not a generated file. release.py theme.py injects
 * it verbatim twice into the head of www\c047d18.html:
 *
 *   1. a small inline copy that runs before the deferred modules and before
 *      first paint, so a saved Dark choice is on <html> without a light flash;
 *   2. the full module copy as js/c047d18theme.js, which owns the selector.
 *
 * The inline copy is generated from this file (see theme.py INLINE_*), so this
 * file stays the single source of truth.
 *
 * Contract:
 *   - choices are exactly System / Light / Dark; the default is System;
 *   - the stored value is validated on read, so a corrupt or hostile
 *     localStorage entry falls back to System instead of an odd attribute;
 *   - localStorage is only touched inside try/catch, so a denied or throwing
 *     storage never breaks boot and never blocks the interface;
 *   - matchMedia is only consulted while the choice is System, so a manual
 *     choice is not overridden by an OS change; the legacy
 *     addListener/removeListener pair is used when addEventListener is absent;
 *   - no network request, no timer and no router call of any kind;
 *   - the OS listener is removed when the choice leaves System; one runtime
 *     remains active before and after login.
 *
 * The resolved theme is written to <html data-theme="light|dark"> and to
 * <html data-theme-choice="system|light|dark">. Nothing else is mutated:
 * authentication, TTL semantics and the favicon/touch assets are untouched.
 */
(function (w) {
  'use strict';
  var KEY = 'mf885-c047d18-theme';
  var CHOICES = ['system', 'light', 'dark'];
  var DARK_QUERY = '(prefers-color-scheme: dark)';

  function root(w) { return w && w.document ? w.document.documentElement : null; }

  function normalize(value) {
    return CHOICES.indexOf(value) >= 0 ? value : 'system';
  }

  function readSaved(w) {
    try {
      var storage = w.localStorage;
      if (!storage || typeof storage.getItem !== 'function') return 'system';
      return normalize(storage.getItem(KEY));
    } catch (error) {
      return 'system';
    }
  }

  function writeSaved(w, choice) {
    try {
      var storage = w.localStorage;
      if (!storage || typeof storage.setItem !== 'function') return false;
      storage.setItem(KEY, choice);
      return true;
    } catch (error) {
      return false;
    }
  }

  function mediaQuery(w) {
    if (!w || typeof w.matchMedia !== 'function') return null;
    try {
      var query = w.matchMedia(DARK_QUERY);
      return query && typeof query.matches === 'boolean' ? query : null;
    } catch (error) {
      return null;
    }
  }

  /* The resolved colour scheme. Light is the safe fallback whenever the OS
     preference is unknown (no matchMedia, a denied/throwing matchMedia, or an
     explicit Light choice). */
  function resolve(w, choice) {
    var wanted = normalize(choice);
    if (wanted === 'dark') return 'dark';
    if (wanted === 'light') return 'light';
    var query = mediaQuery(w);
    return query && query.matches === true ? 'dark' : 'light';
  }

  function paint(w, choice) {
    var html = root(w);
    if (!html) return 'light';
    var wanted = normalize(choice);
    var resolved = resolve(w, wanted);
    html.setAttribute('data-theme-choice', wanted);
    html.setAttribute('data-theme', resolved);
    return resolved;
  }

  function create(w) {
    var choice = 'system';
    var bound = null;
    var boundHandler = null;
    var select = null;
    var loginSelect = null;
    var changeHandler = null;

    function matches() {
      var query = mediaQuery(w);
      return !!(query && query.matches === true);
    }

    function unbind() {
      if (!bound || !boundHandler) { bound = null; boundHandler = null; return; }
      try {
        if (typeof bound.removeEventListener === 'function') bound.removeEventListener('change', boundHandler);
        else if (typeof bound.removeListener === 'function') bound.removeListener(boundHandler);
      } catch (error) { /* a broken media query must not break the interface */ }
      bound = null; boundHandler = null;
    }

    /* Only a System choice follows the OS. A manual choice never subscribes. */
    function bind() {
      unbind();
      if (choice !== 'system') return;
      var query = mediaQuery(w);
      if (!query) return;
      var handler = function () { if (choice === 'system') paint(w, 'system'); };
      try {
        if (typeof query.addEventListener === 'function') query.addEventListener('change', handler);
        else if (typeof query.addListener === 'function') query.addListener(handler);
        else return;
      } catch (error) {
        return;
      }
      bound = query; boundHandler = handler;
    }

    /* The signed-in and pre-login selectors always show the same choice. */
    function syncSelect() {
      if (select && select.value !== choice) select.value = choice;
      if (loginSelect && loginSelect.value !== choice) loginSelect.value = choice;
    }

    function apply(next, persist) {
      choice = normalize(next === undefined || next === null ? 'system' : String(next));
      if (persist) writeSaved(w, choice);
      paint(w, choice);
      bind();
      syncSelect();
      return choice;
    }

    /* Build the compact selector. It is a native <select>, so keyboard
       operation, focus and screen-reader naming come from the platform. */
    function buildSelect(doc) {
      var picker = doc.createElement('div');
      picker.className = 'theme-picker';
      var label = doc.createElement('label');
      label.className = 'theme-picker-label';
      label.setAttribute('for', 'themeChoice');
      label.textContent = 'Theme';
      var selectNode = doc.createElement('select');
      selectNode.setAttribute('id', 'themeChoice');
      selectNode.setAttribute('aria-label', 'Colour theme');
      [['system', 'System'], ['light', 'Light'], ['dark', 'Dark']].forEach(function (pair) {
        var option = doc.createElement('option');
        option.setAttribute('value', pair[0]);
        option.textContent = pair[1];
        selectNode.appendChild(option);
      });
      picker.appendChild(label);
      picker.appendChild(selectNode);
      return { picker: picker, select: selectNode, label: label };
    }

    /* Idempotent: mount() may run before and after sign-in; only one selector
       is ever present in the document. */
    function mount() {
      var doc = w && w.document;
      if (!doc) return null;
      var existing = doc.getElementById('themeChoice');
      if (existing) {
        select = existing;
        syncSelect();
        return existing;
      }
      var built = buildSelect(doc);
      select = built.select;
      var app = doc.getElementById('app');
      var host = app && app.querySelector('header') || app || doc.body;
      if (!host) return null;
      host.insertBefore(built.picker, host.firstChild);
      changeHandler = function () { apply(select.value, true); };
      select.addEventListener('change', changeHandler);
      syncSelect();
      return select;
    }

    /* Pre-login: the login card keeps its own compact selector so the choice is
       visible and usable before authentication. */
    function mountLogin() {
      var doc = w && w.document;
      if (!doc) return null;
      var card = doc.getElementById('loginForm');
      if (!card || doc.getElementById('themeChoiceLogin')) return null;
      var built = buildSelect(doc);
      built.select.setAttribute('id', 'themeChoiceLogin');
      built.label.setAttribute('for', 'themeChoiceLogin');
      var anchor = doc.getElementById('loginStatus');
      if (anchor && anchor.parentNode === card) card.insertBefore(built.picker, anchor);
      else card.appendChild(built.picker);
      loginSelect = built.select;
      built.select.value = choice;
      built.select.addEventListener('change', function () { apply(built.select.value, true); });
      return built.select;
    }

    function init() {
      apply(readSaved(w), false);
      mountLogin();
      mount();
      return choice;
    }

    function reset() {
      /* Theme belongs to the browser, independently of router login state. */
      syncSelect();
      return choice;
    }

    return {
      key: KEY,
      choices: CHOICES.slice(),
      init: init,
      mount: mount,
      mountLogin: mountLogin,
      apply: apply,
      reset: reset,
      current: function () { return choice; },
      resolved: function () { return resolve(w, choice); },
      matches: matches,
      unbind: unbind,
      select: function () { return select; }
    };
  }

  var api = {
    key: KEY,
    choices: CHOICES.slice(),
    normalize: normalize,
    readSaved: readSaved,
    writeSaved: writeSaved,
    resolve: resolve,
    create: create
  };
  w.MF885Community047Dev18Theme = api;
  /* This deferred asset owns its startup; no authentication hook is needed. */
  if (!w.MF885ThemeRuntime) {
    w.MF885ThemeRuntime = create(w);
    w.MF885ThemeRuntime.init();
  }
})(window);
