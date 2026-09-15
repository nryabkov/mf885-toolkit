#include "wire.h"
#if !defined(__arm__) || !defined(__thumb__) || defined(__thumb2__) || \
    (!defined(__ARM_ARCH_5TE__) && !defined(__ARM_ARCH_5TEJ__)) || \
    !defined(__ARM_EABI__) || !defined(__SOFTFP__) || defined(__ARM_PCS_VFP) || \
    __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "Requires verified ARMv5TE Thumb1 LE EABI5 soft-float target"
#endif
_Static_assert(sizeof(void *) == 4, "native ARM32 ABI");
_Static_assert(sizeof(cc_request) == 248, "bounded request frame");
static int nibble(uint32_t c) {
    if (c >= '0' && c <= '9') return (int)(c - '0');
    if (c >= 'a' && c <= 'f') return (int)(c - 'a' + 10u);
    return -1;
}
int cc_parse_request(const char *wire, cc_request *out) {
    if (!wire || !out) return 0;
    uint32_t words[3];
    for (uint32_t word = 0; word < 3; ++word) {
        uint32_t value = 0;
        for (uint32_t i = 0; i < 8; ++i) {
            int v = nibble((uint8_t)*wire++);
            if (v < 0) return 0; /* Includes NUL; no read after terminator. */
            value = (value << 4) | (uint32_t)v;
        }
        if (*wire++ != ':') return 0;
        words[word] = value;
    }
    if (!(words[0] | words[1])) return 0;
    uint32_t kind = (uint8_t)*wire++;
    if (kind != CC_CLAIM && kind != CC_AT && kind != CC_USSD) return 0;
    if (*wire++ != ':') return 0;
    uint32_t count = 0;
    while (*wire) {
        if (count == CC_COMMAND_MAX) return 0;
        int high = nibble((uint8_t)*wire++);
        if (high < 0) return 0;
        int low = nibble((uint8_t)*wire++);
        if (low < 0) return 0;
        uint32_t c = ((uint32_t)high << 4) | (uint32_t)low;
        if (c < 0x20 || c > 0x7e) return 0; /* One printable ASCII line. */
        out->command[count++] = (char)c;
    }
    if (kind == CC_CLAIM) {
        if (count || words[2]) return 0;
    } else {
        if (!count || !words[2]) return 0;
        if (kind == CC_AT && (count < 2 ||
            (out->command[0] != 'A' && out->command[0] != 'a') ||
            (out->command[1] != 'T' && out->command[1] != 't'))) return 0;
    }
    out->command[count] = 0;
    out->nonce_low = words[0]; out->nonce_high = words[1];
    out->sequence = words[2]; out->kind = kind; out->count = count;
    return 1;
}
