fw_setAdvData = 0x15894;
SECTIONS {
  .text 0xa100 : { *(.text .text.*) *(.rodata .rodata.*) }
  .patch_d5b2 0xd5b2 : { *(.patch_d5b2) }
  /DISCARD/ : { *(.data .data.* .bss .bss.* COMMON .comment) }
}
