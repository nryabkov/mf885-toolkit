/* Exact stock call-site wrappers, not complete coverage or a deployment profile.
 * Stock calls are outside IRQ guards; all observer transitions use the port.
 * The original allocator body executes unchanged, including its byte counter.
 * No assembly cloning, new request, callback, allocation or free is introduced. */
#include "lifecycle.h"
#if !defined(MF885_LIFECYCLE_V6) || !defined(__ARM_ARCH_5TEJ__) || \
    !defined(__thumb__) || defined(__thumb2__) || !defined(__SOFTFP__) || \
    !defined(__ARM_EABI__) || __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "Lifecycle requires explicit ARMv5TE Thumb1 LE EABI soft-float profile"
#endif
_Static_assert(sizeof(void *) == 4, "ARM32 pointer");
#define RECORDS ((volatile uint8_t *)(uintptr_t)0x06baca6eu)
static uint16_t key(const volatile uint8_t *p) {
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}
uint32_t uo_native_outgoing(void *context) {
    typedef uint32_t (*handler_fn)(void *);
    /* Stock helper625c94a/62828d6 proves context+0x20 -> wrapper+4.
     * Descriptor+8 is the native request handle, never a browser identifier. */
    const uint32_t *wrapper = (const uint32_t *)(uintptr_t)((uint32_t *)context)[8];
    const uint32_t *descriptor = wrapper ? (const uint32_t *)(uintptr_t)wrapper[1] : 0;
    /* The descriptor identity is consumed under the same guard as beginning
     * the observer interval. Stock tags never become browser sequences. */
    uo_native_track(descriptor ? UO_TRACK_HTTP_OUTGOING : UO_TRACK_LOST,
                    (uintptr_t)descriptor, 0);
    uint32_t result = ((handler_fn)(uintptr_t)0x061d8151u)(context);
    uo_native_track(UO_TRACK_END, 0, 0);
    return result;
}
uint32_t uo_native_allocate_id(void) {
    /* Exact semantics of stock's 14-byte allocator; global entry now routes
     * here too, so calling the original entry would recurse. Independently
     * compare all 256 counter states and ABI against the original instructions. */
    volatile uint8_t *counter = (volatile uint8_t *)(uintptr_t)0x0694aa50u;
    uint32_t value = *counter;
    *counter = (uint8_t)(value + 1u);
    uint32_t id = value + 0x100u;
    uo_native_track(UO_TRACK_ALLOCATE, id, 0);
    return id;
}
static const volatile uint8_t *lookup(uint16_t id);
uint32_t uo_native_insert(const uint8_t *record) {
    typedef uint32_t (*insert_fn)(const uint8_t *);
    uint16_t id = key(record);
    uint8_t kind = record[3];
    uint32_t result = ((insert_fn)(uintptr_t)0x061d76a9u)(record);
    /* Ownership only consumes key/kind, never stale confirmation/padding.
     * Verify their actual presence after stock insertion. A preexisting same
     * key is already ambiguous in the all-allocation seen/reused observer. */
    const volatile uint8_t *observed = lookup(id);
    uo_native_track(observed && observed[3] == kind ? UO_TRACK_INSERT : UO_TRACK_LOST,
                    id, kind);
    return result;
}
uint32_t uo_native_retire(uint32_t id) {
    typedef uint32_t (*retire_fn)(uint32_t);
    uint32_t result = ((retire_fn)(uintptr_t)0x061d827du)(id);
    uo_native_track(result == 1 ? UO_TRACK_RETIRE : UO_TRACK_LOST, id, 0);
    return result;
}

/* Incoming state-machine handlers receive a message rather than the outgoing
 * request descriptor. Snapshot the key before any stock deletion/construction. */
static const uint8_t *message(void *context) {
    const uint32_t *wrapper = (const uint32_t *)(uintptr_t)((uint32_t *)context)[8];
    return wrapper ? (const uint8_t *)(uintptr_t)wrapper[1] : 0;
}
static const volatile uint8_t *lookup(uint16_t id) {
    uint32_t i;
    for (i = 0; i < UO_RECORDS; ++i)
        if (key(RECORDS + 6 * i) == id) return RECORDS + 6 * i;
    return 0;
}
static void capture(uint32_t path, const volatile uint8_t *record) {
    uo_native_track(path, record ? key(record) : 0, record && record[3] == 7);
}
static uint32_t incoming(void *context, uint32_t entry, uint32_t path) {
    typedef uint32_t (*handler_fn)(void *);
    const uint8_t *m = message(context);
    capture(path, m && path != UO_TRACK_INVOKE ? lookup(key(m + 2)) : 0);
    uint32_t result = ((handler_fn)(uintptr_t)entry)(context);
    uo_native_track(UO_TRACK_CAPTURE_END, 0, 0);
    return result;
}
uint32_t uo_native_result(void *context) {
    return incoming(context, 0x061d9777u, UO_TRACK_RESULT);
}
uint32_t uo_native_error_message(void *context) {
    return incoming(context, 0x061d9ab1u, UO_TRACK_ERROR);
}
uint32_t uo_native_invoke(void *context) {
    /* Network-initiated operations may bypass local lookup. Never attribute. */
    return incoming(context, 0x061d9de1u, UO_TRACK_INVOKE);
}
uint32_t uo_native_confirmation(void *context) {
    typedef uint32_t (*handler_fn)(void *);
    return ((handler_fn)(uintptr_t)0x061d9c83u)(context);
}
static uint32_t record_error(const uint8_t *record, const uint8_t *m, uint32_t entry) {
    typedef uint32_t (*handler_fn)(const uint8_t *, const uint8_t *);
    capture(UO_TRACK_ERROR, record);
    uint32_t result = ((handler_fn)(uintptr_t)entry)(record, m);
    uo_native_track(UO_TRACK_CAPTURE_END, 0, 0);
    return result;
}
uint32_t uo_native_error_release(const uint8_t *record, const uint8_t *m) {
    return record_error(record, m, 0x061d82ffu);
}
uint32_t uo_native_error_reject(const uint8_t *record, const uint8_t *m) {
    return record_error(record, m, 0x061d9b1fu);
}
uint32_t uo_native_error_return(const uint8_t *record, const uint8_t *m) {
    return record_error(record, m, 0x061da743u);
}
