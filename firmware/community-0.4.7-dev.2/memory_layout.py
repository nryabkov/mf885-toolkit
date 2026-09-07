"""Exact-stock BSS/stack allocation evidence; no device I/O or mapping claim."""
import hashlib, struct
STATE = 0x070ad234
END_LITERAL = 0x4b5b90
STACK_SOURCE = 0x8e5914
STOCK_SHA = 'd51fb378d8ccf68662174f39d6b8c4f6be5571280790bc3a4dc4a9e8a967078c'
SLICES = (
 (0x4,8,'1468a5c21407ae835dae9954d65123cf12e691bbbf1775c37b448d40df9e7074'),
 (0x7ed5c4,288,'b7a8af74d1033ea41e55460df8843ec605618a2cd7258588f6189da16e1198a7'),
 (0x7ed654,112,'1c360d4ce73fe529d929c82bd0ef90fa22bdd5afc11fb98a3be832a8f3b37a42'),
 (0x7ed704,4,'09bdc64815b08b3c63fdb3c6a1f138a1345738f08863ede4b5a7dbd4af708561'),
 (0x8e5914,4,'2bff43c054c827182cd3645adf20c9cd831376a18edabd9558aab1c6e226c11d'),
 (0x4a944c,440,'4592d7305e7040fee526a0fc5c6eee3632072c42e80093888193cc95c30ef7ec'),
 (0x4a9538,4,'ba94db32a80039b89ccdd3fc2aa0b6f680f60e8f5fe34e80496ad94620ce8aa5'),
 (0x4b5b34,88,'ded6d7b6abc750dabb540b094295fb9fd5d3307c40e5d1fe8f59f174c8c48da4'),
 (0x4b5b8c,48,'c11ca639a45bd95c91d5d4695e75f0c56835d41967f47b8f09a39a537d98f580'),
 (0x44e280,84,'f8983c95a4b6480c8eeadde47960b19928542adc0c610c1e3b7e499b3606cda8'),
)
class Error(ValueError): pass
def check(ok, why):
 if not ok: raise Error(why)
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def references(b,value):
 needle=struct.pack('<I',value);out=[];offset=0
 while True:
  offset=b.find(needle,offset)
  if offset<0:return out
  out.append(offset);offset+=1

def inspect(stock):
 check(len(stock)==9648064 and hashlib.sha256(stock).hexdigest()==STOCK_SHA,'exact golden OSLO required')
 for offset,size,pin in SLICES:check(hashlib.sha256(stock[offset:offset+size]).hexdigest()==pin,'stock initialization pin')
 ranges=[(u32(stock,o),u32(stock,o+4)) for o in range(0x4b5b8c,0x4b5bbc,8)]
 check(ranges==[(0x0697c4ac,STATE),(0x101c8,0x141fc),(0x07934000,0x079341f0),(0x07201300,0x0790bbc0),(0x0794d3f8,0x079fe060),(0x07cd0048,0x07d44680)],'zero ranges')
 check(u32(stock,STACK_SOURCE)==STATE and u32(stock,0x7ed704)==0x068e5914,'stack source')
 aligned=(STATE+7)&~7
 check(STATE%4==0 and aligned==STATE+4,'exact four-byte alignment gap')
 refs={hex(a):references(stock,a) for a in (STATE,STATE+4,STATE+8,STATE-4,0x068e5914)}
 check(refs=={hex(STATE):[END_LITERAL,STACK_SOURCE],hex(STATE+4):[],hex(STATE+8):[],hex(STATE-4):[],hex(0x068e5914):[0x7ed704]},'absolute references changed')
 return {'schema':'mf885-047d2-bss-reservation/v1','stock_sha256':STOCK_SHA,'state_start':STATE,'state_end_exclusive':aligned,'bytes':4,'zero_end_literal_offset':END_LITERAL,'old_zero_length':STATE-ranges[0][0],'new_zero_length':aligned-ranges[0][0], 'stock_zero_ranges':ranges,'stack_source_unchanged':True,'initial_stacks':[[aligned+1000*i,aligned+1000*(i+1)] for i in range(3)],'absolute_reference_offsets':refs,'slices':[{'offset':o,'bytes':n,'sha256':h} for o,n,h in SLICES], 'limits':['Derived-address aliases and complete later MMU mappings are not exhaustively reconstructed.','Early startup entry, stack setup and direct zero-init caller are pinned; all intermediate callees/tasks are not audited.','Device qualification of this new reservation remains required.']}

def reserve(stock):
 report=inspect(stock);out=bytearray(stock);struct.pack_into('<I',out,END_LITERAL,STATE+4)
 check(out[:END_LITERAL]==stock[:END_LITERAL] and out[END_LITERAL+4:]==stock[END_LITERAL+4:],'reservation changed unrelated bytes')
 check(out[STACK_SOURCE:STACK_SOURCE+4]==stock[STACK_SOURCE:STACK_SOURCE+4],'stack boundary moved')
 return bytes(out),report
