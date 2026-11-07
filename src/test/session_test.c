#include <assert.h>
#include <string.h>
#include <stdio.h>
#include "../sw2/session.h"

int main(void)
{
    Sw2Session s={0},before;
    unsigned char cmd[32]={0x15,0x91,1,1,0,14,0,0,0,2,1,2,3,4,5,6,0,2,3,4,5,6};
    unsigned char own[]={0x35,0x66,0xbc,0xd8,0x17,0xe4},out[160],again[160];
    int i,n;
    for(i=0;i<22;++i) assert(!sw2_session_reply(&s,own,cmd,i,out,sizeof(out)));
    assert(s.stage==0);
    before=s;
    assert(!sw2_session_reply(&s,own,cmd,22,out,16));
    assert(!memcmp(&s,&before,sizeof(s)));
    assert(sw2_session_reply(&s,own,cmd,22,out,sizeof(out))==17);
    assert(!memcmp(out+8,"\1\4\1",3) && !memcmp(out+11,own,6));
    assert(!memcmp(s.host,cmd+10,6));
    cmd[3]=2; cmd[5]=17;
    assert(!sw2_session_reply(&s,own,cmd,25,out,sizeof(out))); /* Out of order. */
    cmd[3]=4;
    memcpy(cmd+9,"\x35\x03\xe9\x29\x82\x87\x71\x24\xbe\xa8\x0c\x66\x46\x15\x83\x4b",16);
    n=sw2_session_reply(&s,own,cmd,25,out,sizeof(out)); assert(n==25);
    assert(sw2_session_reply(&s,own,cmd,25,again,sizeof(again))==n);
    assert(!memcmp(out,again,n)); /* Retry after notify backpressure. */
    assert(!memcmp(s.ltk,"\x69\xf5\x07\x50\xae\x58\x74\xc5\x04\x83\x6f\x43\x82\x0f\xdc\x5b",16));
    cmd[3]=2;
    memcpy(cmd+9,"\x6f\xc6\xdf\x8a\xd8\xfe\xdf\x15\xbb\x8c\x15\xe9\x1f\x32\x05\x44",16);
    assert(sw2_session_reply(&s,own,cmd,25,out,sizeof(out))==25);
    assert(!memcmp(out+9,"\x13\x4c\x97\xf5\x11\xb9\xb6\xdd\x4d\x86\xfd\x40\xf5\x36\xe9\xed",16));
    assert(sw2_session_reply(&s,own,cmd,25,again,sizeof(again))==25);
    assert(!memcmp(out,again,25));
    cmd[3]=3; cmd[5]=1;
    assert(sw2_session_reply(&s,own,cmd,9,out,sizeof(out))==9 && out[8]==1 && s.stage==4);
    cmd[0]=0xc; cmd[3]=2; cmd[5]=4; cmd[8]=0x2f;
    assert(sw2_session_reply(&s,own,cmd,12,out,sizeof(out))==12 && s.features==0x2f);
    sw2_input(out,255,s.features,0,0x80008000,0x80008000,0);
    assert(out[0]==255 && out[2]==0 && out[3]==0 && out[4]==0 && out[11]==0x38 && out[14]==40);
    for(i=15;i<63;++i) assert(out[i]==0);
    /* Stock XInput's four face buttons, clockwise from south, become
     * Nintendo B/A/X/Y by physical position. */
    sw2_input(out,0,3,0x2000,0,0,0); assert(out[2]==1);
    sw2_input(out,0,3,0x1000,0,0,0); assert(out[2]==2);
    sw2_input(out,0,3,0x20,0,0,0); assert(out[2]==8);
    sw2_input(out,0,3,0x10,0,0,0); assert(out[2]==4);
    sw2_input(out,0,3,0x200|0x800|1|2,0,0,0xff00);
    assert(out[2]==0x70 && out[3]==0x88);
    sw2_input(out,0,3,0x100|0x400|8|4,0,0,0xff);
    assert(out[2]==0x80 && out[3]==0x71);
    sw2_input(out,0,3,0,0xffff0000,0x0000ffff,0);
    assert(!memcmp(out+5,"\xff\x0f\0\0\xf0\xff",6));
    puts("PASS: complete pairing transcript, golden proof, duplicate replies, invalid sequencing, input framing");
    return 0;
}
