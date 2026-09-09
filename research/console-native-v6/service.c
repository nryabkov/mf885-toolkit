#include "message.h"
#include "lifecycle.h"

/* Only the two pinned calloc(1,231) sites in service066e1484 use this entry. */
void *uo_native_service_alloc(void) {
    return uo_native_request_new(0, 0, 0);
}

/* The stock service loses its request pointer after this call, even on error.
 * Consume that ownership on both outcomes. Do not replace generic65d51a4. */
int32_t uo_native_service_send(uint32_t handle, uint32_t primitive,
                             uint32_t transaction, void *request) {
    uo_message_pair pair = {0, 0};
    int admissible = handle == 0x10000002u;
#ifdef MF885_HTTP_SEND_V15
    /* The new HTTP producer uses a zero native tag. Only a fresh
     * phase0 request (primitive2d) is permitted. In phase2, reject before enqueue
     * and let the original locked service restore its phase and free ownership.
     * A pre-call phase read alone would race with another producer. */
    if (!(transaction & 0xfffffu) && primitive != 0x2du) admissible = 0;
#endif
    int32_t status = admissible ?
        uo_native_message_new(&pair, primitive, transaction, request) :
        UO_QUEUE_INVALID;
    if (!status) {
        /* Before enqueue can run the receiver. Foreign tasks cannot claim the
         * current HTTP ticket. Pointer is never inspected after success. */
        (void)uo_native_track(UO_TRACK_HTTP_PUBLISH, (uintptr_t)pair.descriptor, 0);
        status = uo_native_try_send(&pair);
    }
    if (!status) return 0;
    /* The service owns an unmasked task context throughout this path; these
     * are exclusively owned allocations from the corresponding v10 families.
     * Free envelope first. Neither helper reads transferred/cleared storage. */
    (void)uo_native_message_discard(&pair);
    (void)uo_native_request_discard(&request);
    return status;
}

#ifdef MF885_HTTP_SEND_V15
/* Fixed semantic service only. No browser-controlled AT string, selector,
 * transaction tag, native pointer or continuation reply. HTTP authorization and
 * durable-in-boot reservation must run before this internal entry is wired. */
int32_t uo_native_http_submit(uint32_t sequence) {
    typedef int32_t (*service_fn)(uint32_t, uint32_t, const char *, uint32_t);
    /* Sole production caller is the context-validated v19 pre_set handler. */
    /* Exact stock DCS15 converter selects4 and copies these five ASCII bytes.
     * Add the terminator explicitly because stock service copies strlen(input).
     * Zero low20bits bypass AT pending-response routing, not a browser ID. */
    if (!uo_native_track(UO_TRACK_HTTP_BEGIN, sequence, 0)) return UO_QUEUE_INVALID;
    int32_t status = ((service_fn)(uintptr_t)0x066e1485u)(0, 4, "*100#", 5);
    (void)uo_native_track(UO_TRACK_HTTP_FINISH, (uint32_t)status, 0);
    return status;
}
#endif
