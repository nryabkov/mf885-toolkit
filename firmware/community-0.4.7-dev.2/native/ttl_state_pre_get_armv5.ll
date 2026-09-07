target triple = "thumbv5te-none-eabi"

; Phase4 publishes r47:00RRRRRR:TT from one aligned RAM snapshot.
; GET never mutates global state. Revision counts serialized SETs, not reads.
; Zero word means boot default64/revision0. No persistence across reboot.
define i32 @ttl_state_pre_get_armv5(i32 %phase, ptr %context) #0 {
entry:
  %external = icmp eq i32 %phase, 4
  br i1 %external, label %snapshot, label %done
snapshot:
  %buffer = alloca [16 x i8], align 4
  %statep = inttoptr i32 118149684 to ptr
  %word = load volatile i32, ptr %statep, align 4
  %generation = lshr i32 %word, 8
  %stored = trunc i32 %word to i8
  %boot = icmp eq i32 %word, 0
  %state8 = select i1 %boot, i8 64, i8 %stored
  store i32 976696434, ptr %buffer, align 4
  %hex = inttoptr i32 100668604 to ptr
  br label %digits

digits:
  %index = phi i32 [ 0, %snapshot ], [ %next, %digits ]
  %bits = shl i32 %index, 2
  %shift = sub i32 28, %bits
  %shifted = lshr i32 %generation, %shift
  %nibble = and i32 %shifted, 15
  %letterp = getelementptr i8, ptr %hex, i32 %nibble
  %letter = load i8, ptr %letterp, align 1
  %offset = add i32 %index, 4
  %outp = getelementptr i8, ptr %buffer, i32 %offset
  store i8 %letter, ptr %outp, align 1
  %next = add i32 %index, 1
  %more = icmp ult i32 %next, 8
  br i1 %more, label %digits, label %suffix

suffix:
  %state = zext i8 %state8 to i32
  %hi = lshr i32 %state, 4
  %lo = and i32 %state, 15
  %hp = getelementptr i8, ptr %hex, i32 %hi
  %lp = getelementptr i8, ptr %hex, i32 %lo
  %h = load i8, ptr %hp, align 1
  %l = load i8, ptr %lp, align 1
  %colon = getelementptr i8, ptr %buffer, i32 12
  %outh = getelementptr i8, ptr %buffer, i32 13
  %outl = getelementptr i8, ptr %buffer, i32 14
  %end = getelementptr i8, ptr %buffer, i32 15
  store i8 58, ptr %colon, align 1
  store i8 %h, ptr %outh, align 1
  store i8 %l, ptr %outl, align 1
  store i8 0, ptr %end, align 1
  %setter = inttoptr i32 104887259 to ptr
  %model = inttoptr i32 109962223 to ptr
  %field = inttoptr i32 100668596 to ptr
  %result = call i32 %setter(ptr %model, i32 0, ptr %field, ptr %buffer)
  br label %done
done:
  ret i32 0
}

attributes #0 = { nounwind minsize noinline "frame-pointer"="none" "target-cpu"="arm926ej-s" "target-features"="+thumb-mode,-thumb2,-neon,-vfp2,+strict-align" }
