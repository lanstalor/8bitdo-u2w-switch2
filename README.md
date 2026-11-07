# 8BitDo Ultimate 2 Wireless -> Switch 2 (BLE) project

Experimental on-controller firmware for the **8BitDo Ultimate 2 Wireless**,
based on firmware 1.09. Direct Switch 2 Bluetooth registration and button input
have been demonstrated on one controller. This is firmware, not a Windows driver.
It is not intended for the Ultimate 2 Bluetooth, Ultimate 2C, or other models.

The working implementation adds LE 2M PHY support and a 512-byte ATT MTU with
larger transport buffers. Hold **Y while powering on in Bluetooth mode**, then
open **Controllers → Change Grip/Order** on Switch 2 and press **L+R**.

See [release installation instructions](notes/releases/v0.1.0.md) and the
[GitHub releases](https://github.com/lanstalor/8bitdo-u2w-switch2/releases).
Reconnect after power cycling, console wake, rumble, motion, and extended
gameplay are not yet fully validated. The firmware uses fixed motion data.

Start with `notes/PROGRESS.md` (state, key facts, tools, procedures, gotchas, next steps).

- `notes/`     docs: PROGRESS, PHASE0 (static analysis), PHASE1_WINDOWS (flashing + test log), SWITCH2_PROTOCOL (protocol spec)
- `tools/`     flashers (`u2wflash.py`, `u2wboot.py`), mod builders (`mkmod.py`, `fixcrc.py`), BLE and Ghidra helpers, capture scripts
- `src/`       C sources for the on-controller code (`src/sw2` is the Switch 2 mode; build with `src/sw2/build.sh` via WSL)
- `mods/`      patch specs fed to `tools/mkmod.py`
- `firmware/`  stock 1.09 / 1.10 payloads and built test images
- `backup/`    full 512 KB flash backup of the controller
- `captures/`  USB captures of the official updater
- `analysis/`  Ghidra exports
- `ref/`       reference projects (2C reverse-engineering repo, Telink B80 SDK)

Toolchain lives outside this folder: `C:\Users\lance\re-tools` (Ghidra, JDK, Python venv) and WSL `~/tc32` (Telink compiler).
