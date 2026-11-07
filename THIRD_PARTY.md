# Third-party material

## jgus-org/8bitdo-2c-re-flake (MIT)
https://github.com/jgus-org/8bitdo-2c-re-flake  -  Copyright (c) 2026 Joshua Gustafson

The following files here are copied or adapted from that project and remain under its MIT license:
- `tools/AggressivePre.java`, `Assemble.java`, `CreateFuncs.java` (prologue byte changed for this chip), `DecompileFunc.java`,
  `DisasmRange.java`, `ExportAll.java`, `FindXrefs.java`, `ListingExport.java`, `PoolRegs.java`, `ReportStats.java`, `StringXrefs.java`
  (Ghidra scripts from its `scripts/`)
- `tools/u2wflash.py`, `tools/u2wboot.py`: re-implementations for the Ultimate 2 Wireless that follow the command layout of its
  `flasher/flash2c.py`

MIT License text (from the upstream `LICENSE.md`):

    Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
    documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
    rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
    persons to whom the Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
    Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
    WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
    COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
    OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Not included in this repository (fetch yourself)
- 8BitDo firmware images (download from the vendor's update server), flash dumps and USB captures: kept local on purpose.
- Telink B80 SDK (`telink-semi/tc_ble_simple_sdk`), TC32 toolchain (`flyskywhy/tc32`), Ghidra TC32 module
  (`trust1995/Ghidra_TELink_TC32`), Ghidra, JDK: used as tools; see `notes/PROGRESS.md` for versions and locations.
- Protocol facts in `notes/SWITCH2_PROTOCOL.md` were compiled from public projects (esp-cpp/espp, ndeadly/switch2_controller_research,
  zhantss/ESP32-BLE5-NSController-Emulator); see that file's source key.
