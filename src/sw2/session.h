#ifndef SW2_SESSION_H
#define SW2_SESSION_H
typedef struct {
    unsigned char stage, bonded, features, counter;
    unsigned char host[6], ltk[16];
} Sw2Session;
/* Normalized command: eight-byte header, followed by declared data only. */
int sw2_session_reply(Sw2Session *s, const unsigned char own[6],
                      const unsigned char *cmd, unsigned int len,
                      unsigned char *out, unsigned int capacity);
void sw2_input(unsigned char out[63], unsigned char counter, unsigned char features,
               unsigned int keys, unsigned int left, unsigned int right,
               unsigned int triggers);
#endif
