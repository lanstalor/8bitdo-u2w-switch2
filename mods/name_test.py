# Step 2 test: rename the controller's Bluetooth names (same lengths as stock). Pure data change.
PATCHES = [
    (0x1b3c6, b"8BitDo Ultimate",            b"U2W Switch2 Dev"),             # adv short name (AD type 0x08)
    (0x1b3e6, b"8BitDo Ultimate 2 Wireless", b"U2W Switch2 Dev Firmware 1"),  # scan response complete name (0x09)
    (0x1b448, b"8BitDo Ultimate 2 Wireless", b"U2W Switch2 Dev Firmware 1"),  # GAP Device Name characteristic
]
