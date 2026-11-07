# Complete protocol candidate; hardware acceptance remains unverified.
from pathlib import Path
text = Path('src/sw2/text.bin').read_bytes()
assert len(text) <= 0x2f00
PATCHES = [(0xa100, bytes(len(text)), text)]
for address, original in [(0xd5b2, '08906f99'), (0xd5ba, '0890ad99'),
                          (0xd768, '0a90be98'), (0xd570, '0290a29b'),
                          (0xd5be, '0c901b9d'), (0xd74c, 'ff97a89f'),
                          (0xd48a, '0b90a199'), (0xd496, '0b90f99b'),
                          (0xd750, 'ff97da9f'),
                          (0x18f5e, 'ff972b9e')]:
    patch = Path('src/sw2/patch_%x.bin' % address).read_bytes()
    assert len(patch) == 4
    PATCHES.append((address, bytes.fromhex(original), patch))
