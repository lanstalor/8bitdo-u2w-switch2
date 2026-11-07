"""Hardware command-channel test. Subscribes and writes documented init/read commands.

Does not perform Nintendo pairing, change firmware, or write controller flash.
The 129-byte padded read request deliberately tests L2CAP reassembly above MTU64.
"""
import argparse
import asyncio
from bleak import BleakClient, BleakScanner

COMMAND = '3dacbc7e-6955-40b5-8eaf-6f9809e8b379'
RESPONSE = '506d9f7d-4278-4e95-a549-326ba77657e0'
INPUT = '7492866c-ec3e-4619-8258-32755ffcc0f8'   # Pro Controller 2 input report 0x09, value handle 0x000E


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scan-secs', type=float, default=60)
    parser.add_argument('--input-secs', type=float, default=15, help='how long to stream input reports')
    parser.add_argument('--mtu512', action='store_true', help='require MTU512 and exercise maximum-size ATT write')
    args = parser.parse_args()
    dev = await BleakScanner.find_device_by_filter(
        lambda d,a: (a.local_name or d.name or '') == 'Pro Controller' and 0x0553 in a.manufacturer_data,
        timeout=args.scan_secs)
    if dev is None:
        raise SystemExit('No advertising Switch 2 development controller found')
    print(f'Found {dev.address}; connecting',flush=True)
    async with BleakClient(dev, timeout=90, winrt={'use_cached_services':False}) as client:
        print(f'MTU {client.mtu_size}',flush=True)
        assert client.mtu_size >= 153, 'MTU cannot carry the largest test response'
        if args.mtu512:
            assert client.mtu_size == 512, 'expected negotiated MTU512'
        queue = asyncio.Queue()
        await client.start_notify(RESPONSE,lambda _,data: queue.put_nowait(bytes(data)))
        # Send immediately: the final firmware must retry the stock post-MTU
        # holdoff itself, just as it must when the real console initializes.

        async def exchange(cmd, sub, data=b'', padding=0):
            request = bytes(33)+bytes([cmd,0x91,1,sub,0,len(data),0,0])+data+bytes(padding)
            await client.write_gatt_char(COMMAND,request,response=False)
            try:
                reply = await asyncio.wait_for(queue.get(),5)
            except asyncio.TimeoutError:
                debug=await client.read_gatt_char('ab7de9be-89fe-49ad-828f-118f09df7fde')
                print('Device diagnostic (see tools/sw2_diag.py for the layout):',debug.hex(' '),flush=True)
                raise
            assert reply[:22] == bytes(14)+bytes([cmd,1,1,sub,0x10,0x78,0,0]),reply.hex()
            print(f'PASS {cmd:02x}/{sub:02x}: wrote {len(request)}, received {len(reply)} bytes',flush=True)
            return reply[22:]

        assert await exchange(7,1) == b'\0'
        if args.mtu512:
            assert await exchange(7,1,padding=468) == b'\0'
            debug=await client.read_gatt_char('ab7de9be-89fe-49ad-828f-118f09df7fde')
            assert len(debug)==31 and debug[30]==0xcc and debug[26]==0, 'transport buffer canary changed: '+debug.hex(' ')
            print('PASS: maximum 509-byte value / 512-byte ATT write; buffer guards intact',flush=True)
        assert await exchange(0x10,1) == bytes.fromhex('020104020c00000000020300')
        body=await exchange(2,4,bytes.fromhex('407e000000300100'),padding=80)
        assert len(body)==72 and body[:8] == bytes.fromhex('4000000000300100')
        assert body[8:30] == b'\x01\0HEJ71001121247\0\0\x7e\x05\x69\x20'
        body=await exchange(2,4,bytes.fromhex('787e000040c01f00'))
        assert body==bytes.fromhex('7800000040c01f00')+bytes([255])*120
        assert await exchange(0x16,1)==bytes(24)
        assert await exchange(0x11,3)==bytes.fromhex('01200300000ae81c3b797d8b3a0ae89c4258a00b420ae89c4158a00b41')
        assert await exchange(0x18,1)==bytes.fromhex('000040f000006000')
        assert await exchange(0x0c,2,bytes.fromhex('2f000000'))==bytes(4)
        # Input stream (report 0x09 on handle 0x000E). Streams without link encryption
        # so button/stick mapping can be checked here; hold buttons / move sticks while it runs.
        reports = asyncio.Queue()
        await client.start_notify(INPUT,lambda _,data: reports.put_nowait(bytes(data)))
        last=None; count=0; deadline=asyncio.get_event_loop().time()+args.input_secs
        while asyncio.get_event_loop().time()<deadline:
            try: r=await asyncio.wait_for(reports.get(),2)
            except asyncio.TimeoutError:
                debug=await client.read_gatt_char('ab7de9be-89fe-49ad-828f-118f09df7fde')
                raise SystemExit('no input report; diagnostic '+debug.hex(' ')+' (decode with tools/sw2_diag.py)')
            assert len(r)==63 and r[1]==0x20 and r[11]==0x38 and r[14]==0x28, r.hex()
            count+=1
            if last is not None: assert r[0]==(last[0]+1)&0xff, 'counter skipped'
            if last is None or r[2:11]!=last[2:11]:
                lx=r[5]|((r[6]&15)<<8); ly=(r[6]>>4)|(r[7]<<4)
                rx=r[8]|((r[9]&15)<<8); ry=(r[9]>>4)|(r[10]<<4)
                print(f'buttons {r[2]:02x} {r[3]:02x} {r[4]:02x}  L({lx:4d},{ly:4d}) R({rx:4d},{ry:4d})',flush=True)
            last=r
        await client.stop_notify(INPUT)
        print(f'{count} input reports in {args.input_secs:.0f}s ({count/args.input_secs:.0f}/s)',flush=True)
        await client.stop_notify(RESPONSE)
    print('PASS: command transport, large write reassembly, 150-byte response, initialization vectors and input stream',flush=True)


if __name__=='__main__':
    asyncio.run(main())
