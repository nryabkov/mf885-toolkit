#ifndef MF885_USSD_MESSAGE_V10_H
#define MF885_USSD_MESSAGE_V10_H
#include "queue.h"
#define UO_MESSAGE_CONTEXT (-1001)

/* Internal task-context API. pair is live, aligned, exclusively owned and
 * initially empty. request is an already owned valid stock SS request and
 * remains caller-owned until successful uo_native_try_send. This function
 * allocates only the envelope, never the request. No browser pointer API. */
int32_t uo_native_message_new(uo_message_pair *pair, uint32_t primitive,
                            uint32_t transaction, void *request);
/* Discard only a still-owned envelope made above. Stock disposal clears the
 * pair and returns its partition; request ownership is unaffected. Never call
 * this on a queued message. Empty pair is a no-op. Invalid ownership is a bug. */
int32_t uo_native_message_discard(uo_message_pair *pair);
/* Encoded native SS payload: coding byte, length byte, up to229 body bytes.
 * NULL on invalid input, unavailable heap/context, or ordinary exhaustion.
 * Encoding conversion belongs to the future serialized producer, not this API.
 * request_discard needs exclusive ownership; zeroes its caller pointer on free. */
void *uo_native_request_new(uint32_t coding, const uint8_t *data, uint32_t count);
int32_t uo_native_request_discard(void **request);
/* Internal bounded XML response allocation in the same raw OSA family.
 * Never accepts a browser-provided address; normal exhaustion returns NULL. */
void *uo_native_buffer_new(uint32_t bytes);
#ifdef MF885_HTTP_SEND_V15
int uo_native_context_ok(void);
int32_t uo_native_http_submit(uint32_t sequence);
#endif
#endif
