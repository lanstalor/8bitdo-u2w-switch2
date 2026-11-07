"""Post-mortem reader for the Switch 2 mode firmware. Read-only; no pairing, no flash.

Run it AFTER a console attempt WITHOUT powering the controller off (the diagnostic
block lives in RAM and is overwritten only by the next command/LTK/bond event):

    python tools/sw2_diag.py            # scan, decode the advertisement, connect, read 0x26

It prints two things:
  1. Advertisement: whether the controller believes it is bonded (mfr byte 0x0B = 0x81
     and bytes 0x0C..0x11 = console address) or is in discovery (all zero).
  2. Diagnostic char 0x26: the 15-byte record written by src/sw2/sw2.c (candidate 3+),
     cleared only at boot. Counters and high-water marks survive the console session and
     this PC connection (Windows' own Service Changed CCCD write only touches byte 7).
"""
import argparse
import asyncio
from bleak import BleakClient, BleakScanner

DIAG = 'ab7de9be-89fe-49ad-828f-118f09df7fde'

EVENTS = {
    0x00: 'no command ever accepted since boot',
    0x01: 'last write to a command handle was a malformed frame (rejected)',
    0x02: 'command queued, reply not yet attempted (reply CCCD not enabled, or disconnected first)',
    0x03: 'reply attempted (see status byte: 0x00 sent, 0xB4 hold-off, 0x81 TX FIFO full)',
    0x40: 'console requested the LTK and we answered with the derived key',
    0x41: 'Nintendo bond saved to the stock bond journal',
    0xe1: 'bond save FAILED',
    0xe2: 'a command arrived while one was still queued and was DROPPED',
    0xe3: 'reply generation failed: unknown command or bad 0x15 sequencing',
}
LTK = {0: 'never requested', 1: 'answered with derived key', 2: 'refused: EDIV/RAND nonzero (console used a stale/standard key)',
       3: 'refused: pairing stage < 4 and no stored bond'}
SAVE = {0: 'not attempted', 1: 'ok', 2: 'FAILED'}
REASONS = {0x08: 'supervision timeout (link lost / 5 ms interval not sustained?)', 0x13: 'remote user terminated',
           0x16: 'local host terminated', 0x3d: 'MIC failure (wrong LTK / key byte order)', 0x3e: 'connection failed to establish',
           0x22: 'LMP response timeout', 0x28: 'instant passed'}


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
        if len(raw) < 15:
            raise SystemExit('short diagnostic value: firmware older than candidate 3 (8-byte layout)')
        print('diag bytes 15..30 (trace):', raw[15:].hex(' ') if len(raw) > 15 else '(none: firmware older than candidate 5)')
        r = raw
        chan = {0x16: '0x16 command+rumble', 0x14: '0x14 command', 0: 'none'}.get(r[0], f'0x{r[0]:02x}')
        print(f'commands accepted : {r[4]}   replies sent OK: {r[5]}   effective MTU at last cmd: {r[12]}')
        print(f'last command      : {chan}  cmd 0x{r[1]:02x} sub 0x{r[2]:02x}  reply notify status 0x{r[3]:02x}')
        print(f'last event        : 0x{r[6]:02x} = {EVENTS.get(r[6], "unknown")}')
        print(f'last CCCD/desc wr : handle 0x{r[7]:02x}')
        print(f'pairing high-water: stage {r[14]} of 4 (1=addr, 2=key, 3=proof, 4=finish)')
        print(f'LTK request       : {LTK.get(r[8], r[8])}; fw_ltkReply returned 0x{r[9]:02x}')
        print(f'link encryption   : {"started" if r[10] else "never started"}')
        print(f'bond save         : {SAVE.get(r[11], r[11])}')
        print(f'last disconnect   : 0x{r[13]:02x} {REASONS.get(r[13], "(none / other)")}')
        if len(r) >= 31:
            secs = 'still connected' if r[29] == 255 else f'{r[29]} s'
            print(f'--- first connection since boot (connections so far: {r[15]}; this PC read is one of them) ---')
            print(f'duration          : {secs}')
            print(f'ATT MTU requests  : {r[16]}')
            print(f'ATT discovery PDUs: {r[17]}   reads: {r[18]}')
            print(f'ATT write requests: {r[19]}   write commands: {r[20]}   first written handle: 0x{r[24]:02x}')
            print(f'other ATT PDUs    : {r[21]}   last ATT opcode 0x{r[22]:02x} on handle 0x{r[23]:02x}')
            print(f'SMP PDUs          : {r[25]}   first SMP code 0x{r[26]:02x}' + ('  (0x01 = Pairing Request from the peer)' if r[25] and r[26] == 1 else ''))
            print(f'L2CAP signalling  : {r[27]}   first code 0x{r[28]:02x}')
            print(f'other channels    : {r[30]}')
        print('Note: this PC connection reset the per-connection session; the record above is cumulative since boot.')


if __name__ == '__main__':
    asyncio.run(main())
