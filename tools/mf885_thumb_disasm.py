#!/usr/bin/env python3
"""Strict LLVM-backed Thumb disassembly for MF885 offline evidence.

The helper uses the same pinned system LLVM shared library as the native
builder.  It does not infer code boundaries: callers must provide an exact
byte range and runtime address.  Every byte must decode exactly once.
"""

from __future__ import annotations

import argparse
import ctypes
import json
from pathlib import Path
from typing import Any

from mf885_thumb_llvm_build import LLVM_LIBRARY, NativeBuildError


TRIPLE = b"thumbv7-none-eabi"
PRINT_IMMEDIATE_HEX = 2


def _library() -> ctypes.CDLL:
    if not LLVM_LIBRARY.is_file():
        raise NativeBuildError(f"required LLVM library is absent: {LLVM_LIBRARY}")
    lib = ctypes.CDLL(str(LLVM_LIBRARY))
    for name in (
        "LLVMInitializeARMTargetInfo",
        "LLVMInitializeARMTarget",
        "LLVMInitializeARMTargetMC",
        "LLVMInitializeARMDisassembler",
    ):
        getattr(lib, name)()
    lib.LLVMCreateDisasm.argtypes = [
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    lib.LLVMCreateDisasm.restype = ctypes.c_void_p
    lib.LLVMSetDisasmOptions.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    lib.LLVMSetDisasmOptions.restype = ctypes.c_int
    lib.LLVMDisasmInstruction.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint64,
        ctypes.c_uint64,
        ctypes.c_char_p,
        ctypes.c_size_t,
    ]
    lib.LLVMDisasmInstruction.restype = ctypes.c_size_t
    lib.LLVMDisasmDispose.argtypes = [ctypes.c_void_p]
    return lib


def disassemble(raw: bytes, runtime_address: int) -> list[dict[str, Any]]:
    if not raw or runtime_address < 0 or runtime_address & 1:
        raise NativeBuildError("Thumb input must be non-empty at an even address")
    lib = _library()
    context = lib.LLVMCreateDisasm(TRIPLE, None, 0, None, None)
    if not context:
        raise NativeBuildError("LLVMCreateDisasm failed for Thumb")
    storage = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    output = ctypes.create_string_buffer(512)
    records: list[dict[str, Any]] = []
    offset = 0
    try:
        lib.LLVMSetDisasmOptions(context, PRINT_IMMEDIATE_HEX)
        while offset < len(raw):
            output.value = b""
            consumed = int(
                lib.LLVMDisasmInstruction(
                    context,
                    ctypes.cast(ctypes.byref(storage, offset), ctypes.c_void_p),
                    len(raw) - offset,
                    runtime_address + offset,
                    output,
                    len(output),
                )
            )
            if consumed not in {2, 4} or offset + consumed > len(raw):
                raise NativeBuildError(
                    f"undecodable Thumb bytes at 0x{runtime_address + offset:08x}"
                )
            chunk = raw[offset : offset + consumed]
            records.append(
                {
                    "address": runtime_address + offset,
                    "bytes": chunk.hex(),
                    "size": consumed,
                    "instruction": output.value.decode("utf-8", "strict").strip(),
                }
            )
            offset += consumed
    finally:
        lib.LLVMDisasmDispose(context)
    if sum(item["size"] for item in records) != len(raw):
        raise NativeBuildError("Thumb disassembly did not consume the exact input")
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Strictly disassemble one exact Thumb range")
    parser.add_argument("image", type=Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--length", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--runtime", type=lambda value: int(value, 0), required=True)
    args = parser.parse_args(argv)
    try:
        source = args.image.read_bytes()
        end = args.offset + args.length
        if args.offset < 0 or args.length <= 0 or end > len(source):
            raise NativeBuildError("requested range is outside the image")
        value = {
            "schema": "mf885-thumb-disassembly/v1",
            "source": str(args.image),
            "offset": args.offset,
            "runtime": args.runtime,
            "bytes": args.length,
            "instructions": disassemble(source[args.offset:end], args.runtime),
        }
    except (OSError, NativeBuildError, UnicodeError) as exc:
        parser.exit(2, f"Thumb disassembly failed: {exc}\n")
    print(json.dumps(value, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
