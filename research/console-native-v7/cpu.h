#ifndef MF885_CONSOLE_CPU_V1_H
#define MF885_CONSOLE_CPU_V1_H
#include <stdint.h>

/* Native CPU idle accounting over the stock timer1 (88MP1802, ARM9 ARMv5TE
 * Thumb1 LE EABI5 soft-float). This is an UNQUALIFIED core: it defines the
 * sampling contract, the bounded counter read and the fixed wire codec. It
 * never claims hardware qualification, a hardware-proven counter width or a
 * measured frequency; see README.md for the exact preconditions.
 *
 * There is deliberately NO caller-supplied address, length or selector here.
 * The only readable register is the fixed 32-bit timer1 counter at 0xd408002c,
 * reached through one fixed configuration gate. A caller can only begin an
 * idle interval, end it, or read/serialize the retained snapshot.
 */

/* Wire: marker "cpu2:", lowercase hex, one char per nibble. Frame fields, all
 * little-endian u32 and in this exact order:
 *   version, flags, epoch, frequency_hz, total_low, total_high,
 *   idle_low, idle_high, read_errors, transitions.
 * 10 words = 40 bytes -> visible 5 + 2*40 = 85 chars, buffer 86 with NUL. */
#define CPU_WIRE_MARKER "cpu2:"
#define CPU_WIRE_MARKER_BYTES 5u
#define CPU_FRAME_WORDS 10u
#define CPU_FRAME_BYTES (4u * CPU_FRAME_WORDS)
#define CPU_WIRE_VISIBLE_BYTES (CPU_WIRE_MARKER_BYTES + 2u * CPU_FRAME_BYTES)
#define CPU_WIRE_BYTES (CPU_WIRE_VISIBLE_BYTES + 1u)

/* Layout version. Bump only with a reviewed format change. */
#define CPU_VERSION 1u

/* WARMING: epoch has no elapsed ticks yet. VALID: elapsed ticks exist.
 * UNAVAILABLE: configuration, read, or continuity check failed. */
#define CPU_FLAG_WARMING 0x01u
#define CPU_FLAG_VALID 0x02u
#define CPU_FLAG_UNAVAILABLE 0x04u
#define CPU_FLAG_KNOWN_MASK 0x07u

/* Firmware-intended mode1 frequency (32768 Hz). This is the firmware contract,
 * NOT a hardware measurement. The counter frequency still requires physical calibration. */
#define CPU_FREQUENCY_MODE1_HZ 32768u

/* Bounded consecutive-equal-read attempts. No write, no capture-mode trigger. */
#define CPU_READ_ATTEMPTS 16u

/* Fixed configuration addresses. Internal only; never exposed as parameters. */
#define CPU_CFG_CONFIG 0xd4080000u /* clock select: (value >> 2) & 7 == 1 */
#define CPU_CFG_PRELOAD_CONTROL 0xd408005cu /* must read 0 */
#define CPU_CFG_PRELOAD_VALUE 0xd4080050u   /* must read 0 */
#define CPU_CFG_ENABLE 0xd4080084u          /* bit1 set == timer1 enabled */
#define CPU_CFG_COUNTER 0xd408002cu         /* 32-bit counter; continuity unqualified */
#define CPU_CFG_CMR 0xd4080088u             /* bit1 optionally pinned 0 (type2) */

/* Guard: the existing stock ARM IRQ save/restore. Reads run only between
 * ENTER and LEAVE so I/F are masked and the previous state is restored.
 * The host test build routes the same operations through a recording seam so
 * tests can prove enter/leave symmetry without executing stock code. */
#ifdef MF885_CPU_HOST_TEST
uint32_t cpu_host_guard_enter(void);
void cpu_host_guard_leave(uint32_t saved);
#define CPU_GUARD_ENTER() cpu_host_guard_enter()
#define CPU_GUARD_LEAVE(saved) cpu_host_guard_leave(saved)
#else
#define CPU_GUARD_ENTER() ((uint32_t (*)(void))(uintptr_t)0x06426160u)()
#define CPU_GUARD_LEAVE(saved) ((void (*)(uint32_t))(uintptr_t)0x06426178u)(saved)
#endif

/* One fixed read provider: fills an internal 32-bit word. It receives no
 * address, no length and no selector. Returns 1 only on a bounded success and
 * leaves *value untouched otherwise. */
typedef int (*cpu_read_fn)(void *context, uint32_t *value);

/* Zeroed state is "uninitialized, nothing available" and serializes as an
 * all-unavailable warming frame with zeroed counters. No pointers, no heap. */
typedef struct {
    uint32_t flags;
    uint32_t epoch;
    uint32_t frequency_hz;
    uint32_t last_tick;      /* last accepted counter value              */
    uint32_t total_low, total_high;
    uint32_t idle_low, idle_high;
    uint32_t read_errors;    /* saturating                              */
    uint32_t transitions;    /* saturating                              */
    uint32_t open;           /* an idle interval is currently open      */
    uint32_t have_tick;      /* last_tick holds a valid sample          */
} cpu_state;

/* Zero an uninitialized state. Safe on any state; no read, no config probe. */
void cpu_init(cpu_state *state);

/* All state sampling/mutation is guarded. Transitions are idempotent. Total
 * includes busy and idle elapsed time; idle counts only the previous open
 * state. Failed reads invalidate the epoch; the next successful sample starts
 * fresh counters with a new epoch. Snapshot accrues pending elapsed once. */
void cpu_idle_begin(cpu_state *state, cpu_read_fn read, void *context);
void cpu_idle_end(cpu_state *state, cpu_read_fn read, void *context);
void cpu_snapshot(cpu_state *state, cpu_read_fn read, void *context, cpu_state *out);

/* Serialize a snapshot only. Never reads a register, never captures, never
 * resets. Writes exactly CPU_WIRE_BYTES including the terminator. Returns 1 on
 * success, 0 for a null/short target or an unknown flag bit. */
int cpu_serialize(const cpu_state *state, char *wire, uint32_t capacity);

/* Internal-only geometry for tests: the single fixed counter address. Takes no
 * caller-supplied selector. Returns 1 and the fixed address, or 0 for null. */
int cpu_counter_address(uint32_t *out);

/* Default native provider: reads only the fixed counter address. No external
 * address or count selector. A later qualified integration binds this one. */
int cpu_native_read(void *context, uint32_t *value);

#endif
