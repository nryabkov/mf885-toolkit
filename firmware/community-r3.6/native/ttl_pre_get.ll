target triple = "thumbv7-none-eabi"

; Community R3.6 publishes exactly one field on the same Duster model before
; the bounded core GET region.  This is the minimal functional combination not
; exercised by R3.2 (three fields) or R3.5 (one field after core GET).
define i32 @ttl_pre_get(i32 %phase, ptr %context) #0 {
entry:
  %is.external.get = icmp eq i32 %phase, 4
  br i1 %is.external.get, label %read, label %done.zero

read:
  %digits = alloca [4 x i8], align 4
  %statep = inttoptr i32 100668464 to ptr
  %state = load volatile i8, ptr %statep, align 1
  %off = icmp eq i8 %state, 0
  br i1 %off, label %publish.off, label %format.hundreds

format.hundreds:
  %state32 = zext i8 %state to i32
  %at.least.200 = icmp uge i32 %state32, 200
  %after.200 = sub i32 %state32, 200
  %at.least.100 = icmp uge i32 %state32, 100
  %after.100 = sub i32 %state32, 100
  %hundreds = select i1 %at.least.200, i32 2, i32 1
  %remainder.100 = select i1 %at.least.200, i32 %after.200, i32 %after.100
  %has.hundreds = select i1 %at.least.200, i1 true, i1 %at.least.100
  %remainder = select i1 %has.hundreds, i32 %remainder.100, i32 %state32
  br label %tens.loop

tens.loop:
  %tens = phi i32 [ 0, %format.hundreds ], [ %tens.next, %tens.more ]
  %ones = phi i32 [ %remainder, %format.hundreds ], [ %ones.next, %tens.more ]
  %has.ten = icmp uge i32 %ones, 10
  br i1 %has.ten, label %tens.more, label %digits.store

tens.more:
  %tens.next = add i32 %tens, 1
  %ones.next = sub i32 %ones, 10
  br label %tens.loop

digits.store:
  %digit0 = getelementptr [4 x i8], ptr %digits, i32 0, i32 0
  %digit1 = getelementptr [4 x i8], ptr %digits, i32 0, i32 1
  %digit2 = getelementptr [4 x i8], ptr %digits, i32 0, i32 2
  %digit3 = getelementptr [4 x i8], ptr %digits, i32 0, i32 3
  %hundreds.ascii = add i32 %hundreds, 48
  %hundreds.byte = trunc i32 %hundreds.ascii to i8
  %tens.ascii = add i32 %tens, 48
  %tens.byte = trunc i32 %tens.ascii to i8
  %ones.ascii = add i32 %ones, 48
  %ones.byte = trunc i32 %ones.ascii to i8
  br i1 %has.hundreds, label %digits.three, label %digits.no.hundreds

digits.three:
  store i8 %hundreds.byte, ptr %digit0, align 4
  store i8 %tens.byte, ptr %digit1, align 1
  store i8 %ones.byte, ptr %digit2, align 2
  store i8 0, ptr %digit3, align 1
  br label %publish

digits.no.hundreds:
  %has.tens = icmp ne i32 %tens, 0
  br i1 %has.tens, label %digits.two, label %digits.one

digits.two:
  store i8 %tens.byte, ptr %digit0, align 4
  store i8 %ones.byte, ptr %digit1, align 1
  store i8 0, ptr %digit2, align 2
  br label %publish

digits.one:
  store i8 %ones.byte, ptr %digit0, align 4
  store i8 0, ptr %digit1, align 1
  br label %publish

publish.off:
  %off.value = inttoptr i32 100668504 to ptr
  br label %publish

publish:
  %value = phi ptr [ %off.value, %publish.off ], [ %digits, %digits.three ], [ %digits, %digits.two ], [ %digits, %digits.one ]
  %setter = inttoptr i32 104887259 to ptr
  %model = inttoptr i32 109962223 to ptr
  %output.field = inttoptr i32 100668492 to ptr
  %result = call i32 %setter(ptr %model, i32 0, ptr %output.field, ptr %value)
  ret i32 %result

done.zero:
  ret i32 0
}

attributes #0 = { nounwind minsize noinline "frame-pointer"="none" "target-cpu"="cortex-a9" "target-features"="+thumb-mode,+thumb2,-neon,-vfp2" }
