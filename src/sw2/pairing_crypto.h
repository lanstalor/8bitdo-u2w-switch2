#ifndef SW2_PAIRING_CRYPTO_H
#define SW2_PAIRING_CRYPTO_H
void sw2_aes128(const unsigned char key[16], const unsigned char input[16], unsigned char output[16]);
void sw2_pairing_key(const unsigned char host_key[16], unsigned char ltk[16]);
void sw2_pairing_proof(const unsigned char ltk[16], const unsigned char challenge[16], unsigned char proof[16]);
extern const unsigned char sw2_controller_key[16];
#endif
