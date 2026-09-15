#include "port.h"
#include <stddef.h>
#ifndef MF885_OBSERVER_HOST_TEST
#if !defined(__arm__) || !defined(__thumb__) || !defined(__ARM_EABI__) || \
    (!defined(__ARM_ARCH_5TE__) && !defined(__ARM_ARCH_5TEJ__)) || \
    defined(__thumb2__) || defined(__ARM_PCS_VFP) || !defined(__SOFTFP__)
#error "Port requires ARMv5TE Thumb1 EABI soft-float"
#endif
#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "Port requires little endian"
#endif
_Static_assert(sizeof(void *) == 4, "ARM32 pointer");
#endif
#define MAGIC 0x554f5031u
_Static_assert(offsetof(uo_port_arena, magic) == 48, "preserve stock prefix");
_Static_assert(sizeof(cpu_state) == 48, "v7 appended CPU state");
/* v7 APPENDS cpu_state; every earlier field offset and the whole old prefix are
 * byte-for-byte unchanged. The control arena grows by sizeof(cpu_state) only. */
#ifdef MF885_HTTP_CONTROL_V16
_Static_assert(offsetof(uo_port_arena, cpu) == 3628, "cpu appended after old arena");
_Static_assert(sizeof(uo_port_arena) == 3676, "bounded control arena plus cpu state");
_Static_assert(sizeof(uo_submission) == 16, "u2 trailer");
_Static_assert(offsetof(uo_port_arena, snapshot.submission) == 2220, "contiguous u2 lease");
#else
_Static_assert(offsetof(uo_port_arena, cpu) == 2372, "cpu appended after boot arena");
_Static_assert(sizeof(uo_port_arena) == 2420, "bounded boot allocation plus cpu state");
#endif

/* The stock NU current-task validity probe reads this same task slot.
 * Sample it and interrupt nesting only while protected by the existing guard.
 * A masked caller cannot establish association, even if it inherited a task
 * pointer from interrupted code. SVC is the qualified RTOS thread mode. */
static uint32_t task_identity(uint32_t saved) {
    if ((saved & 0xdfu) != 0x13u ||
        *(volatile uint16_t *)(uintptr_t)0x0694a1a2u) return 0;
    return *(volatile uint32_t *)(uintptr_t)0x0695e0dcu;
}
static uo_port_arena *arena(void *context, void *fallback) {
    uo_port_arena *a;
    if (!context || context == fallback) return 0;
    a = context;
    return a->magic == MAGIC ? a : 0;
}
int uo_port_boot(void **slot, void *fallback, const uo_port_ops *ops,
                 void *arguments, uint32_t *stock_status) {
    uo_port_arena *a;
    uint32_t i, saved, result;
    uint8_t *bytes;
    if (*slot && *slot != fallback) return -1;
    a = ops->allocate(sizeof(*a)); /* Never allocate with interrupts masked. */
    if (!a) {
        result = ops->stock_init(fallback, arguments);
        saved = ops->enter(); *slot = fallback; ops->leave(saved);
        *stock_status = result;
        return 0;
    }
    bytes = (uint8_t *)a;
    for (i = 0; i < sizeof(*a); ++i) bytes[i] = 0;
    result = ops->stock_init(a->stock_context, arguments);
    /* Caller-supplied zeroed storage reproduces the original BSS prefix.
     * Retain even on stock-init failure: status is preserved, no hidden retry,
     * and stock_init may already have retained the new context pointer. */
    uo_init(&a->observer, 1, 0);
    a->magic = MAGIC;
    saved = ops->enter();
    /* Global allocator entry reports BEFORE returning an ID to its caller.
     * A pre-publication allocation marks the slot fallback; it cannot be
     * erased by a later factory. Only a still-null slot starts association. */
    a->observer.complete = *slot == 0;
    *slot = a;
    ops->leave(saved);
    *stock_status = result;
    return 1;
}
uint32_t uo_port_reinit(void *context, void *fallback, const uo_port_ops *ops,
                        void *arguments) {
    uint32_t saved = ops->enter();
    uo_port_arena *a = arena(context, fallback);
    if (a) { uo_coverage_lost(&a->observer); ur_disable(&a->producer); }
    ops->leave(saved);
    /* Preserve stock return and exactly one stock call, outside the guard. */
    return ops->stock_init(context, arguments);
}
uint32_t uo_port_read_begin(void *context, void *fallback, const uo_port_ops *ops,
                            const uo_snapshot **out) {
    uo_port_arena *a;
    uint32_t saved, token = 0;
    *out = 0;
    saved = ops->enter();
    a = arena(context, fallback);
    if (a && !a->reader_busy && a->reader_token != UINT32_MAX) {
#ifdef MF885_HTTP_CONTROL_V16
        uo_read(&a->observer, &a->snapshot.events);
        a->snapshot.submission = a->submission;
#else
        uo_read(&a->observer, &a->snapshot);
#endif
        a->reader_busy = 1;
        token = ++a->reader_token;
#ifdef MF885_HTTP_CONTROL_V16
        *out = &a->snapshot.events;
#else
        *out = &a->snapshot;
#endif
    }
    ops->leave(saved);
    return token;
}
int uo_port_read_end(void *context, void *fallback, const uo_port_ops *ops,
                     uint32_t token) {
    uint32_t saved = ops->enter();
    uo_port_arena *a = arena(context, fallback);
    int released = 0;
    if (a && token && a->reader_busy && a->reader_token == token) {
        a->reader_busy = 0; released = 1;
    }
    ops->leave(saved);
    return released;
}

int uo_port_observe(void *context, void *fallback, const uo_port_ops *ops,
                     const uint8_t *payload) {
    uint32_t saved = ops->enter();
    uo_port_arena *a = arena(context, fallback);
    int copied = 0;
    if (a) {
        /* Only an active captured reply can carry an owner into this event. */
        if (a->observer.capture && a->observer.interval_task != task_identity(saved))
            uo_coverage_lost(&a->observer);
        copied = uo_emit(&a->observer, payload, UO_EVENT_BYTES);
    }
    ops->leave(saved);
    return copied;
}

#ifdef MF885_LIFECYCLE_V6
#include "lifecycle.h"
uint32_t uo_port_track(void **slot, void *fallback, const uo_port_ops *ops,
                   uint32_t operation, uint32_t first, uint32_t second) {
    uint32_t saved = ops->enter();
    /* Early allocation is sticky: stock initialization can proceed using its
     * fallback, but a missed ID must never become a fresh association later. */
    if (!*slot && operation == UO_TRACK_ALLOCATE) *slot = fallback;
    uo_port_arena *a = arena(*slot, fallback);
    uint32_t answer = 0;
    if (a) {
        uo_state *s = &a->observer;
        uint32_t task = task_identity(saved);
        uo_context(s, task);
        if (operation == UO_TRACK_HTTP_BEGIN) answer = ur_begin(&a->producer, task, first);
        else if (operation == UO_TRACK_HTTP_PUBLISH) answer = ur_publish(&a->producer, task, first);
        else if (operation == UO_TRACK_HTTP_FINISH) ur_finish(&a->producer, task, first == 0);
        else if (operation == UO_TRACK_HTTP_OUTGOING) {
            uint32_t sequence = ur_take(&a->producer, first);
            uo_outgoing_begin(s, sequence);
            if (sequence) s->outgoing = 2;
        }
        else if (operation == UO_TRACK_ALLOCATE) uo_allocation(s, (uint16_t)first);
        else if (operation == UO_TRACK_INSERT) uo_record_insert(s, (uint16_t)first, (uint8_t)second);
        else if (operation == UO_TRACK_END) uo_outgoing_end(s);
        else if (operation == UO_TRACK_RETIRE) uo_retire(s, (uint16_t)first);
        else if (operation >= UO_TRACK_RESULT && operation <= UO_TRACK_INVOKE)
            uo_capture_begin(s, (uint8_t)(operation - UO_TRACK_RESULT + UO_PATH_RESULT),
                             (uint16_t)first, second != 0);
        else if (operation == UO_TRACK_CAPTURE_END) uo_capture_end(s);
        else uo_coverage_lost(s);
    }
    ops->leave(saved);
    return answer;
}
#endif
