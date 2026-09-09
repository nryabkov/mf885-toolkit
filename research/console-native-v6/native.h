#ifndef MF885_USSD_NATIVE_V1_H
#define MF885_USSD_NATIVE_V1_H
#include "port.h"

/* Exact generic state-init ABI: r0..r3 followed by seven 32-bit stack words.
 * Private experimental entry, never callable from an HTTP-supplied address. */
uint32_t uo_native_init(void *context, uint32_t transitions, uint32_t states,
    uint32_t events, uint32_t value, uint32_t queue_count, uint32_t message_size,
    uint32_t queue_pool, uint32_t initial_state, uint32_t handlers, uint32_t final);
/* Replace only the constructor's dispatcher call0x061d8276 after placement
 * qualification. Copies group2/event2b before exactly one original dispatch. */
uint32_t uo_native_dispatch(uint32_t group, uint32_t event, const uint8_t *payload);
uint32_t uo_native_read_begin(const uo_snapshot **out);
int uo_native_read_end(uint32_t token);
#endif
