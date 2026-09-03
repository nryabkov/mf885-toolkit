#!/usr/bin/env python3
"""Dependency-free concrete executor for the exact MF885 Thumb subset.

This is a validation primitive, not a general ARM emulator.  It executes the
strict LLVM disassembly of the emitted R3.0/R3.1 helpers, rejects every unsupported
instruction and exposes external BLX calls as explicit host callbacks.  The
purpose is to test the generated machine bytes rather than re-running LLVM IR
or a Python translation of the intended algorithm.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable

import mf885_thumb_disasm as thumb_disasm


MASK32 = 0xFFFFFFFF
RETURN_SENTINEL = 0x0FF00001
REGISTER_ORDER = {
    **{f"r{index}": index for index in range(13)},
    "sp": 13,
    "lr": 14,
    "pc": 15,
}


class ThumbExecutionError(RuntimeError):
    pass


HostCallback = Callable[["ThumbMachine", tuple[int, int, int, int]], int]


def _u32(value: int) -> int:
    return value & MASK32


def _immediate(value: str) -> int:
    if not value.startswith("#"):
        raise ThumbExecutionError(f"not an immediate: {value}")
    return int(value[1:], 0)


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",")]


@dataclass(frozen=True)
class ThumbProgram:
    raw: bytes
    runtime: int
    code_bytes: int

    def __post_init__(self) -> None:
        if self.code_bytes <= 0 or self.code_bytes > len(self.raw):
            raise ThumbExecutionError("invalid code boundary")
        records = thumb_disasm.disassemble(self.raw[: self.code_bytes], self.runtime)
        object.__setattr__(self, "records", records)
        object.__setattr__(self, "by_address", {item["address"]: item for item in records})
        if len(self.by_address) != len(records):
            raise ThumbExecutionError("duplicate instruction address")

    def machine(
        self,
        *,
        registers: dict[str, int] | None = None,
        blobs: Iterable[tuple[int, bytes]] = (),
        callbacks: dict[int, HostCallback] | None = None,
    ) -> "ThumbMachine":
        return ThumbMachine(
            self,
            registers=registers or {},
            blobs=blobs,
            callbacks=callbacks or {},
        )


class ThumbMachine:
    def __init__(
        self,
        program: ThumbProgram,
        *,
        registers: dict[str, int],
        blobs: Iterable[tuple[int, bytes]],
        callbacks: dict[int, HostCallback],
    ) -> None:
        self.program = program
        self.regs = {name: 0 for name in REGISTER_ORDER}
        self.regs.update({name: _u32(value) for name, value in registers.items()})
        self.regs["sp"] = self.regs.get("sp") or 0x20020000
        self.regs["lr"] = self.regs.get("lr") or RETURN_SENTINEL
        self.regs["pc"] = program.runtime
        self.flags = {"n": False, "z": False, "c": False, "v": False}
        self.it_conditions: list[str] = []
        self.memory: dict[int, int] = {}
        self.write_log: list[tuple[int, int, int]] = []
        self.call_log: list[dict[str, object]] = []
        self.steps = 0
        self.returned = False
        self.return_value: int | None = None
        self.load(program.runtime, program.raw)
        for address, raw in blobs:
            self.load(address, raw)
        self.callbacks = {address & ~1: callback for address, callback in callbacks.items()}

    def load(self, address: int, raw: bytes) -> None:
        for offset, value in enumerate(raw):
            self.memory[address + offset] = value

    def bytes(self, address: int, length: int) -> bytes:
        try:
            return bytes(self.memory[address + offset] for offset in range(length))
        except KeyError as exc:
            raise ThumbExecutionError(f"unmapped read at 0x{int(exc.args[0]):08x}") from exc

    def read8(self, address: int) -> int:
        return self.bytes(address, 1)[0]

    def read16(self, address: int) -> int:
        return int.from_bytes(self.bytes(address, 2), "little")

    def read32(self, address: int) -> int:
        return int.from_bytes(self.bytes(address, 4), "little")

    def read_c_string(self, address: int, ceiling: int = 1024) -> bytes:
        value = bytearray()
        for offset in range(ceiling):
            byte = self.read8(address + offset)
            if byte == 0:
                return bytes(value)
            value.append(byte)
        raise ThumbExecutionError("unterminated string exceeds ceiling")

    def write(self, address: int, value: int, width: int) -> None:
        value &= (1 << (width * 8)) - 1
        raw = value.to_bytes(width, "little")
        for offset, byte in enumerate(raw):
            self.memory[address + offset] = byte
        self.write_log.append((address, width, value))

    def _register(self, name: str) -> int:
        if name not in self.regs:
            raise ThumbExecutionError(f"unsupported register {name}")
        return self.regs[name]

    def _set_register(self, name: str, value: int) -> None:
        if name not in self.regs:
            raise ThumbExecutionError(f"unsupported register {name}")
        self.regs[name] = _u32(value)

    def _shifted(self, register: str, shift: str | None = None) -> int:
        value = self._register(register)
        if shift is None:
            return value
        kind, immediate = shift.split(None, 1)
        amount = _immediate(immediate)
        if kind == "lsl":
            return _u32(value << amount)
        if kind == "lsr":
            return value >> amount
        raise ThumbExecutionError(f"unsupported shift {shift}")

    def _set_logic_flags(self, value: int) -> None:
        value = _u32(value)
        self.flags["n"] = bool(value & 0x80000000)
        self.flags["z"] = value == 0

    def _set_sub_flags(self, left: int, right: int) -> None:
        left = _u32(left)
        right = _u32(right)
        result = _u32(left - right)
        self.flags["n"] = bool(result & 0x80000000)
        self.flags["z"] = result == 0
        self.flags["c"] = left >= right
        self.flags["v"] = bool(((left ^ right) & (left ^ result) & 0x80000000))

    def _condition(self, name: str) -> bool:
        if name == "eq":
            return self.flags["z"]
        if name == "ne":
            return not self.flags["z"]
        if name in {"lo", "cc"}:
            return not self.flags["c"]
        if name == "hi":
            return self.flags["c"] and not self.flags["z"]
        raise ThumbExecutionError(f"unsupported condition {name}")

    def _branch_offset(self, operand: str, address: int) -> int:
        return _u32(address + 4 + _immediate(operand))

    def _memory_operand(self, operands: str, address: int) -> tuple[str, int]:
        match = re.fullmatch(
            r"(r(?:1[0-2]|[0-9])|sp|lr), \[(r(?:1[0-2]|[0-9])|sp|pc)(?:, (#[+-]?(?:0x[0-9a-f]+|[0-9]+)))?\]",
            operands,
        )
        if not match:
            raise ThumbExecutionError(f"unsupported memory operand {operands}")
        destination, base, raw_offset = match.groups()
        base_value = ((address + 4) & ~3) if base == "pc" else self._register(base)
        offset = _immediate(raw_offset) if raw_offset else 0
        return destination, _u32(base_value + offset)

    def _push(self, raw_registers: str) -> None:
        registers = [item.strip() for item in raw_registers.split(",")]
        registers.sort(key=lambda name: REGISTER_ORDER[name])
        start = _u32(self.regs["sp"] - 4 * len(registers))
        for index, register in enumerate(registers):
            self.write(start + index * 4, self._register(register), 4)
        self.regs["sp"] = start

    def _finish_or_branch(self, target: int) -> None:
        even = target & ~1
        if even in self.program.by_address:
            self.regs["pc"] = even
            return
        self.returned = True
        self.return_value = self.regs["r0"]

    def _pop(self, raw_registers: str) -> None:
        registers = [item.strip() for item in raw_registers.split(",")]
        registers.sort(key=lambda name: REGISTER_ORDER[name])
        start = self.regs["sp"]
        target: int | None = None
        for index, register in enumerate(registers):
            value = self.read32(start + index * 4)
            if register == "pc":
                target = value
            else:
                self._set_register(register, value)
        self.regs["sp"] = _u32(start + 4 * len(registers))
        if target is not None:
            self._finish_or_branch(target)

    def _host_call(self, register: str, return_address: int) -> None:
        target = self._register(register) & ~1
        callback = self.callbacks.get(target)
        if callback is None:
            raise ThumbExecutionError(f"unregistered BLX target 0x{target:08x}")
        arguments = tuple(self.regs[f"r{index}"] for index in range(4))
        result = callback(self, arguments)
        self.call_log.append(
            {"target": target, "arguments": arguments, "result": _u32(result)}
        )
        self.regs["r0"] = _u32(result)
        # Make the AAPCS caller-saved contract visible to the generated code.
        self.regs["r1"] = 0xA1A1A1A1
        self.regs["r2"] = 0xA2A2A2A2
        self.regs["r3"] = 0xA3A3A3A3
        self.regs["r12"] = 0xACACACAC
        self.regs["lr"] = _u32(return_address | 1)

    @staticmethod
    def _strip_it_suffix(mnemonic: str, condition: str) -> str:
        if mnemonic.endswith(condition + ".w"):
            return mnemonic[: -(len(condition) + 2)] + ".w"
        if mnemonic.endswith(condition):
            return mnemonic[: -len(condition)]
        return mnemonic

    def run(self, max_steps: int = 1024) -> int:
        while not self.returned:
            if self.steps >= max_steps:
                raise ThumbExecutionError("instruction ceiling exceeded")
            address = self.regs["pc"]
            record = self.program.by_address.get(address)
            if record is None:
                raise ThumbExecutionError(f"PC escaped code at 0x{address:08x}")
            self.steps += 1
            instruction = record["instruction"]
            if "\t" in instruction:
                mnemonic, operands = instruction.split("\t", 1)
            else:
                mnemonic, operands = instruction, ""
            next_pc = address + int(record["size"])

            if mnemonic.startswith("it"):
                if self.it_conditions:
                    raise ThumbExecutionError("nested IT block")
                if operands not in {"eq", "ne", "lo", "cc", "hi"} or not set(mnemonic[1:]) <= {"t"}:
                    raise ThumbExecutionError(f"unsupported IT block {instruction}")
                self.it_conditions = [operands] * (len(mnemonic) - 1)
                self.regs["pc"] = next_pc
                continue

            execute = True
            if self.it_conditions:
                condition = self.it_conditions.pop(0)
                execute = self._condition(condition)
                mnemonic = self._strip_it_suffix(mnemonic, condition)
            if not execute:
                self.regs["pc"] = next_pc
                continue

            if mnemonic in {"push", "push.w"}:
                match = re.fullmatch(r"\{(.+)\}", operands)
                if not match:
                    raise ThumbExecutionError(f"unsupported push {instruction}")
                self._push(match.group(1))
            elif mnemonic in {"pop", "pop.w"}:
                match = re.fullmatch(r"\{(.+)\}", operands)
                if not match:
                    raise ThumbExecutionError(f"unsupported pop {instruction}")
                self._pop(match.group(1))
                if self.returned or self.regs["pc"] != address:
                    continue
            elif mnemonic in {"mov", "movs", "movw", "mov.w"}:
                destination, source = _split(operands)
                value = _immediate(source) if source.startswith("#") else self._register(source)
                self._set_register(destination, value)
                if mnemonic == "movs":
                    self._set_logic_flags(value)
            elif mnemonic in {"ldr", "ldrb", "ldrh"}:
                destination, memory_address = self._memory_operand(operands, address)
                width = {"ldr": 4, "ldrb": 1, "ldrh": 2}[mnemonic]
                value = {4: self.read32, 2: self.read16, 1: self.read8}[width](memory_address)
                self._set_register(destination, value)
            elif mnemonic in {"str", "strb", "strh"}:
                source, memory_address = self._memory_operand(operands, address)
                width = {"str": 4, "strb": 1, "strh": 2}[mnemonic]
                self.write(memory_address, self._register(source), width)
            elif mnemonic in {"cbz", "cbnz"}:
                register, offset = _split(operands)
                zero = self._register(register) == 0
                take = zero if mnemonic == "cbz" else not zero
                if take:
                    next_pc = self._branch_offset(offset, address)
            elif mnemonic in {"b", "beq", "bne", "blo", "bhi"}:
                take = mnemonic == "b" or self._condition(mnemonic[1:])
                if take:
                    next_pc = self._branch_offset(operands, address)
            elif mnemonic == "bx":
                self._finish_or_branch(self._register(operands))
                if self.returned or self.regs["pc"] != address:
                    continue
            elif mnemonic == "blx":
                self._host_call(operands, next_pc)
            elif mnemonic in {"cmp", "cmp.w"}:
                parts = _split(operands)
                left = self._register(parts[0])
                right = _immediate(parts[1]) if parts[1].startswith("#") else self._shifted(
                    parts[1], parts[2] if len(parts) == 3 else None
                )
                self._set_sub_flags(left, right)
            elif mnemonic in {"lsl", "lsls", "lsr", "lsrs"}:
                destination, source, amount_raw = _split(operands)
                amount = _immediate(amount_raw)
                source_value = self._register(source)
                if mnemonic.startswith("lsl"):
                    value = _u32(source_value << amount)
                    if amount and mnemonic.endswith("s"):
                        self.flags["c"] = bool(source_value & (1 << (32 - amount)))
                else:
                    value = source_value >> amount
                    if amount and mnemonic.endswith("s"):
                        self.flags["c"] = bool(source_value & (1 << (amount - 1)))
                self._set_register(destination, value)
                if mnemonic.endswith("s"):
                    self._set_logic_flags(value)
            elif mnemonic in {"adds", "adds.w", "subs", "subs.w"}:
                parts = _split(operands)
                if len(parts) == 2:
                    destination, amount_raw = parts
                    original = self._register(destination)
                elif len(parts) == 3:
                    destination, source, amount_raw = parts
                    original = self._register(source)
                else:
                    raise ThumbExecutionError(f"unsupported flag-setting arithmetic {instruction}")
                amount = _immediate(amount_raw)
                subtract = mnemonic.startswith("subs")
                value = original - amount if subtract else original + amount
                self._set_register(destination, value)
                if subtract:
                    self._set_sub_flags(original, amount)
                else:
                    self._set_logic_flags(value)
            elif mnemonic in {"add", "add.w", "sub", "sub.w"}:
                parts = _split(operands)
                if len(parts) == 2:
                    destination, source = parts
                    right_value = self._register(source)
                    value = self._register(destination) + right_value
                elif len(parts) in {3, 4}:
                    destination, left, right = parts[:3]
                    right_value = _immediate(right) if right.startswith("#") else self._shifted(
                        right, parts[3] if len(parts) == 4 else None
                    )
                    value = self._register(left) + right_value
                else:
                    raise ThumbExecutionError(f"unsupported arithmetic {instruction}")
                if mnemonic.startswith("sub"):
                    left_value = self._register(parts[1]) if len(parts) >= 3 else self._register(destination)
                    value = left_value - right_value
                self._set_register(destination, value)
            elif mnemonic in {"and", "and.w", "orr.w", "eor.w", "bic.w"}:
                parts = _split(operands)
                if len(parts) not in {3, 4}:
                    raise ThumbExecutionError(f"unsupported logical instruction {instruction}")
                destination, left, right = parts[:3]
                right_value = _immediate(right) if right.startswith("#") else self._shifted(
                    right, parts[3] if len(parts) == 4 else None
                )
                left_value = self._register(left)
                if mnemonic.startswith("and"):
                    value = left_value & right_value
                elif mnemonic.startswith("orr"):
                    value = left_value | right_value
                elif mnemonic.startswith("eor"):
                    value = left_value ^ right_value
                else:
                    value = left_value & ~right_value
                self._set_register(destination, value)
            elif mnemonic in {"mvn", "mvns"}:
                destination, source = _split(operands)
                source_value = _immediate(source) if source.startswith("#") else self._register(source)
                value = _u32(~source_value)
                self._set_register(destination, value)
                if mnemonic == "mvns":
                    self._set_logic_flags(value)
            elif mnemonic == "rsbs":
                destination, source, immediate = _split(operands)
                right = self._register(source)
                left = _immediate(immediate)
                value = left - right
                self._set_register(destination, value)
                self._set_sub_flags(left, right)
            elif mnemonic == "uxtb":
                destination, source = _split(operands)
                self._set_register(destination, self._register(source) & 0xFF)
            elif mnemonic in {"uxtab", "uxtah"}:
                destination, left, right = _split(operands)
                mask = 0xFF if mnemonic == "uxtab" else 0xFFFF
                self._set_register(
                    destination,
                    self._register(left) + (self._register(right) & mask),
                )
            elif mnemonic == "nop":
                pass
            else:
                raise ThumbExecutionError(f"unsupported instruction {instruction}")

            self.regs["pc"] = next_pc
        if self.return_value is None:
            raise ThumbExecutionError("machine returned without a value")
        return self.return_value
