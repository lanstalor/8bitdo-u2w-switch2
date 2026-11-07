# Step 3 test: first code patch. Hook bls_ll_setAdvData's only call site (tjl @0xd5b2 in BLE init FUN_0000d558)
# to hook_set_adv @0xa100 (src/hook_adv), which drops the short name and appends test manufacturer data.
TEXT = open('src/hook_adv/text.bin', 'rb').read()
CALL = open('src/hook_adv/patch_d5b2.bin', 'rb').read()
PATCHES = [
    (0xa100, bytes(len(TEXT)), TEXT),             # cave: must currently be zero
    (0xd5b2, bytes.fromhex('08906f99'), CALL),    # original: tjl 0x15894 (bls_ll_setAdvData)
]
