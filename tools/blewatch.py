# Live view: one line per second showing whether the controller's advertisements are being seen (passive scan).
# Advertising stops while a central is connected, so gaps = connection attempts. Usage: blewatch.py [seconds] [addr-prefix]
import asyncio, sys, time
from bleak import BleakScanner
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 90
pref = (sys.argv[2] if len(sys.argv) > 2 else 'E4:17:D8:BC:66').upper()
last = {}
def cb(dev, adv):
    if dev.address.upper().startswith(pref):
        last['t'] = time.time(); last['name'] = adv.local_name or last.get('name', ''); last['a'] = dev.address
        last['mfr'] = ','.join(hex(k) for k in adv.manufacturer_data) or last.get('mfr', '')
async def main():
    t0 = time.time(); prev = None
    async with BleakScanner(cb):
        while time.time() - t0 < secs:
            await asyncio.sleep(1)
            age = time.time() - last.get('t', 0)
            state = 'ADVERTISING' if age < 1.5 else 'silent'
            line = f"{time.time() - t0:5.0f}s {state:11s} {last.get('a', '')} {last.get('name', '')} {last.get('mfr', '')}"
            if state != prev:
                print(line + ('   <-- change' if prev else ''), flush=True)
                prev = state
    print('watch done')
asyncio.run(main())
