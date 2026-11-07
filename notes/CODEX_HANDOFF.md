# Handoff to Codex: Switch 2 console stalls below L2CAP

> Historical handoff, superseded by [CURRENT_HANDOFF.md](CURRENT_HANDOFF.md).
> The controller now works on Switch 2 with released v0.1.0/candidate13.
> For restoration use [RECOVERY.md](RECOVERY.md). Preserve this file as history.

Updated 2026-11-07 by Claude. Read this together with `notes/CLAUDE_HANDOFF.md`
(your earlier handoff) and the newest sections of `notes/PROGRESS.md`.

## Headline

**The Switch 2 connects to the controller at the link layer, holds the link, and
never sends a single L2CAP PDU.** No ATT MTU exchange, no discovery, no writes, no
SMP, no signalling. It sat like that for 61 s until the console was put to sleep
(disconnect reason 0x13). No LTK request, no encryption. The stall is in link-layer
control traffic, or the console is waiting for something the controller never sends.

Everything above L2CAP is verified working from a PC (Windows, Intel adapter):
command transport, 150-byte replies, padded 129-byte writes, and the 63-byte input
stream at 65 reports/s with live buttons and sticks.

## Installed firmware

- `firmware/mod-sw2-candidate-5-v109.bin`, SHA256 prefix `b6465a351f6cc556`.
- Flashed over normal-mode USB, 5 sectors (payload offsets 0x5000, 0x6000, 0x8000,
  0x13000, 0x17000), verified, reset OK, re-enumerates normally.
- One-flash rule is lifted. The user permits further flashes.
- Git: committed through `01996f2`. Working tree clean apart from this handoff.

Candidate history since your final candidate (all in `src/sw2/sw2.c`):

| Candidate | Change |
|---|---|
| 2 | Input gated on CCCD + features only (not encryption) so the PC can verify mapping. Normal-mode advertisement passed through unchanged (debug key-bitmask variant removed). `0x844d94 = 0` on connect: no notify hold-off. |
| 3 | Sticky post-mortem record on char 0x26, cleared only at boot. |
| 4 | Keep-awake: sets stock pairing-mode flag `0x846013` while unconnected for 4 min after boot or disconnect. |
| 5 | L2CAP trace of the FIRST connection since boot (hook at 0x18f5e), frozen afterwards. CCCDs moved into the runtime block. Disconnect calls stock LED `0xf60c(4,2)` (does not work, see below). |

## Evidence

### Console attempt, candidate 5 (`sw2_diag.py` output)

```
diag bytes: 00 00 00 00 00 00 00 3b 00 00 00 00 00 13 00 02 00 00 00 00 00 00 00 00 00 00 00 00 00 3d 00
commands accepted 0, replies 0, LTK never requested, encryption never started
last disconnect 0x13; first connection 61 s (0x3d); connections so far 2 (2nd = PC diag read)
ATT MTU 0, discovery 0, reads 0, write req 0, write cmd 0, other ATT 0, SMP 0, signalling 0, other CID 0
```

Byte 7 (0x3b) is the PC's own Service Changed CCCD write during the diag read.
It is not sticky and carries no console information.

### Trace validation with the PC as the first connection

Power-cycled, then `sw2_command_probe.py` as connection 1, diag as connection 2:

```
trace: 02 01 26 02 05 08 00 12 1f 3b 00 00 00 00 07 00
MTU 1, discovery 38, reads 2, write req 5, write cmd 8, first written handle 0x3b,
last ATT 0x12 on 0x1f, SMP 0, signalling 0, duration 7 s
```

That matches the probe exactly (8 commands), so the hook sees all L2CAP traffic.
The console's all-zero trace is real.

### Candidate 4 console attempt

Same picture with the older record: 0 commands, no LTK request, disconnect 0x13
after the user powered the Switch off. Windows has no pairing for the Y-mode
address E4:17:D8:BC:66:36 (only stock-mode addresses …66:AB/AD/B1). No BLE client
process was running. The connected peer was the console.

## Leading hypotheses (ranked)

1. **A link-layer control procedure the console waits on never completes the way it
   expects.** Candidates: feature exchange (0x08/0x09), version (0x0C), data length
   (0x14/0x15), PHY 2M (0x16/0x17/0x18), connection parameter request (0x0F).
   A standard LL response timeout would end the link with 0x22 after 40 s. The
   console held 61 s and ended with 0x13, so this is either a completed procedure
   whose result the console dislikes, or the console idling.
2. **The console expects the peripheral to act first**, for example a peripheral-initiated
   procedure the real Pro Controller 2 performs. Stock requests (MTU 64, conn params
   6/6/59/200) are suppressed in Y mode since V3.
3. **Something in CONNECT_IND or the advertisement makes the console treat the link
   differently**, for example the channel selection bit or address type. The link
   itself is healthy (no supervision timeout).

Windows connects and runs full GATT on the same firmware, so the difference is
console-specific.

## Proposed next step: LL control RX trace (not built yet)

Hook point found and checked:

- Stock wrapper `FUN_00017264`: `push lr; if byte[0x844c10+0x2f]==0: tjl 0x16c04; r0=0; pop`.
  Registered by LL init `0x1619c` into RAM slot `0x844a20` via literal at flash
  `0x16200` (value `0x17265`).
- **Patch call site `0x17270`, stock bytes `ff97c89c` (`tjl 0x16c04`)**, same pattern as
  the other hooks. The wrapper passes the packet in r0 and ignores the return.
- `0x16c04` prologue: `push {r4-r7,lr}; mov r7,r8; push {r7}; sub sp,#32; r4=r0`.
  Uses r0 only.
- Packet layout as used by `0x16c04`: `[4]` header (LLID = `&3`, 3 = control),
  `[5]` payload length (0 = empty PDU), `[6]` control opcode.
- It probably runs in the radio/LL event path, so keep the hook to a few byte writes.
- Storage: the 31-byte record at `0x846fb8` is full and the 68-byte runtime block at
  `0x84710c` is full. Repurpose trace bytes 15..30. Suggestion: connections,
  duration, L2CAP total, ATT writes, SMP count, LL control count, first 9 LL control
  opcodes, last LL control opcode.
- TX side, optional: init also stores `0x163b5` (`FUN_000163b4`, LL TX enqueue) into
  slot `0x844b48` via literal `0x16210`. Direct `tjl 0x163b4` calls bypass that slot.

Validate on the PC first. An Intel adapter normally sends feature, length and PHY
procedures, so a PC-first trace should show them.

**A BLE sniffer (nRF52840 dongle + Wireshark) would answer this in one capture.**
The user has refused to buy hardware so far. Mention it if the LL trace is ambiguous.

## Other findings

- **Idle power-off.** Key scanner `0xf298` counts idle scans in u16 `0x845fd4`. The
  unconnected threshold is at `0x845a1c` (about 1-2 min). Key presses do NOT reset the
  count while unconnected. Pairing-mode flag `0x846013` zeroes the count each scan,
  and the connect handler `0xd448` clears it. Candidate 4+ uses this.
  Stock disconnect `0xd4e0` also powers off on reason 0x13; ours does not.
- **LED is unreliable in Y mode.** Solid appears on ANY connection, including the
  PC probe, and stays solid after disconnect even with candidate 5's `0xf60c(4,2)`.
  State var `0x846008` (written by `0xf60c` channel 4) is read by the RAM LED engine
  `FUN_0000089c`. Other channel-4 setters: `0xfe7c` (pairing mode on/off), `0x10de4`
  (USB cable detect forces solid), key scanner `0xf298` (state 0). Stock disconnect
  also sets app state `0x844458+8 = 2`, which ours skips. Unresolved, cosmetic.
  Tell the user to ignore the LED and use `sw2_diag.py`.
- **Notify 0xB4 root cause.** `0x188b0` refuses while `now - ATT+0x1c <= 10000*ATT+0x28*16`.
  ATT+0x28 (`0x844d94`) is the pending time in 10 ms units. Only discovery opcodes
  0x04/0x06/0x08/0x10 stamp ATT+0x1c (0x17d30/0x17d8a/0x17e60/0x17f0a, opcode jump
  table `0x1c48c`). Zeroed in Y mode since candidate 2.
- **Bond side effect** (not yet exercised): a saved Nintendo bond is a stock journal
  record, so stock normal mode would treat the console as its newest bond.

## Tools

- `tools/sw2_diag.py`: read-only. Decodes the advertisement and the 31-byte record.
  Counts and the trace survive later PC connections.
- `tools/sw2_command_probe.py`: transport test plus `--input-secs N` decoded input stream.
- `tools/sw2_wait_reboot.py`: waits until the controller stops advertising, then
  until it advertises again. Use it before a PC-first validation. I once read a stale
  record because the controller had not actually been rebooted.
- Procedure for a console test: boot with Y held, Change Grip/Order, L+R, wait about
  30 s, sleep the console or enable airplane mode, then run `sw2_diag.py`. The pad
  stays awake 4 min after the disconnect.

## Gotchas hit this session

- Python `Path.write_text` on Windows writes CRLF. That broke `build.sh`.
  `.gitattributes` now pins `*.sh` to LF.
- The TC32 build links no libgcc. A plain `/` on u32 fails with `__udivsi3` undefined.
- Don't filter build output through grep without checking the exit status. A failed
  link looked like a missing `patch_*.bin`.
- The WSL shell prints `ok now generated...` on every `tc32.sh` call. It comes from
  outside the repo and is harmless.
- `runtime_test.c` simulates a reboot partway. The record is cleared there by design.
