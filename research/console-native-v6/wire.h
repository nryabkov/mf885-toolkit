#ifndef MF885_CONSOLE_WIRE_V1_H
#define MF885_CONSOLE_WIRE_V1_H
#include <stdint.h>
#define CC_COMMAND_MAX 224u
#define CC_CLAIM 's'
#define CC_AT 'a'
#define CC_USSD 'u'
typedef struct {
    uint32_t nonce_low, nonce_high, sequence;
    uint32_t kind, count;
    char command[CC_COMMAND_MAX + 1u];
} cc_request;
/* NUL-terminated request text owned by the current XML request. Output is only
 * usable when this returns1. This is framing, not AT effect/USSD DCS validation.
 * No send, reservation, address, selector or automatic retry is exposed here. */
int cc_parse_request(const char *wire, cc_request *out);
#endif
