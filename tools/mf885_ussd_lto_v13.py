"""Pinned ARM bitcode inspection and single-worker full-LTO linker configuration."""
import ctypes as c
import re,subprocess
from pathlib import Path
from mf885_thumb_llvm_build import LLVM_LIBRARY
ROOTS=('uo_native_init','uo_native_read_begin','uo_native_read_end','uo_native_dispatch','uo_native_track',
 'uo_native_outgoing','uo_native_allocate_id','uo_native_insert','uo_native_retire','uo_native_result',
 'uo_native_error_message','uo_native_invoke','uo_native_confirmation','uo_native_error_release',
 'uo_native_error_reject','uo_native_error_return','uo_native_service_alloc','uo_native_service_send')

def inspect_bitcode(path):
    lib=c.CDLL(str(LLVM_LIBRARY))
    lib.LLVMCreateMemoryBufferWithMemoryRangeCopy.argtypes=[c.c_char_p,c.c_size_t,c.c_char_p]
    lib.LLVMCreateMemoryBufferWithMemoryRangeCopy.restype=c.c_void_p
    lib.LLVMParseBitcode2.argtypes=[c.c_void_p,c.POINTER(c.c_void_p)];lib.LLVMParseBitcode2.restype=c.c_int
    for name in ('LLVMGetTarget','LLVMGetDataLayoutStr'):
        getattr(lib,name).argtypes=[c.c_void_p];getattr(lib,name).restype=c.c_char_p
    lib.LLVMPrintModuleToString.argtypes=[c.c_void_p];lib.LLVMPrintModuleToString.restype=c.c_void_p
    for name in ('LLVMDisposeMemoryBuffer','LLVMDisposeModule','LLVMDisposeMessage'):
        getattr(lib,name).argtypes=[c.c_void_p];getattr(lib,name).restype=None
    raw=path.read_bytes();buffer=lib.LLVMCreateMemoryBufferWithMemoryRangeCopy(raw,len(raw),b'ussd-v13')
    module=c.c_void_p();printed=None
    try:
        assert lib.LLVMParseBitcode2(buffer,c.byref(module))==0,'invalid bitcode'
        triple=lib.LLVMGetTarget(module).decode();layout=lib.LLVMGetDataLayoutStr(module).decode()
        assert triple=='thumbv5e-none-unknown-eabi','actual LLVM canonical target'
        assert layout=='e-m:e-p:32:32-Fi8-i64:64-v128:64:128-a:0:32-n32-S64','ARM32 LE layout'
        printed=lib.LLVMPrintModuleToString(module);ir=c.string_at(printed).decode()
        attributes=dict(re.findall(r'^attributes #(\d+) = (.+)$',ir,re.M))
        definitions=re.findall(r'^define [^\n]*? #([0-9]+)\b',ir,re.M)
        assert len(definitions)==len(re.findall(r'^define ',ir,re.M))
        assert definitions,'no typed function definitions'
        for key in definitions:
            row=attributes[key]
            for required in ('"target-cpu"="arm926ej-s"','+armv5tej','+thumb-mode','+soft-float','+strict-align','"use-soft-float"="true"'):
                assert required in row,required
            assert '"frame-pointer"="all"' not in row and '"frame-pointer"="non-leaf"' not in row
            assert '+thumb2' not in row and '+neon' not in row and '+vfp' not in row
        return {'kind':'LLVM bitcode','triple':triple,'data_layout':layout,'definitions':len(definitions),
                'function_attributes':sorted({attributes[k] for k in definitions})}
    finally:
        if printed:lib.LLVMDisposeMessage(printed)
        if module:lib.LLVMDisposeModule(module)
        lib.LLVMDisposeMemoryBuffer(buffer)

def link_flags():
    return ['--lto-partitions=1','--save-temps','--plugin-opt=mcpu=arm926ej-s',
            '--mllvm=-mattr=+strict-align,+thumb-mode,-thumb2,-neon,-vfp2',*[f'--undefined={name}' for name in ROOTS]]

def linker_script(text):
    assert text.count('.text : { *(.text .text.*) }')==1
    # LLD's default padding d4d4 decodes as a branch on Thumb1. Explicit no-op
    # fill keeps alignment bytes within the strict whole-text instruction audit.
    return text.replace('.text : { *(.text .text.*) }','.text : { *(.text .text.*) } =0xc046')

def inspect_backend(elf):
    path=Path(str(elf)+'.lto.o')
    attrs=subprocess.check_output(['readelf','-A',str(path)],text=True)
    for required in ('Tag_CPU_arch: v5TE\n','Tag_THUMB_ISA_use: Thumb-1','Tag_CPU_unaligned_access: None'):
        assert required in attrs,required
    assert 'Tag_ABI_VFP_args' not in attrs
    return {'object':path.name,'attributes':attrs.splitlines(),
        'stack_usage':'No static .su for LTO output; bounded machine-code executions measure observed combined stack.'}
