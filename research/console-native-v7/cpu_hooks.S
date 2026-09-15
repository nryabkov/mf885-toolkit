/* ARM9 ARMv5TE LE EABI. Preserve live registers, flags and exact incoming SP.
 * r4 holds the frame while the C call uses an independently aligned stack.
 * The C wrappers validate the published arena and mask I/F for all accounting.
 */
.syntax unified
.arch armv5te
.arm
.text
.balign 4
.macro SAVE
 push {r0-r4,r12,lr}
 mrs r0,cpsr
 push {r0}
 mov r4,sp
 bic sp,sp,#7
.endm
.macro RESTORE
 mov sp,r4
 pop {r0}
 msr cpsr_f,r0
 pop {r0-r4,r12,lr}
.endm
.global cpu_hook_arm_begin
.type cpu_hook_arm_begin,%function
cpu_hook_arm_begin:
 SAVE
 blx cc_cpu_begin
 RESTORE
 ldr r2,=0x0695e0d8
 ldr pc,=0x067e1ba0
.size cpu_hook_arm_begin,.-cpu_hook_arm_begin
.ltorg
.global cpu_hook_arm_end
.type cpu_hook_arm_end,%function
cpu_hook_arm_end:
 msr cpsr_fsxc,r1
 SAVE
 blx cc_cpu_end
 RESTORE
 ldr pc,=0x067e1bc8
.size cpu_hook_arm_end,.-cpu_hook_arm_end
.ltorg
.global cpu_hook_arm_exit
.type cpu_hook_arm_exit,%function
cpu_hook_arm_exit:
 SAVE
 blx cc_cpu_end
 RESTORE
 /* Tail-call the exact original Thumb function, keeping BL-site LR. Stock
  * caller saves r0-r3,ip,lr; the callee obtains its own input from globals. */
 ldr ip,=0x06085073
 bx ip
.size cpu_hook_arm_exit,.-cpu_hook_arm_exit
.ltorg
