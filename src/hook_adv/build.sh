#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
tc32-elf-gcc -O2 -ffunction-sections -fno-common -fno-builtin -nostdlib -c hook.c -o hook.o
tc32-elf-as call.s -o call.o
tc32-elf-ld -T link.ld hook.o call.o -o hook.elf
tc32-elf-objcopy -O binary --only-section=.text hook.elf text.bin
tc32-elf-objcopy -O binary --only-section=.patch_d5b2 hook.elf patch_d5b2.bin
tc32-elf-nm hook.elf
tc32-elf-objdump -h hook.elf | grep -E "^ +[0-9]"
tc32-elf-objdump -d hook.elf
