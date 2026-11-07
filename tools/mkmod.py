#!/usr/bin/env python3
"""Build a modded U2W payload from a stock payload plus a patch spec, then fix all boot-check values.

Patch spec (python file) defines PATCHES = [(vma, old_bytes, new_bytes), ...]; VMA = 0x5000 + payload offset.
Every patch asserts the stock bytes it replaces, so a spec can never apply to the wrong firmware version.
Usage: mkmod.py <stock.bin> <spec.py> <out.bin>
"""
import runpy
import struct
import sys
import zlib

BASE = 0x5000


def u32(p, o):
    return struct.unpack_from("<I", p, o)[0]


def region2_len(p, size):
    lo, end = size + 4, len(p)
    while end > lo and p[end - 1] == 0:
        end -= 1
    for e in range(end, max(lo, end - 64), -1):
        if (e - lo) % 4 == 0 and (sum(p[lo:e]) & 0xFFFFFFFF) == u32(p, e):
            return e - lo
    raise SystemExit("could not locate region-2 checksum in the stock image")


def fix(p, len2):
    size = u32(p, 0x18)
    struct.pack_into("<I", p, size - 4, (zlib.crc32(bytes(p[:size - 4])) ^ 0xFFFFFFFF) & 0xFFFFFFFF)
    struct.pack_into("<I", p, size, sum(p[:size - 4]) & 0xFFFFFFFF)
    struct.pack_into("<I", p, size + 4 + len2, sum(p[size + 4:size + 4 + len2]) & 0xFFFFFFFF)


def checks(p, len2):
    size = u32(p, 0x18)
    return [
        ((zlib.crc32(bytes(p[:size - 4])) ^ 0xFFFFFFFF) & 0xFFFFFFFF) == u32(p, size - 4),
        (sum(p[:size - 4]) & 0xFFFFFFFF) == u32(p, size),
        (sum(p[size + 4:size + 4 + len2]) & 0xFFFFFFFF) == u32(p, size + 4 + len2),
    ]


def main():
    stock = bytearray(open(sys.argv[1], "rb").read())
    spec = runpy.run_path(sys.argv[2])
    size = u32(stock, 0x18)
    len2 = region2_len(stock, size)
    if not all(checks(stock, len2)):
        raise SystemExit("stock image does not pass its own checks; wrong input?")
    p = bytearray(stock)
    protected = {size - 4, size, size + 4 + len2}
    for vma, old, new in spec["PATCHES"]:
        o = vma - BASE
        if len(old) != len(new):
            raise SystemExit(f"patch @{vma:#x}: old/new length differ")
        if bytes(p[o:o + len(old)]) != old:
            raise SystemExit(f"patch @{vma:#x}: stock bytes mismatch (have {bytes(p[o:o + len(old)]).hex()})")
        if any(o <= x + k < o + len(old) for x in protected for k in range(4)):
            raise SystemExit(f"patch @{vma:#x} overlaps a checksum word")
        p[o:o + len(new)] = new
    fix(p, len2)
    if not all(checks(p, len2)):
        raise SystemExit("internal error: checks still failing after fix")
    open(sys.argv[3], "wb").write(p)
    diff = [i for i in range(len(p)) if p[i] != stock[i]]
    print(f"wrote {sys.argv[3]}: {len(diff)} bytes changed in sectors "
          f"{sorted({hex(i & ~0xfff) for i in diff})}; Telink CRC / check 1 / check 2 OK")


if __name__ == "__main__":
    main()
