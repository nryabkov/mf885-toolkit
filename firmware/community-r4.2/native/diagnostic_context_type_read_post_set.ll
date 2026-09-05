target triple = "thumbv7-none-eabi"

; Read only context.type when phase == 3 and context is non-null.
; Volatile keeps the diagnostic load even though every path returns zero.
; This is a guarded access probe, not a type check or a TTL implementation.
define i32 @diagnostic_context_type_read_post_set(i32 %phase, ptr %context) #0 {
entry:
  %phase_ok = icmp eq i32 %phase, 3
  %context_ok = icmp ne ptr %context, null
  %can_read = and i1 %phase_ok, %context_ok
  br i1 %can_read, label %read_type, label %return_zero

read_type:
  %context_type = load volatile i16, ptr %context, align 2
  br label %return_zero

return_zero:
  ret i32 0
}

attributes #0 = { nounwind minsize noinline "frame-pointer"="none" "target-cpu"="cortex-a9" "target-features"="+thumb-mode,+thumb2,-neon,-vfp2" }
