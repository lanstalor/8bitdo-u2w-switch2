# Connect to the controller as a GATT client (like a console would), print the negotiated MTU, the full
# attribute layout with handles, and the values of readable characteristics. Read-only: no writes.
# Usage: bleprobe.py [name-substring or address] [--scan-secs N]
import asyncio
import sys

from bleak import BleakClient, BleakScanner

target = next((a for a in sys.argv[1:] if not a.startswith("--")), "8BitDo")
scan_secs = float(sys.argv[sys.argv.index("--scan-secs") + 1]) if "--scan-secs" in sys.argv else 15


async def main():
    if ":" in target:
        dev = await BleakScanner.find_device_by_address(target, timeout=scan_secs)
    else:
        dev = await BleakScanner.find_device_by_filter(
            lambda d, a: target in (a.local_name or d.name or ""), timeout=scan_secs)
    if dev is None:
        raise SystemExit(f"no advertising device matching {target!r} (is it in pairing mode?)")
    print(f"found {dev.address} {dev.name!r}; connecting...", flush=True)
    async with BleakClient(dev, timeout=45) as c:
        print(f"connected; negotiated ATT MTU = {c.mtu_size}")
        for s in c.services:
            print(f"service h{s.handle:#06x} {s.uuid}")
            for ch in s.characteristics:
                props = ",".join(ch.properties)
                val = ""
                if "read" in ch.properties:
                    try:
                        v = await c.read_gatt_char(ch)
                        val = f" = {v.hex(' ')}" + (f" ({v.decode(errors='replace')!r})" if v and all(32 <= b < 127 for b in v) else "")
                    except Exception as e:
                        val = f" (read failed: {type(e).__name__})"
                print(f"  char h{ch.handle:#06x} {ch.uuid} [{props}]{val}")
                for d in ch.descriptors:
                    print(f"    desc h{d.handle:#06x} {d.uuid}")
    print("disconnected")


asyncio.run(main())
