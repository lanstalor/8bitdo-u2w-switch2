"""Validate the actual compiled table and pointers, not just generator output."""
import struct
import sys
from pathlib import Path
from uuid import UUID

data = Path(sys.argv[1]).read_bytes()
base = 0x5000


def read(address, length):
    assert base <= address <= base + len(data) - length, hex(address)
    return data[address-base:address-base+length]


tables = []
for offset in range(0, len(data)-60*24, 4):
    if data[offset:offset+24] == struct.pack('<HBBIIIII',59,0,0,0,0,0,0,0):
        tables.append(offset)
assert len(tables) == 1, tables
offset = tables[0]
attrs = []
for handle in range(60):
    count, perm, ul, length, up, vp, wr, rd = struct.unpack_from('<HBBIIIII',data,offset+24*handle)
    if not handle:
        continue
    assert count == {1:7, 8:43, 0x33:5, 0x38:4}.get(handle,0), (handle,'group count',count)
    expected_permission = 1
    if handle in (5,0x12,0x14,0x16,0x18,0x2a,0x2c,0x32):
        expected_permission = 2
    elif handle in (0x1a,0x1e,0x22,0x3a):
        expected_permission = 0
    elif handle in (0xb,0xc,0xf,0x10,0x1b,0x1c,0x1f,0x20,0x23,0x24,0x27,0x28,0x2f,0x30,0x3b):
        expected_permission = 3
    assert perm == expected_permission, (handle,'permissions',perm,expected_permission)
    uid = read(up, ul)
    if handle==0x26:
        assert vp==0x846fb8 and length==15
        value=bytes(8)
    elif handle in (0xb,0xf,0x1b,0x1f,0x23,0x27,0x2f,0x3b):
        assert vp==0x846fc7+2*(0xb,0xf,0x1b,0x1f,0x23,0x27,0x2f,0x3b).index(handle) and length==2
        value=bytes(2)
    else:
        value = read(vp, length)
    assert ul in (2,16)
    if perm & 2:
        assert wr & 1 and 0xa100 <= (wr & ~1) < 0xd000, (handle,wr)
    attrs.append((uid,value))
    if uid == b'\x03\x28':
        value_handle = int.from_bytes(value[1:3],'little')
        assert value_handle == handle+1
        next_up = struct.unpack_from('<I',data,offset+24*(handle+1)+8)[0]
        assert value[3:] == read(next_up,len(value)-3)
for handle, uid in {
    1:'00c5af5d-1964-4e30-8f51-1956f96bd280',
    8:'ab7de9be-89fe-49ad-828f-118f09df7fd0',
    0x0e:'7492866c-ec3e-4619-8258-32755ffcc0f8',
    0x16:'3dacbc7e-6955-40b5-8eaf-6f9809e8b379',
    0x1e:'506d9f7d-4278-4e95-a549-326ba77657e0',
}.items():
    actual = attrs[handle-1][1 if handle in (1,8) else 0]
    assert actual == UUID(uid).bytes[::-1], hex(handle)
for handle in (0xb,0xf,0x1b,0x1f,0x23,0x27,0x2f):
    assert attrs[handle-1] == (b'\x02\x29',b'\0\0')
assert attrs[0x33-1] == (b'\x00\x28', b'\x00\x18')
assert attrs[0x38-1] == (b'\x00\x28', b'\x01\x18')
assert attrs[0x3a-1] == (b'\x05\x2a',bytes(4))
assert attrs[0x3b-1] == (b'\x02\x29',bytes(2))
print('PASS: 59 attributes; service counts, permissions, declarations, fixed Nintendo handles, flash pointers and write callbacks verified')
