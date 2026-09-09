#ifndef MF885_USSD_REQUEST_PRODUCER_V19_H
#define MF885_USSD_REQUEST_PRODUCER_V19_H
#include <stdint.h>
/* Caller serializes EVERY operation under the existing short IRQ guard. Never
 * hold that guard across stock semaphore, allocation, enqueue or callbacks.
 * Task and descriptor are identity values only; this module never dereferences
 * them. Actual current-task identity and all call boundaries must be qualified.
 * A descriptor remains allocated until outgoing dispatch consumes this ticket.
 * State lives for one RAM session and must not reset while a message is queued.
 */
typedef struct {
    uint32_t task, descriptor, sequence, phase;
} ur_producer;
enum { UR_IDLE=0, UR_ENTERED=1, UR_PUBLISHED=2, UR_QUEUED=3,
       UR_TAKEN=4, UR_DISABLED=5 };
/* Reserve before entering the service. The sole production caller must first
 * consume a fresh nonzero sequence in the native CGI reservation gate. This
 * internal helper rejects a queued predecessor or a violated lifetime. The
 * standalone v19 module retains its own independent sequence validation. */
int ur_begin(ur_producer *, uint32_t task, uint32_t sequence);
/* Publish BEFORE the kernel may wake the consumer. Only the same task can
 * publish; unrelated AT/SIM producer tasks leave the ticket untouched. */
int ur_publish(ur_producer *, uint32_t task, uint32_t descriptor);
/* At the actual outgoing handler, before stock frees the descriptor. Returns
 * the HTTP sequence only for the exact published pointer, once. This proves
 * producer-to-dispatch identity, NOT response ownership or SS-ID freshness. */
uint32_t ur_take(ur_producer *, uint32_t descriptor);
/* Called once on the originating task after the service returns. queued_ok is
 * exact zero-return of the reviewed kernel enqueue, not arbitrary HTTP200.
 * A returning failure after consumption is an invariant failure, not a retry. */
void ur_finish(ur_producer *, uint32_t task, int queued_ok);
void ur_disable(ur_producer *);
#endif
