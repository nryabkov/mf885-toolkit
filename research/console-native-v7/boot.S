.syntax unified
.arch armv5te
.thumb
.section .text,"ax",%progbits
.global placement_init
.type placement_init,%function
.thumb_func
placement_init:
 push {r4,lr}
 bl original_init
 movs r4,r0
 ldr r0,=0x0696b3c4
 ldr r1,=8192
 ldr r3,=0x0644e280
 blx r3
 movs r0,r4
 pop {r4,pc}
.size placement_init,.-placement_init
.type original_init,%function
.thumb_func
original_init:
 push {r4,r5,r6,lr}
 ldr r5,=0x06940000
 ldr r4,=0x068edc2c
 ldr r6,=0x0003c4ac
 ldr r3,=0x064b5c59
 bx r3
.size original_init,.-original_init
.ltorg

/* Exact overwritten stock prefixes; all arguments survive the entry detours. */
.global cc_original_parser
.type cc_original_parser,%function
.thumb_func
cc_original_parser:
 push {r0,r1,r2,r4,r5,r6,r7,lr}
 movs r6,r0
 movs r4,r1
 sub sp,#508
 ldr r3,=0x0658d7a5
 bx r3
.size cc_original_parser,.-cc_original_parser
.global cc_original_response
.type cc_original_response,%function
.thumb_func
cc_original_response:
 push {r0,r1,r2,r3,r4,r5,r6,r7,lr}
 lsls r5,r0,#12
 sub sp,#508
 movs r4,r3
 sub sp,#508
 ldr r3,=0x063d1915
 bx r3
.size cc_original_response,.-cc_original_response
.ltorg

/* The eight-byte detour already saved {r4, original LR}. Preserve its return
 * while passing the original call-site LR as the fourth diagnostic argument.
 * Both frames are8bytes, keeping AAPCS8-byte alignment at the C call. */
.global cc_parser_entry
.type cc_parser_entry,%function
.thumb_func
cc_parser_entry:
 push {r4,lr}
 ldr r3,[sp,#12]
 bl cc_parser
 pop {r4,pc}
.size cc_parser_entry,.-cc_parser_entry
