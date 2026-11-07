"""Post-mortem reader for the Switch 2 mode firmware. Read-only; no pairing, no flash.

Run it AFTER a console attempt WITHOUT powering the controller off (the diagnostic
block lives in RAM and is overwritten only by the next command/LTK/bond event):

    python tools/sw2_diag.py            # scan, decode the advertisement, connect, read 0x26

It prints two things:
  1. Advertisement: whether the controller believes it is bonded (mfr byte 0x0B = 0x81
     and bytes 0x0C..0x11 = console address) or is in discovery (all zero).
  2. Diagnostic char 0x26 (8 bytes written by src/sw2/sw2.c):
     u16 handle, u16 L2CAP length, u16 reply length, u8 status, u8 stage.
Stage is the LAST event, not the furthest one reached.
"""
import argparse
import asyncio
from bleak import BleakClient, BleakScanner

DIAG = 'ab7de9be-89fe-49ad-828f-118f09df7fde'

STAGES = {
    0x00: 'nothing happened since boot (no write callback ran)',
    0x01: 'write callback entered; frame rejected (bad length/header or not a command handle)',
    0x02: 'command accepted and queued, reply not yet attempted (CCCD for the reply handle not enabled?)',
    0x03: 'reply attempted; status 0x00 = sent, 0xB4 = notify hold-off (retrying), 0x81 = TX FIFO full (retrying)',
    0x40: 'console asked for the LTK (RAND=0/EDIV=0) and we answered; status = fw_ltkReply result (0 = accepted)',
    0x41: 'Nintendo bond saved to the stock bond journal after link encryption started',
    0xe1: 'bond save FAILED (fw_saveBond returned 0)',
    0xe2: 'second command arrived while one was still queued; it was DROPPED',
    0xe3: 'reply generation failed: unknown/invalid command or bad 0x15 sequencing',
}


def decode_adv(mfr):
    data = mfr.get(0x0553)
    if data is None:
        return 'no Nintendo manufacturer data'
    # data starts after the 2-byte company id; firmware byte 0x0B is data[9]
    mode = data[9] if len(data) > 9 else None
    addr = data[10:16] if len(data) >= 16 else b''
    if mode == 0x81 and any(addr):
        return f'BONDED/wake advertisement; stored console address bytes (as sent) {addr.hex(":")}'
    if mode == 0x00 and not any(addr):
        return 'DISCOVERY advertisement (no bond stored)'
    return f'unexpected mode byte {mode!r}, address {addr.hex()}'


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--scan-secs', type=float, default=30)
    parser.add_argument('--no-connect', action='store_true', help='only decode the advertisement')
    args = parser.parse_args()
    found = {}

    def cb(d, a):
        if (a.local_name or d.name or '') == 'Pro Controller' and 0x0553 in a.manufacturer_data:
            found[d.address] = (d, a)

    scanner = BleakScanner(cb)
    await scanner.start()
    t = 0.0
    while not found and t < args.scan_secs:
        await asyncio.sleep(0.5); t += 0.5
    await scanner.stop()
    if not found:
        raise SystemExit('No Pro Controller advertisement. Controller off, or already connected to the console '
                         '(a connected peripheral does not advertise).')
    for addr, (d, a) in found.items():
        print(f'{addr}: {decode_adv(a.manufacturer_data)}', flush=True)
    if args.no_connect:
        return
    dev = next(iter(found.values()))[0]
    async with BleakClient(dev, timeout=60, winrt={'use_cached_services': False}) as client:
        raw = await client.read_gatt_char(DIAG)
        print('diag bytes:', raw.hex(' '), flush=True)
        if len(raw) < 8:
            raise SystemExit('short diagnostic value')
        handle = raw[0] | raw[1] << 8
        length = raw[2] | raw[3] << 8
        reply = raw[4] | raw[5] << 8
        status, stage = raw[6], raw[7]
        chan = {0x16: 'command+rumble (0x16 -> reply 0x1E)', 0x14: 'command (0x14 -> reply 0x1A)'}.get(handle, f'handle 0x{handle:04x}')
        print(f'last write : {chan}, L2CAP length {length}')
        print(f'last reply : {reply} bytes, notify/ltk status 0x{status:02x}')
        print(f'last stage : 0x{stage:02x} = {STAGES.get(stage, "unknown stage code")}')
        print('Note: this PC connection itself has reset the per-connection session; the console must re-pair/reconnect.')


if __name__ == '__main__':
    asyncio.run(main())
