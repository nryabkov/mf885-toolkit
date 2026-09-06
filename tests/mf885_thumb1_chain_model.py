"""Independent numeric Thumb-1 subset model. No device/network access.

Models ARMv5 BX/BLX/load-PC interworking at an external ABI callback boundary;
it does not execute that external callee or prove the target hardware ISA.
"""
import struct

A = 0x068ed1ca
ENTRY = 0x060012a0
BODY = ENTRY + 8
CONT = A + 12
HOOK = bytes.fromhex('014b984702e0a1120006c046')
STUB = bytes.fromhex('280031002200ffe7')
MASK = 0xffffffff


def checksum(raw):
    raw += b'\0' * (len(raw) % 2)
    s = sum(struct.unpack('!%dH' % (len(raw)//2), raw))
    while s >> 16:
        s = (s & 65535) + (s >> 16)
    return (~s) & 65535


class Machine:
    # Defaults retain the exact R44 model. New releases subclass these layout
    # and write contracts; the instruction decoder remains independent.
    BODY_BYTES = 148
    EXECUTABLE_BYTES = 140
    OUTPUT_RETURN_OFFSET = 138
    PACKET_WRITE_PLAN = ((8, 4),)

    def __init__(self, helper, packet, *, alignment=0, total=None, contiguous=None, arm_output=False):
        assert len(helper) == self.BODY_BYTES
        self.packet_address = 0x21000000 + alignment
        self.pbuf = 0x21001000
        self.netif = 0x22000000
        self.output = 0x23000000 if arm_output else 0x23000001
        self.r = [0xc9000000+i for i in range(16)]
        self.r[4:7] = [self.netif, self.packet_address, self.pbuf]
        self.r[13] = 0x24000200
        self.r[14] = 0x25000001
        self.r[15] = A
        self.original = self.r.copy()
        self.N = self.Z = self.C = self.V = False
        self.regions = []
        self.map(A, HOOK, False, 'hook')
        self.map(CONT, bytes.fromhex('0300'), False, 'continuation')
        self.map(ENTRY, STUB+helper, False, 'helper')
        self.map(self.packet_address, packet, True, 'packet')
        self.map(self.pbuf+8, struct.pack('<HH',len(packet) if total is None else total,
                                        len(packet) if contiguous is None else contiguous), False, 'pbuf')
        self.map(self.netif+0x58, struct.pack('<I', self.output), False, 'netif')
        self.map(0x24000000, bytes(512), True, 'stack')
        self.code = ((A,A+6),(CONT,CONT+2),(ENTRY,BODY+self.EXECUTABLE_BYTES))
        self.reads = []
        self.writes = []
        self.trace = []
        self.calls = []
        self.output_return = 0x13579bdf
        self.output_packet = None
        self.packet_length = len(packet)

    def map(self,a,b,w,name):
        self.regions.append((a,bytearray(b),w,name))

    def region(self,a,n):
        for start,b,w,name in self.regions:
            if start <= a and a+n <= start+len(b):
                return start,b,w,name
        raise AssertionError(('unmapped memory',hex(a),n))

    def read(self,a,n):
        start,b,w,name=self.region(a,n)
        if n in (2,4): assert a % n == 0, ('unaligned read',a,n)
        self.reads.append((a,n,name))
        return int.from_bytes(b[a-start:a-start+n],'little')

    def write(self,a,n,v):
        start,b,w,name=self.region(a,n)
        assert w and a % n == 0
        self.writes.append((a,n,name))
        b[a-start:a-start+n]=(v & ((1<<(8*n))-1)).to_bytes(n,'little')

    def packet(self):
        start,b,_,_=self.region(self.packet_address,self.packet_length)
        return bytes(b[self.packet_address-start:self.packet_address-start+self.packet_length])

    def nz(self,v):
        v &= MASK
        self.N=bool(v & 0x80000000); self.Z=v==0
        return v

    def add(self,x,y):
        v=x+y; self.C=v>MASK
        self.V=bool((~(x^y) & (x^(v&MASK))) & 0x80000000)
        return self.nz(v)

    def sub(self,x,y):
        v=(x-y)&MASK; self.C=x>=y
        self.V=bool(((x^y)&(x^v)) & 0x80000000)
        return self.nz(v)

    def branch_exchange(self,target,link=False):
        if link: self.r[14]=(self.r[15]+2)|1
        if (target & ~1)==(self.output & ~1):
            assert target==self.output
            assert self.r[:3]==[self.netif,self.pbuf,0x0702c14c]
            assert self.r[13]%8==0
            assert self.r[14]==(BODY+self.OUTPUT_RETURN_OFFSET)|1
            self.calls.append({'target_thumb':bool(target&1),'return':self.r[14]})
            assert len(self.calls)==1
            self.output_packet=self.packet()
            for i in (0,1,2,3,12): self.r[i]=0xeeee0000+i
            self.N=True;self.Z=False;self.C=False;self.V=True
            self.r[0]=self.output_return
            assert self.r[14]&1
            self.r[15]=self.r[14]&~1
        else:
            assert target&1, ('unexpected ARM execution',hex(target))
            self.r[15]=target&~1

    def step(self):
        pc=self.r[15]
        assert any(a<=pc and pc+2<=z for a,z in self.code), ('literal/outside execution',hex(pc))
        start,b,_,_=self.region(pc,2);op=int.from_bytes(b[pc-start:pc-start+2],'little')
        self.trace.append(pc); nxt=pc+2
        if op&0xf800 in (0x0000,0x0800,0x1000):
            kind=(op>>11)&3; imm=(op>>6)&31; rm=(op>>3)&7;rd=op&7;v=self.r[rm]
            if kind==0:
                if imm:self.C=bool((v>>(32-imm))&1)
                v=v<<imm
            elif kind==1:
                imm=imm or 32; self.C=bool((v>>(imm-1))&1);v=v>>imm
            else:
                imm=imm or 32;self.C=bool((v>>(imm-1))&1)
                v=(v-(1<<32) if v&0x80000000 else v)>>imm
            self.r[rd]=self.nz(v)
        elif op&0xf800==0x1800:
            rd=op&7;rn=(op>>3)&7;rhs=(op>>6)&7
            y=rhs if op&0x400 else self.r[rhs]
            self.r[rd]=(self.sub if op&0x200 else self.add)(self.r[rn],y)
        elif op&0xe000==0x2000:
            k=(op>>11)&3;rd=(op>>8)&7;v=op&255
            if k==0:self.r[rd]=self.nz(v)
            elif k==1:self.sub(self.r[rd],v)
            elif k==2:self.r[rd]=self.add(self.r[rd],v)
            else:self.r[rd]=self.sub(self.r[rd],v)
        elif op&0xfc00==0x4000:
            k=(op>>6)&15;rs=(op>>3)&7;rd=op&7;x=self.r[rd];y=self.r[rs]
            if k==0:v=x&y
            elif k==1:v=x^y
            elif k==10:self.sub(x,y);return self.advance(nxt)
            elif k==14:v=x&~y
            elif k==15:v=~y
            else:raise AssertionError(('unimplemented ALU',hex(op)))
            self.r[rd]=self.nz(v)
        elif op&0xff00==0x4700:
            assert op&7==0
            self.branch_exchange(self.r[(op>>3)&15],bool(op&0x80));return
        elif op&0xf800==0x4800:
            self.r[(op>>8)&7]=self.read(((pc+4)&~3)+(op&255)*4,4)
        elif op&0xe000==0x6000:
            width=1 if op&0x1000 else 4; a=self.r[(op>>3)&7]+((op>>6)&31)*width;rd=op&7
            if op&0x800:self.r[rd]=self.read(a,width)
            else:self.write(a,width,self.r[rd])
        elif op&0xf000==0x8000:
            a=self.r[(op>>3)&7]+((op>>6)&31)*2;rd=op&7
            if op&0x800:self.r[rd]=self.read(a,2)
            else:self.write(a,2,self.r[rd])
        elif op&0xf000==0x9000:
            a=self.r[13]+(op&255)*4;rd=(op>>8)&7
            if op&0x800:self.r[rd]=self.read(a,4)
            else:self.write(a,4,self.r[rd])
        elif op&0xfe00 in (0xb400,0xbc00):
            pop=bool(op&0x800);regs=[i for i in range(8) if op&(1<<i)]
            if op&0x100:regs.append(15 if pop else 14)
            if pop:
                for j,i in enumerate(regs):self.r[i]=self.read(self.r[13]+4*j,4)
                self.r[13]+=4*len(regs)
                if 15 in regs:
                    target=self.r[15];self.branch_exchange(target);return
            else:
                self.r[13]-=4*len(regs)
                for j,i in enumerate(regs):self.write(self.r[13]+4*j,4,self.r[i])
        elif op&0xf000==0xd000:
            cond=(op>>8)&15;assert cond<14
            yes=(self.Z,not self.Z,self.C,not self.C,self.N,not self.N,self.V,not self.V,
                 self.C and not self.Z,not self.C or self.Z,self.N==self.V,self.N!=self.V,
                 not self.Z and self.N==self.V,self.Z or self.N!=self.V)[cond]
            if yes:nxt=pc+4+((op&255)-256 if op&128 else op&255)*2
        elif op&0xf800==0xe000:
            imm=op&2047;nxt=pc+4+(imm-2048 if imm&1024 else imm)*2
        else:raise AssertionError(('not supported Thumb1 opcode',hex(pc),hex(op)))
        self.advance(nxt)

    def advance(self,pc):self.r[15]=pc

    def run(self):
        for _ in range(300):
            pc=self.r[15];self.step()
            if pc==CONT:break
        else:raise AssertionError('instruction budget')
        assert len(self.calls)==1 and self.trace[:5]==[A,A+2,ENTRY,ENTRY+2,ENTRY+4]
        assert self.trace[-2:]==[A+4,CONT]
        assert self.r[4:12]==self.original[4:12] and self.r[13]==self.original[13]
        assert self.r[0]==self.r[3]==self.output_return
        assert self.output_packet==self.packet()
        packet_writes=[(a,n) for a,n,region in self.writes if region!='stack']
        assert packet_writes in ([],[(self.packet_address+offset,width) for offset,width in self.PACKET_WRITE_PLAN])
        return self.packet(),packet_writes


def expected(packet,alignment,total,contiguous):
    value=bytearray(packet);ihl=(value[0]&15)*4
    eligible=not alignment and value[0]>>4==4 and ihl>=20 and total>=ihl and contiguous>=ihl and value[8]>=2
    writes=eligible and value[8]!=64
    if writes:
        value[8]=64;value[10:12]=b'\0\0';value[10:12]=struct.pack('!H',checksum(bytes(value[:ihl])))
    return bytes(value),writes


def sample(ttl,ihl,proto):
    header=bytearray(ihl*4);header[0]=0x40|ihl;header[1]=0x2c
    struct.pack_into('!HHH',header,2,len(header)+8,0x7a32,0x4000)
    header[8:10]=bytes((ttl,proto));header[12:20]=bytes((192,0,2,3,198,51,100,7))
    header[20:]=bytes((i*13)&255 for i in range(len(header)-20))
    header[10:12]=struct.pack('!H',checksum(bytes(header)))
    return bytes(header)+bytes(range(8))
