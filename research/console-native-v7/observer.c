#include "observer.h"

/* Host execution validates core logic only. ARM emission needs the real target
 * and an independently verified toolchain/port; a successful compile is not
 * hardware or hook qualification. No Thumb2, hard float or ARM-state fallback. */
#ifndef MF885_OBSERVER_HOST_TEST
#if !defined(__arm__) || !defined(__thumb__) || !defined(__ARM_EABI__) || \
    (!defined(__ARM_ARCH_5TE__) && !defined(__ARM_ARCH_5TEJ__)) || defined(__thumb2__) || \
    defined(__ARM_PCS_VFP) || !defined(__SOFTFP__)
#error "Observer target requires ARMv5TE Thumb1 EABI soft-float"
#endif
#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "Observer target requires little endian"
#endif
_Static_assert(sizeof(void *) == 4, "ARM32 pointers");
#endif
_Static_assert(sizeof(uo_record) == 12, "record layout");
_Static_assert(sizeof(uo_event) == 252, "event layout");
_Static_assert(sizeof(uo_state) <= 1536, "bounded state budget");
_Static_assert(sizeof(uo_snapshot) <= 1040, "bounded snapshot budget");

static void zero(void *p, uint32_t n) {
    uint8_t *b = p;
    while (n--) *b++ = 0;
}
static void copy(void *to, const void *from, uint32_t n) {
    uint8_t *d = to;
    const uint8_t *s = from;
    while (n--) *d++ = *s++;
}
static void increment(uint32_t *p) { if (*p != UINT32_MAX) ++*p; }
static int valid_id(uint16_t id) { return id >= 0x100 && id <= 0x1ff; }
static int bit(const uint8_t *map, uint16_t id) {
    return valid_id(id) && (map[(id & 255u) >> 3] & (1u << (id & 7u))) != 0;
}
static void mark(uint8_t *map, uint16_t id) {
    map[(id & 255u) >> 3] |= (uint8_t)(1u << (id & 7u));
}
/* v19 tracks only our HTTP operation. Stock AT/SIM records still produce
 * raw events, but never acquire browser ownership. The producer is serialized
 * through the stock SS task; an overlapping owned insertion loses coverage. */
static uo_record *find(uo_state *s, uint16_t id) {
    /* Stored keys are zero or range-checked at insertion. */
    return id && s->records[0].id == id ? &s->records[0] : 0;
}
void uo_init(uo_state *s, uint32_t epoch, int complete_from_boot) {
    zero(s, sizeof(*s));
    s->boot_epoch = epoch;
    /* A caller assertion, never a self-test or evidence of actual boot hooks. */
    s->complete = (uint8_t)(complete_from_boot && epoch != 0);
}
void uo_coverage_lost(uo_state *s) { s->complete = 0; }
void uo_context(uo_state *s, uint32_t task) {
    if (!task || (task & 3u) ||
        ((s->outgoing || s->capture) && s->interval_task != task))
        uo_coverage_lost(s);
    if (!(s->outgoing || s->capture)) s->interval_task = task;
}
void uo_outgoing_begin(uo_state *s, uint32_t transaction) {
    if (s->outgoing || s->capture) uo_coverage_lost(s);
    s->outgoing = 1;
    s->allocated = 0;
    s->outgoing_id = 0;
    s->outgoing_transaction = transaction;
}
void uo_allocation(uo_state *s, uint16_t id) {
    if (!valid_id(id)) { uo_coverage_lost(s); return; }
    if (bit(s->seen, id)) { s->reused[0] = 1; uo_coverage_lost(s); }
    mark(s->seen, id);
    if (s->outgoing) {
        if (s->allocated) uo_coverage_lost(s);
        s->allocated = 1;
        s->outgoing_id = id;
    }
}
void uo_record_insert(uo_state *s, uint16_t id, uint8_t kind) {
    if (!valid_id(id) || !bit(s->seen, id)) { uo_coverage_lost(s); return; }
    uo_record *r = &s->records[0];
    if (r->id == id) {
        s->reused[0] = 1; r->transaction = 0; uo_coverage_lost(s);
        return;
    }
    if (kind != 7 || s->outgoing != 2) return;
    if (r->id) { uo_coverage_lost(s); return; }
    zero(r, sizeof(*r));
    r->id = id;
    if (s->complete && s->allocated && s->outgoing_id == id) {
        r->transaction = s->outgoing_transaction;
    }
}
void uo_outgoing_end(uo_state *s) {
    if (!s->outgoing) uo_coverage_lost(s);
    s->outgoing = s->allocated = 0;
    /* Values are inaccessible to ownership while outgoing is zero; begin
     * overwrites the transaction and clears allocation before using them. */
}
void uo_confirmation(uo_state *s, uint16_t id, uint16_t value) {
    (void)s; (void)id; (void)value;
    /* Command confirmation is not the network reply and creates no owner. */
}
void uo_retire(uo_state *s, uint16_t id) {
    uo_record *r = find(s, id);
    if (r) zero(r, sizeof(*r));
    /* Preserve an already captured outer error/result context until its end.
     * Some stock error paths delete the record before event construction. */
}
void uo_expire_transaction(uo_state *s, uint32_t transaction) {
    if (s->records[0].transaction == transaction) s->records[0].transaction = 0;
    if (s->captured.transaction == transaction) s->captured.transaction = 0;
}
void uo_capture_begin(uo_state *s, uint8_t path, uint16_t id, int stock_match) {
    uo_record *r;
    if (s->capture || s->outgoing) uo_coverage_lost(s);
    s->capture = 1;
    s->capture_path = path;
    zero(&s->captured, sizeof(s->captured));
    s->captured.id = id;
    /* Invoke/foreign paths do not gain ownership by matching a numeric ID. */
    if (path != UO_PATH_RESULT && path != UO_PATH_ERROR) return;
    r = find(s, id);
    if (stock_match && r) copy(&s->captured, r, sizeof(*r));
}
void uo_capture_end(uo_state *s) {
    if (!s->capture) uo_coverage_lost(s);
    s->capture = 0;
    /* No emitter reads an owner without capture. The next begin zeroes this
     * record before lookup; clearing it twice adds no lifetime protection. */
}
int uo_emit(uo_state *s, const uint8_t *payload, uint32_t bytes) {
    uo_event *e;
    if (!payload || bytes != UO_EVENT_BYTES || payload[2] > 229u ||
        s->sequence == UINT32_MAX) {
        increment(&s->rejected);
        uo_coverage_lost(s);
        return 0;
    }
    e = &s->events[s->next];
    zero(e, sizeof(*e));
    e->sequence = ++s->sequence;
    e->path = s->capture ? s->capture_path : UO_PATH_UNMATCHED;
    if (s->capture) e->local_id = s->captured.id;
    if (!s->complete) e->flags |= UO_INCOMPLETE;
    if (s->reused[0]) e->flags |= UO_REUSED_ID; /* u4: ID-space reuse observed. */
    if (s->capture && s->complete && s->captured.transaction) {
        e->flags |= UO_LINKED | 32u; /* Only HTTP records can be owned in v19. */
        e->transaction = s->captured.transaction;
        /* No confirmation-token attribution in the HTTP-only successor. */
    } else e->flags |= UO_UNMATCHED;
    /* Stock copies stack-backed structs: bytes beyond count may be uninitialized.
     * Preserve defined header/body/details only; never expose padding in polls. */
    copy(e->payload, payload, 3u + payload[2]);
    copy(e->payload + 232u, payload + 232u, 4u);
    if (s->count == UO_EVENTS) increment(&s->overwritten);
    else ++s->count;
    s->next = (uint8_t)((s->next + 1u) & (UO_EVENTS - 1u));
    return 1;
}
void uo_read(const uo_state *s, uo_snapshot *out) {
    uint32_t i, start = (s->next + UO_EVENTS - s->count) & (UO_EVENTS - 1u);
    zero(out, sizeof(*out));
    out->boot_epoch = s->boot_epoch;
    out->newest_sequence = s->sequence;
    out->overwritten = s->overwritten;
    out->rejected = s->rejected;
    out->complete = s->complete;
    out->count = s->count;
    for (i = 0; i < s->count; ++i)
        copy(&out->events[i], &s->events[(start+i) & (UO_EVENTS-1u)], sizeof(uo_event));
}
