import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.LinkedHashSet;
import java.util.Set;

// Args: <outfile> <addr hex>... For each address: list references to it, then decompile every function
// that references it (or, with prefix "f:", the function containing that address). Writes one report.
public class XrefDecomp extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        PrintWriter out = new PrintWriter(new FileWriter(a[0]));
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        Set<Function> done = new LinkedHashSet<>();
        for (int i = 1; i < a.length; i++) {
            boolean direct = a[i].startsWith("f:");
            long v = Long.parseLong(a[i].replace("f:", "").toLowerCase().replace("0x", ""), 16);
            Address t = toAddr(v);
            Set<Function> fs = new LinkedHashSet<>();
            if (direct) {
                Function f = getFunctionContaining(t);
                out.println("#### FUNC CONTAINING " + t + " -> " + (f == null ? "none" : f.getName()));
                if (f != null) fs.add(f);
            } else {
                out.println("#### XREFS TO " + t);
                for (Reference r : getReferencesTo(t)) {
                    Function f = getFunctionContaining(r.getFromAddress());
                    out.println("  from " + r.getFromAddress() + " " + r.getReferenceType() + " in " + (f == null ? "?" : f.getName()));
                    if (f != null) fs.add(f);
                }
            }
            for (Function f : fs) {
                if (done.contains(f)) { out.println("  (already decompiled " + f.getName() + ")"); continue; }
                done.add(f);
                DecompileResults r = di.decompileFunction(f, 60, monitor);
                out.println("=== " + f.getName() + " @ " + f.getEntryPoint() + " size " + f.getBody().getNumAddresses() + " ===");
                out.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "DECOMPILE FAILED: " + r.getErrorMessage());
            }
        }
        out.close();
    }
}
