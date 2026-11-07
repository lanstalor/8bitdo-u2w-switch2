#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "../sw2/protocol.h"
int main(void)
{
    unsigned char req[256]={0},out[160],tiny[7],expect[]={7,1,1,1,0x10,0x78,0,0,0};
    unsigned char *h=req+33;
    unsigned int i,j;
    int n;
    h[0]=7; h[1]=0x91; h[2]=1; h[3]=1;
    assert(sw2_reply(0x16,req,41,out,sizeof(out))==23);
    for(i=0;i<14;i++) assert(out[i]==0);
    assert(!memcmp(out+14,expect,sizeof(expect)));
    assert(sw2_reply(0x14,h,8,out,sizeof(out))==9);
    assert(!memcmp(out,expect,sizeof(expect)));
    memset(tiny,0xa5,sizeof(tiny));
    assert(!sw2_reply(0x14,h,8,tiny,sizeof(tiny)));
    for(i=0;i<sizeof(tiny);i++) assert(tiny[i]==0xa5);
    h[0]=2; h[3]=4; h[5]=8;
    memcpy(h+8,"\x40\x7e\0\0\0\x30\x01\0",8);
    assert(sw2_reply(0x16,req,49,out,sizeof(out))==94);
    assert(!memcmp(out+22,"\x40\0\0\0\0\x30\x01\0",8));
    assert(!memcmp(out+30,"\x01\0HEJ71001121247\0\0\x7e\x05\x69\x20",22));
    for(i=67;i<94;i++) assert(out[i]==0xff);
    for(i=0;i<49;i++) assert(!sw2_reply(0x16,req,i,out,sizeof(out)));
    h[8]=0x79; assert(!sw2_reply(0x16,req,49,out,sizeof(out)));
    h[8]=8; memset(h+12,0xff,4);
    assert(!sw2_reply(0x16,req,49,out,sizeof(out)));
    h[0]=0x10; h[3]=1; h[5]=0;
    assert(sw2_reply(0x14,h,8,out,sizeof(out))==20);
    assert(!memcmp(out+8,"\x02\x01\x04\x02\x0c\0\0\0\0\x02\x03\0",12));
    h[0]=0x15; assert(!sw2_reply(0x14,h,8,out,sizeof(out)));
    /* Exercise malformed frames, lengths and capacity under ASan/UBSan. */
    srand(9);
    for(i=0;i<20000;i++) {
        for(j=0;j<sizeof(req);j++) req[j]=(unsigned char)rand();
        n=sw2_reply(i&1?0x14:0x16,req,i%257,out,i%161);
        assert(n>=0 && n<=(int)(i%161));
    }
    puts("PASS: published init/flash/firmware vectors, truncation, bounds, 20000 malformed frames");
    return 0;
}
