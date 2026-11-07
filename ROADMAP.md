# Feature roadmap

Proposals below are not features of the released firmware. The current verified
state is documented in [CURRENT_HANDOFF.md](notes/CURRENT_HANDOFF.md).

## Native Windows XInput over Bluetooth LE

**Status:** proposed; reference implementation identified on 2026-11-07.
Not implemented or tested on the Ultimate 2 Wireless.

### Goal

Connect the controller directly to Windows Bluetooth and expose Xbox-style
XInput controls through Windows' built-in support, without the original 2.4 GHz
receiver, Steam Input, or a third-party virtual-controller driver. Preserve the
working Switch 2 mode and stock USB/receiver behavior with a separately selected
Bluetooth mode; the selection mechanism remains to be designed.

### Evidence and reference code

- [ESP32-BLE-Gamepad: XInput mode](https://github.com/lemmingDev/ESP32-BLE-Gamepad/blob/master/docs/XInputMode.md)
  documents native Windows XInput through Xbox Series X BLE emulation.
- [Series X example](https://github.com/lemmingDev/ESP32-BLE-Gamepad/blob/master/examples/XInput/XInputSeriesX/XInputSeriesX.ino)
  provides a concrete implementation entry point.
- [ESP32-BLE-CompositeHID](https://github.com/Mystfit/ESP32-BLE-CompositeHID)
  is credited by that project as a reference for Xbox HID descriptors and its
  XInput implementation.

The reference documentation reports that Series X identity (VID 0x045E,
PID 0x0B13) and the corresponding HID behavior matter for native Windows 11
recognition; its older One S mode can enumerate as generic HID without working
through XInput. Treat those Windows-version claims as reference-project findings
to reproduce locally, not guarantees for our controller.

Our existing BLE service/report modifications make this a plausible porting
project. The reference targets ESP32, while this controller uses Telink B80/TC32;
its firmware cannot be flashed directly onto this hardware. No working port for
this exact controller has been established by this project.

### Implementation and acceptance checklist

- [ ] Review reference source and license; identify required advertising identity,
      Device Information, HID report map, GATT services, security, and bonding.
- [ ] Implement a separate mode within available flash/RAM limits, preserving
      Switch 2 mode, stock modes, and documented recovery paths.
- [ ] Pair using Windows' built-in Bluetooth support and record Windows build,
      Bluetooth adapter, and firmware revision.
- [ ] With translation software disabled, verify `XInputGetState` directly reports
      buttons, D-pad, both sticks, and independent analog triggers correctly.
      A Bluetooth device name or successful `joy.cpl` test alone is insufficient.
- [ ] Verify `XInputSetState` rumble if implemented; explicitly document any gaps.
- [ ] Test reconnect, power cycling, mode switching, bond removal/re-pairing,
      and sustained input; regression-test Switch 2 and stock USB behavior.

No release commitment or completion date is assigned.
