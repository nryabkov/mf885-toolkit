"""Pure ARMv5 Thumb branch decoder used by offline build checks."""
def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value

def branch(raw, address):
    require(len(raw) in (2,4), 'branch width')
    a = int.from_bytes(raw[:2], 'little')
    if a & 0xf800 == 0xf000 and len(raw) == 4:
        b = int.from_bytes(raw[2:], 'little')
        require(b & 0xf800 in (0xe800,0xf800), 'not ARMv5 BL/BLX suffix')
        target = address + 4 + signed(((a & 0x7ff) << 12) | ((b & 0x7ff) << 1), 23)
        state = 'arm' if b & 0xf800 == 0xe800 else 'thumb'
        return {'target': target & ~3 if state == 'arm' else target, 'state': state}
    if a & 0xf000 == 0xd000 and a & 0xf00 < 0xe00:
        return {'target':address+4+2*signed(a&0xff,8),'state':'thumb'}
    if a & 0xf800 == 0xe000:
        return {'target':address+4+2*signed(a&0x7ff,11),'state':'thumb'}
    raise ValueError('not supported direct branch')
