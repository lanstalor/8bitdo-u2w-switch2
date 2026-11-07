# 8BitDo Ultimate 2 Wireless -> Switch 2 (BLE) project

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
