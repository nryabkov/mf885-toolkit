#ifndef MF885_USSD_OBSERVER_V1_H
#define MF885_USSD_OBSERVER_V1_H
#include <stdint.h>

/* Private core, not a firmware entry point. All calls, including snapshot,
 * require one externally serialized observation domain. No internal locks,
 * device calls, allocator, writable fixed address or browser request IDs.
 * A port must prove the v5/v6 hooks and boot coverage before enabling links. */
#define UO_EVENT_BYTES 236u
#define UO_RECORDS 14u
#define UO_EVENTS 4u
#define UO_LINKED 1u
#define UO_CONFIRMED 2u
#define UO_REUSED_ID 4u
#define UO_INCOMPLETE 8u
#define UO_UNMATCHED 16u
#define UO_PATH_RESULT 1u
#define UO_PATH_ERROR 2u
#define UO_PATH_INVOKE 3u
#define UO_PATH_UNMATCHED 4u

typedef struct {
    uint32_t transaction;
    uint16_t id, confirmation;
    uint8_t kind, owned, confirmed, reserved;
} uo_record;

typedef struct {
    uint32_t sequence, transaction;
    uint16_t local_id, confirmation;
    uint8_t flags, path, reserved[2];
    uint8_t payload[UO_EVENT_BYTES];
} uo_event;

typedef struct {
    uint32_t boot_epoch, sequence, overwritten, rejected, outgoing_transaction;
    uint8_t seen[32], reused[32];
    uo_record records[1]; /* One owned HTTP record; stock table still has 14. */
    uo_event events[UO_EVENTS];
    uo_record captured;
    uint16_t outgoing_id;
    uint8_t complete, outgoing, allocated, capture, capture_path, count, next, reserved;
    uint32_t interval_task;
} uo_state;

typedef struct {
    uint32_t boot_epoch, newest_sequence, overwritten, rejected;
    uint8_t complete, count, reserved[2];
    uo_event events[UO_EVENTS]; /* oldest to newest, owned copies */
} uo_snapshot;

void uo_init(uo_state *s, uint32_t boot_epoch, int complete_from_boot);
void uo_coverage_lost(uo_state *s);
void uo_context(uo_state *s, uint32_t task);
void uo_outgoing_begin(uo_state *s, uint32_t native_transaction);
void uo_allocation(uo_state *s, uint16_t id); /* EVERY shared SS allocation */
void uo_record_insert(uo_state *s, uint16_t id, uint8_t kind);
void uo_outgoing_end(uo_state *s);
void uo_confirmation(uo_state *s, uint16_t id, uint16_t raw_value);
void uo_retire(uo_state *s, uint16_t id);
void uo_expire_transaction(uo_state *s, uint32_t native_transaction);
void uo_capture_begin(uo_state *s, uint8_t path, uint16_t id, int stock_kind7_match);
void uo_capture_end(uo_state *s);
int uo_emit(uo_state *s, const uint8_t *payload, uint32_t bytes);
void uo_read(const uo_state *s, uo_snapshot *out);
#endif
