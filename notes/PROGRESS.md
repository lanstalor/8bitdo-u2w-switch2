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
| Step 2: Nintendo service table + larger MTU | **discovery/read verified on PC with V3; MTU247 verified with V4** |
| Step 3: pairing handshake (command 0x15, AES) | implemented in final candidate; host transcript/crypto tests pass; radio unverified |
| Step 4: console command replies | implemented with busy retry; host tests pass; live V5 identified dropped reply (0xB4) |
| Step 5: input reports (buttons/sticks) | implemented in final candidate; host framing/gating tests pass; hardware unverified |

Controller state right now: final candidate `mod-sw2-final-candidate-v109.bin` flashed and verified.
Nintendo mode requires **Y held at power-on in Bluetooth mode**. Pairing/input are implemented but
console acceptance is not yet tested. User's ONE final firmware load has now been used; do not flash again.

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

## Continuation: discovery table (2026-11-07)

- Reviewed all prior logs; the cave, three boot checks, recovery and initial console link remain established results.
- Added `tools/gen_sw2_gatt.py`, generated `src/sw2/gatt.inc`, and `mods/sw2_gatt.py`.
  Hook at 0xd768 selects 56 Nintendo attributes in Y mode. All writable flash-backed
  values have a consume-only callback; CCCDs are NOT persisted at this stage.
- `tools/verify_sw2_gatt.py` validates the compiled payload's declarations, key UUIDs,
  fixed handles, pointer bounds and write callbacks. Both builds pass; no RAM globals;
  linker asserts the code remains inside the proven 0xa100..0xd000 cave.
- First build flashed and verified (3 sectors). Windows auto-connected to its old
  E4:17:D8:BC:66:B6 pairing. Removed that Windows pairing only. Subsequent scan found
  `Pro Controller`, but uncached GATT discovery failed with WinError -2147418113,
  even with the permission prompt accepted. This is NOT a successful discovery test.
- V2 flashed and verified (3 sectors). Hooks: 0xd570 (previous no-op) prepares a
  stable mode-specific address from factory bytes at 0x7c000, XORing low byte 0x80
  (this unit: E4:17:D8:BC:66:35); 0xd5be returns zero stock bonds in Y mode to force
  undirected discovery; 0xd74c suppresses stock HID/battery reports in Y mode because
  their handles now mean something else. Normal mode passes through. V2 live test pending.
- `bleprobe.py` now parses options correctly and explicitly requests uncached services.
- New static memory evidence: literal at 0x18c84 points to L2CAP struct 0x844dc8.
  Its initialized +0x0c/+0x10 pointers are 0x845b80/0x845c80, with +0x14/+0x16
  sizes 0x100/0x100. Existing reassembly buffers are 256 B each, distinct from
  the 8x64-byte LL RX FIFO. This does NOT prove safe MTU 512; do not raise MTU to
  512 without resizing/auditing the relevant buffers and handlers.
- Disassembly confirms 0x187d0 is a request-MTU sender, not a general buffer-init API:
  it stores requested size at ATT+0x20, uses 0x9e at +0x22 for connection 0x40, and
  sends ATT opcode 0x02. Prior decompilation obscured the packet construction.

### V3: discovery proven, packet-level diagnosis

- V1 renamed `firmware/obsolete-discovery-v1-do-not-flash.bin` following review.
- Captured the Intel Bluetooth adapter only: USBPcap2, USB device 1 (8087:0032),
  `captures/sw2-gatt-v2-bluetooth.pcap`. Frame 2243 asks for service 0x1801;
  frame 2251 contains repeated `(start=0x38,end=0)` pairs. Windows disconnects
  after 30 seconds, frame 15365, reason Local Host. This was a malformed firmware
  reply, NOT a missing Windows permission. Stock group-end finder 0x1799c returns
  zero for a service at the final handle with no children.
- Added Service Changed declaration/value/CCCD at 0x39/0x3a/0x3b. All original
  Nintendo handles stay fixed; total is now 59 attributes, GATT service group count 4.
- V2's live KEY_Y check failed after release: capture showed stock 0x1d reports.
  V3 runtime hooks use the registered table pointer at 0x844d6c as the mode latch.
- V3 additional hooks 0xd48a (MTU request) and 0xd496 (connection parameters) pass
  through in normal mode; Y mode sends neither stock request. Local RX size remains
  64, host initiates MTU. Stock requests were MTU64 and interval6/6, latency59, timeout200.
- V3 built, boot checks passed, flashed/verified 3 sectors. **Live PC probe succeeded:**
  all four services, Nintendo characteristics and descriptors discovered; known svc1
  values correct; full 63-byte input value read; ATT MTU64; clean probe disconnect.
  Windows/Bleak reports characteristic DECLARATION handles (e.g. 0x0d); wire value
  handles remain 0x0e, verified in HCI capture. Do not shift the firmware table to
  match the Bleak display.
- `captures/sw2-gatt-v3-bluetooth.pcap` verifies host-originated MTU request527,
  controller response64; no stock notifications. SMP Security Request is still sent
  by the stock stack and must be disabled for Nintendo pairing. Read-blob at end of
  the 63-byte value is marked malformed by tshark, but Windows completed the read;
  retain this as a separate stock ATT edge-case to inspect if it matters later.
- Verifier now checks service group counts and every permission byte as requested
  in external review, plus declarations/UUIDs/handles/pointers/callbacks.
- Remaining: larger bounded messages, command replies, SMP suppression, application
  pairing/AES + LTK install/persistence, actual controls, console test and reconnect.
  This is NOT playable firmware and no console pairing success is claimed.

### V4/V5: command transport and diagnostic state

- Added host-testable `src/sw2/protocol.c`: framing, init ACKs, firmware info, canned
  flash/calibration reads, late-init 0x11/0x18 and NFC replies. Pairing command0x15
  explicitly returns no reply until real LTK integration exists; no fake success.
- `src/test/protocol_test.c` passes GCC ASan/UBSan: published byte vectors,
  truncations/capacity limits, 20,000 malformed frames. Compile/run in WSL with
  `gcc -Wall -Wextra -Werror -fsanitize=address,undefined -g src/sw2/protocol.c src/test/protocol_test.c -o /tmp/u2w-protocol-test`.
- V4 flashed/verified 4 sectors; PC negotiated MTU247 (fits existing 256-byte
  reassembly allocation with framing). Subscription and first write0x16 were
  captured, but no notification arrived. See `captures/sw2-command-v4-bluetooth.pcap`.
  MTU negotiation succeeded; large command transport is NOT proven yet.
- V5 adds 8-byte diagnostics at RAM0x846fb8, exposed as readable char value0x26:
  u16 handle, u16 incoming L2CAP length, u16 reply length, u8 notify result, u8 stage.
  This is the first 8 bytes of the 31-byte proprietary-radio RX command scratch:
  init0xff6c, RX0xaf0, reply0x102d4 (see `analysis/q/sw2-state.txt`). These radio
  paths are inactive in BLE mode. Initialized only in Y-mode GATT registration.
- Disabled automatic SMP Security Requests in Y mode by clearing config/pending
  at0x844f28/0x844f29 after SMP init (low/high nibbles govern new/reconnect in
  0x19d94; delayed request read in0x19ea8). Still requires live capture verification.
- `tools/sw2_command_probe.py` subscribes, writes documented commands, verifies
  bytes, tests129-byte padded request and150-byte reply, prints diagnostic on timeout.
  It no longer forces Windows pairing. Removed Windows development-address36 pairing
  before V5 to avoid stale bond interference. Normal controller addresses unaffected.
- V5 built, checksum/table checks passed, flashed/verified 4 sectors. First scan
  timed out without an advertisement; capture had no connection/ATT/SMP attempt.
  That is not a V5 transport failure. Waiting for user power-on, then rerun probe.
  Capture process stopped; no background capture is left running.
- Added independent `pairing_crypto.c/.h` with software AES128, LTK XOR and reversed
  key/challenge proof convention. Native ASan/UBSan test passes FIPS AES vector and
  the published Nintendo golden LTK/B2 vector. TC32 compilation passes. Not linked
  into flashed V5 and no pairing state machine or LTK persistence implemented yet.

### Last-flash constraint and final candidate (2026-11-07)

- User explicitly permits only ONE further firmware load. Direct Bluetooth is the
  required outcome; the dongle is lost and an adapter route is not acceptable.
  **The last flash has NOT been used yet.** Current controller remains V5.
- V5 retry capture `captures/sw2-command-v5-retry-bluetooth.pcap`: diagnostic
  `16 00 2c 00 17 00 b4 03` proves the write callback ran, parsed the request,
  generated 23 bytes, and the stock notify function rejected it with 0xB4.
  Stock notify at0x188b0 temporarily blocks after MTU activity (~300ms).
  V5 discarded that reply. A settled-delay probe then found no advertisement;
  it did NOT prove large-write/reply success. All capture processes stopped.
- Online shortcut research found biase-d's 2026-10-26 exact-model claim of direct
  Switch2 pairing/wake/gyro on controller1.10, but no public firmware/source among
  the author's eight public repositories. Announcement is unverified, not a binary:
  https://gist.github.com/barraIhsan/783a82bcf32bed896c85d27dbb8018a5?permalink_comment_id=6445295
  No messages posted or sent to the author. Published ESP32 implementations remain
  protocol references, not drop-in Telink firmware. Official USB Adapter2 supports
  the controller since1.08 and Switch2 since1.09, but user rejects the hardware route.
- Added `session.c/.h`: ordered 0x15/01,04,02,03 handshake with retry-idempotent
  responses, published AES proof, feature state, 63-byte input packing. Main button
  mapping derived from stock XInput builder0x10fb8; sticks/extra buttons require
  console confirmation. Gyro currently emits zero motion data; rumble is ignored.
- Stock LL key injection now identified directly: register callback0x16220;
  callback ABI(conn, randPointer, ediv) confirmed in disassembly0x16d82..0x16d90;
  key reply0x1727c copies16 bytes to0x844c64 and sets state0x844c3d=2.
  Custom callback answers only RAND0/EDIV0 with the derived LTK; no standard SMP.
  Evidence: `analysis/q/ll-key.txt`, `ll-key-disasm.txt`, `smp-full.txt`.
- Persistent keys use existing stock bond-journal API0x1a560 and load0x1a3b4,
  with a versioned SW2Y tag in the unused local-IRK field. Save occurs only after
  actual encryption flag0x844c3e is set; failed saves do not loop. No invented flash
  region. Record flag matches stock save construction (config0x844f45 OR0x10).
  Reconnect loads the latest tagged record and answers LL key requests without0x15.
- Runtime RAM: proprietary-radio RX first64 bytes0x84618c for normalized pending
  command; proprietary-radio command assembly first68 bytes0x84710c for state;
  31-byte scratch0x846fb8 holds8 diagnostics plus16 CCCD bytes. Literal scans found
  only0x10050 and0xba4 references to the first two regions, both 2.4G-only paths.
  Struct-size compile assertion enforces the68-byte bound. No new linked globals.
- Replaced immediate send with a one-command retry queue; all known initialization
  commands fit64 normalized bytes. Preserves response through busy/FIFO errors;
  reply traffic takes priority over15ms input streaming. Input requires CCCD and
  actual LL encryption. CCCDs are now RAM-backed and readable.
- Own address in handshake comes from initialized LL public address0x8449e4.
  New hook0xd750 bypasses the stock Sync path that rotates the MAC; it returns to
  Nintendo discovery with the same address. Disconnect handler restarts advertising;
  stored bond advertises wake flag0x81 and console identity address.
- Link-layer connection/update paths examined: no lower-bound clamp found in
 0x16788/0x1622c/0x169d0/0x16670; this is static evidence, NOT a proven5ms link.
- Candidate `firmware/mod-sw2-final-candidate-v109.bin`: 7184-byte cave payload,
  all three boot checks and binary GATT verifier pass. No last-flash use yet.
  Host ASan/UBSan tests cover full golden pairing transcript, malformed sequencing,
  repeated replies under backpressure,150-byte response, simulated key callback,
  persistence/reboot/reconnect, input gating and Sync-to-discovery. Mocks cannot
  prove radio timing, flash-journal behavior on hardware, or console acceptance.

### Final load completed

- User connected USB; detected 2dc8:310b interface2 usageff7a.
- Flashed `mod-sw2-final-candidate-v109.bin`, SHA256
  `7c2337f192cadaf5c29c822af95ba0f46a8adee1bc5ab3864611a502b358af3f`.
- All boot checks passed; wrote4/36 sectors (payload offsets0x5000,0x6000,
  0x8000,0x17000), all sectors verified, commit/reset completed successfully.
- **The user's last allowed firmware load is USED. No further flashing authorized.**
  Bluetooth command check and actual console test remain to be performed.

### Final candidate: live PC transport passed

- Controller reboot enumerated normally over USB. User unplugged and booted Y/Bluetooth.
- `sw2_command_probe.py` connected to E4:17:D8:BC:66:36, MTU247. All exchanges
  passed with NO settle delay:07/01,10/01,02/04 padded129-byte request,
  02/04 maximum150-byte reply,16/01,11/03,18/01,0c/02. This is the first
  successful live command-transport test. Capture: `captures/sw2-final-pc-bluetooth.pcap`.
- Read-only pairing-address exchange15/01 also passed: returned identity
  E4:17:D8:BC:66:36 exactly matches the advertisement. No key exchange or
  Nintendo bond was saved during this PC check. Client disconnected cleanly.
- USBPcap process34164 stopped. No PC BLE client/capture remains running.
- User instructed to open Switch2 Controllers > Change Grip/Order and pressL+R.
  Waiting for actual console result; do not infer pairing from PC success or LEDs.

### Console result and Claude handoff (2026-11-07)

- Actual Switch2 test FAILED: controller vibrated/went solid, but no player icon or
  working input after LB+RB in Change Grip/Order; Pair-button attempt did not help.
  Solid LEDs do not establish Nintendo pairing; custom disconnect handling does
  not restore stock LED state. No console-side packet capture is available.
- After restart in Y/Bluetooth, advertisement wake flag and console address were
  zero: no tagged Switch bond loaded. This does not locate the failed handshake,
  encryption or persistence step.
- PC diagnostic read returned `3b 00 05 00 00 00 ff 01`: Windows automatically wrote
  Service Changed CCCD0x3b and overwrote the previous console diagnostic. The current
  single-record diagnostic cannot reliably recover the console failure through a
  Windows reconnect. Retained event/failure logging needs review.
- No further firmware has been loaded. Last observed state: USB unplugged,
  Y/Bluetooth powered on, Switch outside Change Grip/Order, PC client closed.
- User now permits another attempt, superseding the prior no-further-flash limit,
  and requested a fresh Claude Code review. User already has an active Claude chat
  and asked only for a handoff here. See `notes/CLAUDE_HANDOFF.md` for current image
  hash, verified results, unresolved assumptions, code/evidence map and review scope.

### Review and candidate 2 (Claude, 2026-11-07 11:40) - NOT flashed

Independent review of the flashed candidate against the stock disassembly:

- Verified correct: init order (GATT registration zeroes the Y-mode state before
  the advertising hook loads the bond); lazy event-4 registration overrides the
  stock disconnect handler that `FUN_0000d558` registers last; `0x84445c` is the
  app "connected" flag (connect handler sets 1, disconnect 0); `0x844c3e` is
  LL+0x2e, set when the LL moves key state 2->3 and starts encryption.
- 0xB4 root cause: `0x188b0` returns 0xB4 while `now - ATT+0x1c <= 10000*ATT+0x28*16`
  (ATT+0x28 @0x844d94 is the data-pending time in 10 ms units, ~30 = 300 ms).
  ATT+0x1c is stamped ONLY by discovery PDUs: opcodes 0x04/0x06/0x08/0x10 at
  0x17d30/0x17d8a/0x17e60/0x17f0a (jump table @0x1c48c). Writes, reads and MTU
  do not restart it, so rumble/command writes cannot starve replies or input.
  The retry queue is sufficient; the live PC transport pass confirms it.
- Side effect to expect: the Nintendo bond is a stock-journal record, so stock
  normal mode will treat the console as its newest bond and advertise with the
  whitelist/directed path (`FUN_0000d558`, adv type 4, filter 7). After a Switch
  pairing, normal Bluetooth mode will not accept the PC until the pair button is
  pressed (stock then rotates the address and opens advertising).
- Post-mortem after a failed console attempt: do NOT power off. Run
  `tools/sw2_diag.py`: it decodes the advertisement (0x81 + console address =
  the firmware believes it is bonded) and reads char 0x26 (stage codes 0x02
  queued, 0x03 reply attempted + notify status, 0x40 LTK answered, 0x41 bond
  saved, 0xe1 save failed, 0xe2 command dropped, 0xe3 unknown command).

Candidate 2 (`firmware/mod-sw2-final-candidate-2-v109.bin`, SHA256 8d04045400c02ae1...;
boot checks, GATT verifier and all four host suites pass) differs
from the flashed image in three ways, all in `src/sw2/sw2.c`:

1. Input reports gated on CCCD + features only, not on link encryption, so the
   PC can verify report framing and button/stick mapping (`sw2_command_probe.py`
   now streams and decodes input for `--input-secs`). The console encrypts anyway.
2. Normal mode advertises the stock data again (debug key-bitmask variant removed).
3. `0x844d94 = 0` on connect in Y mode: no notify hold-off after discovery.

It is built and verified but NOT flashed: the user's last allowed load was used
on the first candidate. Flash only if the user lifts that rule; the flashed image
is functionally equivalent for the console path (encryption gate, retry queue).

### Candidate 3 flashed (Claude, 2026-11-07 ~12:05) - console result pending

Console test of the first candidate FAILED (vibrate + solid LED = LL connection
only; no icon in Change Grip/Order). Its 8-byte diagnostic was overwritten by
Windows' Service Changed CCCD write, so nothing was learned. Candidate 3
(`firmware/mod-sw2-candidate-3-v109.bin`, SHA256 e126d35c75d3a77c...) =
candidate 2 plus a sticky post-mortem record:

- Char 0x26 now exposes a 15-byte record at 0x846fb8, cleared only at boot:
  last command handle/cmd/sub, last reply notify status, counts of accepted
  commands and sent replies, last event code, last CCCD handle, LTK request
  outcome and fw_ltkReply return, encryption-started flag, bond save result,
  effective ATT MTU at the last command, last disconnect reason, pairing stage
  high-water. Layout documented at the top of `src/sw2/sw2.c`.
- CCCD RAM moved to 0x846fc7..0x846fd6 (record 15 + CCCDs 16 = the 31-byte
  audited scratch, nothing outside it). Verifier updated.
- Carries candidate 2 changes: input streams without link encryption (PC can
  verify mapping), stock normal-mode advertisement, `0x844d94 = 0` on connect
  (no 300 ms notify hold-off after the console's service discovery; the console
  DOES read the table during discovery per SWITCH2_PROTOCOL.md item 8, so the
  first candidate's first reply was delayed up to 300 ms - leading hypothesis
  for the console failure).
- Flashed over normal-mode USB, 4 sectors written and verified, c4/07 OK.
- Host suites (runtime/protocol/session/crypto) pass; runtime test caught the
  record/CCCD overlap in the first build of this candidate.

Procedure: boot with Y held -> `tools/sw2_command_probe.py` (transport, 150-byte
reply, then 15 s of decoded input reports: press buttons / move sticks) ->
console Change Grip/Order with L+R -> on failure, do NOT power off, run
`tools/sw2_diag.py` and paste its output into the notes.

### Candidate 3 PC results and candidate 4 (Claude, 2026-11-07 ~12:40)

- Candidate 3 live PC probe: all 8 command exchanges pass with MTU 247 and no
  delay; 63-byte input report streams at 65/s without link encryption; button
  bits and both sticks change with physical input (mapping/direction still to be
  confirmed against the console). Post-mortem record read back correctly after
  the session: 8 accepted / 8 replied, MTU 247, last disconnect 0x13.
- The controller powered itself off twice while idle. Cause (stock, not Y-mode):
  key scanner 0xf298 counts idle scans in u16 @0x845fd4; unconnected threshold
  @0x845a1c (~1-2 min); key presses do NOT reset the count while unconnected.
  Pairing-mode flag @0x846013 (set by the stock pair-button path 0xf734) zeroes
  the counter every scan and is cleared by the stock connect handler 0xd448.
- Candidate 4 (`firmware/mod-sw2-candidate-4-v109.bin`, SHA256 1d836aaa2acac8d4...)
  = candidate 3 + Y mode sets that flag while unconnected for 4 min after boot or
  disconnect (`idle_from` in Sw2Runtime), so a failed console attempt leaves time
  to run `tools/sw2_diag.py`. Host tests cover the window. NOT yet flashed.
