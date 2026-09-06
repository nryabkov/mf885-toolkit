#!/usr/bin/env python3
"""Compile pinned freestanding MF885 Thumb LLVM IR to relocation-free text.

This is an offline build helper.  It loads the exact system LLVM 20.1 shared
library, emits an ARM EABI object, rejects any relocation against ``.text`` and
extracts only the executable bytes.  It never contacts or writes to a router.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import struct
from pathlib import Path


LLVM_LIBRARY = Path("/lib/x86_64-linux-gnu/libLLVM.so.20.1")
# Historical reproducibility defaults, not a hardware qualification. New native
# variants must select and validate their hardware profile explicitly.
TARGET_TRIPLE = b"thumbv7-none-eabi"
TARGET_CPU = b"cortex-a9"
TARGET_FEATURES = b"-neon,-vfp2"
ELF_MACHINE_ARM = 40
ELF_TYPE_RELOCATABLE = 1
ELF_EABI_VERSION_5 = 0x05000000
SHT_RELA = 4
SHT_REL = 9
SHT_SYMTAB = 2
SHT_NOBITS = 8
SHF_ALLOC = 0x2
LLVM_OBJECT_FILE = 1


class NativeBuildError(RuntimeError):
    pass


def _llvm() -> ctypes.CDLL:
    if not LLVM_LIBRARY.is_file():
        raise NativeBuildError(f"required LLVM library is absent: {LLVM_LIBRARY}")
    lib = ctypes.CDLL(str(LLVM_LIBRARY))
    for name in (
        "LLVMInitializeARMTargetInfo",
        "LLVMInitializeARMTarget",
        "LLVMInitializeARMTargetMC",
        "LLVMInitializeARMAsmPrinter",
    ):
        getattr(lib, name)()

    lib.LLVMContextCreate.restype = ctypes.c_void_p
    lib.LLVMContextDispose.argtypes = [ctypes.c_void_p]
    lib.LLVMCreateMemoryBufferWithMemoryRangeCopy.argtypes = [
        ctypes.c_char_p,
        ctypes.c_size_t,
        ctypes.c_char_p,
    ]
    lib.LLVMCreateMemoryBufferWithMemoryRangeCopy.restype = ctypes.c_void_p
    lib.LLVMParseIRInContext.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_char_p),
    ]
    lib.LLVMParseIRInContext.restype = ctypes.c_int
    lib.LLVMDisposeModule.argtypes = [ctypes.c_void_p]
    lib.LLVMGetTargetFromTriple.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_char_p),
    ]
    lib.LLVMGetTargetFromTriple.restype = ctypes.c_int
    lib.LLVMCreateTargetMachine.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
    ]
    lib.LLVMCreateTargetMachine.restype = ctypes.c_void_p
    lib.LLVMDisposeTargetMachine.argtypes = [ctypes.c_void_p]
    lib.LLVMTargetMachineEmitToMemoryBuffer.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_char_p),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    lib.LLVMTargetMachineEmitToMemoryBuffer.restype = ctypes.c_int
    lib.LLVMGetBufferStart.argtypes = [ctypes.c_void_p]
    lib.LLVMGetBufferStart.restype = ctypes.c_void_p
    lib.LLVMGetBufferSize.argtypes = [ctypes.c_void_p]
    lib.LLVMGetBufferSize.restype = ctypes.c_size_t
    lib.LLVMDisposeMemoryBuffer.argtypes = [ctypes.c_void_p]
    lib.LLVMDisposeMessage.argtypes = [ctypes.c_char_p]
    return lib


def _take_message(lib: ctypes.CDLL, value: ctypes.c_char_p) -> str:
    if not value.value:
        return "unknown LLVM error"
    result = ctypes.string_at(value.value).decode("utf-8", "replace")
    lib.LLVMDisposeMessage(value)
    return result


def _emit_object(source: bytes, *, target_triple: bytes = TARGET_TRIPLE,
                 target_cpu: bytes = TARGET_CPU,
                 target_features: bytes = TARGET_FEATURES) -> bytes:
    lib = _llvm()
    context = lib.LLVMContextCreate()
    module = ctypes.c_void_p()
    error = ctypes.c_char_p()
    memory = lib.LLVMCreateMemoryBufferWithMemoryRangeCopy(
        source, len(source), b"mf885-native.ll"
    )
    machine = None
    try:
        if lib.LLVMParseIRInContext(
            context, memory, ctypes.byref(module), ctypes.byref(error)
        ):
            raise NativeBuildError(_take_message(lib, error))
        target = ctypes.c_void_p()
        if lib.LLVMGetTargetFromTriple(
            target_triple, ctypes.byref(target), ctypes.byref(error)
        ):
            raise NativeBuildError(_take_message(lib, error))
        machine = lib.LLVMCreateTargetMachine(
            target,
            target_triple,
            target_cpu,
            target_features,
            2,
            0,
            0,
        )
        if not machine:
            raise NativeBuildError("LLVMCreateTargetMachine failed")
        output = ctypes.c_void_p()
        if lib.LLVMTargetMachineEmitToMemoryBuffer(
            machine,
            module,
            LLVM_OBJECT_FILE,
            ctypes.byref(error),
            ctypes.byref(output),
        ):
            raise NativeBuildError(_take_message(lib, error))
        try:
            return ctypes.string_at(
                lib.LLVMGetBufferStart(output), lib.LLVMGetBufferSize(output)
            )
        finally:
            lib.LLVMDisposeMemoryBuffer(output)
    finally:
        if machine:
            lib.LLVMDisposeTargetMachine(machine)
        if module:
            lib.LLVMDisposeModule(module)
        lib.LLVMContextDispose(context)


def extract_text(elf: bytes) -> bytes:
    if len(elf) < 52 or elf[:7] != b"\x7fELF\x01\x01\x01":
        raise NativeBuildError("LLVM output is not ELF32 little-endian")
    machine = struct.unpack_from("<H", elf, 18)[0]
    if machine != ELF_MACHINE_ARM:
        raise NativeBuildError(f"LLVM output machine is {machine}, not ARM")
    elf_type = struct.unpack_from("<H", elf, 16)[0]
    if elf_type != ELF_TYPE_RELOCATABLE:
        raise NativeBuildError("LLVM output is not a relocatable object")
    flags = struct.unpack_from("<I", elf, 36)[0]
    if flags != ELF_EABI_VERSION_5:
        raise NativeBuildError(f"LLVM output flags are 0x{flags:08x}, not ARM EABI5")
    section_offset = struct.unpack_from("<I", elf, 32)[0]
    section_size = struct.unpack_from("<H", elf, 46)[0]
    section_count = struct.unpack_from("<H", elf, 48)[0]
    names_index = struct.unpack_from("<H", elf, 50)[0]
    if section_size != 40 or not section_count or names_index >= section_count:
        raise NativeBuildError("ELF section table is invalid")

    sections = []
    for index in range(section_count):
        start = section_offset + index * section_size
        if start + section_size > len(elf):
            raise NativeBuildError("ELF section table exceeds object")
        sections.append(struct.unpack_from("<10I", elf, start))
    names = sections[names_index]
    names_blob = elf[names[4] : names[4] + names[5]]

    def section_name(item: tuple[int, ...]) -> str:
        offset = item[0]
        end = names_blob.find(b"\0", offset)
        if offset >= len(names_blob) or end < 0:
            raise NativeBuildError("ELF section name is invalid")
        return names_blob[offset:end].decode("ascii")

    named_items = [(section_name(item), item) for item in sections]
    named = {name: item for name, item in named_items}
    text = named.get(".text")
    if text is None or text[1] != 1 or not (text[2] & 0x4) or text[8] != 4:
        raise NativeBuildError("ELF has no aligned executable .text section")
    text_index = next(index for index, (name, _item) in enumerate(named_items) if name == ".text")
    for name, item in named_items:
        if item[1] in {SHT_REL, SHT_RELA} and item[7] == text_index:
            raise NativeBuildError(f"generated .text contains relocations in {name}")
        if item[2] & SHF_ALLOC and name not in {".text", ".ARM.exidx"}:
            kind = "NOBITS" if item[1] == SHT_NOBITS else str(item[1])
            raise NativeBuildError(f"generated payload depends on alloc section {name} ({kind})")
    start, size = text[4], text[5]
    if not size or start + size > len(elf):
        raise NativeBuildError("ELF .text range is invalid")
    return elf[start : start + size]


def extract_text_layout(elf: bytes) -> dict[str, object]:
    """Return exact ARM mapping-symbol code/data ranges inside ``.text``.

    LLVM legitimately places PC-relative literal data after the emitted Thumb
    instructions in the executable section.  Treating those words as
    instructions makes disassembly evidence misleading, so the ARM ``$t`` and
    ``$d`` mapping symbols are parsed and pinned separately.
    """

    text = extract_text(elf)
    section_offset = struct.unpack_from("<I", elf, 32)[0]
    section_size = struct.unpack_from("<H", elf, 46)[0]
    section_count = struct.unpack_from("<H", elf, 48)[0]
    names_index = struct.unpack_from("<H", elf, 50)[0]
    sections = [
        struct.unpack_from("<10I", elf, section_offset + index * section_size)
        for index in range(section_count)
    ]
    names = sections[names_index]
    names_blob = elf[names[4] : names[4] + names[5]]

    def section_name(item: tuple[int, ...]) -> str:
        offset = item[0]
        end = names_blob.find(b"\0", offset)
        if offset >= len(names_blob) or end < 0:
            raise NativeBuildError("ELF section name is invalid")
        return names_blob[offset:end].decode("ascii")

    named_items = [(section_name(item), item) for item in sections]
    text_index = next(
        (index for index, (name, _item) in enumerate(named_items) if name == ".text"),
        None,
    )
    if text_index is None:
        raise NativeBuildError("ELF has no .text section")
    mapping: list[tuple[int, str]] = []
    functions: list[dict[str, object]] = []
    for _name, item in named_items:
        if item[1] != SHT_SYMTAB or item[9] != 16 or item[6] >= len(sections):
            continue
        strings = sections[item[6]]
        string_blob = elf[strings[4] : strings[4] + strings[5]]
        for offset in range(0, item[5], item[9]):
            name_offset, value, size, info, _other, section_index = struct.unpack_from(
                "<IIIBBH", elf, item[4] + offset
            )
            if name_offset >= len(string_blob):
                raise NativeBuildError("ELF symbol name exceeds string table")
            end = string_blob.find(b"\0", name_offset)
            if end < 0:
                raise NativeBuildError("ELF symbol name is unterminated")
            symbol = string_blob[name_offset:end].decode("ascii")
            if section_index == text_index and symbol in {"$t", "$d", "$a"}:
                mapping.append((value, symbol))
            if section_index == text_index and info & 0x0F == 2:
                functions.append(
                    {
                        "name": symbol,
                        "offset": value & ~1,
                        "thumb": bool(value & 1),
                        "bytes": size,
                    }
                )
    mapping = sorted(set(mapping))
    if not mapping or mapping[0] != (0, "$t"):
        raise NativeBuildError("generated .text does not start with a Thumb mapping symbol")
    if any(offset < 0 or offset >= len(text) for offset, _kind in mapping):
        raise NativeBuildError("ARM mapping symbol escapes generated .text")
    ranges: list[dict[str, object]] = []
    for index, (start, kind) in enumerate(mapping):
        end = mapping[index + 1][0] if index + 1 < len(mapping) else len(text)
        if start >= end:
            raise NativeBuildError("ARM mapping symbol ranges overlap or are empty")
        ranges.append(
            {
                "kind": {"$t": "thumb", "$d": "data", "$a": "arm"}[kind],
                "offset": start,
                "bytes": end - start,
            }
        )
    if any(item["kind"] == "arm" for item in ranges):
        raise NativeBuildError("generated payload unexpectedly contains ARM-mode code")
    if not functions or any(not item["thumb"] for item in functions):
        raise NativeBuildError("generated function symbol is absent or not Thumb")
    return {"raw": text, "ranges": ranges, "functions": functions}


def compile_ir(source: bytes) -> bytes:
    return extract_text(_emit_object(source))


def compile_ir_layout(source: bytes, *, target_triple: bytes = TARGET_TRIPLE,
                      target_cpu: bytes = TARGET_CPU,
                      target_features: bytes = TARGET_FEATURES) -> dict[str, object]:
    return extract_text_layout(_emit_object(
        source, target_triple=target_triple, target_cpu=target_cpu,
        target_features=target_features))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile freestanding MF885 Thumb LLVM IR to raw text"
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = compile_ir(args.source.read_bytes())
        with args.output.open("xb") as stream:
            stream.write(result)
            stream.flush()
            os.fsync(stream.fileno())
    except (OSError, NativeBuildError) as exc:
        parser.exit(2, f"native build failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
