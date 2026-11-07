#ifndef SW2_PROTOCOL_H
#define SW2_PROTOCOL_H
/* Pure protocol code: no device memory or stack calls, host-testable. */
int sw2_reply(unsigned int handle, const unsigned char *request, unsigned int length,
              unsigned char *reply, unsigned int capacity);
#endif
