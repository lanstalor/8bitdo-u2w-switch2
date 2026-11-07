import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.program.model.address.Address;


import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import java.io.FileInputStream;

// Maps the first <len> bytes of the payload file (Telink ram_code, copied to SRAM at boot and run at VMA 0)
// as block "ramcode" at address 0, then creates functions at tpush{..,lr} prologues (high byte 0x65)
// and at every tjl target that lands inside the block. Args: <payload file> <len hex>
public class AddRamcode extends GhidraScript {
    @Override
    public void run() throws Exception {
        String path = getScriptArgs()[0];
        int len = Integer.parseInt(getScriptArgs()[1].toLowerCase().replace("0x", ""), 16);
        byte[] data = new byte[len];
        try (FileInputStream in = new FileInputStream(path)) { in.readNBytes(data, 0, len); }
        Memory mem = currentProgram.getMemory();
        MemoryBlock old = mem.getBlock("ramcode");
        if (old != null) mem.removeBlock(old, monitor);
        MemoryBlock blk = mem.createInitializedBlock("ramcode", toAddr(0), len, (byte) 0, monitor, false);
        blk.setRead(true); blk.setWrite(true); blk.setExecute(true);
        mem.setBytes(toAddr(0), data);
        int made = 0;
        for (long a = 0; a < len - 1; a += 2) {
            if ((data[(int) a + 1] & 0xff) != 0x65) continue;
            Address ad = toAddr(a);
            if (getFunctionContaining(ad) != null) continue;
            new DisassembleCommand(ad, null, true).applyTo(currentProgram, monitor);
            if (getInstructionAt(ad) != null && createFunction(ad, null) != null) made++;
        }
        println("RAMCODE block 0.." + Integer.toHexString(len) + " prologue funcs made=" + made
            + " total funcs=" + currentProgram.getFunctionManager().getFunctionCount());
    }
}
