# Connect to the controller as a GATT client (like a console would), print the negotiated MTU, the full
# attribute layout with handles, and the values of readable characteristics. Read-only: no writes.
# Usage: bleprobe.py [name-substring or address] [--scan-secs N]
import asyncio
import argparse
import sys

from bleak import BleakClient, BleakScanner

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('target', nargs='?', default='8BitDo')
parser.add_argument('--scan-secs', type=float, default=15)
parser.add_argument('--pair', action='store_true', help='Complete Windows pairing before service discovery')
parser.add_argument('--connect-secs', type=float, default=90)
args = parser.parse_args()
target, scan_secs = args.target, args.scan_secs


async def main():
    if ":" in target:
        dev = await BleakScanner.find_device_by_address(target, timeout=scan_secs)
    else:
        dev = await BleakScanner.find_device_by_filter(
            lambda d, a: target in (a.local_name or d.name or ""), timeout=scan_secs)
    if dev is None:
        raise SystemExit(f"no advertising device matching {target!r} (is it in pairing mode?)")
    print(f"found {dev.address} {dev.name!r}; connecting...", flush=True)
    # Firmware swaps keep the same MAC; a cached stock table would hide the new services.
    async with BleakClient(dev, timeout=args.connect_secs, pair=args.pair,
                           winrt={"use_cached_services": False}) as c:
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
