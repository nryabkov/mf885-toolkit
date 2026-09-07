target triple = "thumbv5te-none-eabi"

; Sample one aligned owned RAM word per packet. Zero word means boot default64.
; Nonzero word packs revision24 and target8 (target0 is Off).
; Packet bytes are read and written individually; checksum bytes precede TTL.
; No atomic packet-word claim: caller owns the packet until output is called.
; Configuration is sampled once before packet inspection. Output ABI is unchanged.
define i32 @ttl_forward_configurable_armv5(ptr %iphdr, ptr %pbuf, ptr %outnetif) #0 {
entry:
  %output.slot = getelementptr i8, ptr %outnetif, i32 88
  %output = load ptr, ptr %output.slot, align 4
  %statep = inttoptr i32 118149684 to ptr
  %word = load volatile i32, ptr %statep, align 4
  %boot = icmp eq i32 %word, 0
  %stored = and i32 %word, 255
  %target32 = select i1 %boot, i32 64, i32 %stored
  %target8 = trunc i32 %target32 to i8
  %enabled = icmp ne i8 %target8, 0
  br i1 %enabled, label %validate, label %send

validate:
  %vihl = load i8, ptr %iphdr, align 1
  %version = lshr i8 %vihl, 4
  %isv4 = icmp eq i8 %version, 4
  %ihl = and i8 %vihl, 15
  %ihl.ok = icmp uge i8 %ihl, 5
  %valid2 = and i1 %isv4, %ihl.ok
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
  %oldttl = load volatile i8, ptr %wordp, align 1
  %oldttl32 = zext i8 %oldttl to i32
  %forwardable = icmp uge i32 %oldttl32, 2
  br i1 %forwardable, label %compare, label %send

compare:
  %same = icmp eq i32 %oldttl32, %target32
  br i1 %same, label %send, label %checksum

checksum:
  %protocolp = getelementptr i8, ptr %iphdr, i32 9
  %protocol8 = load volatile i8, ptr %protocolp, align 1
  %protocol.byte = zext i8 %protocol8 to i32
  %hchip = getelementptr i8, ptr %iphdr, i32 10
  %hclop = getelementptr i8, ptr %iphdr, i32 11
  %hchi8 = load volatile i8, ptr %hchip, align 1
  %hclo8 = load volatile i8, ptr %hclop, align 1
  %hc.hi = zext i8 %hchi8 to i32
  %hc.lo = zext i8 %hclo8 to i32
  %hc.hi.shift = shl i32 %hc.hi, 8
  %hc = or i32 %hc.hi.shift, %hc.lo
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
  %newhc.hi8 = trunc i32 %newhc.hi to i8
  %newhc.lo8 = trunc i32 %newhc to i8
  store volatile i8 %newhc.hi8, ptr %hchip, align 1
  store volatile i8 %newhc.lo8, ptr %hclop, align 1
  store volatile i8 %target8, ptr %wordp, align 1
  br label %send

send:
  %destination = inttoptr i32 117621068 to ptr
  %result = call i32 %output(ptr %outnetif, ptr %pbuf, ptr %destination)
  ret i32 %result
}

attributes #0 = { nounwind minsize noinline "frame-pointer"="none" "target-cpu"="arm926ej-s" "target-features"="+thumb-mode,-thumb2,-neon,-vfp2,+strict-align" }
