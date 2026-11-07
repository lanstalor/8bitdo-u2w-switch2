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
     Candidates 5/6 append a first-connection trace. Candidate 6's marker 0xc6 at
     byte 30 selects LL control RX + summary counters instead of candidate 5's
     detailed L2CAP counts. No transmit trace is available.
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
        return 'DISCOVERY advertisement (no active bond advertised)'
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
        print(f'commands accepted : {r[4]}   replies sent OK: {r[5]}   MTU low byte at last cmd: {r[12]}')
        print(f'last command      : {chan}  cmd 0x{r[1]:02x} sub 0x{r[2]:02x}  reply notify status 0x{r[3]:02x}')
        print(f'last event        : 0x{r[6]:02x} = {EVENTS.get(r[6], "unknown")}')
        print(f'last CCCD/desc wr : handle 0x{r[7]:02x}')
        print(f'pairing high-water: stage {r[14]} of 4 (1=addr, 2=key, 3=proof, 4=finish)')
        print(f'LTK request       : {LTK.get(r[8], r[8])}; fw_ltkReply returned 0x{r[9]:02x}')
        print(f'link encryption   : {"started" if r[10] else "never started"}')
        print(f'bond save         : {SAVE.get(r[11], r[11])}')
        print(f'last disconnect   : 0x{r[13]:02x} {REASONS.get(r[13], "(none / other)")}')
        if len(r) >= 31 and r[30] in (0xc8,0xc9,0xca,0xcb,0xcc):
            print(f'--- candidate {r[30]-0xc0} first connection (connections so far: {r[15]}) ---')
            print(f'duration byte: {r[16]} (255=ongoing); L2CAP PDUs: {r[17]}')
            if r[30] in (0xcb,0xcc):
                print(f'First L2CAP: CID 0x{r[18]:02x}, opcode 0x{r[19]:02x}, length low byte {r[20]}')
                print(f'First two parameters: {r[21]:02x} {r[22]:02x}')
                if r[18] == 4 and r[19] == 2 and r[20] == 3:
                    print(f'ATT Exchange MTU Request: peer wants {r[21] | (r[22]<<8)} bytes')
                if r[30] == 0xcc:
                    print(f'Negotiated MTU: {r[23] | (r[25]<<8)}; highest PHY: {r[24]} (1=1M,2=2M)')
                    print(f'Buffer guard failures: 0x{r[26]:02x} (1=RX,2=TX); last L2CAP opcode: 0x{r[28]:02x}')
                else:
                    print(f'Last connection PHY: {r[23]}; highest observed PHY: {r[24]} (1=1M,2=2M)')
                print(f'FEATURE_RSP queued: {r[27]}')
            elif r[30] in (0xc9,0xca):
                print(f'FEATURE_RSP queued: {r[27]}; first two feature bytes: {r[18:20].hex(" ")}')
                print(f'TX flags: 0x{r[20]:02x}; target captured={bool(r[20]&1)}, software consumed={bool(r[20]&2)}, total empty observed={bool(r[20]&4)}')
                print(f'Software target: {r[21]}; last consumer: {r[22]}')
                if r[30] == 0xca:
                    print(f'Last connection PHY: {r[23]}; highest observed PHY: {r[24]} (1=1M,2=2M)')
                else:
                    print(f'Last total depth: {r[23]}; minimum total: {r[24]}')
                print(f'Connection age at first empty: {r[25]} seconds (255=never,254=saturated)')
                print('FIFO drain does not prove peer acknowledgement.')
            else:
                print(f'FEATURE_RSP queued: {r[27]}; captured features: {r[18:26].hex(" ")}')
            names = {0: 'CONNECTION_UPDATE_IND', 7: 'UNKNOWN_RSP', 13: 'REJECT_IND',
                     15: 'CONNECTION_PARAM_REQ', 16: 'CONNECTION_PARAM_RSP',
                     17: 'REJECT_EXT_IND', 18: 'PING_REQ', 19: 'PING_RSP', 255: 'none'}
            if r[30] != 0xcc:
                print(f'Other LL opcode: 0x{r[26]:02x} {names.get(r[26], "unclassified")}; first parameter: 0x{r[28]:02x}')
                print('First other opcode retained; connection-update can be superseded by another other opcode.')
            classes = ['feature', 'length', 'version', 'PHY', 'encryption', 'other', 'terminate', 'channel map']
            print('LL RX classes: ' + ', '.join(name for bit,name in enumerate(classes) if r[29] & (1 << bit)))
            print('Queue acceptance does not prove over-air delivery or peer acceptance.')
        elif len(r) >= 31 and r[30] == 0xc7:
            print(f'--- candidate 7 first connection (connections so far: {r[15]}) ---')
            print(f'duration byte: {r[16]} (255=ongoing); L2CAP PDUs: {r[17]}')
            print(f'FEATURE_RSP attempts: {r[26]}; queued: {r[27]}; last return: {r[28]}')
            print('actual outgoing features: ' + (r[18:26].hex(' ') if r[26] else '(no response observed)'))
            classes = ['feature', 'length', 'version', 'PHY', 'encryption', 'other', 'terminate', 'channel map']
            print('LL RX classes: ' + ', '.join(name for bit,name in enumerate(classes) if r[29] & (1 << bit)))
            print('Queue acceptance does not prove over-air delivery or peer acceptance.')
        elif len(r) >= 31 and r[30] == 0xc6:
            names = {0: 'CONNECTION_UPDATE_IND', 1: 'CHANNEL_MAP_IND', 2: 'TERMINATE_IND',
                     3: 'ENC_REQ', 4: 'ENC_RSP', 5: 'START_ENC_REQ', 6: 'START_ENC_RSP',
                     7: 'UNKNOWN_RSP', 8: 'FEATURE_REQ', 9: 'FEATURE_RSP', 12: 'VERSION_IND',
                     13: 'REJECT_IND', 14: 'SLAVE_FEATURE_REQ', 15: 'CONNECTION_PARAM_REQ',
                     16: 'CONNECTION_PARAM_RSP', 17: 'REJECT_EXT_IND', 18: 'PING_REQ',
                     19: 'PING_RSP', 20: 'LENGTH_REQ', 21: 'LENGTH_RSP', 22: 'PHY_REQ',
                     23: 'PHY_RSP', 24: 'PHY_UPDATE_IND'}
            def opname(op):
                return f'0x{op:02x} {names.get(op, "unknown")}'
            secs = 'ongoing or >=255 s' if r[16] == 255 else f'{r[16]} s'
            print(f'--- candidate 6 first connection (connections so far: {r[15]}) ---')
            print(f'duration          : {secs}')
            print(f'L2CAP PDUs        : {r[17]}   ATT writes: {r[18]}   SMP: {r[19]}')
            print(f'plaintext LL RX   : {r[20]} (saturates at 255)')
            print('first LL opcodes  : ' + (' -> '.join(opname(op) for op in r[21:21+min(7,r[20])]) or '(none)'))
            if r[20]:
                print(f'last LL opcode    : {opname(r[28])}; first parameter 0x{r[29]:02x}')
            print('RX only: this trace does not prove the controller sent the expected responses.')
        elif len(r) >= 31:
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
