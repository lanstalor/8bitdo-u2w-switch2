fw_setAdvData = 0x15894;
fw_setScanRspData = 0x15918;
fw_setAttributeTable = 0x178e8;
fw_bondCount = 0x19ff8;
fw_stockReports = 0xd6a0;
fw_requestMtu = 0x187d0;
fw_requestParameters = 0x18c8c;
fw_notify = 0x188b0;
fw_ltkReply = 0x1727c;
fw_ltkNegative = 0x172b8;
fw_registerLtk = 0x16220;
fw_registerEvent = 0x155c4;
fw_stockDisconnect = 0xd4e0;
fw_enableAdv = 0x15748;
fw_disconnect = 0x165c0;
fw_stockPairButton = 0xd708;
fw_loadBond = 0x1a3b4;
fw_saveBond = 0x1a560;
fw_compactBonds = 0x1a130;
fw_l2capReassemble = 0x18bb8;
fw_ledState = 0xf60c;
fw_charging = 0x10e6c;
SECTIONS {
  .text 0xa100 : { *(.text .text.*) *(.rodata .rodata.*) }
  .patch_d5b2 0xd5b2 : { *(.patch_d5b2) }
  .patch_d5ba 0xd5ba : { *(.patch_d5ba) }
  .patch_d768 0xd768 : { *(.patch_d768) }
  .patch_d570 0xd570 : { *(.patch_d570) }
  .patch_d5be 0xd5be : { *(.patch_d5be) }
  .patch_d74c 0xd74c : { *(.patch_d74c) }
  .patch_d750 0xd750 : { *(.patch_d750) }
  .patch_d48a 0xd48a : { *(.patch_d48a) }
  .patch_d496 0xd496 : { *(.patch_d496) }
  .patch_18f5e 0x18f5e : { *(.patch_18f5e) }
  .data 0x0 : { *(.data .data.*) *(.bss .bss.*) *(COMMON) }
  /DISCARD/ : { *(.comment) }
}
ASSERT(ADDR(.text) + SIZEOF(.text) <= 0xd000, "Switch 2 code exceeds verified cave")
