#include "queue.h"
#if !defined(__arm__) || !defined(__thumb__) || !defined(__ARM_EABI__) || \
    (!defined(__ARM_ARCH_5TE__) && !defined(__ARM_ARCH_5TEJ__)) || \
    defined(__thumb2__) || defined(__ARM_PCS_VFP) || !defined(__SOFTFP__) || \
    __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "Native queue requires ARMv5TE Thumb1 LE EABI soft-float"
#endif
_Static_assert(sizeof(void *) == 4 && sizeof(uo_message_pair) == 8,
               "Exact stock ARM32 message pair");

int32_t uo_native_try_send(uo_message_pair *pair) {
    typedef int32_t (*send_fn)(void *, void **, uint32_t, uint32_t);
    if (!pair || ((uintptr_t)pair & 3u)) return UO_QUEUE_INVALID;
    uintptr_t code = (uintptr_t)pair->code;
    if (code < 24u || code > UINT32_MAX - 24u || (code & 3u) ||
        (uintptr_t)pair->descriptor != code + 4u)
        return UO_QUEUE_INVALID;
    uint8_t *header = (uint8_t *)(code - 24u);
    /* Pinned SS envelope, not the generic stock OSA assertion interface. */
    if (*pair->code != 0x20304u || *(uint16_t *)(header + 20) != 16u ||
        *(uint32_t *)(header + 44) != 0xdec0ddbau ||
        pair->descriptor[0] != 0x10000002u ||
        (*(uint16_t *)(header + 32) != 0x2du &&
         *(uint16_t *)(header + 32) != 0x2cu) ||
        !pair->descriptor[3])
        return UO_QUEUE_INVALID;
    uint16_t recipient = *(uint16_t *)(header + 18);
    *(uint16_t *)(header + 18) = 0x514u;
    void *message = header;
    /* Exact stock lookup for task514: table[5]=0x33, +0x14 =0x47;
     * queue table06be4cc0 +4*0x47 =06be4ddc. Kernel send retains all
     * scheduling/receiver wakeup behavior; only the assert wrapper is skipped. */
    void *queue = *(void *volatile *)(uintptr_t)0x06be4ddcu;
    int32_t status = ((send_fn)(uintptr_t)0x060c74adu)(queue, &message, 1, 0);
    if (status) {
        *(uint16_t *)(header + 18) = recipient;
        return status;
    }
    /* A woken receiver can already have consumed and freed both allocations.
     * Do not inspect message/header/descriptor/request after successful send. */
    pair->code = 0;
    pair->descriptor = 0;
    return 0;
}
