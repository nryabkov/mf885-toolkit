/* Private u4 snapshot reader: strict HTTP-origin ownership and text decoding.
 * No transport or DOM mutation. Native firmware owns the association proof. */
const BYTES = 1044;
const EVENT_BYTES = 252;
const invalid = () => { throw new Error('Invalid MF885 u4 snapshot'); };
export function decodeSessionSnapshot(wire) {
  if (typeof wire !== 'string' || wire.length !== 3 + 2 * BYTES ||
      !/^u4:[0-9a-f]+$/.test(wire)) invalid();
  const raw = new Uint8Array(BYTES);
  for (let i = 0; i < BYTES; i++) raw[i] = parseInt(wire.slice(3 + 2*i, 5 + 2*i), 16);
  const view = new DataView(raw.buffer);
  const u16 = at => view.getUint16(at, true);
  const u32 = at => view.getUint32(at, true);
  const zero = (start, end) => { for (let i = start; i < end; i++) if (raw[i]) invalid(); };
  const count = raw[17], newest = u32(4);
  if (raw[16] > 1 || count > 4 || count !== Math.min(newest, 4)) invalid();
  zero(18, 20);
  const events = [];
  for (let i = 0; i < count; i++) {
    const at = 20 + i * EVENT_BYTES;
    const sequence = u32(at), transaction = u32(at + 4), confirmation = u16(at + 10);
    const flags = raw[at + 12], path = raw[at + 13], linked = !!(flags & 1);
    if (sequence !== newest - count + i + 1 || flags & ~63 || path < 1 || path > 4) invalid();
    if (linked ? !!(flags & (4 | 8 | 16)) : !(flags & 16)) invalid();
    if (!linked && (transaction || confirmation || flags & 2)) invalid();
    if (linked !== !!(flags & 32) || (linked && !transaction) || confirmation || (flags & 2)) invalid();
    zero(at + 14, at + 16);
    const body = at + 16, size = raw[body + 2], selector = raw[body + 1];
    if (size > 229) invalid();
    zero(body + 3 + size, body + 232);
    events.push({sequence, nativeTransactionRaw: transaction, localIdRaw: u16(at + 8),
      confirmationRaw: confirmation, flagsRaw: flags, pathRaw: path,
      statusRaw: raw[body], codingSelectorRaw: selector,
      stockRenderedDcs: ({2: 4, 4: 16, 5: 17})[selector] ?? 0,
      payloadBytes: size, payloadHex: wire.slice(3 + 2*(body + 3), 3 + 2*(body + 3 + size)),
      detailWordsRaw: [u16(body + 232), u16(body + 234)],
      requestSequence: linked ? transaction : null, ownership: linked ? 'http-request' : 'unattributed'});
  }
  zero(20 + count * EVENT_BYTES, 1028);
  const low = u32(1028), high = u32(1032), sequence = u32(1036), status = view.getInt32(1040, true);
  const initialized = !!(low || high), pending = status === -2147483648;
  if ((!initialized && (sequence || status)) || (pending && !sequence)) invalid();
  const hex = n => n.toString(16).padStart(8, '0');
  const nonceRaw = hex(low) + ':' + hex(high);
  for (const event of events) {
    if (event.requestSequence !== null && (!initialized || event.requestSequence > sequence)) invalid();
    Object.assign(event, decodeUssdText(event));
  }
  const next = initialized && !pending && sequence < 0xffffffff ? sequence + 1 : null;
  return {schema: 'mf885-ussd-snapshot/u4', sessionContract: 'http-request-link/v20',
    submission: {nonceRaw, nonceInitialized: initialized, sequence, status, pending,
      nextArgument: next === null ? null : nonceRaw + ':' + hex(next)}, bootEpochRaw: u32(0),
    bootIdentityQualified: false, newestSequence: newest, overwritten: u32(8),
    rejected: u32(12), coverageComplete: !!raw[16], events};
}


/* Stock selector5 contains big-endian UCS2/UTF16 code units. Selector4
 * contains unpacked GSM default-alphabet septets, not packed network bytes.
 * Selector2 is arbitrary 8-bit data: retain hex without guessing a charset. */
export function decodeUssdText(event) {
  const bytes = Uint8Array.from(event.payloadHex.match(/../g) || [], x => parseInt(x, 16));
  const raw = reason => ({text: null, textEncoding: null, textIssue: reason});
  if (event.codingSelectorRaw === 5) {
    if (bytes.length % 2) return raw('Odd UTF-16BE byte count');
    let text = '';
    for (let i = 0; i < bytes.length; i += 2) {
      const unit = (bytes[i] << 8) | bytes[i+1];
      if (unit >= 0xd800 && unit <= 0xdbff) {
        if (i+3 >= bytes.length) return raw('Incomplete UTF-16BE surrogate');
        const next = (bytes[i+2] << 8) | bytes[i+3];
        if (next < 0xdc00 || next > 0xdfff) return raw('Invalid UTF-16BE surrogate');
        text += String.fromCharCode(unit, next); i += 2;
      } else if (unit >= 0xdc00 && unit <= 0xdfff) return raw('Unexpected UTF-16BE surrogate');
      else text += String.fromCharCode(unit);
    }
    return {text, textEncoding: 'UTF-16BE', textIssue: null};
  }
  if (event.codingSelectorRaw === 4) {
    const alphabet = '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\u001bÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà';
    const extension = {10:'\f',20:'^',40:'{',41:'}',47:'\\',60:'[',61:'~',62:']',64:'|',101:'€'};
    let text = '';
    for (let i = 0; i < bytes.length; i++) {
      const value = bytes[i];
      if (value > 127) return raw('Invalid GSM alphabet byte');
      if (value === 27) {
        const extra = extension[bytes[++i]];
        if (extra === undefined) return raw('Invalid GSM extension');
        text += extra;
      } else text += alphabet[value];
    }
    return {text, textEncoding: 'GSM default alphabet', textIssue: null};
  }
  return raw('Unsupported or binary coding selector');
}
