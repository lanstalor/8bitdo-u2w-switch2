# Switch 2 mode step 1: Y at power-on (BT mode) -> advertise as Pro Controller 2. Otherwise stock.
TEXT = open('src/sw2/text.bin', 'rb').read()
PATCHES = [
    (0xa100, bytes(len(TEXT)), TEXT),
    (0xd5b2, bytes.fromhex('08906f99'), open('src/sw2/patch_d5b2.bin', 'rb').read()),  # was tjl 0x15894 setAdvData
    (0xd5ba, bytes.fromhex('0890ad99'), open('src/sw2/patch_d5ba.bin', 'rb').read()),  # was tjl 0x15918 setScanRspData
]
