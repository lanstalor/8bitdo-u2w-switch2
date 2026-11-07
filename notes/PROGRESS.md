# U2W → Switch 2 (BLE): progress and learnings

Last updated: 2026-11-07. Goal: make the user's own 8BitDo Ultimate 2 Wireless (dongle lost) work with a Switch 2
over Bluetooth by patching the controller firmware so it behaves like a Switch 2 Pro Controller.
Detailed logs: `PHASE0.md` (static analysis), `PHASE1_WINDOWS.md` (flashing + test log), `SWITCH2_PROTOCOL.md` (protocol spec
compiled from public sources: espp PR #765, ndeadly/switch2_controller_research, zhantss emulator).

## Status

| Milestone | State |
|---|---|
| Firmware mapped (BLE stack, modes, buttons, flash layout) | done |
| Safe flashing in both directions with a pre-flight checksum gate | done |
| Recovery via bootloader + full 512 KB flash backup | done, used several times |
| Boot checks fully understood | done |
| C code compiled and running on the controller | done |
| Switch 2 mode step 1: advertise as Pro Controller 2 | **done, the Switch 2 connects to it** |
| Step 2: Nintendo service table (56 attrs) + larger MTU | designing |
| Step 3: pairing handshake (command 0x15, AES) | not started |
| Step 4: console command replies | not started |
| Step 5: input reports (buttons/sticks) | not started |

Controller state right now: running a test image (`mod-sw2adv-y20-v109.bin`): stock behaviour on a normal power-on,
Pro Controller 2 advertisement when **Y is held at power-on in Bluetooth mode**. Stock 1.09 is one command away
(`u2wflash.py flash firmware/payload-ctrl-v109.bin --yes --version 0x6d`).

## Key facts

### Device
- Ultimate 2 Wireless: Telink B80 (TC32 core), 512 KB flash, BLE-only radio (no Bluetooth Classic) plus Telink 2.4G.
- USB 2dc8:310b. Interfaces: If0 XInput, If1 HID keyboard, **If2 vendor HID (usage page 0xff7a) = firmware update channel**.
- Bootloader (hold L1+R1 while plugging USB): 2dc8:3208 "8BitDo Boot", HID, no report IDs.
- BT vs 2.4G is a physical slide switch (GPIO PB3). Power-on button state is a bitmask at RAM 0x845fe4; **Y = 0x20**
  (measured; nothing held = 0).
- Normal advertising address is the MAC stored at flash 0x7c000 (…:66:B5); stock pairing mode uses …:66:B6, and the stock
  firmware creates a new address for every pairing. Once bonded, stock firmware advertises *directed* to that host; Switch 2
  mode must force undirected advertising.
- Firmware downloads: `POST http://dl.8bitdo.com:8080/firmware/select` with header `Type: N`. 94 = Ultimate 2 wireless
  controller (latest public 1.09), 95 = its dongle, 108/98 = "Ultimate 2" family (AES-encrypted, not this model).
  1.10 is not on the public server; it was recovered from a USB capture of the official updater.

### Image and flash layout
- `.dat` = 28-byte header + payload. Payload base = flash 0x5000. Payload bytes 0x0000–0x4500 are ram_code: copied to SRAM
  at boot and executed at VMA 0 (Ghidra block `ramcode`). The rest runs in place from flash.
- Flash map: 0x0–0x4000 bootloader | 0x5000 bank A (live app) | 0x31000 update record (0x34 B) | 0x32000 bank B (staging) |
  0x74000 bonds | 0x7a000–0x7e000 8BitDo config | 0x7c000 holds the MAC.
- Normal-mode USB update writes **bank B**, then `c4` marks the record pending and `07` resets; the bootloader copies B→A,
  validates, and boots. If A fails its checks, the bootloader validates B and recovers from it.
- **Correction:** the empty flash at VMA 0xa100–0xd000 IS usable for new code. Earlier I thought the updater never wrote
  it; in fact the vendor updater skips sectors the device already holds (differential update). Our own flashes wrote code
  there and the pad booted.

### Boot checks (all three must pass or the bootloader refuses the image)
`size = u32 @payload 0x18` (1.09: 0x17a44)
1. Telink: `~CRC32(payload[0:size-4])` stored at `size-4`.
2. Bootloader check 1: sum32 of bytes `[0:size-4]` stored at `size`.
3. Bootloader check 2: sum32 of bytes `[size+4 : size+4+L]` stored right after, L = 0xbbdc (1.09) / 0xbc44 (1.10).
`tools/fixcrc.py` fixes/verifies all three, `tools/mkmod.py` applies asserted byte patches then fixes them, and
`u2wflash.py flash` refuses any image that fails them. My two early test flashes failed because I fixed none (first) and
only the Telink CRC (second); the pad stayed in its bootloader both times and was restored from there.

### Update protocol (HID If2; output report 0x81 + 63 B, input report 0x02)
- `81 04 00 01` device info (version byte, PID 0x6012). Session: `81 05 08`, `00 21 01`, `c1`.
- `c3 <addr><len>` returns CRC16 + sum32 of that flash sector **as currently stored** (read-only probe).
- `04 <sector>` + `03` data writes (46 B chunks, CRC-16/MODBUS) rewrite one sector; verify burst of `c3`; `c4 <total><version>`; `07` reset.
- Generator reproduces both captured vendor streams byte for byte (`u2wflash.py gen --template`).
- Bootloader (2dc8:3208): cmd 8 version, 5 read, 4 erase (param4 = bytes), 3 write; absolute flash addresses.
  Proven on this unit: read, erase, write, read-back verify (`tools/u2wboot.py`).

### Firmware internals (controller v1.09; Ghidra project `u2w_ctrl`)
- Main loop `FUN_0000d8c8`; BLE init `FUN_0000d558`; radio mode = `FUN_0000eef8` (PB3). Stock GATT table at 0x1b5a8
  (50 × 24-byte Telink attribute_t); registered by `FUN_0000d75c` → `FUN_000178e8`. Handles verified against what Windows
  enumerates (GAP 1, GATT 8, DIS 0xc, HID 0xf, Battery 0x2a, Telink OTA 0x2e).
- Hook points used: `tjl` at **0xd5b2** (bls_ll_setAdvData, 0x15894) and **0xd5ba** (setScanRspData, 0x15918).
- ATT dispatcher jump table at 0x1c48c: Exchange-MTU block 0x17ffa, Write Request/Command block 0x18042, Read 0x17ed8.
  ATT state struct 0x844d6c (+0x20/+0x22 MTU fields). `FUN_000187d0(0x40,0x40)` is called at BLE init.
- GATT notify = `FUN_000188b0(conn, handle, data, len)`; HID input report goes out via `FUN_0000e248`; bond store at 0x74000.
- Connection setup (`FUN_00016788`) and connection-update (`FUN_0001622c`) have **no minimum-interval check**, so the console's
  5 ms interval is not blocked in software. Real timing is still untested.
- RAM is tight: bss 0x845d80–0x84777d, stack top 0x848000.
- Stock link: Windows negotiated **ATT MTU 64** with the stock firmware.

### Test results so far
- Rename test: BLE names changed via data patch, visible in a scan.
- Code test: C hook placed in the cave and called through a patched `tjl`; scan showed its output byte for byte.
- Switch 2 test: Switch 2 on *Change Grip/Order*, controller powered on with Y. The console connected within ~1 s
  (8BitDo vibration + solid LED), held the link ~58 s on the stock services, then dropped and reconnected immediately.
  So the console accepts the advertisement and the radio link; nothing is shown on screen yet because the Nintendo
  services are not present.
- Windows auto-pairs with the stock firmware on connect (a prompt had to be allowed); that pairing stalled one probe attempt.

## Tooling (all under `8bitdo/`)
| Tool | Use |
|---|---|
| `tools/u2wflash.py` | normal-mode flasher: `info`, `checksums`, `flash`, `gen` |
| `tools/u2wboot.py` | bootloader: `version`, `read`, `compare`, `restore-sector` (`--base 0x5000/0x32000`) |
| `tools/mkmod.py`, `tools/fixcrc.py` | build and verify modded payloads |
| `tools/blescan.py`, `blewatch.py`, `bleprobe.py` | passive scan, live adv monitor, GATT/MTU probe (bleak) |
| `tools/gh.sh` + `tools/*.java`, `gatt.py` | headless Ghidra queries, GATT table parser |
| `tools/cap_start.ps1`, `cap_stop.ps1`, `extract_iap.py`, `verify_sectors.py` | USBPcap capture and decoding |
| `src/hook_adv`, `src/sw2`, `mods/*.py` | C sources and patch specs (build: `src/sw2/build.sh` via WSL) |
| `backup/flash-full-512k.bin` | full flash backup (copy in `C:\Users\lance\re-tools\backup`) |
Toolchain location (outside OneDrive): `C:\Users\lance\re-tools` (Ghidra 12.2 + JDK 25, TC32 module, Python venv with hidapi/bleak),
WSL Ubuntu-24.04 `~/tc32` (Telink tc32-elf-gcc 4.5.1).

## Procedures
- Flash a mod: build with `mkmod.py`, `fixcrc.py` to verify, unplug-free: controller on USB, then `u2wflash.py flash <img> --yes --version 0x6d`.
- Recover: hold L1+R1 while plugging USB, `u2wboot.py compare/restore-sector <stock> <sector>`; if bank B is stock the bootloader also
  self-heals a bad bank A.
- Back to stock: `u2wflash.py flash firmware/payload-ctrl-v109.bin --yes --version 0x6d`.
- Capture the official updater: reboot once after installing USBPcap, run `tools/cap_start.ps1` elevated (hub 2 had the controller).

## Gotchas learned
- USBPcap's driver only attaches after a reboot. `USBPcapCMD` writes pcap, not pcapng (`editcap -F pcapng` to convert).
- The controller re-enumerates after each update, so its USB device number changes between captures.
- Git Bash rewrites `/mnt/c/...` paths and expands `$PATH`; run WSL commands from PowerShell through `tools/tc32.sh`.
- Ghidra 12.2 needs JDK 25; headless scripts must be Java. The 2C project's prologue scanner searched for the wrong byte
  (`tpush {lr}` is high byte 0x65 here); fixed in our copy.
- TC32 compile guard: patched code must have no RAM globals (nothing initialises them); `build.sh` enforces this.
- Windows shows a permission prompt the first time it connects to the controller; allow it or the probe times out.
- Stock firmware uses a new BT address per pairing; remove stale Windows entries if they pile up.

## Risks and open questions
- 5 ms connection interval: not blocked in software, never exercised on hardware.
- Large ATT writes/replies: the console sends ~80-byte commands and expects ~90-byte replies; sources say it asks for MTU 512.
  Stock accepts 64. RAM for bigger buffers is the main design question (idle 2.4G buffers are candidates).
- Pairing: the console's key exchange is application-level (command 0x15, AES-128) followed by link encryption with a derived key;
  the plan is to write a bond record at 0x74000 so the stock stack handles encryption. Unproven.
- Console-side failure gives no reason, so a debug log (RAM ring buffer read back over BLE) is planned before more console attempts.

## Next steps
1. Build the Nintendo attribute table (56 entries, fixed handles per SWITCH2_PROTOCOL.md §2) and register it only in Y mode.
2. Decide the MTU/buffer approach; test with `bleprobe.py` from the PC (the PC stands in for the console).
3. Add the debug log; then pairing, command replies, input reports, each checked from the PC first and then on the console.
