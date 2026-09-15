/* MF885 Community 0.4.7-dev.18 - private CPU load codec and interval tracker.
 *
 * Standalone, dependency-free and side-effect-free: it decodes the native
 * cpu2: wire frame and derives a CPU load percentage from two retained samples.
 * It never touches the DOM, XHR, timers or the router. The app integration in
 * release.py binds it to one sequential GET inside the existing snapshot lock.
 *
 * Wire (native cpu.h, version 1, exactly 85 visible characters):
 *   "cpu2:" + 80 lowercase hex chars = 10 little-endian u32 fields, in order
 *   version, flags, epoch, frequency_hz, total_low, total_high, idle_low,
 *   idle_high, read_errors, transitions.
 *
 * Flags: warming=1, valid=2, unavailable=4. The uninitialized native state
 * serializes as warming|unavailable (5) and MUST be treated as unavailable.
 *
 * Counter pairs are combined with exact integer arithmetic (BigInt) BEFORE any
 * Number conversion, so a cumulative counter above 2^53 is never rounded.
 * This module is unqualified: no hardware timing was measured here.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module && module.exports) module.exports = api;
  if (root) root.MF885Dev17Cpu = api;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function () {
  'use strict';

  var WIRE_RE = /^cpu2:[0-9a-f]{80}$/;
  var VERSION = 1;
  var FREQUENCY_MODE1_HZ = 32768;
  var FLAG_WARMING = 1, FLAG_VALID = 2, FLAG_UNAVAILABLE = 4, FLAG_KNOWN = 7;
  var U32_MAX = 0xffffffff;
  var MAX_INTERVAL_SECONDS = 600;      // reject absurd / stalled sampling gaps
  var MIN_INTERVAL_SECONDS = 1;        // avoid noisy subsecond UI intervals
  var DEFAULT_MAX_DELTA = 0x80000000;  // matches the native continuity bound

  function fail(code, message) {
    var error = new Error(message);
    error.mfCode = code;
    throw error;
  }

  function combine(low, high) {
    // Exact: build the 64-bit value in BigInt before any Number conversion.
    return (BigInt(high >>> 0) << 32n) | BigInt(low >>> 0);
  }

  function decodeWire(wire) {
    if (typeof wire !== 'string' || !WIRE_RE.test(wire)) {
      fail('E_CPU_WIRE', 'The CPU frame is not a valid cpu2: record.');
    }
    var words = [];
    for (var i = 0; i < 10; i++) {
      var at = 5 + i * 8;
      // Decode four little-endian bytes, independently checked against native output.
      var word=0;for(var byte=0;byte<4;byte++)word|=parseInt(wire.slice(at+2*byte,at+2*byte+2),16)<<(8*byte);
      words.push(word>>>0);
    }
    return {
      version: words[0], flags: words[1], epoch: words[2], frequencyHz: words[3],
      totalLow: words[4], totalHigh: words[5], idleLow: words[6], idleHigh: words[7],
      readErrors: words[8], transitions: words[9]
    };
  }

  function classify(frame) {
    var flags = frame.flags;
    // Reject unknown bits and contradictory combinations outright.
    if (flags & ~FLAG_KNOWN) fail('E_CPU_FLAGS', 'Unknown CPU flag bits.');
    if (flags === 0) fail('E_CPU_FLAGS', 'A CPU frame must declare a state.');
    var warming = !!(flags & FLAG_WARMING), valid = !!(flags & FLAG_VALID),
      unavailable = !!(flags & FLAG_UNAVAILABLE);
    // warming|valid and valid|unavailable are contradictions; warming|unavailable
    // (5) is the native "uninitialized" encoding and is a normal unavailable.
    if (warming && valid) fail('E_CPU_FLAGS', 'Contradictory warming+valid flags.');
    if (valid && unavailable) fail('E_CPU_FLAGS', 'Contradictory valid+unavailable flags.');
    if (unavailable) return 'unavailable';
    if (valid) return 'valid';
    return 'warming';
  }

  /* Decode and validate one complete frame. Throws on any malformed value so a
   * caller never renders a made-up percentage. */
  function parseFrame(wire, options) {
    options = options || {};
    var maxDelta = options.maxDelta === undefined ? DEFAULT_MAX_DELTA : options.maxDelta;
    var frame = decodeWire(wire);
    if (frame.version !== VERSION) fail('E_CPU_VERSION', 'Unsupported CPU frame version.');
    var state = classify(frame);
    var total = combine(frame.totalLow, frame.totalHigh);
    var idle = combine(frame.idleLow, frame.idleHigh);
    if (state === 'valid' || state === 'warming') {
      if (frame.frequencyHz !== FREQUENCY_MODE1_HZ) {
        fail('E_CPU_FREQUENCY', 'Unexpected CPU counter frequency.');
      }
    }
    if (state === 'valid') {
      if (frame.epoch === 0) fail('E_CPU_EPOCH', 'A valid CPU frame needs an epoch.');
      if (total === 0n) fail('E_CPU_TOTAL', 'A valid CPU frame needs elapsed ticks.');
    }
    if (idle > total) fail('E_CPU_TOTAL', 'Idle ticks cannot exceed total ticks.');
    return {
      wire: wire, version: frame.version, flags: frame.flags, state: state,
      epoch: frame.epoch >>> 0, frequencyHz: frame.frequencyHz >>> 0,
      total: total, idle: idle, readErrors: frame.readErrors >>> 0,
      transitions: frame.transitions >>> 0
    };
  }

  function createTracker(options) {
    options = options || {};
    var maxDelta = options.maxDelta === undefined ? DEFAULT_MAX_DELTA : options.maxDelta;
    var minSeconds = options.minIntervalSeconds === undefined ? MIN_INTERVAL_SECONDS : options.minIntervalSeconds;
    var maxSeconds = options.maxIntervalSeconds === undefined ? MAX_INTERVAL_SECONDS : options.maxIntervalSeconds;
    var baseline = null, rendered = null, baselineAt = null;
    var clock = options.now || Date.now;

    function reset() { baseline = null; rendered = null; baselineAt = null; }

    /* Accept one frame. Returns a snapshot describing what the UI may show.
     * Any malformed frame, unavailable state, read failure (null/undefined) or
     * epoch restart clears the baseline and the rendered value: a stale
     * percentage is never relabelled live. */
    function observe(wire) {
      var frame, now=clock();
      if(!Number.isFinite(now)){reset();return {state:"unavailable",percentage:null,reason:"E_CPU_CLOCK"};}
      try {
        if (wire === null || wire === undefined) fail('E_CPU_UNAVAILABLE', 'No CPU frame was read.');
        frame = parseFrame(wire, { maxDelta: maxDelta });
      } catch (error) {
        reset();
        return { state: 'unavailable', percentage: null, intervalSeconds: null, reason: (error && error.mfCode) || 'E_CPU_WIRE', error: error };
      }
      if (frame.state === 'unavailable') {
        reset();
        return { state: 'unavailable', percentage: null, intervalSeconds: null, reason: 'E_CPU_UNAVAILABLE', epoch: frame.epoch };
      }
      if (frame.state === 'warming') {
        // A new epoch always starts warming: keep it as the baseline only.
        baseline = frame; baselineAt = now; rendered = null;
        return { state: 'warming', percentage: null, intervalSeconds: null, epoch: frame.epoch, readErrors: frame.readErrors };
      }
      if (!baseline || baseline.epoch !== frame.epoch) {
        baseline = frame; baselineAt = now; rendered = null;
        return { state: 'warming', percentage: null, intervalSeconds: null, epoch: frame.epoch, readErrors: frame.readErrors };
      }
      if(now<baselineAt || now-baselineAt>maxSeconds*1000) {
        reset();return {state:'unavailable',percentage:null,intervalSeconds:null,reason:'E_CPU_STALE'};
      }
      // A changed error counter invalidates the interval even if the
      // counters still look monotonic.
      if (frame.readErrors !== baseline.readErrors) {
        baseline = frame; baselineAt = now; rendered = null;
        return { state: 'warming', percentage: null, intervalSeconds: null, reason: 'E_CPU_ERRORS', epoch: frame.epoch, readErrors: frame.readErrors };
      }
      var deltaTotal = frame.total - baseline.total;
      var deltaIdle = frame.idle - baseline.idle;
      if (deltaTotal <= 0n || deltaIdle < 0n || deltaIdle > deltaTotal) {
        reset();
        return { state: 'unavailable', percentage: null, intervalSeconds: null, reason: 'E_CPU_DELTA', epoch: frame.epoch };
      }
      if (deltaTotal >= BigInt(maxDelta)) {
        reset();
        return { state: 'unavailable', percentage: null, intervalSeconds: null, reason: 'E_CPU_CONTINUITY', epoch: frame.epoch };
      }
      var intervalSeconds = Number(deltaTotal) / FREQUENCY_MODE1_HZ;
      if (!isFinite(intervalSeconds) || intervalSeconds < minSeconds || intervalSeconds > maxSeconds) {
        // Too short to be meaningful or too long to be called live.
        reset();
        return { state: 'unavailable', percentage: null, intervalSeconds: null, reason: 'E_CPU_INTERVAL', epoch: frame.epoch };
      }
      var busy = deltaTotal - deltaIdle;
      var percentage = 100 * Number(busy) / Number(deltaTotal);
      if (!isFinite(percentage) || percentage < 0 || percentage > 100) {
        reset();
        return { state: 'unavailable', percentage: null, intervalSeconds: null, reason: 'E_CPU_RATIO', epoch: frame.epoch };
      }
      baseline = frame; baselineAt = now;
      rendered = {
        state: 'valid', percentage: Math.round(percentage * 10) / 10,
        intervalSeconds: Math.round(intervalSeconds * 10) / 10,
        epoch: frame.epoch, readErrors: frame.readErrors,
        capturedAt: now
      };
      return rendered;
    }

    return { observe: observe, reset: reset, current: function () { return rendered; }, baseline: function () { return baseline; } };
  }

  return {
    WIRE_RE: WIRE_RE, VERSION: VERSION, FREQUENCY_MODE1_HZ: FREQUENCY_MODE1_HZ,
    FLAG_WARMING: FLAG_WARMING, FLAG_VALID: FLAG_VALID, FLAG_UNAVAILABLE: FLAG_UNAVAILABLE,
    MIN_INTERVAL_SECONDS: MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS: MAX_INTERVAL_SECONDS,
    decodeWire: decodeWire, parseFrame: parseFrame, createTracker: createTracker
  };
});
