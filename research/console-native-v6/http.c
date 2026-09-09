/* Private exact-stock diagnostic post_get adapter. No PSM calls or sends.
 * Requires a request-owned XML text child supplied by a separate template.
 * XML lifetime/concurrent access and CGI routing still require qualification. */
#include "native.h"
#include "message.h"
#ifdef MF885_HTTP_CONTROL_V16
#define WIRE_BYTES (sizeof(uo_snapshot) + sizeof(uo_submission))
#ifdef MF885_HTTP_CONSUME_V18
#define WIRE_VERSION '4'
#else
#define WIRE_VERSION '2'
#endif
#else
#define WIRE_BYTES sizeof(uo_snapshot)
#define WIRE_VERSION '1'
#endif
#define WIRE_ALLOCATION (4u + 2u * WIRE_BYTES)

int32_t uo_native_http_read(uint32_t phase, void *context) {
    typedef void *(*lookup_fn)(void *, const char *);
    typedef char **(*text_fn)(void *);
    if (phase != 4u || !context || *(uint16_t *)context != 1u) return 0;
    void *tree = *(void **)((uint8_t *)context + 12u);
    if (!tree) return 0;
    void *node = ((lookup_fn)(uintptr_t)0x064349efu)(tree, "ussd_v1");
    if (!node) return 0; /* Ordinary TTL template remains untouched. */
    char **slot = ((text_fn)(uintptr_t)0x06434e9fu)(node);
    if (!slot) return -1;
    char *old = *slot;
    /* The stock XML walker owns/frees this same text slot. Invalidate any
     * retained property before a possible allocation/lease failure. */
    if (old) old[0] = 0;
    void *owned = uo_native_buffer_new(WIRE_ALLOCATION);
    if (!owned) return -1;
    const uo_snapshot *snapshot = 0;
    uint32_t token = uo_native_read_begin(&snapshot);
    if (!token) {
        (void)uo_native_request_discard(&owned);
        return -1;
    }
    char *out = owned;
    out[0] = 'u'; out[1] = WIRE_VERSION; out[2] = ':';
#ifdef MF885_HTTP_CONTROL_V16
    /* The event is the first member of this complete snapshot object. */
    const uint8_t *raw = (const uint8_t *)(const uo_http_snapshot *)snapshot;
#else
    const uint8_t *raw = (const uint8_t *)snapshot;
#endif
    const char *hex = "0123456789abcdef";
    for (uint32_t i = 0; i < WIRE_BYTES; ++i) {
        out[3u + 2u*i] = hex[raw[i] >> 4];
        out[4u + 2u*i] = hex[raw[i] & 15u];
    }
    out[WIRE_ALLOCATION - 1u] = 0;
    if (!uo_native_read_end(token)) {
        (void)uo_native_request_discard(&owned);
        return -1;
    }
    *slot = owned; /* One completed owned string transferred to response tree. */
    owned = old;
    (void)uo_native_request_discard(&owned);
    return 0;
}
_Static_assert(sizeof(uo_snapshot) == 1028, "u1 raw snapshot wire ABI");

#ifdef MF885_HTTP_CONTROL_V16
/* Separate pre_set: unlike post_set, it does not depend on a PSM dirty bit.
 * The stock callback wrapper discards return status, so retain it in the arena.
 * v16 alone leaves nonce zero; v17 adds an explicit send-free session claim. */
int32_t uo_native_http_post(uint32_t phase, void *context) {
    typedef void *(*lookup_fn)(void *, const char *);
    typedef char **(*text_fn)(void *);
    typedef uint32_t (*enter_fn)(void);
    typedef void (*leave_fn)(uint32_t);
    if (phase != 3u || !context || *(uint16_t *)context != 1u || !uo_native_context_ok()) return 0;
    void *tree = *(void **)((uint8_t *)context + 12u);
    if (!tree) return 0;
#ifdef MF885_HTTP_CONSUME_V18
    /* Dedicated POST has exactly one child. Mixed modules are not USSD input. */
    if (*(uint32_t *)((uint8_t *)tree + 4u) != 1u) return 0;
    int valid = 0;
#define BAD_TEXT() goto consume
#else
#define BAD_TEXT() return 0
#endif
    void *node = ((lookup_fn)(uintptr_t)0x064349efu)(tree, "ussd_v1");
    if (!node) return 0;
    char **slot = ((text_fn)(uintptr_t)0x06434e9fu)(node);
    if (!slot || !*slot) { BAD_TEXT(); }
    const uint8_t *text = (const uint8_t *)*slot;
    uint32_t values[3] = {0, 0, 0};
    /* Exactly low32:high32:sequence, each eight lowercase hexadecimal digits.
     * Stop at every invalid byte, including NUL, without looking beyond it. */
    for (uint32_t word = 0; word < 3u; ++word) {
        for (uint32_t digit = 0; digit < 8u; ++digit) {
            uint32_t c = *text++, v;
            if (c >= '0' && c <= '9') v = c - '0';
            else if (c >= 'a' && c <= 'f') v = c - 'a' + 10u;
            else { BAD_TEXT(); }
            values[word] = (values[word] << 4) | v;
        }
        if (*text++ != (word == 2u ? 0 : ':')) { BAD_TEXT(); }
    }
#undef BAD_TEXT
#ifdef MF885_HTTP_CONSUME_V18
    valid = 1;
consume:
    /* Stock destructor releases the sole field and its owned text. Keep the
     * parent child-array allocation for the ordinary later tree destructor,
     * but clear its live count before the generic PSM walker can visit it. */
    ((void (*)(void *))(uintptr_t)0x06433ee5u)(node);
    *(uint32_t *)((uint8_t *)tree + 4u) = 0;
    if (!valid) return 0;
#endif
    uint32_t saved = ((enter_fn)(uintptr_t)0x06426160u)();
    uo_port_arena *a = *(uo_port_arena *volatile *)(uintptr_t)0x0694aa5cu;
    int reserved = 0;
    if (a && a != (void *)(uintptr_t)0x06e9db18u && a->magic == 0x554f5031u) {
        uo_submission *s = &a->submission;
#ifdef MF885_HTTP_SESSION_V17
        /* Send-free claim of an empty RAM session. A claim cannot reset an
         * active nonce/counter. The browser must read back before enabling
         * submission and must never retry a claim or reuse it after RAM loss. */
        if (!(s->nonce_low | s->nonce_high | s->sequence | (uint32_t)s->status) &&
            !values[2] && (values[0] | values[1])) {
            s->nonce_low = values[0]; s->nonce_high = values[1];
        }
#endif
        if ((s->nonce_low | s->nonce_high) && s->nonce_low == values[0] && s->nonce_high == values[1] &&
            s->sequence != UINT32_MAX && values[2] == s->sequence + 1u && s->status != INT32_MIN) {
            s->sequence = values[2]; s->status = INT32_MIN; reserved = 1;
        }
    }
    ((leave_fn)(uintptr_t)0x06426178u)(saved);
    if (!reserved) return 0;
    int32_t status = uo_native_http_submit(values[2]); /* Never under the IRQ guard. */
    saved = ((enter_fn)(uintptr_t)0x06426160u)();
    if (a->submission.sequence == values[2] && a->submission.status == INT32_MIN)
        a->submission.status = status;
    ((leave_fn)(uintptr_t)0x06426178u)(saved);
    return 0;
}
#endif
