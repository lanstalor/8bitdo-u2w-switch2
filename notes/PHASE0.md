# U2W → Switch 2 (BLE): Phase 0 notes

Goal: make the 8BitDo Ultimate 2 Wireless controller (no dongle) pair with a Switch 2 over BLE
by emulating a Switch 2 Pro Controller. No hardware has been touched yet.

## Firmware (from dl.8bitdo.com:8080, `POST /firmware/select` with `Type:` header)
| Type | Name | Latest | Notes |
|---|---|---|---|
| 94 | Ultimate 2 wireless (controller) | v1.09 (2026-01-20) | plaintext, Telink TC32 |
| 95 | Ultimate 2 wireless Adapter (dongle) | v1.06 (2025-09-22) | plaintext, contains Switch Pro (USB) emulation |
| 108 | Ultimate 2 | v1.01 | AES-encrypted (different model) |
| 98 | Ultimate 2 Adapter | v1.03 | encrypted; readme: "added Switch 2 support" |

Container: 28-byte ebitdo header + payload.
- ctrl v1.09: dest_addr **0x5000**, len 0x23800, USB PID 0x6012
- dongle v1.06: dest_addr 0x5000, len 0x9e00, USB PID 0x6013

## Findings
- Controller radio is BLE only (Telink BLE SDK: "Telink Remote" default name, HID-over-GATT).
  The Switch 1 Pro Controller protocol runs over Bluetooth Classic, so it isn't possible on this hardware.
  The Switch 2 Pro Controller protocol is BLE (prior art: esp-cpp/espp PR #765, ndeadly/switch2_controller_research).
- The dongle holds all the Switch logic (`init_usb_switch`, `SWITCH_Cmd_0x01_Subcmd_*`). The controller
  sends raw input over Telink 2.4G.
- Controller GATT table: `0x1b5a8`, attNum=50, 24-byte Telink attribute_t records (tools/gatt.py).
  GAP, GATT, DIS (PnP 2dc8:6012), HID (report map 113 B @0x1b4b8, output report write cb 0xd535),
  Battery, Telink OTA (write cb 0x1a9a1). GAP preferred conn params: 25–50 ms, latency 0, timeout 10 s.
- TC32 encoding: `tpush {..,lr}` high byte = 0x65 (the 2C repo's CreateFuncs used 0xB5; fixed here).
  `tjl` high byte = 0x90–0x97.
- Ghidra coverage after the prologue scan: ctrl 600 funcs / 31.7k instr; dongle 217 funcs / 12k instr.

## Memory map (controller v1.09)
- Payload `0x0000–0x4500` = **ram_code**: copied to SRAM at boot and executed at **VMA 0** (verified: 41/54 tjl
  targets below 0x5000 land on tpush prologues). Its flash copy also appears at 0x5000–0x9500.
  Ghidra block `ramcode` @0 added by tools/AddRamcode.java.
- Flash XIP code/data: `0x5000 + offset`, through 0x28800.
- SRAM 32 KB `0x840000–0x848000`; globals reach ~0x847780 and the stack top is 0x848000, so **RAM is tight**.
- ~~Code cave 0xa100–0xd000~~: NOT usable. The official updater never writes flash 0xa000–0xd000 (see PHASE1_WINDOWS.md results). Candidate space: append past 0x28800 (if the bootloader accepts a longer image) or reuse code from features the Switch 2 mode drops.
- Totals after the ramcode block + prologue scan: 1144 functions / 40.7k instructions.

## Phase 0 answers
1. **5 ms connection interval: no software block.**
   - `FUN_00016788` = connect-request (CONNECT_IND) setup: interval `*(u16*)(p+0x1c)` × 20000 ticks, latency `p+0x1e`,
     timeout `p+0x20` × 160000, SCA `p[0x27]>>5`. No minimum check. `FUN_00016670(interval)` only picks a
     scheduling tier (<8, <0x50, else).
   - `FUN_0001622c` = control-PDU instant handler: opcode 0x00 CONN_UPDATE (interval @+6) and 0x01 CHANNEL_MAP,
     with the only check being that the instant is in the future. Opcode 0x18 PHY_UPDATE means 2M PHY is supported.
   - Still to confirm on hardware: real timing and CPU budget at 5 ms (2.4G mode already polls at 1000 Hz).
2. **BLE init** `FUN_0000d558`. Roles inferred from Telink SDK call order:
   - `FUN_0000d75c` → `FUN_000178e8(0x1b5a8)` = set attribute table
   - `FUN_00015894(0x1b3c4, 0x1e)` = set adv data. Adv data: `10 08 "8BitDo Ultimate"`, flags 06, appearance 0x03C4, UUIDs 1812/180F.
   - `FUN_00015918(0x1b3e4, 0x1c)` = set scan response (complete name)
   - `FUN_00019ff8` = bonded-device count; if bonded, `FUN_0001a3b4` loads the bond and adv becomes directed (type 4)
   - `FUN_00015968(0x30, 0x38, type, …, chn 7, filter 0)` = set adv params
   - `FUN_000155c4(evt, cb)` ×5 = event callbacks (1, 0xf, 3, 0xd, 4); `FUN_00019fa8` is probably SMP peripheral init
   - Called from `FUN_0000d778` (RF cal from flash +0x1c0, then full init vs deep-retention init `FUN_0000d69c`)
3. **Mode selection**
   - `main` = `FUN_0000d8c8`. `FUN_0000eef8()` returns radio mode: 1 if flag `0x846040` (cable?) is set, else
     **GPIO PB3** (`0x800588` bit 3), so **BT vs 2.4G is a physical slide switch**.
     Mode 1 → 2.4G init `FUN_0000ff6c` + loop `FUN_000002bc`; mode 0 → BLE init `FUN_0000d778` + loop `FUN_0000d73c`.
   - Power-on sub-mode (2.4G): button bitmask `u32 @0x845fe4`. Mask `0x20020` → submode 2 (D-input, B) and
     `0x21000` → submode 1 (Switch, Y), stored at `0x84615d`. Each mask has 2 bits (likely two label layouts).
   - Plan: in BLE init, if `(*(u32*)0x845fe4 & 0x21000)` → Switch 2 BLE mode.
   - `FUN_0000dfd4` / `FUN_0000e0b8` = battery voltage check / low-battery shutdown (not mode related).
4. **Free space:** 12 KB flash cave (see above). RAM must reuse 2.4G and normal-HID buffers.
5. **LTK route:** Telink bond storage is a flash record `smp_param_save_t` {flag, peer_addr_type, peer_addr[6], cflg,
   peer_id_adrType, peer_id_addr[6], own_ltk[16], peer_irk[16], local_irk[16]} (b80 SDK smp_storage.h).
   After the Switch 2 pairing handshake derives the LTK, write a bond record for the console, and the stock
   LL_ENC_REQ path should find it. No stack-internals patch needed, if this holds.

6. **Flash layout (512 KB chip):** `FUN_000128a8` = flash capacity code (0x13 = 512K, 0x14 = 1M, 0x15 = 2M).
   `FUN_00018b18` (host/L2CAP callback registration) calls `FUN_0001a004(0x74000)` = bond storage address
   (0xfc000 / 0x1fc000 on bigger chips). Other sectors: 0x76000 MAC, 0x77000 RF cal, 0x7a000/0x7b000 8BitDo
   settings (`FUN_0000e7b4` = sector erase, `FUN_0000e8f4` = flash write), 0x7c000–0x7e000 more config (`FUN_0001274c`).
   `FUN_0001a3b4` = load bond by index (64-byte record = sizeof smp_param_save_t). `FUN_00019ff8` = bond count.
7. **GATT notify:** `FUN_000188b0(connHandle, attHandle, data, len)`.
   - HID input report: `FUN_0000e248` → `FUN_000188b0(0x40, 0x1d, buf, 0x21)`, a 33-byte report, so MTU > 23 already.
   - Battery: `FUN_0000e1cc` → `(0x40, 0x2c, &lvl, 1)`.
   - OTA uses it too (~0x1a99c).
   - BLE loop `FUN_0000d73c` → `FUN_00002cac` (stack main loop, ramcode) + `FUN_0000d6a0` (periodic report/battery) + `FUN_0000d708`.
   - ATT writes go through the per-attribute `.w` callback in the table, so a Switch 2 command characteristic just gets its own callback.

## Phase 0 verdict (2026-11-07): GO for non-destructive Phase 1
Measured against notes/SWITCH2_PROTOCOL.md:
- 5 ms interval: no software check (items 1).
- 2M PHY: the PHY_UPDATE handler is present.
- LTK with EDIV = Rand = 0: route via a bond record at 0x74000 (item 5/6). Unproven; this is the second-biggest risk.
- Flash: the new mode is estimated at ~6 KB (GATT ~1.5 KB, command handler ~3 KB, pairing ~0.5 KB using HW AES,
  reports/adv ~1 KB, canned flash blocks ~250 B). UPDATE: the 0xa000–0xd000 "cave" is not usable (never written by the updater), so space must come from appending past 0x28800 or reusing dropped-feature code. Open item for Phase 2.
- RAM: **ATT MTU 512** (the console reportedly stalls if offered less) needs a ~512 B L2CAP RX buffer
  (`blc_l2cap_initRxDataBuffer`) on top of 63-byte notifies. Telink loads these sizes from constant pools, so
  static reading was inconclusive. Plan: reuse 2.4G-mode buffers, which are idle in BLE mode, and measure
  the current MTU on hardware first.

## Next
- Phase 1a (no flashing): connect from a phone with nRF Connect in BT mode; record the MTU granted when 512 is
  requested, the GATT handles (compare with tools/gatt.py output), and the connection parameters.
- Pull the Switch 2 Pro Controller GATT layout, adv data and pairing sequence from ndeadly/switch2_controller_research
  and espp PR #765 into notes/SWITCH2_PROTOCOL.md.
- Size estimate for the new mode against the 12 KB cave.

## Hardware steps (Phase 1, needs the controller)
- USBPcap capture of Ultimate Software V2 flashing the controller (confirm 0x8105 protocol + CRC as on the 2C).
- Test the L1+R1 bootloader entry (expect a new USB ID such as 2dc8:32xx).
- Optional: SWS full flash backup (USB-serial adapter, opens the shell).

## Environment
- Tools (not OneDrive-synced): `C:\Users\lance\re-tools` → Ghidra 12.2, Temurin JDK 25.0.4.1,
  TC32 module (trust1995 @ f466dac), Ghidra projects in `projects/`, Python venv with pyelftools.
- Ghidra headless: `support\analyzeHeadless.bat`, processor `Telink_TC32:LE:16:default`, BinaryLoader, base 0x5000.
- Reference: `ref/8bitdo-2c-re-flake` (2C RE), `ref/tc_ble_simple_sdk/b80_ble_sdk` (Telink B80 SDK + liblt_8208.a).
