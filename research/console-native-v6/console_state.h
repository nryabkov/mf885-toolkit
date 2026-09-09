#ifndef MF885_CONSOLE_STATE_V1_H
#define MF885_CONSOLE_STATE_V1_H
#include <stdint.h>
#include "wire.h"
#define CC_OUTPUT_MAX 960u
enum { CC_IDLE, CC_QUEUED, CC_READY, CC_RUNNING, CC_PENDING,
       CC_SUCCESS, CC_ERROR, CC_UNKNOWN };
typedef struct {
    uint32_t flags, samples, foreign_calls, owned_calls, busy_rejections;
    uint32_t pending_count, pending_mask, last_response_tag;
    uint32_t last_response_code, last_response_error, responses, callback_class;
    uint32_t pending_tags[8];
    char foreign_verb[24];
    uint32_t parser_address, callback_address, pending_address, caller_address;
} cc_diagnostic;
_Static_assert(sizeof(cc_diagnostic)==120,"bounded diagnostic snapshot");
typedef struct {
    uint32_t phase, kind, sequence, count;
    uint32_t queued_pointer, worker_task, parser, tag, last_tag;
    uint32_t output_count, truncated, quarantined;
    char command[CC_COMMAND_MAX+1u];
    char output[CC_OUTPUT_MAX];
    uint32_t original_output;
    cc_diagnostic diagnostic;
} cc_state;
_Static_assert(sizeof(cc_state)==1360,"bounded console state");
#endif
