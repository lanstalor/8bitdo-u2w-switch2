#!/usr/bin/env python3
"""Extract and verify 8BitDo 0x8105 IAP OUT reports from a USBPcap pcapng capture.

Pure standard library. Parses pcapng directly (link type 249 = USBPcap), so it
works on a file saved from Wireshark ("Save As" pcapng) or by USBPcapCMD.

Usage:
  extract_iap.py capture.pcapng                    # list every 81 05 OUT report
  extract_iap.py capture.pcapng --summary          # command histogram + CRC stats only
  extract_iap.py capture.pcapng --out image.bin    # reassemble written image
  extract_iap.py capture.pcapng --dump reports.txt # one hex report per line
                                                   #   (same format as flash2c.py `gen --template`)
  Options: --device N (USBPcap device address), --endpoint 0x06, --bus N

Report layout (64 bytes, from NOTES.md "On-wire flash protocol"):
  [0:2]=81 05  [2]=cmd  [6:8]=len u16  [8:10]=crc16 u16  [10:14]=len u32 (cmd 03 only)
  [14:18]=addr/offset u32  [18:18+len]=data
Device replies start 02 05 (or 02 22). CRC-16/MODBUS is over data[18:18+len].

HID note: if the vendor tool talks via HID WriteFile and the interface has a
report ID, Windows prepends it, so the bytes on the wire may be 00 81 05 ...;
this script accepts the magic at offset 0 or 1 (see --no-strip). If the tool uses
HID SET_REPORT control transfers rather than an interrupt OUT endpoint, those
are picked up too (control data stage, OUT direction).
"""

import argparse
import struct
import sys
from collections import Counter

LINKTYPE_USBPCAP = 249
CMD_NAMES = {
    0x00: "session-start",
    0xC1: "write-start",
    0xC3: "set-block-addr",
    0x04: "block-start",
    0x03: "data-write",
    0xC4: "write-finish",
    0x07: "reset",
    0x05: "read",
}
XFER = {0: "iso", 1: "int", 2: "ctrl", 3: "bulk"}


def crc16(d):
    """CRC-16/MODBUS: poly 0xA001 reflected, init 0xFFFF, no xorout."""
    c = 0xFFFF
    for x in d:
        c ^= x
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return c & 0xFFFF


# ---------------------------------------------------------------- pcapng ----
def pcapng_packets(path):
    """Yield (frame_no, ts_ticks, linktype, payload) for every packet block."""
    with open(path, "rb") as f:
        buf = f.read()
    pos, end = 0, len(buf)
    endian = "<"
    ifaces = []  # linktype per interface id
    frame = 0
    if buf[:4] != b"\x0a\x0d\x0d\x0a":
        raise SystemExit("not a pcapng file (Save As -> pcapng in Wireshark)")
    while pos + 12 <= end:
        if buf[pos : pos + 4] == b"\x0a\x0d\x0d\x0a":  # SHB sets endianness
            bom = buf[pos + 8 : pos + 12]
            endian = "<" if bom == b"\x4d\x3c\x2b\x1a" else ">"
            btype = 0x0A0D0D0A
            blen = struct.unpack_from(endian + "I", buf, pos + 4)[0]
            ifaces = []
        else:
            btype, blen = struct.unpack_from(endian + "II", buf, pos)
        if blen < 12 or pos + blen > end:
            print(f"warn: truncated/odd block at {pos}", file=sys.stderr)
            break
        body = buf[pos + 8 : pos + blen - 4]
        if btype == 1:  # Interface Description Block
            ifaces.append(struct.unpack_from(endian + "H", body, 0)[0])
        elif btype == 6:  # Enhanced Packet Block
            iid, th, tl, cap, _orig = struct.unpack_from(endian + "IIIII", body, 0)
            frame += 1
            lt = ifaces[iid] if iid < len(ifaces) else -1
            yield frame, (th << 32) | tl, lt, body[20 : 20 + cap]
        elif btype == 3:  # Simple Packet Block
            frame += 1
            orig = struct.unpack_from(endian + "I", body, 0)[0]
            lt = ifaces[0] if ifaces else -1
            yield frame, 0, lt, body[4 : 4 + orig]
        pos += blen


# --------------------------------------------------------------- USBPcap ----
def parse_usbpcap(pkt):
    """Return dict for one USBPcap record or None.

    Header (little endian, packed): u16 headerLen, u64 irpId, u32 status,
    u16 function, u8 info, u16 bus, u16 device, u8 endpoint, u8 transfer,
    u32 dataLength  (=27 bytes); control transfers add u8 stage (=28).
    info bit0 set => PDO->FDO (device-to-host completion).
    """
    if len(pkt) < 27:
        return None
    hlen, irp, status, func, info, bus, dev, ep, xfer, dlen = struct.unpack_from(
        "<HQIHBHHBBI", pkt, 0
    )
    stage = pkt[27] if xfer == 2 and hlen >= 28 and len(pkt) > 27 else None
    return dict(
        irp=irp,
        status=status,
        info=info,
        completion=bool(info & 1),
        bus=bus,
        dev=dev,
        ep=ep,
        xfer=xfer,
        dlen=dlen,
        stage=stage,
        data=pkt[hlen : hlen + dlen],
    )


def is_out_with_data(r):
    """Host->device request packet carrying a payload (int/bulk OUT, or ctrl data stage OUT)."""
    if r["completion"] or not r["data"]:
        return False
    if r["xfer"] in (1, 3):
        return not (r["ep"] & 0x80)
    if r["xfer"] == 2:
        # stage 1 = data stage; direction bit of ep 0x00 means OUT for host->device requests
        return r["stage"] == 1 and not (r["ep"] & 0x80)
    return False


def find_report(data, strip=True):
    """Return the 64-byte (or shorter) report starting at the 81 05 magic, or None."""
    if data[:2] == b"\x81\x05":
        return data
    if strip and data[1:3] == b"\x81\x05":
        return data[1:]
    return None


def decode(rep):
    cmd = rep[2] if len(rep) > 2 else -1
    ln = int.from_bytes(rep[6:8], "little") if len(rep) >= 8 else 0
    crc = int.from_bytes(rep[8:10], "little") if len(rep) >= 10 else 0
    len32 = int.from_bytes(rep[10:14], "little") if len(rep) >= 14 else 0
    addr = int.from_bytes(rep[14:18], "little") if len(rep) >= 18 else 0
    data = bytes(rep[18 : 18 + ln])
    return cmd, ln, crc, len32, addr, data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pcapng")
    ap.add_argument("--out", help="write reassembled image (cmd 0x03 data at offset [14:18]) to this .bin")
    ap.add_argument("--dump", help="write one 64-byte hex report per line (OUT, in order)")
    ap.add_argument("--summary", action="store_true", help="no per-report lines")
    ap.add_argument("--device", type=lambda s: int(s, 0), help="USBPcap device address filter")
    ap.add_argument("--bus", type=lambda s: int(s, 0), help="USBPcap bus (root hub) filter")
    ap.add_argument("--endpoint", type=lambda s: int(s, 0), help="endpoint address filter, e.g. 0x06")
    ap.add_argument("--no-strip", action="store_true", help="do not accept a leading HID report-ID byte")
    ap.add_argument("--fill", type=lambda s: int(s, 0), default=0xFF, help="byte for unwritten gaps (default 0xFF)")
    a = ap.parse_args()

    stats = Counter()
    crc_ok = crc_bad = crc_na = 0
    reports = []  # raw reports in order
    image = {}  # offset -> bytes chunk (last write wins)
    conflicts = 0
    acks = Counter()
    devs = Counter()
    ep_seen = Counter()
    total_end = None
    c4_ver = None

    for frame, ts, lt, pkt in pcapng_packets(a.pcapng):
        if lt != LINKTYPE_USBPCAP:
            continue
        r = parse_usbpcap(pkt)
        if not r:
            continue
        if a.device is not None and r["dev"] != a.device:
            continue
        if a.bus is not None and r["bus"] != a.bus:
            continue
        if a.endpoint is not None and r["ep"] != a.endpoint:
            continue
        # device replies: IN completions starting 02 05 / 02 22
        if r["completion"] and r["data"][:2] in (b"\x02\x05", b"\x02\x22"):
            acks[r["data"][:2].hex()] += 1
            continue
        if not is_out_with_data(r):
            continue
        rep = find_report(r["data"], strip=not a.no_strip)
        if rep is None:
            continue
        cmd, ln, crc, len32, addr, data = decode(rep)
        devs[(r["bus"], r["dev"])] += 1
        ep_seen[(XFER[r["xfer"]], r["ep"])] += 1
        stats[cmd] += 1
        reports.append(bytes(rep).ljust(64, b"\x00")[:64])

        if ln > 46:
            status = f"BAD-LEN({ln})"
            crc_bad += 1
        elif ln == 0 or cmd in (0x07,):
            status = "crc n/a"
            crc_na += 1
        else:
            calc = crc16(data)
            if calc == crc and len(data) == ln:
                status = "crc ok"
                crc_ok += 1
            else:
                status = f"CRC MISMATCH calc={calc:04x}"
                crc_bad += 1

        name = CMD_NAMES.get(cmd, f"cmd{cmd:02x}")
        if cmd == 0xC3 and len(data) >= 8:
            detail = f"block addr=0x{int.from_bytes(data[0:4], 'little'):x} size=0x{int.from_bytes(data[4:8], 'little'):x}"
        elif cmd == 0x04:
            detail = f"block-start addr=0x{addr:x}"
        elif cmd == 0x03:
            detail = f"off=0x{addr:06x} len={ln} len32={len32}"
        elif cmd == 0xC4 and len(data) >= 8:
            total_end = int.from_bytes(data[0:4], "little")
            c4_ver = int.from_bytes(data[4:8], "little")
            detail = f"total=0x{total_end:x} ({total_end}) version=0x{c4_ver:x}"
        else:
            detail = f"len={ln} addr=0x{addr:x}"
        if not a.summary:
            print(f"#{frame:<6} dev {r['bus']}.{r['dev']} {XFER[r['xfer']]} ep 0x{r['ep']:02x}  {cmd:02x} {name:<15} {detail:<42} {status}")

        if cmd == 0x03 and ln and len(data) == ln:
            old = image.get(addr)
            if old is not None and old != data:
                conflicts += 1
            image[addr] = data

    print("\n=== summary ===")
    print("devices:", {f"{b}.{d}": n for (b, d), n in devs.items()})
    print("endpoints:", {f"{t}/0x{e:02x}": n for (t, e), n in ep_seen.items()})
    for cmd, n in sorted(stats.items()):
        print(f"  cmd {cmd:02x} {CMD_NAMES.get(cmd, '?'):<15} x{n}")
    print(f"CRC-16/MODBUS: ok={crc_ok} bad={crc_bad} n/a={crc_na}")
    print("device replies (first 2 bytes):", dict(acks) or "none seen")
    if total_end is not None:
        print(f"c4 declares total length 0x{total_end:x} ({total_end}), version byte 0x{c4_ver:x}")

    if image:
        chunks = sorted(image.items())
        size = max(o + len(d) for o, d in chunks)
        buf = bytearray([a.fill & 0xFF]) * size
        covered = []
        for o, d in chunks:
            buf[o : o + len(d)] = d
            if covered and covered[-1][1] == o:
                covered[-1][1] = o + len(d)
            else:
                covered.append([o, o + len(d)])
        print(f"image: {len(chunks)} unique 03 chunks, span 0..0x{size:x} ({size} bytes), overwrite-conflicts={conflicts}")
        print("covered ranges:", ", ".join(f"0x{s:x}-0x{e:x}" for s, e in covered))
        if total_end and size != total_end:
            print(f"note: written span {size} != c4 total {total_end} (differential write or trailing blank?)")
        if a.out:
            open(a.out, "wb").write(bytes(buf))
            print(f"wrote {a.out} ({size} bytes; gaps filled with 0x{a.fill & 0xFF:02x})")
    elif a.out:
        print("no 0x03 data-write reports found; nothing to write", file=sys.stderr)

    if a.dump:
        with open(a.dump, "w") as f:
            for rep in reports:
                f.write(rep.hex() + "\n")
        print(f"wrote {len(reports)} reports to {a.dump}")
    if crc_bad:
        sys.exit(2)


if __name__ == "__main__":
    main()
