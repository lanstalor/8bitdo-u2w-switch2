#!/usr/bin/env bash
# Run a command with Telink's tc32-elf toolchain on PATH (WSL). Usage from Windows:
#   wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Users/lance/OneDrive/Documents/_CODE/8bitdo/tools/tc32.sh <cmd...>
export PATH="$HOME/tc32/bin:$PATH"
cd /mnt/c/Users/lance/OneDrive/Documents/_CODE/8bitdo
exec "$@"
