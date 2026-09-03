target triple = "thumbv7-none-eabi"

define i32 @ttl_post_get(i32 %phase, ptr %context) #0 {
entry:
  %is.external.get = icmp eq i32 %phase, 4
  br i1 %is.external.get, label %read, label %done

read:
  %statep = inttoptr i32 110309888 to ptr
  %state = load volatile i8, ptr %statep, align 1
  %state32 = zext i8 %state to i32
  %slot.offset = shl i32 %state32, 2
  %slot.address = add i32 %slot.offset, 110310144
  %arg = inttoptr i32 %slot.address to ptr
  %off = icmp eq i8 %state, 0
  %output.off = inttoptr i32 110309940 to ptr
  %output.numeric = inttoptr i32 110310016 to ptr
  %output = select i1 %off, ptr %output.off, ptr %output.numeric
  %setter = inttoptr i32 104887259 to ptr
  %model = inttoptr i32 110309892 to ptr
  %command.field = inttoptr i32 110309904 to ptr
  %arg.field = inttoptr i32 110309912 to ptr
  %output.field = inttoptr i32 110309916 to ptr
  %ttl.value = inttoptr i32 110309924 to ptr
  %u0 = call i32 %setter(ptr %model, i32 0, ptr %command.field, ptr %ttl.value)
  %u1 = call i32 %setter(ptr %model, i32 0, ptr %arg.field, ptr %arg)
  %u2 = call i32 %setter(ptr %model, i32 0, ptr %output.field, ptr %output)
  br label %done

done:
  ret i32 0
}

attributes #0 = { nounwind minsize noinline "frame-pointer"="none" "target-cpu"="cortex-a9" "target-features"="+thumb-mode,+thumb2,-neon,-vfp2" }
