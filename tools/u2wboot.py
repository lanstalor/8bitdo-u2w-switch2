#!/usr/bin/env python3
"""8BitDo Ultimate 2 Wireless bootloader tool (USB 2dc8:3208, enter by holding L1+R1 while plugging in).

Report layout from the 2C project's reversal of 8BitDoFirmwareUpdaterTools.dll (ref/8bitdo-2c-re-flake/flasher/flash2c.py):
  host -> dev (64 B, HID has no report IDs, so hidapi gets a leading 0x00):
     [0]=0x05 [1:3]=cmd u16 [5:7]=datalen u16 [7:9]=crc16 u16 [9:13]=param4 u32 [13:17]=addr u32 [17:]=data
  dev -> host: [0]=0x00 [1]=0x05 [2]=0x00 [4]=cmd ... data at [18:]
  cmd 8 = version, 5 = read, 4 = erase (param4 = byte count), 3 = write (<=46 B, CRC-16/MODBUS)
Addresses are absolute flash addresses (U2W app image starts at 0x5000 = payload offset 0).

Commands:
  version
  read ADDR N [--out FILE]
  compare PAYLOAD [--lo 0x0 --hi 0x23800]      read back app range and compare to a payload (read-only)
  restore-sector PAYLOAD SECTOR_OFFSET --yes  erase + write one 4 KB sector of the app from PAYLOAD, then read back
"""
import argparse
import sys

import hid

VID, PID = 0x2DC8, 0x3208
APP_BASE = 0x5000


def crc16(d):
    c = 0xFFFF
    for x in d:
        c ^= x
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return c & 0xFFFF


def boot_report(cmd, addr=0, param4=0, datalen=0, data=b"", crc=0):
    r = bytearray(64)
    r[0] = 0x05
    r[1:3] = cmd.to_bytes(2, "little")
    r[5:7] = datalen.to_bytes(2, "little")
    r[7:9] = crc.to_bytes(2, "little")
    r[9:13] = param4.to_bytes(4, "little")
    r[13:17] = addr.to_bytes(4, "little")
    r[17:17 + len(data)] = data
    return bytes(r)


class Boot:
    def __init__(self, verbose=False):
        ds = hid.enumerate(VID, PID)
        if not ds:
            raise SystemExit("no 2dc8:3208 bootloader device (hold L1+R1 while plugging in)")
        self.h = hid.device()
        self.h.open_path(ds[0]["path"])
        self.v = verbose

    def xfer(self, rep, cmd, timeout_ms=3000):
        self.h.write(b"\x00" + rep)
        for _ in range(8):
            r = self.h.read(64, timeout_ms)
            if not r:
                return False, None
            r = bytes(r)
            if self.v:
                print("  <-", r[:40].hex(), file=sys.stderr)
            if len(r) >= 5:
                return (r[0] == 0 and r[1] == 5 and r[2] == 0 and r[4] == cmd), r
        return False, None

    def read(self, addr, n):
        out = bytearray()
        while len(out) < n:
            k = min(46, n - len(out))
            ok, r = self.xfer(boot_report(5, addr=addr + len(out), param4=k, datalen=k), 5)
            if not ok:
                raise SystemExit(f"read failed at {addr + len(out):#x}: {r.hex() if r else None}")
            out += r[18:18 + k]
        return bytes(out)


def cmd_version(a):
    b = Boot(verbose=True)
    ok, r = b.xfer(boot_report(8, param4=4, datalen=4), 8)
    print("version reply:", r.hex() if r else None, "ACK" if ok else "no ACK")


def cmd_read(a):
    b = Boot(verbose=a.verbose)
    d = b.read(int(a.addr, 0), int(a.n, 0))
    if a.out:
        open(a.out, "wb").write(d)
        print("wrote", a.out, len(d))
    else:
        print(d.hex())


def cmd_compare(a):
    p = open(a.payload, "rb").read()
    lo, hi = int(a.lo, 0), min(int(a.hi, 0), len(p))
    b = Boot()
    bad = []
    for s in range(lo, hi, 0x1000):
        n = min(0x1000, hi - s)
        d = b.read(int(a.base, 0) + s, n)
        same = d == p[s:s + n]
        if not same:
            diff = [i for i in range(n) if d[i] != p[s + i]]
            bad.append(s)
            print(f"payload sector {s:#07x} (flash {int(a.base, 0) + s:#07x}): {len(diff)} bytes differ, first at +{diff[0]:#x}")
    print(f"{(hi - lo + 0xfff) // 0x1000 - len(bad)} sectors identical, {len(bad)} differ: {[hex(x) for x in bad]}")


def cmd_restore_sector(a):
    if not a.yes:
        raise SystemExit("refusing without --yes")
    p = open(a.payload, "rb").read()
    s = int(a.sector, 0)
    if s % 0x1000 or s >= len(p):
        raise SystemExit("sector offset must be 4K aligned inside the payload")
    data = p[s:s + 0x1000]
    base = int(a.base, 0)
    if base not in (0x5000, 0x32000):
        raise SystemExit("base must be 0x5000 or 0x32000")
    addr = base + s
    b = Boot()
    print(f"erasing flash {addr:#x} (+0x1000)", file=sys.stderr)
    ok, r = b.xfer(boot_report(4, addr=addr, param4=0x1000), 4, timeout_ms=8000)
    if not ok:
        raise SystemExit(f"erase not ACKed: {r.hex() if r else None}")
    blank = b.read(addr, 64)
    print("after erase first 64 B:", blank.hex()[:32], "...", file=sys.stderr)
    for off in range(0, len(data), 46):
        blk = data[off:off + 46]
        ok, r = b.xfer(boot_report(3, addr=addr + off, param4=len(data), datalen=len(blk), data=blk, crc=crc16(blk)), 3)
        if not ok:
            raise SystemExit(f"write not ACKed at {addr + off:#x}: {r.hex() if r else None}")
    back = b.read(addr, len(data))
    print("verify:", "MATCH" if back == data else "MISMATCH")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("version").set_defaults(f=cmd_version)
    r = sub.add_parser("read"); r.add_argument("addr"); r.add_argument("n"); r.add_argument("--out")
    r.add_argument("--verbose", action="store_true"); r.set_defaults(f=cmd_read)
    c = sub.add_parser("compare"); c.add_argument("payload"); c.add_argument("--lo", default="0x0")
    c.add_argument("--base", default="0x5000")
    c.add_argument("--hi", default="0x23800"); c.set_defaults(f=cmd_compare)
    w = sub.add_parser("restore-sector"); w.add_argument("payload"); w.add_argument("sector")
    w.add_argument("--base", default="0x5000", help="image base: 0x5000 = live app (bank A), 0x32000 = staging bank B")
    w.add_argument("--yes", action="store_true"); w.set_defaults(f=cmd_restore_sector)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
