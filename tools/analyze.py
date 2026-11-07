import sys, math, collections, re, struct
for p in sys.argv[1:]:
    b=open(p,'rb').read()
    h,pl=b[:28],b[28:]
    def ent(x):
        c=collections.Counter(x); n=len(x); return -sum(v/n*math.log2(v/n) for v in c.values())
    blocks=[pl[i:i+16] for i in range(0,len(pl)-15,16)]
    dup=len(blocks)-len(set(blocks))
    # entropy per 4KB window
    w=[round(ent(pl[i:i+4096]),2) for i in range(0,len(pl),4096)]
    strs=[s.decode() for s in re.findall(rb'[\x20-\x7e]{8,}',pl)]
    print('==',p.split('/')[-1],len(b),'bytes')
    print(' header:',h.hex(' '))
    print(' entropy %.3f  zero%% %.1f  dup16 %d/%d'%(ent(pl),100*pl.count(0)/len(pl),dup,len(blocks)))
    print(' 4K-window entropy:',w[:40])
    print(' first64:',pl[:64].hex())
    print(' KNLT/TLNK at:',[m.start() for m in re.finditer(b'KNLT|TLNK',pl)][:5])
    print(' strings(%d):'%len(strs),strs[:40])
