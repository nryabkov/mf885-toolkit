#include "producer.h"
#ifndef MF885_PRODUCER_HOST_TEST
#if !defined(__arm__) || !defined(__thumb__) || !defined(__ARM_EABI__) || \
 (!defined(__ARM_ARCH_5TE__) && !defined(__ARM_ARCH_5TEJ__)) || \
 defined(__thumb2__) || defined(__ARM_PCS_VFP) || !defined(__SOFTFP__) || \
 __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "Requires ARMv5TE Thumb1 LE EABI soft-float"
#endif
_Static_assert(sizeof(void *) == 4, "ARM32 deployment");
#endif
_Static_assert(sizeof(ur_producer) == 16, "bounded producer state");
__attribute__((noinline)) void ur_disable(ur_producer *s) {
    s->task = s->descriptor = 0;
    s->phase = UR_DISABLED;
}
static __attribute__((noinline)) void idle(ur_producer *s) {
    s->task = s->descriptor = 0;
    s->phase = UR_IDLE; /* Preserve the monotonically consumed sequence. */
}
__attribute__((noinline)) int ur_begin(ur_producer *s, uint32_t task, uint32_t sequence) {
    /* Integrated caller already consumed a fresh nonzero sequence atomically
     * in the native CGI gate. The internal ticket cannot be called by HTTP. */
    if (s->phase != UR_IDLE || !task || (task & 3u)) return 0;
    s->sequence = sequence;
    s->task = task;
    s->phase = UR_ENTERED;
    return 1;
}
__attribute__((noinline)) int ur_publish(ur_producer *s, uint32_t task, uint32_t descriptor) {
    /* ur_disable clears task, so the identity check also rejects disabled. */
    if (!task || task != s->task) return 0;
    if (s->phase != UR_ENTERED || !descriptor || (descriptor & 3u)) {
        ur_disable(s);
        return 0;
    }
    s->descriptor = descriptor;
    s->phase = UR_PUBLISHED;
    return 1;
}
__attribute__((noinline)) uint32_t ur_take(ur_producer *s, uint32_t descriptor) {
    if ((s->phase != UR_PUBLISHED && s->phase != UR_QUEUED) ||
        !descriptor || descriptor != s->descriptor) return 0;
    if (s->phase == UR_QUEUED) idle(s);
    else { s->descriptor = 0; s->phase = UR_TAKEN; }
    return s->sequence;
}
__attribute__((noinline)) void ur_finish(ur_producer *s, uint32_t task, int queued_ok) {
    if (!task || task != s->task ||
        (s->phase != UR_ENTERED && s->phase != UR_PUBLISHED && s->phase != UR_TAKEN)) {
        ur_disable(s);
        return;
    }
    if (queued_ok) {
        if (s->phase == UR_PUBLISHED) { s->phase = UR_QUEUED; s->task = 0; }
        else if (s->phase == UR_TAKEN) idle(s);
        else ur_disable(s); /* Success without a published queue message. */
    } else if (s->phase == UR_TAKEN) ur_disable(s);
    else idle(s);
}
