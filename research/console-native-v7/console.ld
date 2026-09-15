ENTRY(placement_init)
SECTIONS {
 . = 0x06918ff0;
 .text : { *(.text .text.*) . = ALIGN(4); }
 .rodata : { *(.rodata .rodata.*) . = ALIGN(4); }
 /DISCARD/ : { *(.comment) *(.note*) *(.ARM.exidx*) *(.ARM.extab*) }
 ASSERT(. <= 0x0691aff0, "console exceeds reserved source window")
}
