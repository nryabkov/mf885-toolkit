target triple = "thumbv7-none-eabi"

; Phase-3 only.  Read the stock-retained diagnostic command/arg model, update
; one volatile Community state byte for exact valid TTL values, free every
; caller-owned getter result, and return zero.  There is deliberately no
; property setter and no diagnostic.output publication.
define i32 @ttl_command_arg_post_set(i32 %phase, ptr %context) #0 {
entry:
  %is.external.set = icmp eq i32 %phase, 3
  br i1 %is.external.set, label %read, label %done

read:
  %getter = inttoptr i32 104887443 to ptr
  %model = inttoptr i32 100668468 to ptr
  %command.field = inttoptr i32 100668480 to ptr
  %arg.field = inttoptr i32 100668488 to ptr
  %command = call ptr %getter(ptr %model, i32 0, ptr %command.field)
  %arg = call ptr %getter(ptr %model, i32 0, ptr %arg.field)
  %command.present = icmp ne ptr %command, null
  %arg.present = icmp ne ptr %arg, null
  %both.present = and i1 %command.present, %arg.present
  br i1 %both.present, label %command.0, label %cleanup

command.0:
  %c0 = load i8, ptr %command, align 1
  %c0.valid = icmp eq i8 %c0, 116
  br i1 %c0.valid, label %command.1, label %cleanup

command.1:
  %cp1 = getelementptr i8, ptr %command, i32 1
  %c1 = load i8, ptr %cp1, align 1
  %c1.valid = icmp eq i8 %c1, 116
  br i1 %c1.valid, label %command.2, label %cleanup

command.2:
  %cp2 = getelementptr i8, ptr %command, i32 2
  %c2 = load i8, ptr %cp2, align 1
  %c2.valid = icmp eq i8 %c2, 108
  br i1 %c2.valid, label %command.end, label %cleanup

command.end:
  %cp3 = getelementptr i8, ptr %command, i32 3
  %c3 = load i8, ptr %cp3, align 1
  %command.valid = icmp eq i8 %c3, 0
  br i1 %command.valid, label %arg.0, label %cleanup

arg.0:
  %a0 = load i8, ptr %arg, align 1
  %is.o = icmp eq i8 %a0, 111
  br i1 %is.o, label %off.1, label %numeric.0

off.1:
  %offp1 = getelementptr i8, ptr %arg, i32 1
  %off1 = load i8, ptr %offp1, align 1
  %off1.valid = icmp eq i8 %off1, 102
  br i1 %off1.valid, label %off.2, label %cleanup

off.2:
  %offp2 = getelementptr i8, ptr %arg, i32 2
  %off2 = load i8, ptr %offp2, align 1
  %off2.valid = icmp eq i8 %off2, 102
  br i1 %off2.valid, label %off.end, label %cleanup

off.end:
  %offp3 = getelementptr i8, ptr %arg, i32 3
  %off3 = load i8, ptr %offp3, align 1
  %off.valid = icmp eq i8 %off3, 0
  br i1 %off.valid, label %set.off, label %cleanup

numeric.0:
  %n0.low = icmp uge i8 %a0, 49
  %n0.high = icmp ule i8 %a0, 57
  %n0.valid = and i1 %n0.low, %n0.high
  br i1 %n0.valid, label %numeric.1.read, label %cleanup

numeric.1.read:
  %d0 = sub i8 %a0, 48
  %nump1 = getelementptr i8, ptr %arg, i32 1
  %a1 = load i8, ptr %nump1, align 1
  %numeric.one = icmp eq i8 %a1, 0
  br i1 %numeric.one, label %numeric.store.one, label %numeric.1.validate

numeric.store.one:
  %value.one = zext i8 %d0 to i32
  br label %set.numeric

numeric.1.validate:
  %n1.low = icmp uge i8 %a1, 48
  %n1.high = icmp ule i8 %a1, 57
  %n1.valid = and i1 %n1.low, %n1.high
  br i1 %n1.valid, label %numeric.2.read, label %cleanup

numeric.2.read:
  %d0.32 = zext i8 %d0 to i32
  %d1 = sub i8 %a1, 48
  %d1.32 = zext i8 %d1 to i32
  %d0x10 = mul i32 %d0.32, 10
  %value.two = add i32 %d0x10, %d1.32
  %nump2 = getelementptr i8, ptr %arg, i32 2
  %a2 = load i8, ptr %nump2, align 1
  %numeric.two = icmp eq i8 %a2, 0
  br i1 %numeric.two, label %numeric.store.two, label %numeric.2.validate

numeric.store.two:
  br label %set.numeric

numeric.2.validate:
  %n2.low = icmp uge i8 %a2, 48
  %n2.high = icmp ule i8 %a2, 57
  %n2.valid = and i1 %n2.low, %n2.high
  br i1 %n2.valid, label %numeric.3.read, label %cleanup

numeric.3.read:
  %d2 = sub i8 %a2, 48
  %d2.32 = zext i8 %d2 to i32
  %value.two.x10 = mul i32 %value.two, 10
  %value.three = add i32 %value.two.x10, %d2.32
  %nump3 = getelementptr i8, ptr %arg, i32 3
  %a3 = load i8, ptr %nump3, align 1
  %numeric.three.end = icmp eq i8 %a3, 0
  %numeric.three.range = icmp ule i32 %value.three, 255
  %numeric.three.valid = and i1 %numeric.three.end, %numeric.three.range
  br i1 %numeric.three.valid, label %numeric.store.three, label %cleanup

numeric.store.three:
  br label %set.numeric

set.off:
  %state.off = inttoptr i32 100668464 to ptr
  store volatile i8 0, ptr %state.off, align 1
  br label %cleanup

set.numeric:
  %numeric.value = phi i32 [ %value.one, %numeric.store.one ], [ %value.two, %numeric.store.two ], [ %value.three, %numeric.store.three ]
  %numeric.byte = trunc i32 %numeric.value to i8
  %state.numeric = inttoptr i32 100668464 to ptr
  store volatile i8 %numeric.byte, ptr %state.numeric, align 1
  br label %cleanup

cleanup:
  %free = inttoptr i32 105181199 to ptr
  br i1 %command.present, label %free.command, label %free.arg.check

free.command:
  call void %free(ptr %command)
  br label %free.arg.check

free.arg.check:
  br i1 %arg.present, label %free.arg, label %done

free.arg:
  call void %free(ptr %arg)
  br label %done

done:
  ret i32 0
}

attributes #0 = { nounwind minsize noinline "frame-pointer"="none" "target-cpu"="cortex-a9" "target-features"="+thumb-mode,+thumb2,-neon,-vfp2" }
