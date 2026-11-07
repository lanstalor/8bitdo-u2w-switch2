#!/usr/bin/env python3
"""8BitDo Ultimate 2 Wireless flasher for Windows (hidapi, stock HID driver; no Zadig).

Protocol learned from two USBPcap captures of Ultimate Software V2 (notes/PHASE1_WINDOWS.md):
  * Channel: USB 2dc8:310b interface 2 (HID usage page 0xff7a). Output report ID 0x81 (+63 B), input report ID 0x02.
  * 81 04 00 01            -> device info (reply carries firmware version byte + PID 0x6012)
  * 81 05 08 / 00 21 01 / c1  session open (00 replies 02 22 <version>)
  * c3 <addr u32><len u32><cc*4>  -> reply [18:20] CRC-16/MODBUS + [20:24] sum32 of that flash sector, as it is now (read-only)
  * 04 <sector u32 @14> (block-start) + 03 data-writes (46 B each, CRC-16/MODBUS)  rewrite the sector selected by the preceding c3
  * Verify burst: c3 for every sector; then c4 <total u32><version u32>; then 07 reset.
  * The vendor tool skips 04/03 for sectors whose device checksum already equals the new content (differential update).
The sequence generator below reproduces the vendor stream byte-for-byte (see `gen --template`).

Commands:
  list                          enumerate 2dc8 HID interfaces (no I/O)
  gen PAYLOAD [--template T]    offline: build the stream for a full write, optionally diff against a captured stream
  info                          send 81 04 00 01 only and print the reply (version / PID)
  checksums [--payload P]       open session, read every sector's device checksum (c3 only, no 04/03/c4/07), compare to P
  flash PAYLOAD --yes [--version 0x6d] [--full]   differential flash (like the vendor tool); --full rewrites every sector
"""
import argparse
import sys
import time

import hid

VID, PID_APP, PID_BOOT = 0x2DC8, 0x310B, 0x3208
USAGE_PAGE = 0xFF7A
SECTOR = 0x1000
CHUNK = 46
DEFAULT_VERSION = 0x6D  # v1.09


def crc16(d):
    c = 0xFFFF
    for x in d:
        c ^= x
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return c & 0xFFFF


def sector_sig(data):
    return crc16(data).to_bytes(2, "little") + (sum(data) & 0xFFFFFFFF).to_bytes(4, "little")


# ---- report builders (64 bytes incl. report ID 0x81) ----
def _r(cmd):
    r = bytearray(64)
    r[0], r[1], r[2] = 0x81, 0x05, cmd
    return r


def _data(cmd, data, crc=None, off=0, len10=True):
    r = _r(cmd)
    r[6:8] = len(data).to_bytes(2, "little")
    r[8:10] = (crc16(data) if crc is None else crc).to_bytes(2, "little")
    if len10:
        r[10:14] = len(data).to_bytes(4, "little")
    r[14:18] = off.to_bytes(4, "little")
    r[18:18 + len(data)] = data
    return bytes(r)


def r08():
    return bytes(_r(0x08))


def r00():
    r = _r(0x00)
    r[3], r[4] = 0x21, 0x01
    return bytes(r)


def rc1():
    return bytes(_r(0xC1))


def rc3(addr, ln):
    return _data(0xC3, addr.to_bytes(4, "little") + ln.to_bytes(4, "little") + b"\xcc" * 4, len10=False)


def r04(sec):
    r = _r(0x04)
    r[14:18] = sec.to_bytes(4, "little")
    return bytes(r)


def rc4(total, version):
    return _data(0xC4, total.to_bytes(4, "little") + version.to_bytes(4, "little"))


def r07():
    return _data(0x07, b"\x00" * 8, crc=0)


def info_req():
    r = bytearray(64)
    r[0], r[1], r[2], r[3] = 0x81, 0x04, 0x00, 0x01
    return bytes(r)


def sectors(total):
    return [(a, min(SECTOR, total - a)) for a in range(0, total, SECTOR)]


def sector_writes(payload, a, ln):
    out = [r04(a)]
    for o in range(0, ln, CHUNK):
        out.append(_data(0x03, payload[a + o:a + o + min(CHUNK, ln - o)], off=a + o))
    return out


def full_stream(payload, version, skip=()):
    """Offline model of the vendor stream; `skip` = sector addresses the device already holds (no 04/03)."""
    total = len(payload)
    seq = [r08(), r00(), rc1()]
    for a, ln in sectors(total):
        seq.append(rc3(a, ln))
        if a not in skip:
            seq += sector_writes(payload, a, ln)
    seq += [rc3(a, ln) for a, ln in sectors(total)]
    seq += [rc4(total, version), r07()]
    return seq


def boot_checks(p):
    """Bootloader/Telink integrity values (notes/PHASE1_WINDOWS.md 'Boot checks'). Returns list of failures."""
    import struct, zlib
    u32 = lambda o: struct.unpack_from("<I", p, o)[0]
    size = u32(0x18)
    bad = []
    if ((zlib.crc32(p[:size - 4]) ^ 0xFFFFFFFF) & 0xFFFFFFFF) != u32(size - 4):
        bad.append("Telink CRC32 @size-4")
    if struct.unpack_from("<H", p, 0x1e)[0] and (sum(p[:size - 4]) & 0xFFFFFFFF) != u32(size):
        bad.append("bootloader check 1 (sum @size)")
    lo, end = size + 4, len(p)
    while end > lo and p[end - 1] == 0:
        end -= 1
    if not any((e - lo) % 4 == 0 and (sum(p[lo:e]) & 0xFFFFFFFF) == u32(e) for e in range(end, max(lo, end - 64), -1)):
        bad.append("bootloader check 2 (region-2 sum)")
    return bad


# ---- device I/O ----
def find_iface(pid=PID_APP):
    for d in hid.enumerate(VID, pid):
        if d["usage_page"] == USAGE_PAGE or (pid == PID_APP and d["interface_number"] == 2):
            return d
    return None


class Dev:
    def __init__(self, pid=PID_APP):
        d = find_iface(pid)
        if d is None:
            raise SystemExit(f"no {VID:#06x}:{pid:#06x} vendor HID interface found (is the controller plugged in by USB?)")
        self.h = hid.device()
        self.h.open_path(d["path"])
        print(f"opened {d['product_string']} {VID:#06x}:{pid:#06x} if{d['interface_number']} up {d['usage_page']:#06x}", file=sys.stderr)

    def xfer(self, report, timeout_ms=3000, expect=None):
        self.h.write(report)
        t0 = time.time()
        while (time.time() - t0) * 1000 < timeout_ms:
            r = self.h.read(64, 200)
            if r:
                r = bytes(r)
                if expect is None or r[:2] in expect:
                    return r
        return None

    def close(self):
        self.h.close()


ACK = (b"\x02\x05", b"\x02\x22", b"\x02\x04")


def open_session(dev):
    for rep, name in ((r08(), "08"), (r00(), "00"), (rc1(), "c1")):
        r = dev.xfer(rep, expect=ACK)
        if r is None:
            raise SystemExit(f"no reply to {name}; aborting before any write")
        if name == "00":
            print(f"session open: device reports firmware version byte {r[2]:#04x}", file=sys.stderr)


def read_sig(dev, a, ln):
    r = dev.xfer(rc3(a, ln), expect=(b"\x02\x05",))
    if r is None or r[4] != 0xC3:
        raise SystemExit(f"bad/no c3 reply for sector {a:#x}: {r.hex() if r else None}")
    return r[18:24]


def cmd_list(a):
    for d in hid.enumerate(VID):
        print(f"{d['product_id']:#06x} if{d['interface_number']} up {d['usage_page']:#06x} u {d['usage']:#04x} {d['product_string']}")


def cmd_gen(a):
    p = open(a.payload, "rb").read()
    tmpl = [bytes.fromhex(x) for x in open(a.template).read().split()] if a.template else None
    skip = ()
    if tmpl:  # infer which sectors the template skipped (c3 not followed by 04)
        skip = set()
        for i, r in enumerate(tmpl[:-1]):
            if r[2] == 0xC3 and tmpl[i + 1][2] != 0x04 and i < len(tmpl) - 40:
                skip.add(int.from_bytes(r[18:22], "little"))
        skip = {s for s in skip if s < len(p)}
    seq = full_stream(p, a.version, skip)
    if tmpl is None:
        print(f"generated {len(seq)} reports")
        return
    diffs = [i for i in range(min(len(seq), len(tmpl))) if seq[i] != tmpl[i]]
    ok = not diffs and len(seq) == len(tmpl)
    print(f"skip={sorted(hex(s) for s in skip)} generated {len(seq)} vs template {len(tmpl)}: "
          + ("MATCH byte-for-byte" if ok else f"{len(diffs)} diffs, first at {diffs[:3]}"))
    if not ok:
        for i in diffs[:3]:
            print(" gen ", seq[i][:32].hex(), "\n tmpl", tmpl[i][:32].hex())
        raise SystemExit(1)


def cmd_info(a):
    dev = Dev()
    r = dev.xfer(info_req(), expect=(b"\x02\x04",))
    print("info reply:", r.hex() if r else "(none)")
    dev.close()


def cmd_checksums(a):
    p = open(a.payload, "rb").read() if a.payload else None
    total = len(p) if p else int(a.total, 0)
    dev = Dev()
    open_session(dev)
    same = 0
    for s, ln in sectors(total):
        sig = read_sig(dev, s, ln)
        tag = ""
        if p:
            m = sig == sector_sig(p[s:s + ln])
            same += m
            tag = "same" if m else "DIFFERENT"
        print(f"{s:#07x} {sig.hex()} {tag}")
    if p:
        print(f"{same}/{len(sectors(total))} sectors already identical to {a.payload}")
    dev.close()
    print("note: session left open without c4/07; unplug + power-cycle the controller to return to normal", file=sys.stderr)


def cmd_flash(a):
    if not a.yes:
        raise SystemExit("refusing to flash without --yes")
    p = open(a.payload, "rb").read()
    if len(p) % 2 or len(p) > 0x60000:
        raise SystemExit("payload size looks wrong")
    if p[8:12] != b"KNLT":
        raise SystemExit("payload has no Telink KNLT magic at offset 8; refusing")
    bad = boot_checks(p)
    if bad:
        raise SystemExit(f"REFUSING: image would not boot, failed: {bad}. Run tools/fixcrc.py first.")
    print("boot checks: Telink CRC, check 1, check 2 all OK", file=sys.stderr)
    dev = Dev()
    open_session(dev)
    total = len(p)
    plan = []
    for s, ln in sectors(total):
        sig = read_sig(dev, s, ln)
        need = a.full or sig != sector_sig(p[s:s + ln])
        plan.append((s, ln, need))
        if need:
            print(f"writing sector {s:#07x}", file=sys.stderr)
            for rep in sector_writes(p, s, ln):
                r = dev.xfer(rep, expect=(b"\x02\x05",))
                if r is None or r[4] != rep[2]:
                    raise SystemExit(f"no/odd ACK at sector {s:#x} cmd {rep[2]:#04x}: {r.hex() if r else None}. "
                                     "Do NOT power off; re-run flash (sectors are retried), or use the L1+R1 bootloader.")
    print(f"wrote {sum(n for *_, n in plan)} of {len(plan)} sectors; verifying", file=sys.stderr)
    bad = [s for s, ln, _ in plan if read_sig(dev, s, ln) != sector_sig(p[s:s + ln])]
    if bad:
        raise SystemExit(f"VERIFY FAILED for sectors {[hex(b) for b in bad]}; NOT sending c4/07. Re-run flash.")
    r = dev.xfer(rc4(total, a.version), timeout_ms=5000, expect=(b"\x02\x05",))
    print("c4 reply:", r.hex()[:40] if r else None, file=sys.stderr)
    try:
        dev.xfer(r07(), timeout_ms=1500, expect=(b"\x02\x05",))
    except OSError:
        pass
    dev.close()
    print("flash complete and verified; controller resets now")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(f=cmd_list)
    g = sub.add_parser("gen"); g.add_argument("payload"); g.add_argument("--template")
    g.add_argument("--version", type=lambda s: int(s, 0), default=DEFAULT_VERSION); g.set_defaults(f=cmd_gen)
    sub.add_parser("info").set_defaults(f=cmd_info)
    c = sub.add_parser("checksums"); c.add_argument("--payload"); c.add_argument("--total", default="0x23800")
    c.set_defaults(f=cmd_checksums)
    fl = sub.add_parser("flash"); fl.add_argument("payload"); fl.add_argument("--yes", action="store_true")
    fl.add_argument("--full", action="store_true")
    fl.add_argument("--version", type=lambda s: int(s, 0), default=DEFAULT_VERSION); fl.set_defaults(f=cmd_flash)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
