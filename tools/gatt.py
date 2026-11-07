# Parse Telink attribute_t tables: {u16 attNum; u8 perm; u8 uuidLen; u32 attrLen; u32 uuid*; u32 value*; u32 w_cb; u32 r_cb} = 24 bytes
import sys,struct
f,base=sys.argv[1],int(sys.argv[2],16)
b=open(f,'rb').read()
def rd(a,n):
    o=a-base
    return b[o:o+n] if 0<=o<=len(b)-n else None
def valid(a): return base<=a<base+len(b) or 0x840000<=a<0x860000
cands=[]
for o in range(0,len(b)-24,4):
    n,perm,ul,al,up,vp,w,r=struct.unpack_from('<HBBIIIII',b,o)
    if n>=8 and n<120 and perm==0 and ul==0 and al==0 and up==0 and vp==0:
        # next entry must look like primary service decl (uuid 0x2800, len 2)
        n2,p2,ul2,al2,up2,vp2,w2,r2=struct.unpack_from('<HBBIIIII',b,o+24)
        u=rd(up2,2)
        if ul2==2 and u==b'\x00\x28': cands.append((o,n))
for o,n in cands:
    print('== table @%#x attNum=%d'%(o+base,n))
    for i in range(1,n):
        e=o+24*i
        _,perm,ul,al,up,vp,w,r=struct.unpack_from('<HBBIIIII',b,e)
        u=rd(up,ul) if ul in (2,16) else None
        us=u[::-1].hex() if u else '?'
        v=rd(vp,min(al,24)) if valid(vp) and vp<0x840000 else None
        print(' h%#04x perm=%02x uuid=%s len=%d val@%#x %s w=%#x r=%#x'%(i,perm,us,al,vp,(v.hex() if v else ''),w,r))
