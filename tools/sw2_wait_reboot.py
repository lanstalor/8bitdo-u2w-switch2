"""Wait until the Y-mode controller stops advertising (powered off), then until it advertises again (rebooted)."""
import asyncio, sys, time
from bleak import BleakScanner

ADDR = 'E4:17:D8:BC:66:36'


async def main():
    last_seen = [0.0]

    def cb(d, a):
        if d.address.upper() == ADDR:
            last_seen[0] = time.monotonic()

    scanner = BleakScanner(cb)
    await scanner.start()
    start = time.monotonic()
    phase = 'off'
    print('waiting for the controller to power off...', flush=True)
    try:
        while time.monotonic() - start < 600:
            await asyncio.sleep(0.5)
            gone = time.monotonic() - last_seen[0] > 6
            if phase == 'off' and gone:
                phase = 'on'; off_at = time.monotonic()
                print('controller off; waiting for it to come back...', flush=True)
            elif phase == 'on' and last_seen[0] > off_at:
                print('controller back on', flush=True)
                return 0
    finally:
        await scanner.stop()
    print('timed out', flush=True)
    return 1

sys.exit(asyncio.run(main()))
