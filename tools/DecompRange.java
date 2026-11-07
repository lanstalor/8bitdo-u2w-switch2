import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;
import java.util.regex.*;

// Read-only report of functions and literal-pool values in a firmware range.
public class DecompRange extends GhidraScript {
    public void run() throws Exception {
        String[] a=getScriptArgs();
        long lo=Long.parseLong(a[1],16), hi=Long.parseLong(a[2],16);
        DecompInterface di=new DecompInterface(); di.openProgram(currentProgram);
        PrintWriter out=new PrintWriter(a[0]);
        for(Function f:currentProgram.getFunctionManager().getFunctions(toAddr(lo),true)) {
            if(f.getEntryPoint().getOffset()>=hi) break;
            var r=di.decompileFunction(f,60,monitor);
            out.println("=== "+f.getName()+" @ "+f.getEntryPoint()+" ===");
            if(!r.decompileCompleted()) continue;
            String c=r.getDecompiledFunction().getC(); out.println(c);
            Matcher m=Pattern.compile("(?:DAT|PTR_[A-Za-z0-9_]+)_([0-9a-f]{8})").matcher(c);
            java.util.Set<String> seen=new java.util.HashSet<>();
            while(m.find()) if(seen.add(m.group(1))) {
                var addr=toAddr(Long.parseLong(m.group(1),16));
                try {out.printf("literal %s = %08x%n",addr,getInt(addr));} catch(Exception e) {}
            }
        }
        out.close(); di.dispose();
    }
}
