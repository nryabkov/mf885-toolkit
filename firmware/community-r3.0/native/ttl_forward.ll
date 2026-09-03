target triple = "thumbv7-none-eabi"

define i32 @ttl_forward(ptr %iphdr, ptr %pbuf, ptr %outnetif, ptr %output) #0 {
entry:
  %statep = inttoptr i32 110309888 to ptr
  %target = load volatile i8, ptr %statep, align 1
  %enabled = icmp ne i8 %target, 0
  br i1 %enabled, label %validate, label %send

validate:
  %aligned.raw = ptrtoint ptr %iphdr to i32
  %aligned.bits = and i32 %aligned.raw, 3
  %aligned = icmp eq i32 %aligned.bits, 0
  %vihl = load i8, ptr %iphdr, align 1
  %version = lshr i8 %vihl, 4
  %isv4 = icmp eq i8 %version, 4
  %ihl = and i8 %vihl, 15
  %ihl.ok = icmp uge i8 %ihl, 5
  %valid1 = and i1 %aligned, %isv4
  %valid2 = and i1 %valid1, %ihl.ok
  br i1 %valid2, label %length, label %send

length:
  %totp = getelementptr i8, ptr %pbuf, i32 8
  %tot = load i16, ptr %totp, align 2
  %lenp = getelementptr i8, ptr %pbuf, i32 10
  %len = load i16, ptr %lenp, align 2
  %ihl16 = zext i8 %ihl to i16
  %header.bytes = shl i16 %ihl16, 2
  %total.ok = icmp uge i16 %tot, %header.bytes
  %contiguous.ok = icmp uge i16 %len, %header.bytes
  %length.ok = and i1 %total.ok, %contiguous.ok
  br i1 %length.ok, label %change, label %send

change:
  %wordp = getelementptr i8, ptr %iphdr, i32 8
  %oldword = load i32, ptr %wordp, align 4
  %oldttl32 = and i32 %oldword, 255
  %forwardable = icmp uge i32 %oldttl32, 2
  br i1 %forwardable, label %compare, label %send

compare:
  %target32 = zext i8 %target to i32
  %same = icmp eq i32 %oldttl32, %target32
  br i1 %same, label %send, label %checksum

checksum:
  %protocol = and i32 %oldword, 65280
  %hc.hi.raw = lshr i32 %oldword, 16
  %hc.hi = and i32 %hc.hi.raw, 255
  %hc.lo = lshr i32 %oldword, 24
  %hc.hi.shift = shl i32 %hc.hi, 8
  %hc = or i32 %hc.hi.shift, %hc.lo
  %protocol.byte = lshr i32 %protocol, 8
  %oldttl.shift = shl i32 %oldttl32, 8
  %target.shift = shl i32 %target32, 8
  %oldm = or i32 %oldttl.shift, %protocol.byte
  %newm = or i32 %target.shift, %protocol.byte
  %not.hc = xor i32 %hc, 65535
  %not.oldm = xor i32 %oldm, 65535
  %sum1 = add i32 %not.hc, %not.oldm
  %sum2 = add i32 %sum1, %newm
  %sum2.lo = and i32 %sum2, 65535
  %sum2.hi = lshr i32 %sum2, 16
  %fold1 = add i32 %sum2.lo, %sum2.hi
  %fold1.lo = and i32 %fold1, 65535
  %fold1.hi = lshr i32 %fold1, 16
  %fold2 = add i32 %fold1.lo, %fold1.hi
  %newhc.raw = xor i32 %fold2, 65535
  %newhc = and i32 %newhc.raw, 65535
  %newhc.hi = lshr i32 %newhc, 8
  %newhc.hi.byte = and i32 %newhc.hi, 255
  %newhc.lo = and i32 %newhc, 255
  %newhc.hi.mem = shl i32 %newhc.hi.byte, 16
  %newhc.lo.mem = shl i32 %newhc.lo, 24
  %base1 = or i32 %target32, %protocol
  %base2 = or i32 %base1, %newhc.hi.mem
  %commit = or i32 %base2, %newhc.lo.mem
  store volatile i32 %commit, ptr %wordp, align 4
  br label %send

send:
  %destination = inttoptr i32 117621068 to ptr
  %result = call i32 %output(ptr %outnetif, ptr %pbuf, ptr %destination)
  ret i32 %result
}

attributes #0 = { nounwind minsize noinline "frame-pointer"="none" "target-cpu"="cortex-a9" "target-features"="+thumb-mode,+thumb2,-neon,-vfp2" }
