#include "session.h"
#include "protocol.h"
#include "pairing_crypto.h"
typedef unsigned char u8;
typedef unsigned int u32;
static void copy(u8 *d,const u8 *s,u32 n) { while(n--) *d++=*s++; }

int sw2_session_reply(Sw2Session *s,const u8 own[6],const u8 *h,u32 len,u8 *out,u32 cap)
{
    const u8 *d;
    u32 n=0,i;
    int r;
    if(len<8 || h[1]!=0x91 || h[2]!=1 || h[6] || h[7] || h[5]>len-8) return 0;
    d=h+8;
    if(h[0]!=0x15) {
        r=sw2_reply(0x14,h,len,out,cap);
        if(r && h[0]==0x0c && h[5]>=4) {
            if(h[3]==2 || h[3]==4) s->features=d[0];
            if(h[3]==3 || h[3]==5) s->features&=~d[0];
        }
        return r;
    }
    if(!h[5] || d[0]!=0) return 0;
    switch(h[3]) {
    case 1: if(h[5]<8 || d[1]==0 || (u32)h[5]<2u+6u*d[1]) return 0; n=9; break;
    case 4: if(h[5]!=17 || s->stage<1 || s->stage>2) return 0; n=17; break;
    case 2: if(h[5]!=17 || s->stage<2 || s->stage>3) return 0; n=17; break;
    case 3: if(h[5]!=1 || s->stage<3) return 0; n=1; break;
    default: return 0;
    }
    if(cap<8+n) return 0;
    for(i=0;i<8+n;++i) out[i]=0;
    out[0]=0x15; out[1]=1; out[2]=1; out[3]=h[3]; out[4]=0x10; out[5]=0x78;
    out[8]=1;
    switch(h[3]) {
    case 1:
        copy(s->host,d+2,6); s->stage=1; s->bonded=0;
        out[9]=4; out[10]=1; copy(out+11,own,6); break;
    case 4:
        sw2_pairing_key(d+1,s->ltk); copy(out+9,sw2_controller_key,16); s->stage=2; break;
    case 2:
        sw2_pairing_proof(s->ltk,d+1,out+9); s->stage=3; break;
    case 3: s->stage=4; break;
    }
    return (int)(8+n);
}

static void stick(u8 *o,u32 packed)
{
    /* Stock XInput builder 0x10fb8 uses centre minus each raw axis.
     * Low half is X, high half Y; Nintendo Y grows upwards as XInput does. */
    u32 x=(65535u-(packed&65535u))>>4, y=(65535u-(packed>>16))>>4;
    o[0]=(u8)x; o[1]=(u8)((x>>8)|((y&15)<<4)); o[2]=(u8)(y>>4);
}
void sw2_input(u8 out[63],u8 counter,u8 features,u32 k,u32 left,u32 right,u32 triggers)
{
    u32 i;
    for(i=0;i<63;++i) out[i]=0;
    out[0]=counter; out[1]=0x20;
    /* Position-based Nintendo mapping of the stock processed key bitmask. */
    out[2]=((k&0x2000)?1:0)|((k&0x1000)?2:0)|((k&0x10)?4:0)|((k&0x20)?8:0)
          |((k&0x800)?16:0)|(((triggers>>8)&255)>77?32:0)|((k&1)?64:0)|((k&4)?128:0);
    /* Hardware Switch test: processed0x80 is physical Left,0x40 Right. */
    out[3]=((k&0x100)?1:0)|((k&0x40)?2:0)|((k&0x80)?4:0)|((k&0x200)?8:0)
          |((k&0x400)?16:0)|((triggers&255)>77?32:0)|((k&8)?64:0)|((k&2)?128:0);
    out[4]=((k&0x20000)?1:0)|((k&0x200000)?2:0)|((k&0x4000000)?4:0)|((k&0x2000000)?8:0);
    stick(out+5,left); stick(out+8,right);
    out[11]=(features&0x20)?0x38:0x30;
    out[14]=(features&4)?0x28:0;
}
