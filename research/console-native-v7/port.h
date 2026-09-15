#ifndef MF885_USSD_PORT_V1_H
#define MF885_USSD_PORT_V1_H
#include "observer.h"
#include "producer.h"
#include "console_state.h"
#include "cpu.h"

/* Boot-only factory and bounded read lease. Bind these operations only after
 * auditing their real stock ABI; this file contains no fixed device addresses. */
typedef struct {
    void *(*allocate)(uint32_t bytes);
    uint32_t (*stock_init)(void *context, void *arguments);
    uint32_t (*enter)(void);
    void (*leave)(uint32_t saved);
} uo_port_ops;

#ifdef MF885_HTTP_CONTROL_V16
/* Native boot identity is deliberately zero/unavailable until a qualified
 * initializer supplies it. Never set this from an HTTP request or uptime. */
typedef struct {
    uint32_t nonce_low, nonce_high, sequence;
    int32_t status; /* INT32_MIN=in progress; otherwise synchronous send status. */
} uo_submission;
typedef struct { uo_snapshot events; uo_submission submission; } uo_http_snapshot;
#endif

typedef struct {
    uint32_t stock_context[12]; /* Stock state-machine prefix: exactly48bytes. */
    uint32_t magic, reader_token, reader_busy;
    uo_state observer;
#ifdef MF885_HTTP_CONTROL_V16
    uo_http_snapshot snapshot; /* Typed complete object for the u2 read lease. */
    uo_submission submission;
    ur_producer producer; /* v19: one task/queue lifetime ticket */
    cc_state console;
#else
    uo_snapshot snapshot;
#endif
    cpu_state cpu; /* v7: APPENDED last. No earlier field offset changes. */
} uo_port_arena;

/* Precondition: before any SS producer starts, slot is null or fallback.
 * Calls stock_init exactly once unless reinitialization is refused. Both
 * caller and stock_init are quiescent until the new context is published.
 * The allocation lives until device reset; no detach/free is supported.
 * Returns1 extended context,0 allocation-failure fallback,-1 reinit refused.
 * Complete hook coverage is intentionally disabled in this unqualified port. */
int uo_port_boot(void **slot, void *fallback, const uo_port_ops *ops,
                 void *arguments, uint32_t *stock_status);

/* Re-run stock init on the already published context without reallocating or
 * resetting an outstanding snapshot. Disable attribution before the callback.
 * Precondition: context is the factory result; stock reinit itself is quiescent.
 * This preserves the call, not proof that stock supports concurrent reinit. */
uint32_t uo_port_reinit(void *context, void *fallback, const uo_port_ops *ops,
                        void *arguments);

/* Copy while the stock constructor still owns a complete236byte event.
 * Do not free or retain payload. Validated context and serialized domain rules
 * match read_begin. Return0 if unavailable/rejected,1 copied. */
int uo_port_observe(void *context, void *fallback, const uo_port_ops *ops,
                     const uint8_t *payload);

/* Only a validated published context from the boot factory may be supplied.
 * Reader gets one stable heap snapshot; render outside the interrupt guard,
 * then release the exact token on every exit. Busy/unavailable returns0.
 * A leaked lease blocks later snapshots, never native event observation. */
uint32_t uo_port_read_begin(void *context, void *fallback, const uo_port_ops *ops,
                            const uo_snapshot **snapshot);
int uo_port_read_end(void *context, void *fallback, const uo_port_ops *ops,
                     uint32_t token);
#endif
