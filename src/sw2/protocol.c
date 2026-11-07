/* Nintendo wire formats documented in notes/SWITCH2_PROTOCOL.md.
 * Pairing deliberately has no placeholder ACK: LTK installation is not wired yet. */
#include "protocol.h"
typedef unsigned char u8;
typedef unsigned int u32;
static void copy(u8 *to, const u8 *from, u32 n) { while(n--) *to++=*from++; }
static void clear(u8 *to,u32 n) { while(n--) *to++=0; }
static u32 get32(const u8 *p) { return (u32)p[0]|((u32)p[1]<<8)|((u32)p[2]<<16)|((u32)p[3]<<24); }
static const u8 info[] = {
  1,0,'H','E','J','7','1','0','0','1','1','2','1','2','4','7',0,0,
  0x7e,5,0x69,0x20,1,6,1,0x23,0x23,0x23,0xa0,0xa0,0xa0,0xe6,0xe6,0xe6,0x32,0x32,0x32
};
static const u8 block40[] = {0x3b,0xe0,0xd3,0x41,0xc6,0x60,0x6a,0xbc,0x4d,0xd7,0xa2,0xbb,0x71,0x1e,0xdd,0x37};
static const u8 cal_common[] = {
  1,0xad,0xd9,0x9a,0x55,0x56,0x65,0xa0,0,0x0a,0xa0,0,0x0a,0xe2,0x20,0x0e,0xe2,0x20,0x0e,
  0x9a,0xad,0xd9,0x9a,0xad,0xd9,0x0a,0xa5,0x50,0x0a,0xa5,0x50,0x2f,0xf6,0x62,0x2f,0xf6,0x62,0x0a,0xff,0xff
};
static const u8 cal_left[] = {0xb3,0x67,0x83,0x2e,0x66,0x5e,0x3a,6,0x5f};
static const u8 cal_right[] = {0x2c,8,0x84,0xd1,0x65,0x63,0x2a,0x26,0x62};
static const u8 block100[] = {0,0,0,0,0,0,0,0,0,0,0,0,0xa6,0xf2,0x62,0xbd,0xa8,0,8,0x3d,0x2f,0xed,0x20,0x41};
static u8 flash_byte(u32 a)
{
  u32 o;
  if(a>=0x13000 && a<0x13000+sizeof(info)) return info[a-0x13000];
  if(a>=0x13040 && a<0x13050) return block40[a-0x13040];
  if(a>=0x13080 && a<0x13100) {
    o=(a-0x13080)&63;
    if(o<sizeof(cal_common)) return cal_common[o];
    if(o<49) return a<0x130c0 ? cal_left[o-40] : cal_right[o-40];
  }
  if(a>=0x13100 && a<0x13118) return block100[a-0x13100];
  return 0xff;
}

int sw2_reply(u32 handle,const u8 *request,u32 length,u8 *reply,u32 capacity)
{
  const u8 *h,*d,*fixed=0;
  u32 prefix,skip,n=0,i,address=0,flash_len=0;
  static const u8 fw[]={2,1,4,2,12,0,0,0,0,2,3,0};
  static const u8 late11[]={1,0x20,3,0,0,0x0a,0xe8,0x1c,0x3b,0x79,0x7d,0x8b,0x3a,0x0a,0xe8,0x9c,0x42,0x58,0xa0,0x0b,0x42,0x0a,0xe8,0x9c,0x41,0x58,0xa0,0x0b,0x41};
  static const u8 late18[]={0,0,0x40,0xf0,0,0,0x60,0};
  static const u8 nfc[]={0x61,0x12,0x50,0x0d};
  if(handle==0x16) { skip=33; prefix=14; }
  else if(handle==0x14) { skip=0; prefix=0; }
  else return 0;
  if(length<skip+8) return 0;
  h=request+skip; d=h+8;
  if(h[1]!=0x91 || h[2]!=1 || h[6] || h[7] || h[5]>length-skip-8) return 0;
  if(h[0]==0x15) return 0; /* Requires real pairing state and encryption integration. */
  if(h[0]==2 && h[3]==4) {
    if(h[5]!=8 || d[0]>0x78) return 0;
    flash_len=d[0]; address=get32(d+4);
    if(address>0xffffffffu-flash_len) return 0;
    n=8+flash_len;
  } else if(h[0]==7 && h[3]==1) n=1;
  else if(h[0]==0x16 && h[3]==1) n=24;
  else if(h[0]==0x0c) n=4;
  else if(h[0]==0x11 && h[3]==1) n=4;
  else if(h[0]==0x11 && h[3]==3) { fixed=late11; n=sizeof(late11); }
  else if(h[0]==0x18 && h[3]==1) { fixed=late18; n=sizeof(late18); }
  else if(h[0]==0x18 && h[3]==3) {
    if(h[5]<1) return 0;
    fixed=d; n=1;
  } else if(h[0]==0x10 && h[3]==1) { fixed=fw; n=sizeof(fw); }
  else if(h[0]==1 && h[3]==0x0c) { fixed=nfc; n=sizeof(nfc); }
  if(capacity<prefix+8+n) return 0;
  clear(reply,prefix+8+n);
  reply[prefix]=h[0]; reply[prefix+1]=1; reply[prefix+2]=h[2];
  reply[prefix+3]=h[3]; reply[prefix+4]=0x10; reply[prefix+5]=0x78;
  if(fixed) copy(reply+prefix+8,fixed,n);
  else if(h[0]==2 && h[3]==4) {
    reply[prefix+8]=(u8)flash_len;
    copy(reply+prefix+12,d+4,4);
    for(i=0;i<flash_len;++i) reply[prefix+16+i]=flash_byte(address+i);
  } else if(h[0]==0x11 && h[3]==1) reply[prefix+8]=1;
  return (int)(prefix+8+n);
}
