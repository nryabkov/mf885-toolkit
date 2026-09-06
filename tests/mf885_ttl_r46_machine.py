"""Numeric ARMv5 Thumb1 component/ABI model; never executes stock callees.

Independent of LLVM and the builder's pin/layout parser. External XML/property
helpers are modeled at their pinned ABI boundary, not claimed as hardware proof.
"""
import struct
import mf885_thumb1_chain_model as base
STATE=0x060014a0
STOP=0x25000000
FIELD=0x064349ef
TEXT=0x06434e9f
PUBLISH=0x064073db

class Instructions(base.Machine):
    def step(self):
        pc=self.r[15]
        assert any(a<=pc and pc+2<=z for a,z in self.code),('outside code',hex(pc))
        start,b,_,_=self.region(pc,2);op=int.from_bytes(b[pc-start:pc-start+2],'little')
        kind=(op>>6)&15
        if op&0xfc00==0x4000 and kind in (3,13):
            self.trace.append(pc);rd=op&7;rs=(op>>3)&7;x=self.r[rd];y=self.r[rs]
            if kind==13:
                value=(x*y)&0xffffffff
                # C/V are not consumed before subsequent flag-setting ops.
                self.C=not self.C;self.V=not self.V
            else:
                amount=y&255
                if amount==0:value=x
                elif amount<32:self.C=bool((x>>(amount-1))&1);value=x>>amount
                elif amount==32:self.C=bool(x>>31);value=0
                else:self.C=False;value=0
            self.r[rd]=self.nz(value);self.advance(pc+2)
        elif op&0xff00==0x4600:
            self.trace.append(pc);kind=(op>>8)&3;rd=(op&7)|((op>>4)&8);rs=(op>>3)&15
            assert kind==2 and rd!=15 and rs!=15,('unsupported high register operation',hex(op))
            self.r[rd]=self.r[rs];self.advance(pc+2)
        elif op&0xf800==0xa800:
            self.trace.append(pc);self.r[(op>>8)&7]=(self.r[13]+4*(op&255))&0xffffffff;self.advance(pc+2)
        elif op&0xfe00==0x5c00:
            self.trace.append(pc);rd=op&7;rn=(op>>3)&7;rm=(op>>6)&7
            self.r[rd]=self.read((self.r[rn]+self.r[rm])&0xffffffff,1);self.advance(pc+2)
        else:super().step()

class ForwardMachine(Instructions):
    BODY_BYTES=140
    EXECUTABLE_BYTES=126
    OUTPUT_RETURN_OFFSET=124
    PACKET_WRITE_PLAN=((10,1),(11,1),(8,1))
    def __init__(self,helper,packet,*,target,**kwargs):
        super().__init__(helper,packet,**kwargs)
        self.map(STATE,bytes((target,)),True,'state')
    def read(self,address,width):
        if self.region(address,width)[3]=='packet':assert width==1,('wide packet read',address,width)
        return super().read(address,width)
    def write(self,address,width,value):
        if self.region(address,width)[3]=='packet':assert width==1,('wide packet write',address,width)
        assert self.region(address,width)[3]!='state','forward writes configuration'
        return super().write(address,width,value)

class CallbackMachine(Instructions):
    def __init__(self,kind,body,data,*,target=64,generation=0,phase=None,command=b'ttl',argument=b'65',
                 context_present=True,context_type=1,tree_present=True,missing=None,publish_failure=False):
        assert kind in ('set','get')
        self.kind=kind;self.entry=0x06001340 if kind=='set' else 0x06001520
        self.r=[0xc9000000+i for i in range(16)];self.r[0]=(3 if kind=='set' else 4) if phase is None else phase
        self.context=0x21000000;self.tree=0x21000100
        self.r[1]=self.context if context_present else 0;self.r[13]=0x24001000;self.r[14]=STOP|1;self.r[15]=self.entry
        self.original=self.r.copy();self.N=self.Z=self.C=self.V=False
        self.regions=[];self.reads=[];self.writes=[];self.trace=[];self.calls=[];self.published=None;self.publish_failure=publish_failure
        self.code=((self.entry,self.entry+(212 if kind=='set' else 112)),)
        assert len(body)==(224 if kind=='set' else 128)
        self.map(self.entry,body,False,'code')
        memory=bytearray(data);memory[0]=target;struct.pack_into('<I',memory,4,generation)
        self.map(STATE,memory,True,'state')
        self.map(0x24000000,bytes(4096),True,'stack')
        ctx=bytearray(16);struct.pack_into('<H',ctx,0,context_type);struct.pack_into('<I',ctx,12,self.tree if tree_present else 0)
        self.map(self.context,ctx,False,'context')
        self.fields={};self.nodes={};self.missing=missing
        for i,(name,raw) in enumerate((('command',command),('arg',argument))):
            node=0x21000200+i*0x100;slot=node+0x10;value=node+0x20
            if raw is not None:
                self.fields[name]=node;self.nodes[node]=(name,slot)
                self.map(slot,struct.pack('<I',0 if missing==name+'_value' else value),False,'slot')
                self.map(value,raw+b'\0',False,'borrowed')
    def cstring(self,address,limit=64):
        out=bytearray()
        for i in range(limit):
            v=self.read(address+i,1)
            if v==0:return bytes(out)
            out.append(v)
        raise AssertionError('unterminated ABI string')
    def branch_exchange(self,target,link=False):
        if target==STOP|1 and not link:self.r[15]=STOP;return
        assert link and target in (FIELD,TEXT,PUBLISH),('unexpected external ABI',hex(target),link)
        assert self.r[13]%8==0,'misaligned external stack'
        ret=(self.r[15]+2)|1;args=self.r[:4];self.calls.append((target,tuple(args),ret))
        if target==FIELD:
            assert self.kind=='set' and args[0]==self.tree
            name=self.cstring(args[1]).decode();assert name in ('command','arg')
            value=self.fields.get(name,0)
        elif target==TEXT:
            assert self.kind=='set' and args[0] in self.nodes
            name,slot=self.nodes[args[0]];value=0 if self.missing==name+'_text' else slot
        else:
            assert self.kind=='get' and args[:3]==[0x068de3ef,0,STATE+20]
            assert self.cstring(args[2])==b'output'
            output=self.cstring(args[3],16)
            if not self.publish_failure:self.published=output
            value=1 if self.publish_failure else 0
        for i in (0,1,2,3,12):self.r[i]=0xeeee0000+i
        self.r[14]=0xbbbb0000;self.N=True;self.Z=False;self.C=True;self.V=True
        self.r[0]=value;self.r[15]=ret&~1
    def run(self):
        for _ in range(600):
            if self.r[15]==STOP:break
            self.step()
        else:raise AssertionError('callback instruction budget')
        assert self.r[15]==STOP and self.r[0]==0
        assert self.r[4:12]==self.original[4:12] and self.r[13]==self.original[13], 'callback ABI preservation'
        start,data,_,_=self.region(STATE,96)
        return bytes(data)
