# Phase 1 (Windows): capture, transport options, port checklist, safety

Status: preparation only. Nothing here connects to, probes or flashes a device, and no driver is installed. Target: user's own 8BitDo Ultimate 2 Wireless (Telink TC32), controller VID 0x2DC8 / PID 0x6012, dongle PID 0x6013 (from the .dat header, see PHASE0.md). Reference implementation: `ref/8bitdo-2c-re-flake/flasher/flash2c.py` (2C, Linux) and its `NOTES.md` sections "Flashing" and "On-wire flash protocol".

Facts that differ between the 2C reference and this device (do not copy 2C constants blindly):

| item | 2C (reference) | Ultimate 2 Wireless (this project) |
| --- | --- | --- |
| normal PID | 0x310a (ctrl), 0x301c (dongle) | 0x6012 (ctrl), 0x6013 (dongle) per header; confirm by enumeration |
| interface / OUT / IN | intf 2, EP 0x06 / 0x83 (ctrl) | UNKNOWN, take from the capture (section 1.5) |
| bootloader (L1+R1) | 2dc8:3208, intf 0, EP 0x05 / 0x84 | UNKNOWN PID, test first (section 4) |
| `.dat` dest_addr / app base | 0x6000 | 0x5000 (PHASE0.md) |
| image length | ~0x12400 | 0x23800 (ctrl v1.09), 0x9e00 (dongle v1.06) |
| 0xc4 version byte | 0x6d (2C ctrl v1.09) | take from capture; do not assume |

---

## 1. Capturing the official Ultimate Software V2 update (USBPcap + Wireshark)

### 1.1 Versions and install

- USBPcap 1.5.4.0 (signed installer, Windows 7/8/10 x86+x64; works on Windows 11). Download from the project's GitHub releases linked from <https://desowin.org/usbpcap/>. A reboot is required after install (stated on that page). It is old (2019) but is the current release, so the "two weeks old" rule is satisfied.
- Wireshark: install the current stable 4.6.x from <https://www.wireshark.org/download.html>. Sources disagree on the exact point release (<https://endoflife.date/wireshark> says 4.6.16 on 2026-05-19; Wikipedia and a tutorial site give lower numbers). UNVERIFIED: pick whatever the download page lists as "Stable Release", and confirm its date is at least 2 weeks before today (2026-11-07). A Wireshark 5.0 line may be about to ship (user's guide metadata hints November 2026); do not use a 5.0 release or any 4.7.x development build unless it is >= 2 weeks old and listed stable. Any 4.4/4.6 release reads USBPcap pcapng fine.
- The Wireshark Windows installer offers USBPcap as an optional component (from memory, not confirmed by the pages fetched; if the checkbox is absent just run the standalone USBPcap installer). The official Wireshark docs: <https://www.wireshark.org/docs/wsug_html/> (section "Capturing USB traffic on Windows" / USBPcap).
- Tool versions: Ultimate Software V2 from 8BitDo's support page; use the current one the user already has, record its version in the capture notes.

### 1.2 Pick the right root hub

USBPcap exposes one capture interface per USB root hub (`USBPcap1`, `USBPcap2`, ...). Each controller/port group is a different hub.

1. Plug the controller (normal mode, USB-C cable to the PC) into a port you will not change for the whole session. Prefer a direct motherboard port, not an external hub.
2. In Wireshark's capture start screen the `USBPcapN` entries show a sparkline; the one that moves when you touch the controller sticks is a candidate. Click the gear/"Options" (or Capture > Options > Input > USBPcapN "Capture Options"): USBPcap's own dialog lists the hub's device tree and shows `2DC8:6012` (or whatever the product string is) under the right hub. Tick ONLY the controller device. This also avoids capturing keyboards/mice (a keylogger risk) on the same hub. Alternatively tick "Capture from all devices connected" if the device re-enumerates and the address changes; then treat the file as sensitive and delete it after extraction.
3. The updater re-enumerates the device (reset command 0x07, maybe a bootloader hop). The device address changes, so a device-only filter can drop the second half. Safer: capture the whole hub for the session, filter later.
4. To also capture the descriptors (you need them for section 2), start the capture first, then unplug and replug the controller into the same port. The `GET_DESCRIPTOR` exchange then appears at the start.

### 1.3 Capture procedure

1. Charge the controller (battery > 50%) and connect it by cable; wireless and dongle must not be involved.
2. Back up first (section 4).
3. Start Wireshark as Administrator the first time (USBPcap driver filter needs the device to be re-enumerated; Wireshark asks for a replug if a device was already attached: say yes).
4. Start capture on `USBPcapN`. Replug as in 1.2 step 4, wait for enumeration to finish, then start the update in Ultimate Software V2 (it flashes the 2C in normal mode; the EP 0x06 style transfer on that interface is expected, per NOTES.md).
5. Let the whole update finish and the device reboot, then stop the capture. Expect a few thousand 64-byte OUT reports (the 2C controller capture was 1643 data-writes for 74752 B; this image is 0x23800 = 145408 B, so about 3195 data-writes plus about 130 control commands; my synthetic test of the generator gives 3317 reports).
6. If the official tool says "already up to date" and refuses: the NOTES say it is update-gated. Options: use a newer/older `.dat` if the tool allows it (do not hand-patch the updater), or capture a dongle update instead (pad stays idle). Record what happened; no workaround is attempted here.
7. File > Save As > pcapng, name it e.g. `u2w-ctrl-v109-flash.pcapng`. (pcapng is the Wireshark 4.x default; the extractor requires pcapng, not legacy pcap.)

### 1.4 Display filters

- Everything for one device: `usb.bus_id == 1 && usb.device_address == 5` (use the values shown in the packet list).
- Only the IAP OUT reports: `usb.capdata[0:2] == 81:05 && usb.endpoint_address.direction == 0` (some HID dissector paths expose the bytes as `usbhid.data` instead; if the filter finds nothing try `frame contains 81:05`).
- Device replies: `usb.capdata[0:2] == 02:05 || usb.capdata[0:2] == 02:22`.
- Descriptors: `usb.bDescriptorType` (or `usb.descriptor_type`), also look at `usb.bInterfaceClass` to see whether the flash interface is HID (3) or vendor (0xff).
- Quick CLI alternative: `tshark -r cap.pcapng -Y "usb.capdata[0:2]==81:05" -T fields -e frame.number -e usb.endpoint_address -e usb.capdata`.

### 1.5 What to read from the capture before writing any code

- Interface number and endpoint addresses carrying the `81 05` traffic, and whether they are interrupt OUT/IN (`int`) or HID SET_REPORT/GET_REPORT control transfers. The extractor prints this (`endpoints:` line). This single fact decides the transport option in section 2.
- Interface class (HID vs vendor 0xff) from the configuration descriptor, and the HID report descriptor if HID (is there a report ID? is 0x81 a report ID?).
- 0xc4 total length and version byte, session handshake repeat counts (`s_start`, `s_end`), the verify burst, and whether blocks are 4 KB at sequential offsets starting from 0.

### 1.6 Extractor

`tools/extract_iap.py` (pure stdlib, parses pcapng and USBPcap records directly, link type 249):

```
python -I tools\extract_iap.py cap.pcapng                      # every 81 05 OUT report: cmd, address, length, CRC verdict
python -I tools\extract_iap.py cap.pcapng --summary            # histogram + CRC counts only
python -I tools\extract_iap.py cap.pcapng --out image.bin      # reassemble all 0x03 data-writes by offset [14:18]
python -I tools\extract_iap.py cap.pcapng --dump tmpl.txt      # one hex report per line, order preserved
python -I tools\extract_iap.py cap.pcapng --device 5 --endpoint 0x06
```

- Verifies CRC-16/MODBUS (poly 0xA001, init 0xFFFF) over `data[18:18+len]` for every report with a payload; exit code 2 if any mismatch. Counts device ACKs (`02 05`/`02 22`).
- Accepts interrupt/bulk OUT and control data-stage OUT (HID SET_REPORT), with the magic at offset 0 or 1 (leading HID report-ID byte; `--no-strip` to disable).
- `--out` fills gaps with 0xFF; for a differential (skip-unchanged) update the covered ranges are printed so you know it is partial. Compare with `firmware\payload-ctrl-v109.bin` (the `.dat` minus header): a stock-to-stock flash must be byte-identical.
- `--dump` output has the same format as `flash2c.py gen --template` (whitespace-separated hex reports), so once the flasher is adapted to the U2W the generated stream can be diffed against it.
- Tested here on a synthetic pcapng generated from the flash2c sequence logic over `payload-ctrl-v109.bin` (3317 reports, all CRCs ok, reassembled image identical to the payload). It has NOT been run on a real USBPcap capture yet; the header layout is from the USBPcap spec (27-byte header, +1 stage byte on control transfers). If a real capture decodes oddly, check `info` bit 0 handling (1 = device-to-host completion) first.

Optional pyshark/scapy route: not needed. scapy's pcapng reader works but has no USBPcap dissector for these header fields, so the direct parser is simpler and has no dependencies.

---

## 2. Talking to the device from Windows (pyusb/libusb vs hidapi)

### 2.1 What Windows binds

Normal-mode 2C-family controllers present as XInput (Xbox 360 style, class 0xFF/0x5D) plus extra interfaces, one of which carries the IAP traffic (2C: interface 2, EP 0x06 OUT / 0x83 IN). On Windows the composite parent `usbccgp.sys` splits the device into one child per interface, and each child gets its own driver:

- XInput interface: `xusb22.sys`/inbox XInput stack (leave alone).
- If the IAP interface is class 3 (HID): bound to `hidusb.sys`, exposed as a HID collection.
- If it is vendor class 0xFF: usually no driver (shows as "Unknown device" / a yellow bang) unless the device ships Microsoft OS descriptors that auto-load WinUSB. Check Device Manager (read-only) and the section 1.5 capture.

Unknown: which of the two it is for the U2W. Decide from the descriptors before choosing below.

### 2.2 Options

A. hidapi on the HID interface (no driver change). Use if the IAP interface is HID. `hid_write` maps to an interrupt-OUT transfer if the interface has an OUT endpoint, else to a HID SET_REPORT control transfer; `hid_read`/`hid_read_timeout` returns input reports. This is what most vendor tools do on Windows and is exactly what Windows already supports, so there is nothing to break. Python: `pip install hidapi` (0.15.0, released 2025-12-09, <https://pypi.org/project/hidapi/>). Details to handle: the write buffer must start with the report ID, so for a descriptor with no report IDs prepend `0x00` (65 bytes); if the capture shows the 0x81 is itself a report ID, send it as-is. Enumerate by path/interface number (`hid.enumerate(0x2dc8, 0x6012)` returns one entry per top-level collection; use `interface_number` and `usage_page`). Close other HID readers (Ultimate Software V2, Steam Input, other tools) because hidapi on Windows needs a handle, and a competing reader can eat input reports.

B. pyusb + libusb with WinUSB bound to that single interface (Zadig). Use only if the IAP interface is vendor class 0xFF or HID access via hidapi does not reach the endpoint. libusb on Windows only works on devices bound to WinUSB, libusbK, libusb-win32 or its limited HID backend (<https://github.com/libusb/libusb/wiki/Windows>). That wiki "strongly discourages" the HID backend ("use hidapi") and notes only the first top-level collection is supported. So pyusb on a HID-bound interface is not a path: claim returns NOT_SUPPORTED/ACCESS errors (compare the composite-device reports at <https://github.com/libusb/libusb/issues/422>, <https://github.com/libusb/libusb/issues/619>).

C. libusb's HID backend. Not recommended (same sources); equivalent to A with fewer features.

### 2.3 Risks of Zadig (option B)

Zadig 2.9 (libwdi 1.5.1, June 2024; <https://github.com/pbatard/libwdi/releases>, user guide <https://github.com/pbatard/libwdi/wiki/Zadig>) installs WinUSB/libusbK/libusb-win32 onto the selected device. Risks:

- By default Zadig lists only devices without a driver; to see the XInput/HID ones you need Options > List All Devices. Do not do that casually: the guide warns that replacing the driver of a keyboard/mouse "will no longer be usable for input", and the same holds for the pad: replacing the XInput interface's driver kills gamepad input in games.
- Composite devices: Zadig shows interface IDs as `(Interface N)` / `MI_0N` in the device name. Choose ONLY the single IAP interface (the one with no driver or the vendor one). Never pick the composite parent (`usbccgp`; hidden by default via "Ignore Hubs or Composite Parents", keep that checked) or the whole device entry, because that would affect every interface.
- Windows can silently roll back a libusbK install to a newer inbox driver (guide), and unsigned/test-signed drivers may complain; WinUSB via Zadig is signed so acceptable on Windows 11.
- The guide gives no restore procedure. Standard restore (from general Windows knowledge, not from the Zadig page): Device Manager > the interface node > Uninstall device, tick "Attempt to remove the driver for this device" > unplug and replug the controller; Windows re-installs the inbox driver. Or `pnputil /enum-drivers` to find the `oemNN.inf` for WinUSB/libusbK and `pnputil /delete-driver oemNN.inf /uninstall /force`. Create a System Restore point before any Zadig use. Test the revert on a throwaway unplug/replug cycle before relying on it.
- The 8BitDo Ultimate Software V2 (and WebUSB site) likely cannot talk to the device while WinUSB owns that interface only if it uses that interface; revert before using the official tool again.

### 2.4 Recommendation

1. Least invasive: Phase 1 capture shows the interface class and transfer type. If HID: use option A (hidapi), zero driver changes.
2. If the IAP interface is vendor class and already has no driver: Zadig WinUSB on that interface only (the XInput interface is untouched), with a restore point, and revert afterwards.
3. Never replace the composite parent or the XInput interface. Never use libusb-win32/usbdk (usbdk is discouraged in the libusb wiki).
4. Note for the bootloader (L1+R1) device: for the 2C it was a plain HID interface with EP 0x05 OUT / 0x84 IN, so hidapi works with no driver change; the last-resort recovery path should therefore be written for hidapi first.

Vendor vs HID difference summary: with HID the Windows driver owns the pipe, you get framed reports (report ID byte, 64-byte reports, no choice of endpoint), reads are queued input reports, no ZLP handling, and no `claim_interface`. With a vendor interface via WinUSB you pick endpoints directly, can use `usb.core` almost unchanged, and must handle timeouts/ZLPs as flash2c does, at the cost of a driver swap.

---

## 3. Porting checklist: flash2c.py to Windows

Linux-specific or environment items:

- `usb.core.find` needs a libusb backend DLL. Options: `pip install pyusb libusb-package` and pass `backend=libusb_package.get_libusb1_backend()`, or put `libusb-1.0.dll` (x64) from the libusb release next to the script. (Versions: pyusb 1.3.1, libusb 1.0.29 from memory; verify >= 2 weeks old.) Only relevant for option B.
- `dev.is_kernel_driver_active(i)` / `dev.detach_kernel_driver(i)` (`open_target`): not implemented in the Windows backends (raise `NotImplementedError`; the script already catches that and warns). Remove the loop on Windows; the replacement is "the right interface already has WinUSB bound" (option B) or "do not use libusb at all" (option A).
- `usb.util.claim_interface/release_interface`: fine with WinUSB, unnecessary with hidapi (drop).
- `--dev BUS:ADDR` selection: bus numbers are not meaningful on Windows. Replace by `hid.enumerate` path, or libusb `dev.bus`/`dev.address` as printed by a list command (these exist but are backend-internal).
- Root requirement (`needs root for USB`): not applicable; no admin needed for hidapi or WinUSB after the driver is in place.
- Transport swap for option A: replace `dev.write(ep_out, buf, to)` with `h.write(b"\x00" + buf)` (or `buf` if 0x81 is a report ID) and `dev.read(ep_in, 64, to)` with `h.read(64, timeout_ms)`; map `usb.core.USBError` to `OSError`/empty-read. Drain stale input reports before the session handshake. Keep `time.sleep` granularity in mind (about 15 ms on Windows default timers).
- Post-reset (`0x07`) the device re-enumerates; the open handle becomes invalid and the write raises. The existing code already treats that as normal; with hidapi expect `OSError`.
- `__main__`/console: use `python -I`, avoid Unicode box characters in print on cp1252 consoles (the script uses none).
- File paths: `argparse` values are fine; avoid reading payloads from OneDrive-synced folders mid-sync (copy to a local temp first so a file lock cannot truncate a read).

U2W-specific constants that must be re-derived (from capture, not assumed):

- `TARGETS`: VID 0x2DC8, PID 0x6012 (ctrl) / 0x6013 (dongle), interface number, OUT/IN endpoints, bootloader PID.
- `APP_BASE`: 0x6000 on the 2C; the U2W `.dat` says dest_addr 0x5000. The bootloader address protocol must use the real base.
- `APP_KINDS` size sanity (`0x10000..0x16000` for ctrl) rejects a 0x23800 image; update ranges (ctrl 0x23800, dongle 0x9e00).
- `s_start`, `s_end`, `version` (0xc4 byte) and any dongle `write_len` quirk: copy from the captured stream; run `extract_iap.py --dump` then `flash2c gen --template` against the stock payload until it reports MATCH (offline, no hardware).
- `_device_kind` reads flash at 0x10000 to tell dongle from controller; that heuristic is 2C-specific (dongle app ends at 0x10000). Replace by PID check only on the U2W.
- Command 0x05 (read) and the boot protocol (`cmd 3/4/5/8`) are from the 2C DLL reversing; not verified on U2W. Treat as unknown until probed in Phase 2.

---

## 4. Pre-flash safety checklist

Do these in order. Nothing is done in this Phase 1 preparation step.

1. Backup of the image: keep the stock `.dat` at `C:\Users\lance\OneDrive\Documents\_CODE\8bitdo\firmware\u2w-ctrl-v109.dat` (and `payload-ctrl-v109.bin`). Copy it to a second location that is not OneDrive-synced and record SHA-256 (`Get-FileHash`). This is only the app image; the device's own flash (bootloader at 0x0-0x4FFF, MAC, RF calibration) is NOT in the `.dat`.
2. Full device backup is only possible with SWS (single wire) or a bootloader/IAP read command. Until a read is proven, assume factory-written regions are not recoverable from the `.dat`. On the 2C the MAC is at 0x76000 and RF-cal at 0x77000 (NOTES.md "Brick hazards"); Phase 0 found the U2W app uses the same layout on its 512 KB flash: MAC 0x76000, RF-cal 0x77000, bonds 0x74000, 8BitDo settings 0x7a000–0x7e000 (see PHASE0.md item 6). This comes from static analysis and is not yet confirmed on the device. Never write or erase outside the app range described by the `.dat` header (dest_addr 0x5000, len 0x23800).
3. Never chip-erase and never issue erase commands whose block addresses fall outside the image range. The flasher must hard-clamp every `0xc3` address to the declared range and refuse otherwise.
4. Test L1+R1 bootloader enumeration first (power off, hold L1+R1, plug USB-C, LED behavior per NOTES.md for the 2C family). Check with Device Manager / USBView (read only, or a USBPcap capture) that a new device appears (2C: 2dc8:3208). Record the U2W bootloader PID and interface/endpoints. If it does not enumerate, STOP: you have no recovery channel and SWS hardware must be ready first.
5. Have SWS recovery ready (USB-serial, TX to SWS, RTS to RESET, GND, 3V3, pvvx tooling, NOTES.md) before the first write, as the bootloader recovery is itself unverified for this model.
6. Null-modification round trip: with the generator validated (`gen --template` MATCH against the captured official stream, offline), first flash the unmodified stock payload via the new tool and confirm normal boot, controller and dongle function. Only then a one-byte non-functional change with fixed CRC, then real patches. Remember the 2C dongle IAP stages into a window and the resident bootloader applies it on reboot; for the U2W confirm whether a bad image is rejected by a boot-time whole-image check.
7. Power: wired USB only, fully charged, other USB devices unplugged, no sleep/hibernate, OneDrive and AV not touching the working copy, laptop on AC.
8. Do the dongle and controller separately; never the dongle while the pad is relaying through it (2C finding).
9. Keep the vendor tool for restoring: after any experiment, try the official Ultimate Software V2 update to put stock firmware back (if it is update-gated this may be unavailable; that is why SWS is the real safety net).
10. Log every session (device PID, bytes written, ACK counts, final result) so a failed run can be diagnosed.

---

## Open questions / uncertain

- IAP interface class (HID vs vendor) and endpoints for the U2W: unknown until a capture or descriptor dump.
- Whether `0x81` is a HID report ID or a payload byte.
- Whether Ultimate Software V2 will reflash an already-current v1.09 (update gating).
- Exact current Wireshark stable point release (sources conflict); pyusb/libusb version numbers recommended here come from memory.
- Whether the Wireshark Windows installer bundles USBPcap (believed to be an optional component; not confirmed by the pages read).
- U2W bootloader PID, protocol, MAC/RF-cal addresses.
- `extract_iap.py` untested on a real USBPcap capture.

## Sources

- USBPcap: <https://desowin.org/usbpcap/>
- Wireshark: <https://www.wireshark.org/download.html>, <https://www.wireshark.org/docs/wsug_html/>, <https://endoflife.date/wireshark>
- libusb Windows wiki: <https://github.com/libusb/libusb/wiki/Windows>; issues <https://github.com/libusb/libusb/issues/422>, <https://github.com/libusb/libusb/issues/619>
- Zadig / libwdi: <https://github.com/pbatard/libwdi/releases>, <https://github.com/pbatard/libwdi/wiki/Zadig>
- hidapi (PyPI): <https://pypi.org/project/hidapi/>
- Reference protocol: `ref/8bitdo-2c-re-flake/NOTES.md`, `flasher/flash2c.py`

## Results (2026-11-07, real captures)
Captures are in `captures/`: `upgrade-109-to-110.pcapng` and `downgrade-110-to-109.pcapng`, both from USBPcap2,
controller = device 5, USB `2dc8:310b` (wired PID; the .dat header PID 0x6012 is not the USB PID).
- USB interfaces: If0 vendor 0xff/0x5d/0x01 (XInput, EP 0x84 IN / 0x05 OUT, 32 B); If1 HID boot keyboard
  (EP 0x82); **If2 HID vendor-defined, EP 0x83 IN / EP 0x06 OUT, 64 B = the IAP channel.** Use hidapi on If2
  (Windows "HID-compliant vendor-defined device", MI_02). No Zadig needed.
- Sequence (both directions identical in shape): `08` (new vs 2C, len 0, sent before session-start), `00` session-start
  (reply 0222), `c1`, then 33× `04` block-start, 72× `c3` set-block-addr, 2925× `03` data-write, `c4` (total 0x23800,
  version byte 0x6e for v1.10 / 0x6d for v1.09), `07` reset. CRC-16/MODBUS ok on all 2998 checked chunks in each capture.
- `extract_iap.py` verified: the reassembled 1.09 matches the vendor .dat payload byte for byte everywhere it wrote.
- **The updater never writes payload 0x5000–0x8000 (flash 0xa000–0xd000)**, in either direction, although the
  1.09 .dat has 52 high-entropy bytes at payload 0x5000. Treat that range as reserved or unknown, NOT as a code
  cave, until the device flash there can be read.
- v1.10 image reassembled from capture: `firmware/payload-ctrl-v110-captured.bin` (0x5000–0x8000 filled 0xFF,
  never sent). v1.10 is not on dl.8bitdo.com (server tops out at 1.09).
- Controller is back on v1.09 after the downgrade.
- **Bootloader entry confirmed** (2026-11-07): controller off, hold L1+R1, plug USB → small centre LED blinks, and it
  enumerates as **`2dc8:3208`** (HID, Windows names it "HID-compliant bar code badge reader", instance
  `USB\VID_2DC8&PID_3208\8BITDO`). Same PID as the 2C bootloader. Its protocol (2C: host `0508` / device `0005`) has
  not been probed yet. Exit = unplug, then power on normally.

## Phase 2 log (2026-11-07)
- `tools/u2wflash.py` (hidapi, If2, report ID 0x81): `info`, `checksums` (read-only c3 sector CRC16+sum32), `flash`
  (differential, verifies each sector's device checksum before c4/07). `gen --template` reproduces both captured
  vendor streams byte for byte. `info` + `checksums` on the live pad: 36/36 identical to stock 1.09.
- **First write (mod-px-v109.bin, one byte 'C'->'X' at payload 0x16c68, sector 0x16000):** flashed and verified,
  but the pad came back as `2dc8:3208` "8BitDo Boot" and never started the app.
  **Cause: boot-time whole-image CRC.** Telink layout: size = u32 @0x18 (1.09: 0x17a44), stored value at size-4 =
  ~CRC32 over [0:size-4]. Verified on stock 1.09 and 1.10. `tools/fixcrc.py` recomputes it. The IAP path itself
  does not check it (the flash was accepted); the bootloader does at boot.
- **Recovery:** `tools/u2wboot.py` (bootloader HID, no report ID, protocol as the 2C's: cmd 8 version, 5 read,
  4 erase, 3 write) — `version` ACKs (PID 0x6012 in reply), `read` matches the payload, `compare` found exactly the
  one differing byte, `restore-sector 0x16000` erased + rewrote + read back MATCH, pad boots normally, reports 0x6d.
  So the bootloader can erase/write/read the app region at absolute flash addresses (app base 0x5000).
- Ultimate Software V2 showed "0.00" after recovery until restarted; the device's own info reply was 0x6d throughout.
- **Second write (mod-px-v109-crc.bin, 'X' + recomputed Telink CRC):** device flash ended up byte-identical to the
  intended image (bootloader `compare` 36/36), but the pad again stayed in the bootloader. So there is **a second
  boot check** beyond the Telink ~CRC32 @size-4. Candidate seen in 1.09 only: u32 @0x23624 = sum32 of
  [0x17a48:0x23624] (0x4c9bc0); not confirmed (no analogous hit in 1.10). Restored both sectors to stock via the
  bootloader, compare 36/36 vs stock 1.09.
- **Rule from here (user request): no more writes to the controller until the boot check is identified by reading
  and disassembling the bootloader (flash 0x0–0x5000, read-only via u2wboot `read`) and a predicted-good image is
  verified offline against both stock images.**

## Boot checks — SOLVED from the bootloader dump (2026-11-07)
Full flash backup: `backup/flash-full-512k.bin` (two reads identical, sha256 dbf3aa44…8dfa; copy in re-tools/backup).
Flash map: 0x0–0x4000 bootloader (Telink image, KNLT), 0x5000 bank A (live app), 0x31000 update record (0x34 B,
CRC-16 of first 0x30 B at +0x30; +0x18 pending magic 0xaeb14d6c, +0x1c src bank, +0x20 size, +0x0c version),
0x32000 bank B (staging: the normal-mode IAP writes here; bootloader copies B→A, sector 0 last),
0x74000 bonds, 0x7a000–0x7e000 config.
Boot flow `FUN_0000161c`: unless L1+R1 / analog reg 0x3c=='Z': load record, apply pending B→A; validate(A)
(`0x1e4`) else validate(B) and copy; then `FUN_00000274`; then jump to app.
- **check 1** (`0x1e4`, enabled if u16 @payload 0x1e != 0): sum32 of bytes payload[0 : size-4] == u32 @payload[size],
  size = u32 @payload 0x18. (The Telink ~CRC32 word at size-4 is excluded.)
- **check 2** (`0x274`): sum32 of bytes payload[size+4 : size+4+len] == u32 right after, len = 0xbbdc (1.09)/0xbc44 (1.10).
- Verified offline: stock 1.09 and 1.10 PASS both; both PX test images FAIL check 1 (sum +0x15). That is the whole
  explanation of both failed boots.
- Any patch must update: Telink ~CRC32 @size-4, sum @size (check 1), and sum after region 2 if region 2 changes.

## Flashing: SOLVED end to end (2026-11-07)
1. `mod-px-v109-fixed.bin` ('X' + Telink CRC + check-1 sum, made by `tools/fixcrc.py`) written to bank A only via the
   bootloader (bank B left stock as self-healing fallback) → **booted; USB name "…Controller for PX"**.
2. Normal-mode IAP `u2wflash.py flash payload-ctrl-v109.bin` while running PX: **0 of 36 sectors written** (bank B
   already stock), c4 → bootloader copied B→A → back to stock "…for PC". Confirms: IAP c3/04/03 operate on bank B,
   c4 writes the pending record at 0x31000, bootloader copies B→A at reset, then runs both checks on A.
- `u2wflash.py flash` now refuses any image failing Telink CRC / check 1 / check 2 (`boot_checks`), so the two
  earlier failures cannot recur from this tool. Region-2 length is found automatically.
- Recovery, if ever needed: L1+R1 → `u2wboot.py compare/restore-sector` (bank A at 0x5000, bank B at 0x32000);
  with bank B stock, a failing bank A is restored by the bootloader itself.
- State at end of session: controller on stock 1.09, both banks stock.

## Phase 3 start (2026-11-07)
- Toolchain: Telink tc32-elf-gcc 4.5.1 (flyskywhy/tc32 @8ec375b, sparse clone at WSL ~/tc32), run via
  `wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/.../tools/tc32.sh <cmd>` (call from PowerShell; Git Bash mangles paths).
  Test compile OK: tpush{lr}=0x6500, R_TC32_CALL / R_TC32_ABS32 relocs.
- BLE scan from this PC: Intel adapter + bleak 1.1.1, `tools/blescan.py` (passive). Controller BT address
  E4:17:D8:BC:66:B6; flash 0x7c000 holds b5 66 bc d8 17 e4 (= …:B5 reversed) → MAC/identity storage.
- `tools/mkmod.py stock spec out`: asserted byte patches + auto-fix of all 3 boot values. `mods/name_test.py` renamed
  adv short name, scan-rsp name, GAP name → flashed via normal IAP, booted, scan shows "U2W Switch2 Dev" /
  "U2W Switch2 Dev Firmware 1". BLE data patches confirmed end to end.
- **First code patch works (step 3):** `src/hook_adv` (C, tc32-elf-gcc -O2, 232 B at VMA 0xa100 in the cave) +
  `tjl` at 0xd5b2 redirected from bls_ll_setAdvData (0x15894) to `hook_set_adv`. Built with `mods/hook_adv.py` +
  mkmod, flashed via normal IAP (4 sectors), booted. BLE scan: short name gone, mfr data {0xffff: 5532571e1b}
  exactly as predicted (incl. runtime xor 0x1b and passed len 0x1e). Compiled C + call patch + callback into stock
  firmware all confirmed.
- Memory facts used: startup copies 0x5040 B (header word 0x0504×16) of ramcode/retention data to SRAM 0x840000, and
  0x80 B .data from flash 0x1c6bc → 0x845a00. BSS 0x845d80–0x84777d, IRQ sp 0x845f00, SVC sp 0x848000 (≈2.1 KB stack).
  Cave usable from payload 0x5040; chosen code base VMA 0xa100 (≈11.8 KB to 0xd000).

## Switch 2 mode — step 1 (advertising) DONE (2026-11-07)
- `src/sw2` + `mods/sw2_adv.py`: hooks tjl @0xd5b2 (setAdvData) and @0xd5ba (setScanRspData). Normal power-on →
  stock adv (minus short name) + debug mfr {0xFFFF: 'K' + boot KEYS u32}. **Physical Y = KEYS bit 0x20** (measured;
  nothing held = 0). Y at power-on in BT mode → 31-byte Pro Controller 2 adv (0x0553 block) + scan rsp "Pro Controller".
- Normal power-on advertises from …:66:B5 (MAC @0x7c000); stock pairing mode uses …:66:B6.
- **Console test:** Switch 2 on Change Grip/Order, controller powered on with Y → console connected within ~1 s
  (adv stopped; 8BitDo connect vibration + solid LED), held the link ~58 s on stock GATT, dropped, reconnected at once.
  Advertising accepted; initial link works.

## Design notes for step 2+ (GATT / MTU / RAM)
- Stock: ATT RX/TX MTU = 23 (`FUN_00018840`/`FUN_0001884c` write 0x17 to struct 0x844d6c +0x22/+0x20).
  LL ACL RX FIFO: 8 × 64 B @0x844464 (descriptor @0x844664, init values live in the ramcode image).
- Console needs ~80 B command writes on 0x0016 and sends up to ~90 B responses on 0x001E; sources say the console
  exchanges MTU 512 and stalls if granted less. Telink SDK rule: L2CAP RX buffer ≥ MTU+6
  (`blc_l2cap_initRxDataBuffer`, `blc_att_setRxMtuSize`). Need to find those lib functions in the binary and decide
  between a true 512+ buffer (RAM!) or a smaller buffer with a large declared MTU (only safe if the lib bounds-checks).
- Switch 2 GATT: 56 attributes (0x0001–0x0038, notes/SWITCH2_PROTOCOL.md §2) → ~1.35 KB attribute_t table + UUIDs in
  flash; RAM only for CCCDs if write callbacks don't store. Must swap table via the call in FUN_0000d75c in Y mode.
