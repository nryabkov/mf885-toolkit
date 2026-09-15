#include "message.h"
#if !defined(__arm__) || !defined(__thumb__) || !defined(__ARM_EABI__) || \
    (!defined(__ARM_ARCH_5TE__) && !defined(__ARM_ARCH_5TEJ__)) || \
    defined(__thumb2__) || defined(__ARM_PCS_VFP) || !defined(__SOFTFP__) || \
    __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "Native message requires ARMv5TE Thumb1 LE EABI soft-float"
#endif
_Static_assert(sizeof(void *) == 4, "Exact ARM32 partition ABI");

static __attribute__((noinline)) int context_ok(void) {
    uint32_t saved = ((uint32_t (*)(void))(uintptr_t)0x06426160u)();
    uint16_t depth = *(volatile uint16_t *)(uintptr_t)0x0694a1a2u;
    ((void (*)(uint32_t))(uintptr_t)0x06426178u)(saved);
    return !(saved & 0xc0u) && !depth;
}

int32_t uo_native_message_new(uo_message_pair *pair, uint32_t primitive,
                            uint32_t transaction, void *request) {
    typedef int32_t (*alloc_fn)(void *, void **, uint32_t);
    typedef uint32_t (*enter_fn)(void);
    typedef void (*leave_fn)(uint32_t);
    if (!pair || ((uintptr_t)pair & 3u) || pair->code || pair->descriptor ||
        (primitive != 0x2cu && primitive != 0x2du) || !request)
        return UO_QUEUE_INVALID;
    if (!context_ok()) return UO_MESSAGE_CONTEXT;
    void *block = 0;
    /* Exact stock class0: 52 user bytes, sufficient for 24 header +4 code
     * +16 descriptor +4 canary =48. Retain NU's hidden8-byte partition header. */
    int32_t status = ((alloc_fn)(uintptr_t)0x0615eb11u)(
        (void *)(uintptr_t)0x06bdd33cu, &block, 0);
    if (status) return status;
    uint32_t saved = ((enter_fn)(uintptr_t)0x06426160u)();
    volatile uint16_t *used = (volatile uint16_t *)(uintptr_t)0x06be4c92u;
    volatile uint16_t *peak = (volatile uint16_t *)(uintptr_t)0x06be4c88u;
    uint16_t count = (uint16_t)(*used + 1u);
    *used = count;
    if (*peak < count) *peak = count;
    ((leave_fn)(uintptr_t)0x06426178u)(saved);
    uint32_t *words = block;
    for (unsigned i = 0; i < 12; ++i) words[i] = 0;
    uint8_t *header = block;
    words[0] = (uintptr_t)__builtin_return_address(0);
    *(uint16_t *)(header + 4) = 0xffffu;
    header[6] = 0x81;
    header[12] = 1;
    *(uint16_t *)(header + 16) = 0xffffu;
    *(uint16_t *)(header + 18) = 0xffffu;
    *(uint16_t *)(header + 20) = 16;
    words[6] = 0x20304u;
    words[7] = 0x10000002u;
    words[8] = primitive;
    words[9] = transaction;
    words[10] = (uintptr_t)request;
    words[11] = 0xdec0ddbau;
    pair->code = words + 6;
    pair->descriptor = words + 7;
    return 0;
}

int32_t uo_native_message_discard(uo_message_pair *pair) {
    typedef void (*free_fn)(uo_message_pair *);
    if (!pair || ((uintptr_t)pair & 3u)) return UO_QUEUE_INVALID;
    if (!pair->code) return pair->descriptor ? UO_QUEUE_INVALID : 0;
    if (!context_ok()) return UO_MESSAGE_CONTEXT;
    ((free_fn)(uintptr_t)0x00000b19u)(pair);
    return 0;
}

void *uo_native_request_new(uint32_t coding, const uint8_t *data, uint32_t count) {
#ifdef MF885_HTTP_READ_V14
    if (coding > 255u || count > 229u || (count && !data)) return 0;
    uint8_t *request = uo_native_buffer_new(231);
#else
    typedef void *(*alloc_fn)(void *, uint32_t, uintptr_t);
    if (coding > 255u || count > 229u || (count && !data)) return 0;
    void *heap = *(void *volatile *)(uintptr_t)0x000100f0u;
    if (!heap || !context_ok()) return 0;
    /* Same OSA allocation family as stock calloc, bypassing only its outer
     * assertion-on-NULL policy. Initialized default heap is required; retain
     * raw OSA header/refcount, coalescing and low-memory notifications. */
    uint8_t *request = ((alloc_fn)(uintptr_t)0x00002355u)(
        heap, 231, (uintptr_t)__builtin_return_address(0));
#endif
    if (!request) return 0;
    request[0] = (uint8_t)coding;
    request[1] = (uint8_t)count;
    for (uint32_t i = 0; i < 229u; ++i)
        request[i + 2u] = i < count ? data[i] : 0;
    return request;
}

int32_t uo_native_request_discard(void **request) {
    typedef void (*free_fn)(void *);
    if (!request || ((uintptr_t)request & 3u)) return UO_QUEUE_INVALID;
    if (!*request) return 0;
    if (!context_ok()) return UO_MESSAGE_CONTEXT;
    ((free_fn)(uintptr_t)0x00002a8du)(*request);
    *request = 0;
    return 0;
}

#ifdef MF885_HTTP_READ_V14
void *uo_native_buffer_new(uint32_t bytes) {
    typedef void *(*alloc_fn)(void *, uint32_t, uintptr_t);
    #ifdef MF885_HTTP_CONTROL_V16
    if (!bytes || bytes > 2092u) return 0;
#else
    if (!bytes || bytes > 2060u) return 0;
#endif
    void *heap = *(void *volatile *)(uintptr_t)0x000100f0u;
    if (!heap || !context_ok()) return 0;
    return ((alloc_fn)(uintptr_t)0x00002355u)(
        heap, bytes, (uintptr_t)__builtin_return_address(0));
}
#endif

#ifdef MF885_HTTP_SEND_V15
int uo_native_context_ok(void) { return context_ok(); }
#endif
