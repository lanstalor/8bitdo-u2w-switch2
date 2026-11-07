typedef unsigned char u8; typedef unsigned int u32;
extern int notify(u32 conn, u32 handle, u8 *p, u32 len);
static u8 buf[8];
int send_test(u8 v) { buf[0] = v; buf[1] = v + 1; return notify(0x40, 0x0e, buf, 2); }
