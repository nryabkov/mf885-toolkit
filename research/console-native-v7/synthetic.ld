/* Synthetic execution fixture only. 0x01000000 is NOT qualified device space. */
ENTRY(uo_native_init)
SECTIONS {
 . = 0x01000000;
 .text : { *(.text .text.*) }
 .rodata ALIGN(4) : { *(.rodata .rodata.*) }
 .data : { *(.data .data.*) }
 .bss : { *(.bss .bss.* COMMON) }
 /DISCARD/ : { *(.ARM.exidx* .ARM.extab* .comment .note*) }
 ASSERT(SIZEOF(.data) == 0, "unexpected writable data")
 ASSERT(SIZEOF(.bss) == 0, "unexpected BSS")
}
