target triple = "thumbv7-none-eabi"

define i32 @diagnostic_return_zero_low_entry_post_set(i32 %phase, ptr %context) #0 {
entry:
  ret i32 0
}

attributes #0 = { nounwind minsize noinline "frame-pointer"="none" "target-cpu"="cortex-a9" "target-features"="+thumb-mode,+thumb2,-neon,-vfp2" }
