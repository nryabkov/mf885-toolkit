/* Bounded timer1 accounting; hardware timing contract requires qualification. */
#include "cpu.h"
#ifndef MF885_CPU_HOST_TEST
#if !defined(__ARM_ARCH_5TEJ__) && !defined(__ARM_ARCH_5TE__)
#error "ARMv5TE required"
#endif
#if !defined(__thumb__) || defined(__thumb2__) || !defined(__SOFTFP__) || !defined(__ARM_EABI__) || __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "Thumb1 little-endian EABI soft-float required"
#endif
_Static_assert(sizeof(void *) == 4, "ARM32");
#define READ32(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define READ8(a) (*(volatile uint8_t *)(uintptr_t)(a))
#else
uint32_t cpu_mmio_read32(uint32_t);
uint8_t cpu_mmio_read8(uint32_t);
#define READ32(a) cpu_mmio_read32(a)
#define READ8(a) cpu_mmio_read8(a)
#endif
static void increment(uint32_t *v) { if (*v != UINT32_MAX) ++*v; }
static void add(uint32_t *lo, uint32_t *hi, uint32_t d) {
    uint32_t next=*lo+d;
    if(next<*lo) { if(*hi==UINT32_MAX) {*lo=UINT32_MAX;return;} ++*hi; }
    *lo=next;
}
static int sample(cpu_read_fn read, void *ctx, uint32_t *v) {
    uint32_t previous, current;
    if(!read || READ8(0x12385u)!=1u || ((READ32(CPU_CFG_CONFIG)>>2)&7u)!=1u ||
       !(READ32(CPU_CFG_ENABLE)&2u) || READ32(CPU_CFG_PRELOAD_CONTROL) ||
       READ32(CPU_CFG_PRELOAD_VALUE) || (READ32(CPU_CFG_CMR)&2u)) return 0;
    if(read(ctx,&previous)!=1)return 0;
    for(uint32_t n=1;n<CPU_READ_ATTEMPTS;++n) {
        if(read(ctx,&current)!=1)return 0;
        if(current==previous){*v=current;return 1;}
        previous=current;
    }
    return 0;
}
void cpu_init(cpu_state *s) {
    if(!s)return;
    uint32_t *p=(uint32_t *)s;
    for(uint32_t n=0;n<sizeof(*s)/4u;++n)p[n]=0;
    s->flags=CPU_FLAG_WARMING|CPU_FLAG_UNAVAILABLE;
}
/* Caller masks I/F over both the sample and all state changes. Total advances
 * during busy AND idle time. Idle advances only for the previous open state.
 * Any failed read discards the epoch, including an unobserved gap; recovery
 * starts new counters and never bridges that gap. */
static void advance(cpu_state *s,cpu_read_fn read,void *ctx) {
    uint32_t tick,delta;
    if(!sample(read,ctx,&tick))goto unavailable;
    if(!s->have_tick) {
        increment(&s->epoch);s->have_tick=1;s->last_tick=tick;
        s->total_low=s->total_high=s->idle_low=s->idle_high=0;
        s->frequency_hz=CPU_FREQUENCY_MODE1_HZ;s->flags=CPU_FLAG_WARMING;
        return;
    }
    delta=tick-s->last_tick;
    if(delta>=0x80000000u)goto unavailable;
    s->last_tick=tick;
    add(&s->total_low,&s->total_high,delta);
    if(s->open)add(&s->idle_low,&s->idle_high,delta);
    if(s->total_low || s->total_high)s->flags=CPU_FLAG_VALID;
    return;
unavailable:
    increment(&s->read_errors);s->have_tick=0;s->frequency_hz=0;
    s->total_low=s->total_high=s->idle_low=s->idle_high=0;
    s->flags=CPU_FLAG_UNAVAILABLE;
}
static void transition(cpu_state *s,cpu_read_fn read,void *ctx,uint32_t open) {
    if(!s)return;
    uint32_t saved=CPU_GUARD_ENTER();
    if(s->open!=open) {advance(s,read,ctx);s->open=open;increment(&s->transitions);}
    CPU_GUARD_LEAVE(saved);
}
void cpu_idle_begin(cpu_state *s,cpu_read_fn read,void *ctx){transition(s,read,ctx,1);}
void cpu_idle_end(cpu_state *s,cpu_read_fn read,void *ctx){transition(s,read,ctx,0);}
void cpu_snapshot(cpu_state *s,cpu_read_fn read,void *ctx,cpu_state *out) {
    if(!s || !out)return;
    uint32_t saved=CPU_GUARD_ENTER();
    advance(s,read,ctx);
    volatile uint8_t *dst=(volatile uint8_t *)out;
    const uint8_t *src=(const uint8_t *)s;
    for(uint32_t n=0;n<sizeof(*s);++n)dst[n]=src[n];
    CPU_GUARD_LEAVE(saved);
}
int cpu_serialize(const cpu_state *state, char *wire, uint32_t capacity) {
    static const char hex[] = "0123456789abcdef";
    uint32_t fields[CPU_FRAME_WORDS];
    if (!state || !wire) return 0;
    if (capacity < CPU_WIRE_BYTES) return 0;
    if (state->flags & ~CPU_FLAG_KNOWN_MASK) return 0;
    fields[0] = CPU_VERSION;
    fields[1] = state->flags;
    fields[2] = state->epoch;
    fields[3] = state->frequency_hz;
    fields[4] = state->total_low;
    fields[5] = state->total_high;
    fields[6] = state->idle_low;
    fields[7] = state->idle_high;
    fields[8] = state->read_errors;
    fields[9] = state->transitions;
    wire[0] = 'c';
    wire[1] = 'p';
    wire[2] = 'u';
    wire[3] = '2';
    wire[4] = ':';
    for (uint32_t word = 0; word < CPU_FRAME_WORDS; ++word) {
        uint32_t value = fields[word];
        for (uint32_t byte = 0; byte < 4u; ++byte) {
            uint8_t octet = (uint8_t)((value >> (8u * byte)) & 0xffu);
            uint32_t at = 4u * word + byte;
            wire[CPU_WIRE_MARKER_BYTES + 2u * at] = hex[octet >> 4];
            wire[CPU_WIRE_MARKER_BYTES + 2u * at + 1u] = hex[octet & 15u];
        }
    }
    wire[CPU_WIRE_BYTES - 1u] = '\0';
    return 1;
}

int cpu_counter_address(uint32_t *out) {
    if (!out) return 0;
    *out = CPU_CFG_COUNTER;
    return 1;
}

/* Native provider: fixed addresses only, no external address/count selector.
 * This is the default provider a later qualified integration binds. */
int cpu_native_read(void *context, uint32_t *value) {
    (void)context;
    if (!value) return 0;
    *value = READ32(CPU_CFG_COUNTER);
    return 1;
}
