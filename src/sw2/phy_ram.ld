SECTIONS {
  .text 0xc04 : { *(.text .text.*) *(.rodata .rodata.*) }
  .data 0 : { *(.data .data.*) *(.bss .bss.*) *(COMMON) }
  /DISCARD/ : { *(.comment) }
}
ASSERT(SIZEOF(.text) <= 352, "PHY overlay exceeds audited 2.4G function body")
ASSERT(SIZEOF(.data) == 0, "PHY overlay cannot allocate globals")
