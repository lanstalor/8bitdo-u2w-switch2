fw_setAdvData = 0x15894;
fw_setScanRspData = 0x15918;
SECTIONS {
  .text 0xa100 : { *(.text .text.*) *(.rodata .rodata.*) }
  .patch_d5b2 0xd5b2 : { *(.patch_d5b2) }
  .patch_d5ba 0xd5ba : { *(.patch_d5ba) }
  .data 0x0 : { *(.data .data.*) *(.bss .bss.*) *(COMMON) }
  /DISCARD/ : { *(.comment) }
}
