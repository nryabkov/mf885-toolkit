target triple = "thumbv7-none-eabi"

; Phase-3 diagnostic discriminator.  Parse the current request tree through
; the exact stock pin_puk helpers, accept only command=ttl,arg=x, and return
; zero on every path.  Borrowed tree values are never freed.  There is no
; property getter/setter, custom-state access, packet hook, or other store.
define i32 @diagnostic_context_no_store_post_set(i32 %phase, ptr %context) #0 {
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
  %command.name = inttoptr i32 100668464 to ptr
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
  %arg.name = inttoptr i32 100668472 to ptr
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
  %a0 = load volatile i8, ptr %arg, align 1
  %a0.valid = icmp eq i8 %a0, 120
  br i1 %a0.valid, label %arg.end, label %done

arg.end:
  %ap1 = getelementptr i8, ptr %arg, i32 1
  %a1 = load volatile i8, ptr %ap1, align 1
  %arg.valid = icmp eq i8 %a1, 0
  br i1 %arg.valid, label %accepted.proof.read, label %done

accepted.proof.read:
  ; Keep the final NUL condition in emitted code without creating a state
  ; write: repeat one already-proved readable context-type load and discard it.
  %proof.type = load volatile i16, ptr %context, align 2
  br label %done

done:
  ret i32 0
}

attributes #0 = { nounwind minsize noinline "frame-pointer"="none" "target-cpu"="cortex-a9" "target-features"="+thumb-mode,+thumb2,-neon,-vfp2" }
