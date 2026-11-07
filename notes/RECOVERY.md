# Restoring stock firmware — Ultimate 2 Wireless

Current as of 2026-11-07. These instructions distinguish tested paths from
unverified vendor-tool behavior. Reading this guide does not perform a restore.

## Reset is not a firmware rollback

Power cycling or a settings reset leaves the installed firmware in place.
With the controller powered off, hold **L1+R1 (LB+RB)** while plugging in USB
to enter its existing bootloader. This was tested on this controller; USB ID
changes from normal `2dc8:310b` to bootloader `2dc8:3208`. Entry alone does not
write stock firmware. Unplug and power on normally to leave bootloader mode.

The mod updates the application, not the bootloader. Its RAM overlays disappear
on reset and are reinstalled only by the modified application in Y mode.

## Normal USB restoration — tested mechanism

When normal USB firmware is running, use the known-good stock application image:

```powershell
& C:/Users/lance/re-tools/venv/Scripts/python.exe tools/u2wflash.py list
& C:/Users/lance/re-tools/venv/Scripts/python.exe tools/u2wflash.py flash firmware/payload-ctrl-v109.bin --yes
```

Run from the repository; connect by USB and keep it connected through completion.
The tool checks all three image integrity values, writes staging bankB,
verifies its sectors, commits the update and resets. The bootloader copiesB toA.
This mechanism was tested restoring an earlier modified image to stock1.09;
we have not rolled the final working v0.1.0 back merely to repeat that test.
Use `--version 0x6d` for1.09 if explicitly supplying a version (it is the default).
Restoring the app is not a factory erase of settings or bond records.

## If the application will not boot — tested recovery primitives

Enter L1+R1 USB bootloader mode. Use `u2wboot.py`, not the normal-mode flasher:

```powershell
& C:/Users/lance/re-tools/venv/Scripts/python.exe tools/u2wboot.py version
& C:/Users/lance/re-tools/venv/Scripts/python.exe tools/u2wboot.py compare firmware/payload-ctrl-v109.bin --base 0x5000
& C:/Users/lance/re-tools/venv/Scripts/python.exe tools/u2wboot.py compare firmware/payload-ctrl-v109.bin --base 0x32000
```

These commands read only. Bootloader reading, sector erase/write/read-back and
successful return to stock were tested during failed early experiments.

`restore-sector` takes a **payload-relative,4KB-aligned offset**, not an absolute
flash address. An agent must inspect the comparison and update-record state,
verify the stock image, then restore the needed application sectors. Example
syntax for one identified live-bank sector:

```powershell
& C:/Users/lance/re-tools/venv/Scripts/python.exe tools/u2wboot.py restore-sector firmware/payload-ctrl-v109.bin 0x16000 --base 0x5000 --yes
```

That offset is an example from an earlier recovery, not the complete set changed
by v0.1.0. Verify every restored sector and compare complete banks before reboot.
Account for both banks and pending update metadata: a valid modified bankB can
otherwise be copied back toA. Current bankB must NOT be assumed stock.
`restore-sector` prints MATCH/MISMATCH; an agent must inspect that result, not
only the process exit code. Do not erase the bootloader, factory data, settings,
or update metadata indiscriminately, or flash the full-device dump as an app.

## Files and verified hashes

- Stock app: `firmware/payload-ctrl-v109.bin`, SHA256
  `6a2ff4de75982f398a2d19a57f1c43f1bda98e4154f1e3b9686ee41678c7b3a1`.
- Full private backup: `backup/flash-full-512k.bin`,524288 bytes, SHA256
  `dbf3aa4495513ee81891d92d3a4d79c906d3778bd3606fbf474c8b3a10188dfa`.
- Second full-backup copy: `C:/Users/lance/re-tools/backup/flash-full-512k.bin`.
  Both copies were rechecked against the same hash on2026-11-07.
- Keep private backups private: they include device-specific data. They are not
  on GitHub. Source and flasher tools are in the repository.

Flash map: liveA0x5000, stagingB0x32000, update record0x31000,
bond journal0x74000. App payload length1.09=0x23800. See PHASE1_WINDOWS.md for
the original recovery evidence and boot checks, not its obsolete early status.

## Official 8BitDo software

Ultimate Software V2 supports firmware updates for this model:
https://app.8bitdo.com/Ultimate-Software-V2/

Official updates/downgrades were used earlier in this project. However, direct
reinstallation from the released mod, same-version overwrite, and recognition
in bootloader mode have not been verified with the current vendor software.
The mod still reports1.09, so an updater may regard it as already current.
Do not promise a button reset plus vendor software will always restore it.
If the vendor updater offers and successfully completes a stock update, that
replaces the mod; otherwise the local tested tools/stock image are the fallback.
