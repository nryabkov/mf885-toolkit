/* Exact base2.5.94/MF96 Ver.D bindings. This file is NOT a deployment profile:
 * allocator boot admissibility, placement and complete hooks remain unproved. */
#include "native.h"
#if !defined(__arm__) || !defined(__thumb__) || !defined(__ARM_EABI__) || \
    (!defined(__ARM_ARCH_5TE__) && !defined(__ARM_ARCH_5TEJ__)) || \
    defined(__thumb2__) || defined(__ARM_PCS_VFP) || !defined(__SOFTFP__) || \
    __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "Native bindings require ARMv5TE Thumb1 LE EABI soft-float"
#endif
_Static_assert(sizeof(void *) == 4, "ARM32 pointers");
#define SLOT ((void **)(uintptr_t)0x0694aa5cu)
#define FALLBACK ((void *)(uintptr_t)0x06e9db18u)

typedef struct {
    uint32_t transitions, states, events;
    uint32_t value, queue_count, message_size, queue_pool, initial_state;
    uint32_t handlers, final;
} init_args;
_Static_assert(sizeof(init_args) == 40, "ten retained stock arguments");
typedef uint32_t (*init_fn)(void *, uint32_t, uint32_t, uint32_t,
    uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);
typedef void *(*allocate_fn)(uint32_t, uint32_t, uint32_t);

static void *allocate(uint32_t bytes) {
#if defined(MF885_POOL_ALLOCATOR_V5) && defined(MF885_CI_ALLOCATOR_V4)
#error "Select exactly one experimental allocator profile"
#endif
#if defined(MF885_POOL_ALLOCATOR_V5)
    /* The stock CI wrapper escalates pool exhaustion to KMDYNMEM assertion.
     * Use its actual non-waiting pool primitive, without CI's extra header.
     * Pool-owned metadata remains intact; this arena is never freed/detached.
     * The stock pool guard unconditionally enables I/F at depth zero. Refuse
     * optional allocation if called masked or inside that guard, instead of
     * violating the caller's state. Stock initialization still runs normally. */
    typedef uint32_t (*pool_fn)(void *, uint32_t, void **);
    typedef uint32_t (*enter_fn)(void);
    typedef void (*leave_fn)(uint32_t);
    uint32_t saved = ((enter_fn)(uintptr_t)0x06426160u)();
    uint16_t depth = *(volatile uint16_t *)(uintptr_t)0x0694a1a2u;
    ((leave_fn)(uintptr_t)0x06426178u)(saved);
    if ((saved & 0xc0u) || depth) return 0;
    void *result = 0;
    uint32_t status = ((pool_fn)(uintptr_t)0x00004559u)(
        (void *)(uintptr_t)0x06c08680u, bytes, &result);
    return status == 0 ? result : 0;
#elif defined(MF885_CI_ALLOCATOR_V4)
    /* Same ABI used by 27 allocations in the stock predecessor initializer.
     * Stock callers initialize the output pointer and ignore the status word.
     * Low-memory body and real failure behavior still require qualification. */
    typedef uint32_t (*ci_allocate_fn)(uint32_t, void **);
    void *result = 0;
    (void)((ci_allocate_fn)(uintptr_t)0x06367290u)(bytes, &result);
    return result;
#else
    /* Raw ARM veneer avoids the ordinary wrapper's task-dependent assertion.
     * Its Thumb0x2355 body/failure policy still needs target qualification.
     * Caller tag is the original call-site return PC, for allocator diagnostics. */
    return ((allocate_fn)(uintptr_t)0x0641b0e8u)(0, bytes, 0x061d7311u);
#endif
}
/* Keep the eleven-argument marshaler out of the entry frame. */
static __attribute__((noinline)) uint32_t stock_init(void *context, void *opaque) {
    const init_args *a = opaque;
    return ((init_fn)(uintptr_t)0x0625c7ddu)(context,
        a->transitions, a->states, a->events, a->value, a->queue_count,
        a->message_size, a->queue_pool, a->initial_state, a->handlers, a->final);
}
static const uo_port_ops ops = {
    allocate, stock_init,
    (uint32_t (*)(void))(uintptr_t)0x06426160u,
    (void (*)(uint32_t))(uintptr_t)0x06426178u
};

uint32_t uo_native_init(void *context, uint32_t transitions, uint32_t states,
    uint32_t events, uint32_t value, uint32_t queue_count, uint32_t message_size,
    uint32_t queue_pool, uint32_t initial_state, uint32_t handlers, uint32_t final) {
    init_args args = {transitions, states, events, value, queue_count,
        message_size, queue_pool, initial_state, handlers, final};
    uint32_t result;
    /* A mismatched call site must retain its own context and original behavior. */
    if (context != FALLBACK) return stock_init(context, &args);
    /* A published fallback also records a completed allocation attempt. */
    if (*SLOT) return uo_port_reinit(*SLOT, FALLBACK, &ops, &args);
    if (uo_port_boot(SLOT, FALLBACK, &ops, &args, &result) < 0)
        return uo_port_reinit(*SLOT, FALLBACK, &ops, &args);
    return result;
}
uint32_t uo_native_read_begin(const uo_snapshot **out) {
    return uo_port_read_begin(*SLOT, FALLBACK, &ops, out);
}
int uo_native_read_end(uint32_t token) {
    return uo_port_read_end(*SLOT, FALLBACK, &ops, token);
}

uint32_t uo_native_dispatch(uint32_t group, uint32_t event, const uint8_t *payload) {
    typedef uint32_t (*dispatch_fn)(uint32_t, uint32_t, const uint8_t *);
    if (group == 2 && event == 0x2b)
        (void)uo_port_observe(*SLOT, FALLBACK, &ops, payload);
    /* The stock dispatcher may call the original client or release payload.
     * Never touch it after this call; preserve stock return even if copy fails.
     * No allocation, wait, callback replacement or cleanup belongs here. */
    return ((dispatch_fn)(uintptr_t)0x06282579u)(group, event, payload);
}

#ifdef MF885_LIFECYCLE_V6
#include "lifecycle.h"
uint32_t uo_native_track(uint32_t operation, uint32_t first, uint32_t second) {
    return uo_port_track(SLOT, FALLBACK, &ops, operation, first, second);
}
#endif
