# Switch 2 Pro Controller (BLE) - Protocol Spec for an Embedded C Implementation

Purpose: byte-exact reference for emulating a Switch 2 Pro Controller (PID 0x2069) over BLE
from a Telink BLE-only chip. Research compiled 2026-11-07 from the sources below. Nothing here
was tested on hardware by the author of this file.

Convention: "(inferred)" = deduced by me, not stated in a source. "(unverified)" = stated by one
source only and not cross-checked. All multi-byte wire values are little-endian unless noted.
Bluetooth addresses on the wire are in **reverse (on-air LE) byte order** (LSB first).

## Source key

| Tag | Source | Raw files read |
|---|---|---|
| ND-BT | ndeadly `bluetooth_interface.md` https://github.com/ndeadly/switch2_controller_research/blob/main/bluetooth_interface.md | adv formats, pairing narrative, GATT table, init sequence |
| ND-CMD | ndeadly `commands.md` https://github.com/ndeadly/switch2_controller_research/blob/main/commands.md | command header, 0x15, 0x0c, 0x10, 0x11, 0x16, 0x18 ... |
| ND-HID | ndeadly `hid_reports.md` https://github.com/ndeadly/switch2_controller_research/blob/main/hid_reports.md | input report 0x09 layout |
| ND-MEM | ndeadly `memory_layout.md` https://github.com/ndeadly/switch2_controller_research/blob/main/memory_layout.md | flash map |
| ESPP-D | espp `components/switch2_pro/DESIGN.md` https://github.com/esp-cpp/espp/blob/main/components/switch2_pro/DESIGN.md | design + verified behaviour |
| ESPP-R | espp `.../switch2_pro/README.md` | 5 ms interval discussion |
| ESPP-P | espp `.../include/switch2_pro_protocol.hpp` | UUIDs, constants, fixed key, golden vector |
| ESPP-C | espp `.../src/switch2_pro.cpp` | GATT build, adv, pairing handler, command handler, streaming |
| ESPP-K | espp `.../src/switch2_pro_pairing.cpp` + `include/switch2_pro_pairing.hpp` | AES step |
| ESPP-F | espp `.../src/switch2_pro_flash.hpp` | simulated flash blocks |
| ESPP-RPT | espp `.../include/switch2_pro_report.hpp` | report packing |
| ZH | zhantss/ESP32-BLE5-NSController-Emulator `main/src/{gatt,gap,device,ns2_codec,pro2}.c`, `main/src/controller/*`, `README.en.md` https://github.com/zhantss/ESP32-BLE5-NSController-Emulator | working C reference (NimBLE) |
| PK | Peterksharma/switch2mac `research/PROTOCOL.md` https://github.com/Peterksharma/switch2mac/blob/main/research/PROTOCOL.md | host-side notes |
| NF | Nadeflore/switch2-controllers | README only (host-side Python app, no protocol detail; not used) |

espp base: `https://github.com/esp-cpp/espp/blob/main/components/switch2_pro/` (PR #765 merged; file list confirmed via the PR page).

Important framing: ND/PK document the **real controller as seen by a host**. ESPP/ZH are
**emulators that a real console accepts** (ESPP verified on ESP32-S3 + IDF >= 6.1 incl. pairing,
streaming, reconnect, wake; ZH verified on C6/C61, S3 reported basic). Where they disagree, both are listed.

---

## 1. Advertising

### 1.1 Primary advertisement (ADV_IND, legacy, connectable + scannable)

Two AD structures, 31 bytes exactly (ESPP-P comment, ESPP-C `start_advertising`, ND-BT "Bluetooth LE Advertisements"):

```
02 01 06                      ; Flags: LE General Discoverable | BR/EDR Not Supported (0x06)
1B FF                         ; len=27, AD type 0xFF (manufacturer specific)
<26 bytes manufacturer data below, first two bytes are the company ID>
```

Manufacturer data, "Standard / discovery / pairing" variant (ND-BT row "Standard", ESPP-P `MANUFACTURER_DATA_DISCOVERY`, ZH `controller.c`):

```
53 05 01 00 03 7e 05 69 20 00 01 00 00 00 00 00 00 00 0f 00 00 00 00 00 00 00
```

| Off | Len | Value | Meaning (source) |
|---|---|---|---|
| 0x00 | 2 | `53 05` | Company ID 0x0553 Nintendo (ND-BT) |
| 0x02 | 1 | `01` | unknown, "always" (ND-BT) |
| 0x03 | 1 | `00` | unknown, always |
| 0x04 | 1 | `03` | unknown, always (ZH comment: "maybe version") |
| 0x05 | 2 | `7e 05` | Vendor ID 0x057E (LE) |
| 0x07 | 2 | `69 20` | Product ID 0x2069 = Pro Controller 2 (LE). "Switch 2 PIDs begin at 0x2060" (ND-BT). Other PIDs (PK): JC2-R 0x2066, JC2-L 0x2067, NSO GC 0x2073 |
| 0x09 | 1 | `00` | unknown, always |
| 0x0A | 1 | `01` | unknown, always |
| 0x0B | 1 | `00` / `81` | **wake flag**: 0x81 = wake advertisement, 0x00 otherwise (ND-BT) |
| 0x0C | 6 | host BD_ADDR | Bonded console address, **reverse byte order**; all 0x00 in discovery adv (ND-BT) |
| 0x12 | 1 | `0f` | unknown, always |
| 0x13 | 7 | `00`x7 | reserved |

Variants (ND-BT table; values from a real console, address `5f 11 85 eb f1 48` is that capture's console):

| Variant | Mfr data |
|---|---|
| Standard (unpaired, pairing mode) | `53 05 01 00 03 7e 05 69 20 00 01 00 00 00 00 00 00 00 0f 00 00 00 00 00 00 00` |
| Reconnection (bonded, no wake) | `53 05 01 00 03 7e 05 69 20 00 01 00 5f 11 85 eb f1 48 0f 00 00 00 00 00 00 00` |
| Wake console (bonded) | `53 05 01 00 03 7e 05 69 20 00 01 81 5f 11 85 eb f1 48 0f 00 00 00 00 00 00 00` |

Per-device / per-pairing fields: only bytes 0x0C..0x11 (console address) and byte 0x0B (mode). PID is fixed per model.
Everything else is constant (ND-BT). Console address = the **identity address the console sent in pairing 0x15/0x01**
(first address in that request), NOT necessarily the over-the-air connect address (ESPP-C `advertise()` comment;
ZH instead stores the connect-event peer address `desc.peer_ota_addr`, see section 8 item 5).

Behavioural notes:
- The console filters at SoC level on AD type 0xFF being present (ND-BT).
- An awake console **ignores the 0x00-flag reconnect variant** on idle screens; user-initiated wake must use 0x81 (ESPP-R "What the captures established", ESPP-C `advertise()` comment).
- Switching variants: stop advertising, set data, start (do not update while enabled) (ESPP-C `start_advertising`).

### 1.2 Scan response

- ESPP: scan response contains only the **device name** (default "Pro Controller") - `scan_response.setName(device_name_)` (ESPP-C `start_advertising`; `params.scan_response = true`).
- ZH: **no scan response**, only the 31-byte primary payload (ZH `device.c ble_advertise`).
- ND-BT: states the adv data "consists of only two entries, Flags and Manufacturer Data"; says nothing about scan response. Which means a scan response is **optional** (both emulators connect; ZH without). 

### 1.3 Type / interval / PHY

| Item | Value | Source |
|---|---|---|
| PDU | ADV_IND (connectable, scannable undirected), legacy | ND-BT |
| Address type | Public. A real controller uses a fixed address. ESPP prefers public; falls back to a stable static-random derived from the MAC. Console stores the controller address from 0x15/0x01 and "rejects an unstable one" | ESPP-C `init()` comment; ZH uses `BLE_OWN_ADDR_PUBLIC` |
| Interval | ESPP: 20-40 ms (library default `AdvertisingParameters`). ZH: 30 ms fixed (`BLE_GAP_ADV_FAST_INTERVAL1_MIN`). Real controller interval: not documented | espp `ble_gatt_server.hpp`; ZH `device.c` |
| Channels / PHY | all 3 channels, 1M | ZH `device.c` |
| Legacy vs extended | **Legacy.** ESPP errors out if NimBLE ext-adv is enabled. ZH uses ESP ext-adv API but with `legacy_pdu=1` (i.e. legacy PDUs on air) | ESPP-C top `#error`; ZH `device.c` |
| Console-to-controller wake adv | console sends ADV_NONCONN_IND, flags `18`, mfr data `53 05 03 00 01 00 80 <controller addr rev 6B> 01` - this is how "Search for controllers" wakes a controller. Not implemented by either emulator | ND-BT |

Wake behaviour (what to send, when): see section 6.

ZH controller address: `78:81:8c:xx:xx:xx` (Nintendo OUI, lower 3 bytes random, persisted) (ZH `controller.c`, `pro2.c`). ESPP uses the chip's own MAC. Whether the console checks the OUI: unknown (open question).

---

## 2. GATT

No standard HID-over-GATT, no DIS/BAS. A real Pro 2 exposes **only** two vendor services plus GAP and GATT (ESPP-C `init()` comment: extra DIS/BAS "make the console reject us after discovery").

### 2.1 Handle map (Pro Controller 2, firmware >= 2.0.0 layout with headset-audio attributes)

Source for UUIDs/handles: ND-BT GATT table; ESPP-C `log_handle_map`/`build_gatt`; ZH `gatt.c`. All three agree on these numbers.
The console **addresses attributes by fixed handle** and, per ESPP, a layout that does not match makes it fall into a discovery +
firmware-probe fallback that rejects the controller at pairing commit (ESPP-C `build_gatt` comment). ND-BT's init sequence is a list of writes
to fixed handles (0x0016, 0x001F, 0x000F ...). So: **reproduce these handle numbers exactly.**

| Handle | Kind | UUID | Props | Role |
|---|---|---|---|---|
| 0x0001 | Primary Service | `00c5af5d-1964-4e30-8f51-1956f96bd280` | - | "svc1", unknown purpose; end 0x0007 |
| 0x0002/0x0003 | Char | `00c5af5d-1964-4e30-8f51-1956f96bd281` | READ | unknown. ZH read value: `04 00 05 00 01 01 00` (ZH `gatt.c`) |
| 0x0004/0x0005 | Char | `...bd282` | WRITE (with response) | console writes `01 00` here first (ND-BT init). ZH accepts any 2 bytes, returns success |
| 0x0006/0x0007 | Char | `...bd283` | READ | unknown. ZH read value: `36 80 74 ee bb 3d 8e 13` (ZH marks as "TODO ... may need to generate/store"). ESPP: no value set (ESPP-C `build_gatt`) |
| 0x0008 | Primary Service | `ab7de9be-89fe-49ad-828f-118f09df7fd0` | - | "svc2", main; ends **0x0032** (with audio attrs; 0x002A on factory FW) |
| 0x0009/0x000A | Char | `ab7de9be-89fe-49ad-828f-118f09df7fd2` | READ,NOTIFY | **Input report 0x05** (common; 32-bit counter; layout in ND-HID "Input Report 0x05"; not streamed by either emulator) |
| 0x000B | CCCD 0x2902 | | | |
| 0x000C | Desc | `679d5510-5a24-4dee-9557-95df80486ecb` | READ,WRITE | "Set Report Rate?" (ND-BT); ESPP creates it with 32-byte value storage |
| 0x000D/0x000E | Char | `7492866c-ec3e-4619-8258-32755ffcc0f8` | READ,NOTIFY | **Pro Controller 2 input report 0x09** (the stream) |
| 0x000F | CCCD | | | console writes `01 00` last in init |
| 0x0010 | Desc | `679d5510-...ecb` | READ,WRITE | console writes `85 00` just before enabling 0x000F (ND-BT init) |
| 0x0011/0x0012 | Char | `cc483f51-9258-427d-a939-630c31f72b05` | WRITE_NR | **Output report 0x02**: HD rumble (see 5.7) |
| 0x0013/0x0014 | Char | `649d4ac9-8eb7-4e6c-af44-1ea54fe5f005` | WRITE_NR | **Command channel (no rumble prefix)**; responses on 0x001A (inferred, ND-BT says "Basic command response") |
| 0x0015/0x0016 | Char | `3dacbc7e-6955-40b5-8eaf-6f9809e8b379` | WRITE_NR | **Rumble + command**: 33-byte prefix then command; the channel the console uses for all init/pairing; responses on 0x001E |
| 0x0017/0x0018 | Char | `4147423d-fdae-4df7-a4f7-d23e5df59f8d` | WRITE_NR | firmware-update/large command (chunked; ND-BT) |
| 0x0019/0x001A | Char | `c765a961-d9d8-4d36-a20a-5315b111836a` | NOTIFY | Command response #1 |
| 0x001B | CCCD | | | (Pro init sequence does not enable it; JC/GC do) |
| 0x001C | Desc | `b746df8c-f358-495b-9cd2-e3bbeda4f979` | READ,WRITE | unknown |
| 0x001D/0x001E | Char | `506d9f7d-4278-4e95-a549-326ba77657e0` | NOTIFY | **Command response #2** (answers 0x0016 writes) |
| 0x001F | CCCD | | | console writes `01 00` early in init |
| 0x0020 | Desc | `b746df8c-...979` | READ,WRITE | |
| 0x0021/0x0022 | Char | `d3bd69d2-841c-4241-ab15-f86f406d2a80` | NOTIFY | unknown input |
| 0x0023 | CCCD | | | |
| 0x0024 | Desc | `b746df8c-...979` | READ,WRITE | |
| 0x0025/0x0026 | Char | `ab7de9be-89fe-49ad-828f-118f09df7fde` | READ,NOTIFY | unknown input |
| 0x0027 | CCCD | | | |
| 0x0028 | Desc | `679d5510-...ecb` | READ,WRITE | |
| 0x0029/0x002A | Char | `ab7de9be-89fe-49ad-828f-118f09df7fdf` | WRITE_NR | unknown output |
| 0x002B/0x002C | Char | `cc483f51-9258-427d-a939-630c31f72b06` | WRITE_NR | headset audio out |
| 0x002D/0x002E | Char | `7492866c-ec3e-4619-8258-32755ffcc0f9` | READ,NOTIFY | headset audio + input (fw 2.0.0+) |
| 0x002F | CCCD | | | |
| 0x0030 | Desc | `679d5510-...ecb` | (ZH: READ only; ESPP: READ,WRITE) | |
| 0x0031/0x0032 | Char | `3dacbc7e-6955-40b5-8eaf-6f9809e8b380` | WRITE_NR | unknown + command |
| 0x0033 | Primary Service | `0x1800` Generic Access | | 0x0033-0x0037 |
| 0x0034/0x0035 | Char | `0x2A00` Device Name | READ | |
| 0x0036/0x0037 | Char | `0x2A01` Appearance | READ | |
| 0x0038 | Primary Service | `0x1801` Generic Attribute | | **no characteristics beneath it** (ND-BT) |

Notes:
- Columns "Handle 0x00XX/0x00YY" give (declaration / value) handles; the odd/even pairing is derived from ND-BT value handles and the standard
  decl+1 rule (inferred for the decl handle numbers; the value handles are the published ones). CCCD/desc handles are published in ND-BT.
- "+8 handle shift": ND-BT states that Pro controllers updated from factory firmware add the headset-audio attributes (0x002B-0x0032, 8 handles), so the
  standard GAP/GATT services move from 0x002B-0x0030 (factory) to **0x0033-0x0038**. The numbers in the last 4 rows are ND-BT's factory numbers + 8
  (ND-BT says "offset by +8, starting from 0x0033"; I computed the exact start/end rows - inferred arithmetic).
- Both emulators implement the **updated-firmware layout including audio attrs** and report DSP version in firmware-info (5.6). ESPP states the
  console uses attr presence + valid DSP version to distinguish an updated controller; without the audio attrs the console treats it as factory
  firmware and "diverges (probing firmware-info, rejecting)" (ESPP-P comment on `AUDIO_*` UUIDs).
- ESPP registers vendor services **first** (`registerAppServicesFirst(true)`) so they get handles 0x0001+, with GAP/GATT last. ZH omits GAP/GATT entirely (`ble_svc_gap_init()` etc. commented out) and works, so GAP/GATT are probably not required (inferred from ZH).
  Open: whether ZH really never sees ATT reads of 0x2A00 etc.
- All NOTIFY characteristics carry a standard CCCD (0x2902); the vendor descriptors `679d5510` (on 0x000A, 0x000E, 0x0026, 0x002E) and `b746df8c` (on 0x001A, 0x001E, 0x0022) are replicated for discovery parity (ESPP-P). Their values/initial contents are **not documented**; ESPP leaves them zeroed/empty (32 byte capacity), ZH returns success on any access with no data.
- Attribute permissions/encryption requirements: not documented. ESPP sets `bonding=false, mitm=false, secure=false`; ZH sets `sm_sec_lvl=2` in config (ZH `device.c`). Treat attributes as open (inferred); streaming is gated on link encryption (ESPP-C stream task requires `encrypted_`).
- Characteristics with the same handle across controller types (0x000E, 0x0012, 0x0016, 0x001E) differ only by UUID (ND-BT). Use the **Pro** UUIDs in the table.

### 2.2 Console behaviour at connection (ND-BT "Initialisation Sequence", Pro Controller 2 table)

Order of ATT operations the console performs (all by fixed handle; `W` = write):

```
W 0x0005  01 00                      ; svc1 characteristic 282
W 0x001F  01 00                      ; CCCD: enable resp2 notifications (command responses on 0x001E)
W 0x0016  07 91 01 01 00 00 00 00    ; cmd 0x07/0x01   (each prefixed by 33 zero bytes, see 5.2)
W 0x0016  02 91 01 04 00 08 00 00 40 7e 00 00 00 30 01 00   ; flash read 0x40 @0x13000
W 0x0016  16 91 01 01 00 00 00 00
W 0x0016  15 91 01 01 ...            ; pairing (omitted on reconnect)  -- see 3
 ...
W 0x0016  0a 91 01 02 00 04 00 00 03 00 00 00                ; connection vibration sample 3
W 0x0016  09 91 01 07 00 08 00 00 01 00 00 00 00 00 00 00    ; player LED pattern
W 0x0016  0c 91 01 02 00 04 00 00 2f 00 00 00                ; feature mask 0x2F
W 0x0016  02 ... reads @0x13080 (0x40), 0x130C0 (0x40), 0x1FC040 (0x40), 0x13040 (0x10), 0x13100 (0x18)
W 0x0016  11 91 01 03 00 00 00 00
W 0x0016  02 ... read 0x20 @0x13060
W 0x0016  0a 91 01 08 00 14 00 00 01 ff ff ff ff ff ff ff ff 35 00 46 00 00 00 00 00 00 00 00   ; vibration data
W 0x0016  0c 91 01 04 00 04 00 00 2f 00 00 00                ; enable features 0x2F
W 0x0010  85 00                                              ; report-rate descriptor
W 0x000F  01 00                                              ; CCCD: enable input report 0x09 notifications
```
(ND-BT; a single captured Pro session. The 0x10/0x11/0x18 probes that ESPP and ZH also answer are not in this capture; see 5.6 and section 8 item 15.)

---

## 3. Pairing handshake (command 0x15)

No SMP. **Any SMP pairing attempt by the peer makes the real controller terminate the link** (ND-BT). Configure the stack to never initiate/accept SMP
(ESPP-C `configure_security`: bonding=false, mitm=false, secure=false, IO caps NoInputNoOutput; ZH: "disable standard bonding process").

Pairing is performed by the console over the command channel (0x0016 write -> reply on 0x001E notify) at the **initial 15 ms connection interval**
(ESPP-C `connect_callback` comment, verified against a real-controller capture). The console also enables encryption using the derived LTK right after.

### 3.1 Framing recap (details in 5.2)

Request (written to 0x0016): `[33 x 00 prefix][cmd=15][91][01][sub][00][len][00][00][data...]`
Response (notified on 0x001E): `[14 x 00 prefix][15][01][01][sub][10][78][00][00][data...]`

### 3.2 Steps

| # | Sub | Request data (after 8-byte header) | Controller response data | Source |
|---|---|---|---|---|
| 1 | 0x01 Exchange addresses | `00 02 <addr1: 6B rev> <addr2: 6B rev>` (len 0x0e). addr1 = console identity address; addr2 = addr1 with last LSB byte decremented (example: `81 eb 3a eb f1 48` / `80 eb 3a eb f1 48`). First byte 0x00 = request; 2nd = count | `01 04 01 <controller addr 6B rev>` (9 bytes). Example resp: `01 04 01 88 16 c2 55 e2 98` | ND-CMD 0x15/0x01; ESPP-C `handle_pairing`; ZH `cmd_0x15_handler` |
| 2 | 0x04 Exchange keys | `00 <A1: 16B>` (len 0x11) e.g. `00 35 03 e9 29 82 87 71 24 be a8 0c 66 46 15 83 4b` | `01 <B1: 16B>`; B1 is the **constant** `5c f6 ee 79 2c df 05 e1 ba 2b 63 25 c4 1a 5f 10` | ND-CMD 0x15/0x04; ESPP-P `CONTROLLER_KEY_B1` |
| 3 | 0x02 Confirm LTK | `00 <A2: 16B>` e.g. `00 6f c6 df 8a d8 fe df 15 bb 8c 15 e9 1f 32 05 44` | `01 <B2: 16B>` e.g. `01 13 4c 97 f5 11 b9 b6 dd 4d 86 fd 40 f5 36 e9 ed` | ND-CMD 0x15/0x02 |
| 4 | 0x03 Finalise | `00` (len 1) | `01` (1 byte) | ND-CMD 0x15/0x03; ESPP-C |

Sequence on the wire in capture order is 01, 04, 02, 03 (ND-BT init table). ESPP enforces ordering 01 -> 04 -> 02 -> 03 (stage counter) and rejects out-of-order (ESPP-C).
Subcommand 0x15/0x07 + 0x03/0x09 "send pairing info" (host injects addr+LTK directly) exists in ND-CMD ("allows bypassing 0x15") and was seen from the console for Joy-Con 2 only
(ND-BT JoyCon table); neither emulator handles it for Pro (ESPP enum only).

### 3.3 Crypto - exactly as published

(ND-BT "Pairing" + python snippet; ESPP-K `PairingCrypto`; ZH `cmd_0x15_handler`)

```
A1 = bytes 1..16 of the 0x15/04 request data      (as received on the wire, no reversal for XOR)
B1 = 5CF6EE792CDF05E1BA2B6325C41A5F10             (constant, sent as-is on the wire)
LTK = A1 XOR B1                                    (bytewise, wire order)          <- 16 bytes
A2 = bytes 1..16 of the 0x15/02 request data
B2 = AES-128-ECB-ENCRYPT( key = reverse(LTK), plaintext = reverse(A2) )            <- single 16B block, no padding
B2 is sent on the wire as the raw cipher output (NOT reversed again)
```
"Fixed key": the only fixed value is **B1** above. The AES key is `reverse(LTK)`, i.e. derived per pairing (not a compile-time key).
ND-BT: "B1 appears to be fixed". ESPP-D calls it "a fixed controller key". Reasoning: console verifies by decrypting B2 with LTK and comparing to A2 (ND-BT); no attestation.

Golden vector (ND-BT python; ESPP-P `golden`, ESPP-D says host-verified with openssl):

```
A1  = 3503e92982877124bea80c664615834b
B1  = 5cf6ee792cdf05e1ba2b6325c41a5f10
A2  = 6fc6df8ad8fedf15bb8c15e91f320544
LTK = 69f50750ae5874c504836f43820fdc5b      (= A1 ^ B1)
B2  = 134c97f511b9b6dd4d86fd40f536e9ed      (= AES128-ECB(rev(LTK), rev(A2)))
```
Embedded C: needs one AES-128 ECB encrypt of one block (Telink chips have an HW AES or software AES lib; (inferred) available in the Telink SDK).
Self-test this vector at boot (ESPP does: `PairingCrypto::self_test()`).

Note on "reverse byte-order" wording: ND-CMD calls the on-wire A1/A2/B1/B2 "reverse byte-order". The python snippet and the golden vector use the wire bytes as-is for
XOR and reverse only for the AES key/plaintext, and three independent implementations (ND python, ESPP C++, ZH C) reproduce the same wire output, so the algorithm above
is the operative one. ZH stores `ltk[i] = A1[15-i] ^ B1[15-i]` (i.e. reversed LTK) and calls the natural-order version `ltk_re`.

### 3.4 Link-layer encryption / what to hand the controller (BLE stack)

After Finalise the console starts standard LL encryption (LE Start Encryption) using this LTK; no SMP key distribution.
- Install the LTK so the stack answers the LTK Request with: **LTK = A1 XOR B1 in natural (wire) order** passed straight to the LL/HCI LTK reply (NimBLE `ble_store_value_sec.ltk[]`, no byte swap), `EDIV = 0`, `Rand = 0`, key size 16, authenticated=1 (ESPP-C `inject_ltk`; ZH `ltk_sec_init`: `ltk_re`, ediv=rand=0, authenticated=1, sc=1). Peer address in the store = the console's connection address (ESPP uses `peer_id_addr` of the connection).
- The 0x03/0x07 "send pairing info" blob form is this LTK **byte-reversed** (ESPP-C comment) - that's the transmission form, not the key order the LL uses. (ND-CMD: "byte-reversed".)
- On Telink (inferred): the SDK's LL needs the equivalent of "LTK request -> reply with stored LTK" without an SMP pairing having happened; check how the SDK's `blc_smp` bond store can be pre-seeded, or hook the LL LTK-request event directly. Not covered by any source.

### 3.5 What is persisted (so reconnect works)

(ESPP-C `StoredBond`; ZH `pro2_pairing_info_nvs_save`; ND-MEM 0x1FA000 for the real controller)

| Item | ESPP | ZH | Real controller (ND-MEM) |
|---|---|---|---|
| LTK (16B) | yes | yes | yes (x2 entries share the same LTK) |
| Console identity address (6B, wire order, from 0x15/0x01 addr1) | yes (`host_addr`) | yes (the connect-event peer addr) | yes, 2 entries: addr and addr-1 (0x1FA008, 0x1FA030) |
| Console connection peer addr + type | yes (`peer_type`, `peer_val`) | yes (BLE_ADDR_PUBLIC assumed) | - |
| Own controller address | stable (public / derived from MAC) | persisted random lower 3 bytes | - |
| Magic byte | 0xB2 | - | item count |

Controller (own) address **must be stable** across boots (ESPP-C `init()`).

---

## 4. Connection behaviour

| Parameter | Value | Source |
|---|---|---|
| Role | controller = GAP peripheral / GATT server; console = central | ND-BT |
| Initial interval (fresh pairing) | **15 ms** (CONNECT_IND); pairing completes at 15 ms | ESPP-D, ESPP-R (decrypted captures + hardware) |
| Interval after pairing/subscription | **~1.5 s after input-report subscription the console sends LL_CONNECTION_UPDATE -> 5 ms** (itvl=4 units of 1.25 ms) and stays there | ESPP-D milestone 3, ESPP-R |
| Interval on bonded reconnect / wake | **5 ms from CONNECT_IND** (itvl=4) | ESPP-R, ESPP-D milestone 4 |
| Spec issue | 5 ms < 7.5 ms BT-spec min. **The peripheral LL must accept it** or connect/reconnect/wake fail (console gives up) | ND-BT, ESPP-R |
| How the console sets it | "a vendor-specific HCI command" on the console side; the controller never sends a Connection Parameter Update Request | ND-BT. ESPP-C: "do NOT initiate a connection-parameter update" - doing so correlated with a degraded tx link. ZH instead calls `ble_gap_update_params(itvl_min=6, itvl_max=current)` after connect (ZH `gap.c`) - contradiction, see section 8 |
| Active-use motion captures | ~7.5 ms / 133 Hz for minutes (ND, quoted in ESPP-R) | ESPP-R |
| Latency | 0 (ZH sets 0; ESPP just logs) | ZH `gap.c` |
| Supervision timeout | Not documented. Both emulators accept the value the console sets. Sub-5 ms-interval failure presents as supervision timeout (ESPP-C comment). | - |
| PHY | **2M after connect** ("the only other post-connect LL change is the PHY switch to 2M" - ESPP-R); ZH requests 2M preferred as default PHY (`ble_gap_set_prefered_default_le_phy(2M, 2M)`) - the console initiates; peripheral must accept | ESPP-R, ZH `device.c` |
| ATT MTU | **512**: console exchanges MTU 512 and "appears to stall right after the MTU exchange if the controller grants less" than a real controller (512). Set preferred MTU = 512 | ESPP example `sdkconfig.defaults` (`CONFIG_BT_NIMBLE_ATT_PREFERRED_MTU=512`), ZH `ble_att_set_preferred_mtu(512)` |
| DLE / data length | not documented (inferred: needed for 63-byte notifies at MTU 512? a 63-byte notify + 3 ATT header = 66 B > 27 B default LL payload so DLE or L2CAP fragmentation is exercised; stacks handle either) | inferred |
| Link-layer encryption start | Immediately after 0x15/0x03 on fresh pair; on reconnect the console skips 0x15 and starts LL encryption first using the stored LTK (so the LTK must be loaded **before** the console connects) | ESPP-C `init()`, ND-BT ("0x15 commands are only used during initial pairing") |
| Keep-alive | None documented as a controller requirement. ESPP streams reports every connection interval (continuous mode default; on-change mode keeps a keepalive report every 10 intervals ~150 ms at 15 ms). PK reports a 1 Hz **host->controller write** is needed on macOS (host-side CoreBluetooth quirk) - not relevant to emulation | ESPP-C `kKeepaliveIntervals`; PK 9 |
| Wake-from-sleep fields | see section 6 | |

Resource lessons from ESPP-R (apply to a Telink port): 5 ms interval x continuous notify stresses tx buffering; use real backpressure, do not call HCI commands inside the per-interval loop; `NOTIFY_TX` fires at host->controller handoff not over-air completion.

---

## 5. Input report, commands and responses

### 5.1 Input report 0x09 (Pro Controller 2) - notified on handle 0x000E

BLE omits the report-ID byte. Length **63 bytes** (0x3F). Sources: ND-HID "Input Report 0x09"; ESPP-RPT; ZH `hid_controller_pro2.h` (both emulators send exactly 63).

| Off | Len | Field | Notes |
|---|---|---|---|
| 0x00 | 1 | Counter | 8-bit, +1 per **delivered** report (ESPP increments only on successful notify) |
| 0x01 | 1 | Power info | bit0 external power, bit1 charging, bits[5:2] battery level 0-9, bits[7:6] reserved. ESPP: `(level<<2)|(charging?2:0)|(ext?1:0)`, level clamped 0..9. ZH sends constant 0x20 (level 8) |
| 0x02 | 3 | Buttons | see 5.3 |
| 0x05 | 3 | Left stick | 12-bit x,y packed, see 5.4 |
| 0x08 | 3 | Right stick | same |
| 0x0B | 1 | Unknown | `0x38` if feature bit5 (rumble) enabled, else `0x30`. ESPP tracks the negotiated feature mask; ZH hard-codes 0x38 |
| 0x0C | 1 | NFC state | 0x00 idle (0..7) |
| 0x0D | 1 | Headset audio state | 0x00 when none |
| 0x0E | 1 | Motion data length | ESPP sets 0x28 when IMU feature enabled; observed {0, 30, 40}. ZH always 0x28 |
| 0x0F | 40 (0x28) | Motion data | "unknown packed format"; **all-zero accepted** by the console (ZH, ESPP default). ESPP can replay 128 captured 40-byte frames |
| 0x37 | 8 | Reserved | zero |

Total = 0x3F = 63. Stick centre = 0x800 each axis (ESPP/ZH).

### 5.2 Command channel framing

8-byte header (ND-CMD "Command Header"; ESPP-P `COMMAND_HEADER_SIZE`):

| Off | Value |
|---|---|
| 0 | Command ID |
| 1 | Direction: 0x91 = host->device, 0x01 = device->host |
| 2 | Transport: 0x00 USB, **0x01 Bluetooth** |
| 3 | Subcommand |
| 4 | request: 0x00 ; **response over BLE: 0x10** |
| 5 | request: data length ; **response over BLE: 0x78** (ACK marker) |
| 6-7 | 0x0000 |

Requests:
- Written to **0x0016** (Pro): `[0x00 report-id][16B HD rumble left][16B HD rumble right]` = **33 bytes** prefix (ND-BT 0x0016 Pro table; ESPP-P `VIBRATION_COMMAND_PREFIX_SIZE=33`; ZH `NS2_DATA_EMPTY_LEN=0x21`), then the 8-byte header, then data.
- Written to **0x0014**: header directly, no prefix.
- Typical ATT write-command (no response). Minimum accepted length = 33 + 8.

Responses (ESPP-C `send_response`; ZH `cmd_process`):
- On 0x001E: **14 zero bytes** + `[cmd][01][transport][sub][10][78][00][00]` + data. (ND-BT table lists the header at offset 0xF after a 0xE-byte field; that is internally inconsistent by one - see section 8. Both emulators use 14 = 0x0E and the console accepts that.)
- On 0x001A (replies to 0x0014 writes - ESPP behaviour; ZH ignores 0x0014): no prefix, header + data.
- Header byte 2 echoes the request's transport byte; byte 3 echoes the subcommand.
- Bare ACK = header only, no data, with bytes 4/5 = `10 78`. (USB uses `00 f8`; never on BLE.)
- **Every command written to 0x0016 gets a response on 0x001E** (ND-BT). Even for unknown commands both emulators send the bare ACK.
- Response data max 0x78 bytes in ZH `CMD_PROCESS_MAX_RSP_DATA_LEN`.

### 5.3 Button bits (Pro, ND-HID "Button Format"; ESPP-RPT; ZH `btn_bits_pro2_t`; all agree)

| Byte (abs report offset) | 0x80 | 0x40 | 0x20 | 0x10 | 0x08 | 0x04 | 0x02 | 0x01 |
|---|---|---|---|---|---|---|---|---|
| 2 | R-Stick click | Plus | ZR | R | X | Y | A | B |
| 3 | L-Stick click | Minus | ZL | L | Up | Left | Right | Down |
| 4 | - | - | - | C | GL | GR | Capture | Home |

### 5.4 Stick packing

Per stick 3 bytes carrying two 12-bit values (ESPP-RPT `pack_stick`; ZH `pack_stick_data`):

```
b0 = x & 0xFF
b1 = ((y & 0x0F) << 4) | ((x >> 8) & 0x0F)
b2 = (y >> 4) & 0xFF
```
x,y in 0..4095, centre 2048. Values are "uncalibrated" (ND-HID); the console applies stick calibration from flash (5.5).
The mapping of Y direction (up = larger?) is not stated in the sources reviewed (unverified/unknown; verify on hardware).

### 5.5 Flash reads the console performs (command 0x02, subcommand 0x04)

Request (after 8-byte header) 8 bytes: `[len][7e][00][00][addr32 LE]` e.g. `40 7e 00 00 00 30 01 00` = read 0x40 @ 0x013000.
Response data: `[len][00][00][00][addr32 LE][len bytes of flash]` (ESPP-C FLASH_READ: len(4 LE)+addr(4 LE)+data, no status byte; ZH identical: copies request bytes then zeroes byte 1). Unmapped addresses return 0xFF. Max length 0x78 (ZH).

Blocks served (ESPP-F, captured from a real Pro 2; ZH has the same plus editable serial/colours):

```
0x013000 (64B): 01 00 48 45 4a 37 31 30 30 31 31 32 31 32 34 37 00 00 7e 05 69 20 01 06 01
                23 23 23 a0 a0 a0 e6 e6 e6 32 32 32 ff*27
   = start flag 01 00 | serial (16B, ASCII "HEJ71001121247" + 2x00) | VID 7e05 | PID 6920 | 01 06 01 |
     body 232323 | buttons a0a0a0 | highlight e6e6e6 | grip 323232 | 0xFF
0x013040 (16B): 3b e0 d3 41 c6 60 6a bc 4d d7 a2 bb 71 1e dd 37
0x013080 (64B): 01 ad d9 9a 55 56 65 a0 00 0a a0 00 0a e2 20 0e e2 20 0e 9a ad d9 9a ad d9 0a a5 50 0a a5 50 2f f6 62 2f f6 62 0a ff ff
                b3 67 83 2e 66 5e 3a 06 5f  ff*15           ; 0x0130A8 = primary (left) stick calibration (9B)
0x0130C0 (64B): same first 40 bytes as 0x013080, then 2c 08 84 d1 65 63 2a 26 62 ff*15  ; 0x0130E8 = secondary (right) stick cal (9B)
0x013100 (24B): 00*12 a6 f2 62 bd a8 00 08 3d 2f ed 20 41
0x013060, 0x1FC040 (user calibration, uninitialised), others: all 0xFF
```
ND-MEM adds: 0x13060 = `4c 09 00 00` on a real unit (4B) and 0x13140 = `00 d7 a3 bc 41 d7 a3 bc 41` (unknown); both emulators return 0xFF for 0x13060 and the console accepts. Validate: "the console reads and validates blocks (serial and VID/PID at 0x13000) before it will pair" (ESPP-F).
The 9-byte stick calibration blocks are 3x 12-bit-pair triplets (format not documented in the sources read; inferred: centre/min/max offsets). If your hardware sticks do not span 0..4095 around 2048 you must either scale in firmware or alter these calibration blocks (not verified).

### 5.6 Minimum command replies (what the console sends and what the emulators answer)

All replies use header `[cmd][01][transport][sub][10][78][00][00]` + data below, sent on 0x001E for 0x0016 writes. Sources: ESPP-C `handle_command`, ZH `ns2_codec.c`, example data from ND-CMD.

| Cmd/Sub | Purpose | Response data | Notes |
|---|---|---|---|
| 0x07/0x01 | init handshake | `00` | ZH, ESPP agree |
| 0x02/0x04 | flash read | see 5.5 | |
| 0x16/0x01 | init handshake | 24 x `00` | |
| 0x15/xx | pairing | see 3.2 | |
| 0x0a/0x02 | play vibration sample (id in data[0]; 3 = connection) | bare ACK | ESPP ACK; ZH ACK (empty) |
| 0x09/0x07 | set player LED pattern (data[0] = 4-bit mask) | bare ACK | |
| 0x0c/0x01 | get feature info | `00 00 00 00` + 8B info (ESPP replies only 4 zero bytes; ZH encodes: byte0=0x07 if btn, byte1=0x07 if sticks, byte2=0x01 if IMU, byte3=0x01 if bit7, byte4=0x01 mouse, byte5=0x03 rumble) | |
| 0x0c/0x02 | set feature mask (`2f 00 00 00`) | `00 00 00 00` | ESPP also treats set-mask as enabling those features (on reconnect the console only sends 0x0c/02) |
| 0x0c/0x04 | enable features | `00 00 00 00` | ZH sets "ready" here and starts streaming |
| 0x0c/0x03, /0x05 | clear mask / disable | `00 00 00 00` | |
| 0x11/0x01 | late-init | `01 00 00 00` | |
| 0x11/0x03 | late-init | `01 20 03 00 00 0a e8 1c 3b 79 7d 8b 3a 0a e8 9c 42 58 a0 0b 42 0a e8 9c 41 58 a0 0b 41` (29B). "Header-only ACK stalls init" (ESPP) | |
| 0x18/0x01 | late-init probe | `00 00 40 f0 00 00 60 00` (8B). ACK-only stalls (ESPP) | 0x18/0x03 echoes its 1 byte (ND-CMD example `07`), ESPP only ACKs |
| 0x10/0x01 | firmware info | `02 01 04 02 0c 00 00 00 00 02 03 00` = fw 2.1.4 / type 0x02 Pro / BT patch 12.0.0 / pad / DSP 2.3.0 / pad. **Type byte MUST be 0x02 (Pro)**; wrong type is cross-checked against VID/PID and rejected. A valid DSP version is needed because audio attrs exist; ND-CMD sample for an un-updated controller: `01 00 0e 02 0c 00 00 00 ff ff ff ff` | ZH uses the same 12 bytes and notes it blocks the console's firmware-update prompt |
| 0x01/0x0c | NFC probe | `61 12 50 0d` (ESPP, ND-CMD) / `61 12 50 10` (ZH) - see section 8 | other 0x01 subcommands: ACK |
| 0x03/0x*, 0x0b/*, 0x0d/* ... | anything else | bare ACK | ESPP default; ZH responds with header only (same thing) |
| 0x17/0x02 | audio setup (`80 bb 00 00 02 f0 00` = 48 kHz, ...) | bare ACK (ND-CMD) | headset only; not implemented by either emulator |

Battery: no command needed during init; battery shown via the Power Info byte of the input report. ESPP says battery cmds are ACK-only "refined in later work" (so the console showed "full battery" with just ACK) (ESPP-R status).

### 5.7 Vibration / output

- Output report 0x02 on 0x0012: `[0x00][16B HD rumble L][16B HD rumble R][9B reserved]` (ND-HID). Neither emulator acts on it (ZH returns 0; ESPP passive log). Writes are no-response, so **no ack is required** (they are ATT Write Commands).
- Rumble also arrives as the 33-byte prefix on every 0x0016 write; ignored by both emulators.
- Command 0x0a/0x08 "send vibration data" (20B): answered with bare ACK.

### 5.8 Report rate

- Notifications are sent **once per connection interval** by default in ESPP ("continuous", mirrors a real controller): ~62 Hz at 15 ms, ~200 Hz at 5 ms (ESPP-R). Real controller at 7.5 ms ~133 Hz in motion captures (ND via ESPP-R).
- ZH: fixed 15 ms timer by default (`CONFIG_HID_REPORT_INTERVAL 15`) - it works without following the 5 ms interval, so a lower rate than the interval is tolerated (inferred: console accepts reports slower than the connection interval).
- The `679d5510` descriptor at 0x0010 gets `85 00` from the console (= 0x0085 = 133 decimal; (inferred) a requested report rate in Hz). Neither emulator reacts to this write.
- Streaming starts only after the console writes CCCD 0x000F = 0x0001 (at the end of init). ESPP additionally gates on link encryption.

---

## 6. Reconnect and wake from sleep

Facts (ESPP-D, ESPP-R, ESPP-C, ZH, ND-BT):

1. After successful 0x15/0x03 the controller persists {console address, LTK} (section 3.5) and is "bonded". The console likewise stores controller address + LTK.
2. On next power-up with a bond present, the controller advertises the **Reconnection** variant (host address in mfr bytes 0x0C..0x11, flag 0x00) or the **Wake** variant (flag 0x81) - section 1. The advertisement address bytes are the console identity address from 0x15/0x01.
3. Wake: when the console is asleep and the user presses a button on the controller, advertise the 0x81 variant. ESPP also re-broadcasts it every 5 s on boot (`wake_interval`), stopping when an encrypted session is established; ZH always uses wake mode (`g_adv_opcode=0x81`) when pairing info exists. A "passive" 0x00 reconnect variant only reconnects an awake console and an awake console on idle screens ignores it.
4. The console connects with **CONNECT_IND interval = 5 ms** (itvl 4) from the first packet. The link must accept it.
5. **No 0x15 on reconnect.** The console immediately starts LL encryption; the LTK must already be in the stack's key store before the console connects (ESPP inserts it at `init()`).
6. The console then repeats a shortened init (flash reads, player LEDs, `0x0c/0x02` mask only - ESPP: "never sends 0x0c/04; expects the controller to have persisted its enabled features", hence ESPP treats set-mask as enable) and enables CCCD 0x000F.
7. Advertising restart after disconnect: ESPP immediately; ZH after 3 s. Both loop forever.
8. Fresh pairing mode: the real controller enters pairing advertising when "Sync" is held (PK 1: reconnect field zero = pairing mode). An emulator with no bond advertises the Standard variant. Clear bond => back to Standard.
9. ZH known issue: connecting through the console's "Change Grip/Order" screen causes HID reports to get stuck on reconnect (ZH README).
10. Console-originated "Search for controllers" wake (ADV_NONCONN_IND, section 1.3) is not implemented by either emulator; a sleeping controller would need to scan.

Wake flag semantic: 0x81 = "user pressed a button - connect to me" (ESPP-R). PK 1 describes the same field as "reconnect host address".

---

## 7. Minimum viable implementation checklist (Telink)

1. Link layer: peripheral that accepts **CONNECT_IND with interval 4 (5 ms)** and LL_CONNECTION_UPDATE to 5 ms (below spec minimum; Telink SDK may clamp - the biggest risk); supervision timeout as chosen by the console; 2M PHY request from the console; ATT MTU 512.
2. Static address: public (or stable static-random). Do not change between boots.
3. Advertise ADV_IND legacy: `02 01 06` + `1B FF` + 26-byte mfr data (1.1), connectable+scannable, ~30 ms; scan response name optional.
4. GATT: build the table in 2.1 in exactly that order so handles match (svc1 0x0001-0x0007, svc2 0x0008-0x0032, then GAP/GATT or omit). Vendor descriptors + CCCDs on all NOTIFY chars. Write-no-response on 0x0012/0x0014/0x0016/0x0018/0x002A/0x002C/0x0032. Service1 char 0x0003 readable (use ZH value `04 00 05 00 01 01 00`), 0x0005 writable, 0x0007 readable (ZH value `36 80 74 ee bb 3d 8e 13`).
5. No SMP: reject/ignore pairing requests; do not set security-requested on connect.
6. Command parser on 0x0016 (strip 33 bytes) and 0x0014; responder on 0x001E (14 zero prefix) / 0x001A. Implement table 5.6 and flash 5.5 verbatim.
7. 0x15 handshake + AES-128-ECB (3.2, 3.3); self-test golden vector.
8. Inject LTK = A1^B1 (natural order), EDIV=0, RAND=0 into the LL so the console's LE Start Encryption succeeds; persist LTK + console identity address + connect peer address in flash.
9. After CCCD 0x000F=0x0001 and (preferably) link encrypted: stream 63-byte report 0x09 on 0x000E each connection interval, with counter+1 per sent report, 0x0B = 0x38, motion len 0x28 + 40 zero bytes. Apply tx backpressure.
10. Reconnect: on boot with bond, load LTK before advertising; advertise Reconnection/Wake variant with address bytes; wake variant on button press when disconnected.
11. Bond-clear path (e.g. long-press) -> Standard advertising and re-pair.

Hardware-specific (inferred): map the 8BitDo Ultimate 2's controls to bits in 5.3; its sticks are 12-bit-ish centred ADC values; triggers are digital ZL/ZR on Pro 2 (analog triggers are GC-only per ND-HID).

---

## 8. Open questions and contradictions

1. **5 ms interval on Telink**: all sources require the peripheral LL to accept itvl < 6 (7.5 ms). On ESP32 S3/C3 it needs an Espressif controller option; C6 needed a binary patch of `libble_app.a` (ZH `patch/`). Telink behaviour unknown. Highest risk. (ESPP-D, ZH README)
2. **Who starts the 5 ms interval**: ESPP: console sends LL_CONNECTION_UPDATE ~1.5 s after subscription; ND-BT: console uses a vendor HCI command locally (no peripheral involvement) and the controller never requests it; ZH: peripheral calls `ble_gap_update_params(itvl_min=6, itvl_max=current)` right after connect; ESPP explicitly removed its own update request because it "correlated with a degraded tx link". Treat the peripheral request as unnecessary/risky.
3. **Response prefix length on 0x001E**: ND-BT table puts the 8-byte header at offset 0xF after a 0xE-byte "unknown" field (0xE + 8 = 0x16, but table says data at 0x17, so off by one); ESPP and ZH both prefix 14 (0x0E) zero bytes and work on a real console. Use 14.
4. **NFC probe 0x01/0x0c response last byte**: `0x0d` (ND-CMD capture and ESPP) vs `0x10` (ZH). Both reportedly accepted. Use 0x0d.
5. **Console address stored/advertised**: ESPP uses the identity address from 0x15/0x01 payload (and says the connect address can be a rotating private one); ZH stores `peer_ota_addr` from the connect event and compares it against the 0x15/0x01 payload (rejecting on mismatch). Real controller stores two entries (addr and addr-1). If the console connects with its identity address the two coincide.
6. **GAP/GATT services**: ND-BT/ESPP include them (+8 shift story); ZH omits both. ND-BT notes the Generic Attribute service has no child attributes. ESPP's NimBLE GATT service will include Service Changed (a deviation, unreported). Not known whether the console cares.
7. **Updated vs factory firmware layout**: ND-BT's headline table is the factory layout (service 2 ends at 0x002A, GAP at 0x002B); the "+8" text describes the updated layout. Both emulators choose the updated one + DSP version 2.3.0. Whether the console would accept the factory layout with firmware-info `ff ff ff` DSP: ESPP says it diverges/rejects. (ESPP-P)
8. **Unknown vendor descriptors & svc1 contents**: initial values of `679d5510`, `b746df8c` descriptors and reads of 0x0003/0x0007 (ZH hard-codes values, ESPP leaves empty). The console reads the whole table during discovery but evidently doesn't validate contents (ESPP works with empty). ZH's 0x0007 value may be per-device (ZH "TODO may need to generate/store").
9. **Attribute security requirements**: unknown whether real controller requires encryption on any attribute. Both emulators run open.
10. **Own device address OUI**: ZH uses Nintendo OUI 78:81:8c (random lower 3B); ESPP uses chip MAC. Both said to work. Likely not checked (inferred).
11. **Motion data**: format unknown; zeros accepted. Telink port can send zeros. Real captures show 133 Hz motion frames. ESPP notes replay can produce backward timestamps and the known-working emulator (ZH) sends zeros.
12. **Report rate vs interval**: ZH at 15 ms timer works on a 5 ms link; ESPP sends every interval. `85 00` write to descriptor 0x0010 unexplained.
13. **0x0c/0x01 feature info and 0x18/0x03, 0x17/0x02**: ESPP answers 0x18/0x03 with ACK-only, ND-CMD sample echoes `07`; ZH doesn't handle 0x18/0x03 (returns empty). Not shown to matter.
14. **Supervision timeout / slave latency / DLE / MTU-data-length** values the console picks are not documented in the sources (only logged by ESPP). Capture on first hardware connect.
15. **ZH vs ND init**: ND Pro init shows `0x0016` command 0x07/0x01, 0x02, 0x16, 0x15..., but not 0x10/0x11/0x18 which ESPP and ZH answer (ESPP: console issues them when it considers firmware stale). Document the set the console actually sends on your target firmware.
16. **Stick Y direction / calibration semantics**: not stated; check against console's "Test Input Devices" screen (ESPP verified buttons/sticks register there).
17. **NSO / Joy-Con 2 pairing difference**: Joy-Con 2 is sent `0x03/0x07` and `0x03/0x09` after pairing (ND-BT); Pro is not. Irrelevant unless PID changes.
18. **Console system updates may change behaviour** (ZH README "Compatibility Issues").

## 9. Legal / scope

All content describes publicly documented interoperability behaviour (ND, ESPP, ZH are MIT/community RE). No Nintendo code or keys beyond the published constant B1 are involved. This file does not describe or require touching hardware.
