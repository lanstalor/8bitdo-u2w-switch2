#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
tc32-elf-gcc -O2 -ffunction-sections -fno-common -fno-builtin -nostdlib -c sw2.c -o sw2.o
tc32-elf-gcc -Os -ffunction-sections -fno-common -fno-builtin -nostdlib -c protocol.c -o protocol.o
tc32-elf-gcc -Os -ffunction-sections -fno-common -fno-builtin -nostdlib -c session.c -o session.o
tc32-elf-gcc -Os -ffunction-sections -fno-common -fno-builtin -nostdlib -c pairing_crypto.c -o pairing_crypto.o
tc32-elf-as calls.s -o calls.o
tc32-elf-ld -T link.ld sw2.o protocol.o session.o pairing_crypto.o calls.o -o sw2.elf
# any RAM data would be silently wrong (nothing initialises it): refuse
d=$(tc32-elf-size -A sw2.elf | awk '$1==".data"{print $2}'); if [ -n "$d" ] && [ "$d" != "0" ]; then echo "ERROR: code uses RAM globals"; exit 1; fi
for s in text patch_d5b2 patch_d5ba patch_d768 patch_d570 patch_d5be patch_d74c patch_d750 patch_d48a patch_d496; do tc32-elf-objcopy -O binary --only-section=.$s sw2.elf $s.bin; done
tc32-elf-nm -n sw2.elf
tc32-elf-size -A sw2.elf | grep -E "^\.(text|data|patch)"
tc32-elf-objdump -d -j .patch_d5b2 -j .patch_d5ba sw2.elf | grep tjl
