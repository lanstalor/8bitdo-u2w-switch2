#include <assert.h>
#include <string.h>
#include <stdio.h>
#include "../sw2/pairing_crypto.h"
int main(void)
{
 unsigned char k[16],p[16],out[16],ltk[16]; unsigned int i;
 for(i=0;i<16;i++) {k[i]=i;p[i]=i*17;}
 sw2_aes128(k,p,out);
 assert(!memcmp(out,"\x69\xc4\xe0\xd8\x6a\x7b\x04\x30\xd8\xcd\xb7\x80\x70\xb4\xc5\x5a",16));
 sw2_pairing_key((const unsigned char *)"\x35\x03\xe9\x29\x82\x87\x71\x24\xbe\xa8\x0c\x66\x46\x15\x83\x4b",ltk);
 assert(!memcmp(ltk,"\x69\xf5\x07\x50\xae\x58\x74\xc5\x04\x83\x6f\x43\x82\x0f\xdc\x5b",16));
 sw2_pairing_proof(ltk,(const unsigned char *)"\x6f\xc6\xdf\x8a\xd8\xfe\xdf\x15\xbb\x8c\x15\xe9\x1f\x32\x05\x44",out);
 assert(!memcmp(out,"\x13\x4c\x97\xf5\x11\xb9\xb6\xdd\x4d\x86\xfd\x40\xf5\x36\xe9\xed",16));
 puts("PASS: FIPS AES-128 and published Nintendo LTK/proof vectors");
 return 0;
}
