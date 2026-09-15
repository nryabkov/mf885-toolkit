#ifndef MF885_USSD_QUEUE_V9_H
#define MF885_USSD_QUEUE_V9_H
#include <stdint.h>

/* Internal, task-context-only API for an exclusively owned, stock-allocated
 * message. Both members and all referenced storage must be valid/live; these
 * structural checks do not make arbitrary browser pointers safe. The pair
 * itself must outlive this call and be separate from the message/payload.
 * A caller must qualify allocation, disposal and task serialization first.
 * No stock/global call site or HTTP handler uses this experimental entry yet. */
typedef struct {
    uint32_t *code;
    uint32_t *descriptor;
} uo_message_pair;

#define UO_QUEUE_INVALID (-1000)
/* Exactly one zero-wait queue attempt. Zero transfers message AND request to
 * the stock consumer and clears pair. Nonzero preserves the complete message,
 * pair and request for caller cleanup; returns the kernel status unchanged.
 * Never free or retry here. Zero means accepted, not a carrier response. */
int32_t uo_native_try_send(uo_message_pair *pair);
#endif
