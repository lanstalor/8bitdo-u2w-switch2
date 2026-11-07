# Passive BLE scan (listen only). Prints advertisements whose name/services look like the controller.
# Usage: blescan.py [seconds] [--all]
import asyncio, sys
from bleak import BleakScanner
secs = float(next((a for a in sys.argv[1:] if not a.startswith('--')), 12))
seen = {}
def cb(dev, adv):
    name = adv.local_name or dev.name or ''
    hit = ('--all' in sys.argv) or any(k in name for k in ('8BitDo', 'U2W', 'Pro Controller')) \
        or any(u.lower().startswith('00001812') for u in adv.service_uuids) or 0x0553 in adv.manufacturer_data
    if not hit:
        return
    key = (dev.address, name, tuple(adv.service_uuids), tuple(sorted(adv.manufacturer_data.items())))
    if key in seen: return
    seen[key] = 1
    md = {hex(k): v.hex() for k, v in adv.manufacturer_data.items()}
    print(f"{dev.address} rssi={adv.rssi} name={name!r} services={[u[4:8] for u in adv.service_uuids]} mfr={md}", flush=True)
async def main():
    async with BleakScanner(cb):
        await asyncio.sleep(secs)
    print(f"scan done ({len(seen)} matching advertisements)")
asyncio.run(main())
