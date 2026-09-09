/* Community 0.4.7-dev.15: explicit reads and one serialized TTL write. */
(function (w) {
  'use strict';
  var core = w.MF885Community047Dev15, bridge = core && core.ttlBridge;
  var capabilityText = '{"schema":"mf885-ttl-editor/v1","communityVersion":"0.4.7-dev.15","vendorBase":"2.5.94","nativeApi":"r47-revision24-ttl8","settings":["64","off"],"persistence":"ram","bootTtl":64}\n';
  var state = {current: null, locked: true, busy: false, epoch: 0, bound: false};
  function node(id) { return w.document.getElementById(id); }
  function problem(code) { var e = new Error(code); e.mfCode = code; return e; }
  function label(value) { return value === 0 ? 'Off' : String(value); }
  function status(phase, message) {
    node('ttlStatus').textContent = message;
    node('ttlStatus').setAttribute('data-phase', phase);
    node('ttlStatus').classList.toggle('error', ['unknown', 'unavailable', 'changed', 'rejected'].indexOf(phase) >= 0);
  }
  function elements(parent) { return Array.prototype.filter.call(parent && parent.childNodes || [], function (n) { return n.nodeType === 1; }); }
  function plain(parent) { return Array.prototype.every.call(parent && parent.childNodes || [], function (n) { return n.nodeType === 1 || n.nodeType === 3 && !/\S/.test(n.nodeValue); }); }
  function fields(doc) {
    var root = doc && doc.documentElement, models = elements(root), model = models[0], children = elements(model), result = {};
    if (!root || root.nodeName !== 'RGW' || root.attributes.length || models.length !== 1 || model.nodeName !== 'diagnostic' || model.attributes.length || children.length !== 3 || !plain(root) || !plain(model)) throw problem('E_TTL_RESPONSE');
    children.forEach(function (field) {
      var name = field.nodeName;
      if (['command', 'arg', 'output'].indexOf(name) < 0 || Object.prototype.hasOwnProperty.call(result, name) || field.attributes.length || Array.prototype.some.call(field.childNodes, function (n) { return n.nodeType !== 3; })) throw problem('E_TTL_RESPONSE');
      result[name] = field.textContent;
    });
    return result;
  }
  function strictState(doc) {
    var value = fields(doc), match = /^r47:(00[0-9a-f]{6}):([0-9a-f]{2})$/.exec(value.output);
    if (!match || match[0] !== value.output) throw problem('E_TTL_RESPONSE');
    var result = {generation: parseInt(match[1], 16), value: parseInt(match[2], 16)};
    if (result.generation === 0 && result.value !== 64) throw problem('E_TTL_BOOT_STATE');
    return result;
  }
  function same(a, b) { return a.generation === b.generation && a.value === b.value; }
  function nextRevision(value) { return value === 0xffffff ? 1 : value + 1; }
  function check(epoch) { if (epoch !== state.epoch || !bridge.sessionPresent()) throw problem('E_TTL_SESSION'); }
  function capability(owner, epoch) {
    return Promise.resolve().then(function () {
      check(epoch);
      if (core.version !== '0.4.7-dev.15') throw problem('E_TTL_CORE_VERSION');
      return bridge.capability(owner);
    }).then(function (body) {
      check(epoch);
      if (body !== capabilityText) throw problem('E_TTL_COMPATIBILITY');
    });
  }
  function get(owner, epoch) {
    check(epoch);
    return bridge.get(owner).then(function (doc) { check(epoch); return strictState(doc); });
  }
  function render(value) {
    state.current = value;
    node('ttlCurrent').textContent = label(value.value);
    node('ttlReadTime').textContent = 'Last read at ' + new Date().toLocaleTimeString() + '. Read again after a restart or changes in another session.';
    node('ttlCurrentHelp').textContent = value.value === 0 ? 'TTL replacement is off.' : value.value === 64 ? 'TTL replacement is set to 64.' : 'The router reports another value. This editor can apply 64 or Off.';
  }
  function invalidate() {
    state.locked = true;
    node('ttlCurrent').textContent = 'Not confirmed';
    node('ttlCurrentHelp').textContent = 'The current router setting is unknown.';
    node('ttlReadTime').textContent = 'Read the router setting before applying another change.';
  }
  function syncControls() {
    if (!node('ttlRead')) return;
    var signed = !!bridge && bridge.sessionPresent(), busy = state.busy || !bridge || bridge.routerBusy();
    node('ttlRead').disabled = !signed || busy;
    node('ttlMode').disabled = !signed || busy;
    node('ttlApply').disabled = !signed || busy || state.locked || state.current === null;
    node('ttlForm').setAttribute('aria-busy', state.busy ? 'true' : 'false');
  }
  function hint() {
    node('ttlChoiceHint').textContent = node('ttlMode').value === 'off' ? 'Stop replacing TTL. Packets keep their normal TTL behavior along the route.' : 'Set eligible IPv4 packets to TTL 64. Later routers can reduce the value received at the destination.';
  }
  function begin(owner) {
    if (!bridge || !bridge.sessionPresent() || state.busy || !bridge.begin(owner, 'ttlStatus')) return false;
    state.busy = true; syncControls(); return true;
  }
  function end(owner) { state.busy = false; bridge.end(owner); syncControls(); }
  function read() {
    var owner = 'ttl-read', epoch = state.epoch;
    if (!begin(owner)) return Promise.resolve(null);
    status('pending', 'Reading the router setting…');
    return capability(owner, epoch).then(function () { return get(owner, epoch); }).then(function (value) {
      render(value); state.locked = false;
      status('ready', 'Router setting read. Choose a mode, then apply it.'); return value;
    }).catch(function (e) {
      if (epoch === state.epoch) { invalidate(); status('unavailable', 'The setting could not be read. Changes are locked; read again manually. [' + (e.mfCode || 'E_TTL_READ') + ']'); }
      return null;
    }).finally(function () { end(owner); });
  }
  function setValue(value) {
    if (value !== '64' && value !== 'off') { status('rejected', 'Choose 64 or Off. Other values are not available in this version.'); return Promise.resolve(null); }
    if (state.locked || !state.current) { status('unavailable', 'Read the router setting first.'); return Promise.resolve(null); }
    var owner = 'ttl-write', epoch = state.epoch, submitted = false, baseline = null, previous = state.current;
    if (!begin(owner)) return Promise.resolve(null);
    status('pending', 'Checking the setting before applying…');
    return capability(owner, epoch).then(function () { return get(owner, epoch); }).then(function (current) {
      baseline = current;
      if (!same(previous, baseline)) {
        render(baseline); state.locked = true;
        status('changed', 'The setting changed since your last read. Nothing was sent. Read again and review your choice.'); return null;
      }
      render(baseline);
      var wanted = value === 'off' ? 0 : 64;
      if (baseline.value === wanted) { status('ready', 'Already set to ' + label(wanted) + '. No change was sent.'); return baseline; }
      check(epoch); submitted = true; status('pending', 'Applying once, then checking the result…');
      return bridge.post(value, owner).then(function (doc) {
        check(epoch);
        var ackFields = fields(doc), ack = strictState(doc);
        if (ackFields.command !== 'ttl' || ackFields.arg !== value || ack.value !== wanted || ack.generation !== nextRevision(baseline.generation)) throw problem('E_TTL_ACK');
        return get(owner, epoch).then(function (after) {
          if (!same(ack, after)) throw problem('E_TTL_READBACK');
          render(after); state.locked = false;
          status('applied', 'Applied: ' + label(after.value) + '. Confirmed by a separate read. After a restart, TTL returns to 64.'); return after;
        });
      });
    }).catch(function (e) {
      if (epoch === state.epoch) {
        invalidate();
        status(submitted ? 'unknown' : 'unavailable', (submitted ? 'The change may have reached the router, but its result is not confirmed. No retry was sent. Read the setting manually.' : 'The setting could not be checked. No change was sent. Read again manually.') + ' [' + (e.mfCode || 'E_TTL_CHECK') + ']');
      }
      return null;
    }).finally(function () { end(owner); });
  }
  function reset() {
    state.epoch++; state.current = null; state.locked = true;
    node('ttlCurrent').textContent = 'Not read';
    node('ttlReadTime').textContent = 'Read the router setting to unlock Apply.';
    node('ttlCurrentHelp').textContent = 'The current setting is not read automatically.';
    node('ttlMode').value = '64';
    status('unavailable', 'Sign in and read the router setting.'); hint(); syncControls();
  }
  function bind() {
    if (state.bound) return; state.bound = true;
    node('ttlRead').addEventListener('click', read);
    node('ttlMode').addEventListener('change', hint);
    node('ttlForm').addEventListener('submit', function (event) { event.preventDefault(); setValue(node('ttlMode').value); });
    hint(); syncControls();
  }
  w.MF885Community047Dev15TTL = {version: '0.4.7-dev.15', state: state, strictState: strictState, nextRevision: nextRevision, read: read, setValue: setValue, reset: reset, syncControls: syncControls, bind: bind};
  if (w.document.readyState === 'loading') w.document.addEventListener('DOMContentLoaded', bind); else bind();
})(window);
