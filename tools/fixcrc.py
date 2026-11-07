# Fix/verify all integrity values the U2W bootloader + Telink header use (see notes/PHASE1_WINDOWS.md "Boot checks"):
#   size = u32 @0x18
#   T: Telink  ~CRC32(payload[0:size-4])        stored @ size-4
#   1: sum32 of bytes payload[0:size-4]         stored @ size      (bootloader check 1, if u16 @0x1e != 0)
#   2: sum32 of bytes payload[size+4:size+4+L]  stored @ size+4+L  (bootloader check 2), L = region-2 length
# Usage: fixcrc.py <in.bin> [out.bin] [--len2 0xbbdc]   (verify only when no out given)
import sys, struct, zlib
argv = sys.argv[1:]
if '--len2' in argv:
    i = argv.index('--len2'); argv = argv[:i] + argv[i + 2:]
args = [a for a in argv if not a.startswith('--')]
p = bytearray(open(args[0], 'rb').read())
u32 = lambda o: struct.unpack_from('<I', p, o)[0]
size = u32(0x18)
def find_len2():
    if '--len2' in sys.argv: return int(sys.argv[sys.argv.index('--len2') + 1], 0)
    lo = size + 4  # region 2 ends where the stored sum matches; search near the end of the data
    end = len(p)
    while end > lo and p[end - 1] == 0: end -= 1
    for e in range(end, max(lo, end - 64), -1):
        if (e - lo) % 4 == 0 and (sum(p[lo:e]) & 0xffffffff) == u32(e): return e - lo
    return None
L = find_len2()
def calc():
    t = (zlib.crc32(bytes(p[:size - 4])) ^ 0xFFFFFFFF) & 0xFFFFFFFF
    s1 = sum(p[:size - 4]) & 0xffffffff
    s2 = (sum(p[size + 4:size + 4 + L]) & 0xffffffff) if L else None
    return t, s1, s2
t, s1, s2 = calc()
ok = [t == u32(size - 4), s1 == u32(size), (L is not None and s2 == u32(size + 4 + L))]
print(f"size={size:#x} len2={L:#x}" if L else f"size={size:#x} len2=?",
      f"T {'OK' if ok[0] else 'BAD'}  check1 {'OK' if ok[1] else 'BAD'}  check2 {'OK' if ok[2] else 'BAD'}")
if len(args) > 1:
    if L is None: raise SystemExit('region-2 length unknown; pass --len2')
    struct.pack_into('<I', p, size - 4, t)
    struct.pack_into('<I', p, size, s1)
    struct.pack_into('<I', p, size + 4 + L, s2)
    open(args[1], 'wb').write(p)
    print('wrote', args[1])
