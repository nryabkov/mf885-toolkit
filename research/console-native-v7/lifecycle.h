#ifndef MF885_USSD_LIFECYCLE_V6_H
#define MF885_USSD_LIFECYCLE_V6_H
#include "port.h"
/* Private, incomplete lifecycle instrumentation. No operation enables coverage. */
enum { UO_TRACK_LOST, UO_TRACK_BEGIN, UO_TRACK_ALLOCATE, UO_TRACK_INSERT,
       UO_TRACK_END, UO_TRACK_CONFIRM, UO_TRACK_RETIRE, UO_TRACK_EXPIRE,
       UO_TRACK_RESULT, UO_TRACK_ERROR, UO_TRACK_INVOKE, UO_TRACK_CAPTURE_END };
uint32_t uo_port_track(void **, void *, const uo_port_ops *, uint32_t, uint32_t, uint32_t);
uint32_t uo_native_track(uint32_t operation, uint32_t first, uint32_t second);
uint32_t uo_native_outgoing(void *context);
uint32_t uo_native_allocate_id(void);
uint32_t uo_native_insert(const uint8_t *record);
uint32_t uo_native_retire(uint32_t id);
/* Producer identity operations, still not global hook-coverage evidence. */
#define UO_TRACK_HTTP_BEGIN 20u
#define UO_TRACK_HTTP_PUBLISH 21u
#define UO_TRACK_HTTP_TAKE 22u
#define UO_TRACK_HTTP_FINISH 23u
#define UO_TRACK_HTTP_OUTGOING 24u

#endif
