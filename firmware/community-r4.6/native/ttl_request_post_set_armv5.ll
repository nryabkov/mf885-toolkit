target triple = "thumbv5te-none-eabi"

; Parse this request tree only. Borrowed values are never freed.
; Accept exact ttl + off|1..255, then one byte store. No property getter/setter.
define i32 @ttl_request_post_set_armv5(i32 %phase, ptr %context) #0 {
entry:
  %is.phase3 = icmp eq i32 %phase, 3
  %context.present = icmp ne ptr %context, null
  %can.inspect.context = and i1 %is.phase3, %context.present
  br i1 %can.inspect.context, label %context.type, label %done

context.type:
  %type = load i16, ptr %context, align 2
  %is.request.context = icmp eq i16 %type, 1
  br i1 %is.request.context, label %context.tree, label %done

context.tree:
  %tree.slot = getelementptr i8, ptr %context, i32 12
  %tree = load ptr, ptr %tree.slot, align 4
  %tree.present = icmp ne ptr %tree, null
  br i1 %tree.present, label %command.lookup, label %done

command.lookup:
  %field.lookup = inttoptr i32 105073135 to ptr
  %text.child = inttoptr i32 105074335 to ptr
  %command.name = inttoptr i32 100668584 to ptr
  %command.node = call ptr %field.lookup(ptr %tree, ptr %command.name)
  %command.node.present = icmp ne ptr %command.node, null
  br i1 %command.node.present, label %command.child, label %done

command.child:
  %command.value.slot = call ptr %text.child(ptr %command.node)
  %command.slot.present = icmp ne ptr %command.value.slot, null
  br i1 %command.slot.present, label %command.value, label %done

command.value:
  %command = load ptr, ptr %command.value.slot, align 4
  %command.present = icmp ne ptr %command, null
  br i1 %command.present, label %command.0, label %done

command.0:
  %c0 = load i8, ptr %command, align 1
  %c0.valid = icmp eq i8 %c0, 116
  br i1 %c0.valid, label %command.1, label %done

command.1:
  %cp1 = getelementptr i8, ptr %command, i32 1
  %c1 = load i8, ptr %cp1, align 1
  %c1.valid = icmp eq i8 %c1, 116
  br i1 %c1.valid, label %command.2, label %done

command.2:
  %cp2 = getelementptr i8, ptr %command, i32 2
  %c2 = load i8, ptr %cp2, align 1
  %c2.valid = icmp eq i8 %c2, 108
  br i1 %c2.valid, label %command.end, label %done

command.end:
  %cp3 = getelementptr i8, ptr %command, i32 3
  %c3 = load i8, ptr %cp3, align 1
  %command.valid = icmp eq i8 %c3, 0
  br i1 %command.valid, label %arg.lookup, label %done

arg.lookup:
  %arg.name = inttoptr i32 100668592 to ptr
  %arg.node = call ptr %field.lookup(ptr %tree, ptr %arg.name)
  %arg.node.present = icmp ne ptr %arg.node, null
  br i1 %arg.node.present, label %arg.child, label %done

arg.child:
  %arg.value.slot = call ptr %text.child(ptr %arg.node)
  %arg.slot.present = icmp ne ptr %arg.value.slot, null
  br i1 %arg.slot.present, label %arg.value, label %done

arg.value:
  %arg = load ptr, ptr %arg.value.slot, align 4
  %arg.present = icmp ne ptr %arg, null
  br i1 %arg.present, label %arg.0, label %done

arg.0:
  %a0 = load i8, ptr %arg, align 1
  %is.o = icmp eq i8 %a0, 111
  br i1 %is.o, label %off.1, label %numeric.0

off.1:
  %offp1 = getelementptr i8, ptr %arg, i32 1
  %off1 = load i8, ptr %offp1, align 1
  %off1.valid = icmp eq i8 %off1, 102
  br i1 %off1.valid, label %off.2, label %done

off.2:
  %offp2 = getelementptr i8, ptr %arg, i32 2
  %off2 = load i8, ptr %offp2, align 1
  %off2.valid = icmp eq i8 %off2, 102
  br i1 %off2.valid, label %off.end, label %done

off.end:
  %offp3 = getelementptr i8, ptr %arg, i32 3
  %off3 = load i8, ptr %offp3, align 1
  %off.valid = icmp eq i8 %off3, 0
  br i1 %off.valid, label %set.off, label %done

numeric.0:
  %n0.low = icmp uge i8 %a0, 49
  %n0.high = icmp ule i8 %a0, 57
  %n0.valid = and i1 %n0.low, %n0.high
  br i1 %n0.valid, label %numeric.1.read, label %done

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
  br i1 %n1.valid, label %numeric.2.read, label %done

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
  br i1 %n2.valid, label %numeric.3.read, label %done

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
  br i1 %numeric.three.valid, label %numeric.store.three, label %done

numeric.store.three:
  br label %set.numeric

set.off:
  %state.off = inttoptr i32 100668576 to ptr
  store volatile i8 0, ptr %state.off, align 1
  br label %done

set.numeric:
  %numeric.value = phi i32 [ %value.one, %numeric.store.one ], [ %value.two, %numeric.store.two ], [ %value.three, %numeric.store.three ]
  %numeric.byte = trunc i32 %numeric.value to i8
  %state.numeric = inttoptr i32 100668576 to ptr
  store volatile i8 %numeric.byte, ptr %state.numeric, align 1
  br label %done

done:
  ret i32 0
}

attributes #0 = { nounwind minsize noinline "frame-pointer"="none" "target-cpu"="arm926ej-s" "target-features"="+thumb-mode,-thumb2,-neon,-vfp2,+strict-align" }
