# Claude Code handoff — Ultimate 2 Wireless to Switch 2

Updated 2026-11-07. Read this before proposing another flash. This is a mature reverse-engineering effort, not a stock controller pairing question.

## Request and current outcome

Lance wants his exact **8BitDo Ultimate 2 Wireless** to work directly over Bluetooth with Switch 2. It is NOT the Ultimate 2 Bluetooth model. The original dongle is lost; adapters/dongles are not the requested solution.

**Current firmware passes live Windows BLE command tests but failed the actual Switch 2 test. No successful Nintendo pairing or playable input has been demonstrated.** The controller vibrates and goes solid, but no player/controller icon appears in Change Grip/Order, including after LB+RB and a subsequent Pair-button attempt. LEDs/vibration are not proof of successful Nintendo pairing. The custom disconnect path also does not restore stock LED state.

The user had limited us to one final flash; that flash was used. He has now said another attempt is okay, but asked for a fresh Claude review and specifically requested this handoff for his existing Claude chat. Review and diagnose before another build/flash. Do not repeat the introductory experiments or reset the working tree. There are substantial uncommitted changes.

Last observed hardware state: USB unplugged, powered on with Y held in physical Bluetooth mode, Switch outside Change Grip/Order, PC diagnostic connection closed. Reconfirm physical state only when an operation needs it. No BLE probe or capture process was left running at handoff.

## Installed image and recovery

- Workspace: `C:\Users\lance\OneDrive\Documents\_CODE\8bitdo` (PowerShell).
- Installed: `firmware/mod-sw2-final-candidate-v109.bin`.
- SHA256, rechecked at handoff: `7c2337f192cadaf5c29c822af95ba0f46a8adee1bc5ab3864611a502b358af3f`.
- Flash completed and verified: four of 36 sectors, payload offsets `0x5000, 0x6000, 0x8000, 0x17000`; commit/reset successful, normal USB re-enumeration.
- Normal USB `2dc8:310b`, interface 2, usage `ff7a`. Recovery: hold L1+R1 while connecting USB, bootloader `2dc8:3208`. Recovery has worked previously.
- Full backup: `backup/flash-full-512k.bin` (also backed up under re-tools).
- Telink B80 / TC32, BLE-only, 512 KB flash, 32 KB RAM. Original Switch Bluetooth Classic emulation is not an option on this chip.
- Stock 1.09 payload at flash `0x5000`; bank B `0x32000`, update metadata `0x31000`, stock bonds `0x74000`, factory address `0x7c000`.
- First `0x4500` payload bytes execute from RAM VMA 0; later code executes from flash. Proven cave: `0xa100..0xd000`, currently 7184 bytes. Some early notes predate this finding.
- All three boot checks (Telink CRC and two sums) and binary GATT checks passed. Never flash the obsolete discovery image: V1 was renamed `firmware/obsolete-discovery-v1-do-not-flash.bin`.

## Verified results and important failed experiments

1. Windows discovery originally failed because the final empty GATT service at handle `0x38` made stock service-end finder `0x1799c` return zero. Capture showed repeated `(0x38,0)` ranges. This was NOT a Windows permission problem. Appending Service Changed declaration/value/CCCD at `0x39..0x3b` fixed it; Nintendo handles remain unchanged, total 59 attributes.
2. Checking the physical Y key at runtime was wrong: releasing Y allowed stock HID/battery reports onto Nintendo handles `0x1d`/`0x2c`. Runtime mode now uses the registered table pointer at `0x844d6c`.
3. Stock connect handler requested MTU64 and interval 6/6, latency59, timeout200. Both requests are suppressed in Y mode. Local preferred MTU247 fits the existing 256-byte L2CAP reassembly buffers; MTU512 is not justified.
4. V5 constructed replies but notify returned `0xb4` during a stock post-MTU holdoff (~300 ms); immediate callback replies were lost. Final firmware queues/retries from the main loop. Do not revive the immediate-send design.
5. **Final live Windows test passed with no settling delay**, address `E4:17:D8:BC:66:36`, MTU247: commands `07/01`, `10/01`, `02/04` with a padded 129-byte request, `02/04` with a 150-byte response, `16/01`, `11/03`, `18/01`, `0c/02`. Capture: `captures/sw2-final-pc-bluetooth.pcap`.
6. Separate `15/01` address exchange returned `E4:17:D8:BC:66:36`, matching advertising. The PC did NOT perform the full Nintendo key exchange or save a Nintendo bond.
7. Actual Switch 2 test then failed as described above. We do not have an over-the-air console capture. USBPcap on the PC Bluetooth adapter does not capture console-controller traffic.

## Latest diagnostic evidence — critical blind spot

After the console attempt and a power cycle, manufacturer data (excluding company ID) was:

`01 00 03 7e 05 69 20 00 01 00 00 00 00 00 00 00 0f 00 00 00 00 00 00 00`

Wake flag and console address are zero: no tagged Switch bond was loaded after restart. This does NOT identify whether the failure was before handshake completion, during encryption, or during persistence.

Reading diagnostic characteristic value `0x26` returned:

`3b 00 05 00 00 00 ff 01`

**Windows automatically wrote Service Changed CCCD `0x3b` when connecting, overwriting the console's last diagnostic.** The write callback resets diagnostic bytes before classifying the write. Do not interpret this as the console's last operation. A retained console-event trace or first-failure record that survives PC reconnect is the strongest next observability improvement. Also review what connect/disconnect/MTU hooks reset before relying on any retained state.

## Code map and runtime assumptions to audit

Read `src/sw2/sw2.c`, `session.c/.h`, `pairing_crypto.c/.h`, `protocol.c/.h`, `calls.s`, `link.ld`, `mods/sw2_gatt.py`, and `notes/SWITCH2_PROTOCOL.md`. Treat notes as evidence/history, not proof that implementation is correct.

- Y at boot selects Nintendo GATT; runtime latch is table-pointer equality. Normal mode passes through stock hooks.
- Hook sites: `d570` address preparation, `d5b2` advertising, `d5ba` scan response, `d5be` bond count, `d768` GATT, `d48a` MTU, `d496` connection parameters, `d74c` report loop, `d750` Pair button. Patch script asserts original bytes.
- Y address is factory address with bit7 of first stored byte flipped. Earlier notes show suffix `35`; current measured address is `...:66:36`. Handshake identity is copied from actual initialized LL address `0x8449e4`.
- Stock SMP Security Request config/pending at `0x844f28/29` is cleared in Y mode.
- Pending normalized command: 64 bytes at `0x84618c`; strips 33-byte transport prefix on handle `0x16`, ignores padding beyond declared payload. One pending command only; collision reports stage `e2`.
- Runtime state: at most 68 bytes at `0x84710c`. Diagnostics: 8 bytes at `0x846fb8`; RAM CCCDs: 16 bytes at `0x846fc0` for handles `b,f,1b,1f,23,27,2f,3b`.
- Those RAM regions are stock proprietary 2.4G buffers. Literal-reference audit found only 2.4G paths, but host mocks cannot establish absence of all hardware collisions. Do not enlarge allocations casually.
- Notify API `0x188b0`: `a1` for SMP state, `b5` for excessive MTU length, `b4` during holdoff. Queue retries until return0. Responses on `0x1e/0x1a` require respective CCCD. Largest known response150 bytes.
- Pairing session sequence `15/01` addresses, `15/04` key, `15/02` proof, `15/03` finish. AES implementation passes published Nintendo vector and FIPS vector. Ordering/duplicate retries tested. Hardware key byte order and console acceptance remain unproven.
- LTK callback registration `0x16220`; ABI `(conn, randPointer, ediv)` confirmed from assembly `0x16d82..0x16d90`. Reply `0x1727c` copies key to `0x844c64` and sets `0x844c3d=2`; negative reply `0x172b8`. Custom callback requires RAND0/EDIV0 and stage4 or loaded bond.
- Runtime marks bonded after successful finish reply; saves only when encryption byte `0x844c3e` is nonzero. Stock journal APIs: compact `0x1a130`, save `0x1a560`, load by index `0x1a3b4`, count `0x19ff8`. 64-byte record uses stock config flag OR `0x10`, host address and LTK, and `SW2Y` version1 tag in local-IRK bytes48 onward. Audit the record and encryption flag assumptions; actual successful saving is not demonstrated.
- Loaded bond sets wake advertisement flag `0x81` and host address. Pair button bypasses stock address rotation, clears runtime bond/session and restarts discovery; old flash bond is not erased by this action.
- Input: 63 bytes at handle `0x0e` every15ms, gated on CCCD, LL encryption and enabled feature bits. Main buttons derived from stock XInput builder `0x10fb8`; actual console mappings unverified. Gyro is zero data, rumble unimplemented. These omissions must not be mistaken for fully complete emulation.
- Custom disconnect clears connection/session/CCCD state and restarts advertising; audit replacement of stock disconnect cleanup as well as misleading solid LEDs.
- Static examination of `0x16788/0x1622c/0x169d0/0x16670` found no explicit minimum interval clamp below6. This does NOT prove a working 5ms Switch connection.

## Evidence, tools and tests

Decompilation can hide arguments at TC32 trampoline boundaries; confirm suspect ABI claims in assembly.

- `analysis/q/`: `smp-full.txt`, `smp-store.txt`, `ll-key.txt`, `ll-key-disasm.txt`, `bond-notify-disasm.txt`, `ble-app.txt`, `own-address.txt`, `adv-params.txt`, `notify.txt`, `radio-ram.txt`, `radio-xrefs.txt`, `keymap.txt` and earlier discovery/connection reports.
- Full decompilation: `analysis/ctrl/decomp.c`.
- SDK: `ref/tc_ble_simple_sdk/b80_ble_sdk`; `stack/ble/host/smp/smp_storage.h` documents journal record layout. Libraries `proj_lib/liblt_8208.a` and `liblt_8208B.a` provide symbol corroboration.
- Ghidra project: `C:/Users/lance/re-tools/projects`, project `u2w_ctrl`, program `payload-ctrl-v109.bin`. Ghidra12.2 and JDK25 are under `C:/Users/lance/re-tools/`. Scripts `tools/DecompRange.java`, `DisasmRange.java`, `XrefDecomp.java` support read-only investigation.
- Python: `C:/Users/lance/re-tools/venv/Scripts/python.exe`.
- Build: `wsl.exe -d Ubuntu-24.04 -- bash tools/tc32.sh bash src/sw2/build.sh`.
- Generator `tools/gen_sw2_gatt.py`; packer `tools/mkmod.py`; binary verifier `tools/verify_sw2_gatt.py` checks service group counts, permission bytes, declarations, UUIDs, handles and callback/pointer bounds.
- Native tests under `src/test/`: `protocol_test.c`, `pairing_crypto_test.c`, `session_test.c`, `runtime_test.c`. Passed GCC `-Wall -Wextra -Werror` with ASan/UBSan. Runtime test includes firmware with `SW2_HOST_TEST`, maps RAM and mocks stock APIs. Covers queue backpressure, 150-byte reply, handshake, LTK callback, simulated save/reboot/reconnect, input gates and Pair button. These mocks do NOT prove radio, encryption, journal persistence or console interoperability.
- Example session test: `wsl.exe -d Ubuntu-24.04 -- bash tools/tc32.sh bash -c 'gcc -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all -g src/sw2/protocol.c src/sw2/pairing_crypto.c src/sw2/session.c src/test/session_test.c -o /tmp/u2w-session-test && /tmp/u2w-session-test'`.
- Live PC probe: `tools/sw2_command_probe.py`. Reconnecting Windows can overwrite current diagnostics; avoid treating it as passive observation of console history.

## Online references already investigated

- Exact-model announcement by biase-d, 2026-10-26, claims experimental direct Switch2 Bluetooth on controller1.10/dongle1.06: <https://gist.github.com/barraIhsan/783a82bcf32bed896c85d27dbb8018a5?permalink_comment_id=6445295>. No released source/binary found in the author's eight public repositories. This is an unverified announcement, not an available shortcut firmware. No contact/message sent.
- <https://esp-cpp.github.io/espp/ble/switch2_pro.html>
- <https://github.com/esp-cpp/espp/blob/main/components/switch2_pro/DESIGN.md>
- <https://github.com/zhantss/ESP32-BLE5-NSController-Emulator>
- <https://github.com/ndeadly/switch2_controller_research>

These implementations are protocol references, not Telink drop-in binaries.

User also reported LT shorter/obstructed travel versus RT. Exact model has physical trigger-mode switches (long Hall travel versus short tactile travel); suggested checking LT's switch gently with trigger released. Not confirmed resolved, and does not explain the missing console player icon.

## Requested fresh review

Identify concrete bugs or unsupported assumptions from code and primary reference evidence. Rank findings by likelihood and consequence, distinguish proven defects from hypotheses, and cite files/addresses. Prioritize handshake/encryption transition, callback ABI/state, disconnect cleanup, bond-record construction, transport framing/CCCD behavior, and preservation of console diagnostics. Recommend the smallest change that can reveal or fix the actual failure before spending another user-assisted flash/test. Do not claim success based on Windows transport, mock tests, vibration or LEDs.
