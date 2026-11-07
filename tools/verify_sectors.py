# Check an image against the device-reported per-sector (CRC-16/MODBUS, sum32) from the final c3 verify burst
# of a capture. Usage: verify_sectors.py <ep0x06.txt> <ep0x83.txt> <image.bin> [--fill-from other.bin]
import sys
h=lambda s:s.replace(':','')
def crc16(d):
    c=0xFFFF
    for x in d:
        c^=x
        for _ in range(8): c=(c>>1)^0xA001 if c&1 else c>>1
    return c
def load(f): return [l.split('\t') for l in open(f).read().split('\n') if '\t' in l]
O,I=load(sys.argv[1]),load(sys.argv[2])
img=bytearray(open(sys.argv[3],'rb').read())
if '--fill-from' in sys.argv:
    src=open(sys.argv[sys.argv.index('--fill-from')+1],'rb').read(); img[0x5000:0x8000]=src[0x5000:0x8000]
ev=sorted([(float(t),0,bytes.fromhex(h(d))) for t,d in O]+[(float(t),1,bytes.fromhex(h(d))) for t,d in I])
pairs=[];last=None
for t,k,d in ev:
    if k==0: last=d
    elif last is not None: pairs.append((last,d)); last=None
c3=[(o,i) for o,i in pairs if o[1]==5 and o[2]==0xc3]
nsec=(len(img)+0xfff)//0x1000; ver=c3[-nsec:]; ok=0
for o,i in ver:
    a=int.from_bytes(o[18:22],'little'); n=int.from_bytes(o[22:26],'little'); s=bytes(img[a:a+n])
    exp=crc16(s).to_bytes(2,'little')+(sum(s)&0xffffffff).to_bytes(4,'little')
    if exp==i[18:24]: ok+=1
    else: print('MISMATCH sector',hex(a),'device',i[18:24].hex(),'image',exp.hex())
print(f'{ok}/{len(ver)} sectors match device-reported checksums')
if '--save' in sys.argv: open(sys.argv[sys.argv.index('--save')+1],'wb').write(img); print('saved')
