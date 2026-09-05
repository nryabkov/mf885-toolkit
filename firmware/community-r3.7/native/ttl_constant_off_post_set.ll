target triple = "thumbv7-none-eabi"

; Community R3.7 is a return-path discriminator, not a TTL implementation.
; On the exact external SET phase it publishes one constant value on the same
; diagnostic model.  Both strings are stack-local: there is no custom state,
; low-page data access, getter, free, GET callback or forwarding hook.
define i32 @ttl_constant_off_post_set(i32 %phase, ptr %context) #0 {
entry:
  %is.external.set = icmp eq i32 %phase, 3
  br i1 %is.external.set, label %publish, label %done

publish:
  %field = alloca [8 x i8], align 4
  %value = alloca [4 x i8], align 4
  %field.head = getelementptr [8 x i8], ptr %field, i32 0, i32 0
  %field.tail = getelementptr [8 x i8], ptr %field, i32 0, i32 4
  %value.head = getelementptr [4 x i8], ptr %value, i32 0, i32 0
  store volatile i32 1886680431, ptr %field.head, align 4
  store volatile i32 29813, ptr %field.tail, align 4
  store volatile i32 6710895, ptr %value.head, align 4
  %setter = inttoptr i32 104887259 to ptr
  %model = inttoptr i32 109962223 to ptr
  %ignored = call i32 %setter(ptr %model, i32 0, ptr %field.head, ptr %value.head)
  br label %done

done:
  ret i32 0
}

attributes #0 = { nounwind minsize noinline "frame-pointer"="none" "target-cpu"="cortex-a9" "target-features"="+thumb-mode,+thumb2,-neon,-vfp2" }
