# Current handoff — read this first

Updated 2026-11-07. Applies to Codex, Claude, or a human maintaining this project.

## Verified outcome

The exact **8BitDo Ultimate 2 Wireless** connects directly to Switch 2 over BLE.
Candidate 13 is installed. User verified connection, inputs, and the corrected
left/right D-pad mapping. Released as experimental v0.1.0:
https://github.com/lanstalor/8bitdo-u2w-switch2/releases/tag/v0.1.0

Image: `firmware/mod-sw2-candidate-13-v109.bin` and
`firmware/mod-sw2-working-v109.bin` (identical).
SHA256: `dcc2b955b425271f1193bb4a8ee49918fdb38b7f51b99be2ec1e36f9d52c07d0`.
Source release commit: `3551ad3f5437a9a31179e7d71a8d72457fab1268`.
Startup: Bluetooth mode, hold Y while powering on; Switch Change Grip/Order, L+R.

## What fixed it

1. A Bluetooth link, vibration, or stock solid LED did not mean Nintendo pairing.
2. Retained first-connection tracing survived a later PC diagnostic connection.
3. FEATURE_RSP was queued and transmit queues drained, but initial firmware
   advertised no LE2M. A new address alone did not fix the stall.
4. Real 2M support required radio-switch, PHY-instant, and connection-start
   callbacks. Candidate10 negotiated2M and progressed to an ATT MTU request.
5. Switch requested MTU512 and stalled at the earlier247 configuration.
   Candidate12 expanded transport buffers and negotiated512; pairing/input worked.
6. Candidate13 swapped the two horizontal D-pad bits. User confirmed the fix.

## Implementation constraints

- Telink B80/TC32, stock1.09 base. Three firmware integrity checks are mandatory.
- Code cave a100..d000; executable PHY overlay c04..d0c in RAM, copied at boot.
- Radio callback844d3c; instant844b88; connection-start844b8c. SDK and stock
  layouts differ: do not copy the SDK initializer wholesale or double-adjust
  the stock TX settle table.
- RX840d8c and TX840f9c each have520 usable bytes plus8 guard bytes. They reuse
  2.4G-only RAM code. The d9ba guard blocks the2.4G loop during physical-switch
  debounce, until stock reset reloads original RAM code. Never remove that guard.
- Normal flash updates staging bankB; bootloader copies to live bankA. Bootloader
  and factory/config regions were not replaced. Nintendo bonds use stock journal.
- Current diagnostic markercc: see sw2.c and tools/sw2_diag.py. Connecting a PC
  can interfere with the console connection; don't probe during gameplay.
- Keep application command bounds64 despite transportMTU512. Motion is fixed
  data; rumble is unimplemented. Reconnect/wake/endurance need further testing.

## Reproduce and validate

From the repository in PowerShell (this workstation):

```powershell
wsl.exe -d Ubuntu-24.04 -- bash tools/tc32.sh bash src/sw2/build.sh
wsl.exe -d Ubuntu-24.04 -- bash tools/test_sw2.sh
& C:/Users/lance/re-tools/venv/Scripts/python.exe tools/mkmod.py firmware/payload-ctrl-v109.bin mods/sw2_gatt.py firmware/rebuilt.bin
& C:/Users/lance/re-tools/venv/Scripts/python.exe tools/verify_sw2_gatt.py firmware/rebuilt.bin
```

Stop on any failed command. Five native suites, firmware integrity and GATT
checks passed. Live PC testing verified2M,MTU512,509-byte write value (ATT512),
150-byte response, input stream and intact guards. Full512-byte TX was not tested.
`tools/sw2_command_probe.py --mtu512 --input-secs 3` performs the boundary test.

For restoration, use [RECOVERY.md](RECOVERY.md). Original stock images and the
private full-device backup are local/ignored; GitHub alone does not include them.
`PROGRESS.md` records detailed chronological evidence; old CODEX_HANDOFF.md and
CLAUDE_HANDOFF.md describe pre-success states and are historical only.

Motion hardware was subsequently confirmed by the exact-model official product
page (6-axis control). Raw sensor access and Nintendo motion translation were
not implemented; user elected not to pursue it. No firmware change for that check.
