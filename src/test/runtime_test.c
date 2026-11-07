#define _GNU_SOURCE
#define SW2_HOST_TEST
#include <sys/mman.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../sw2/sw2.c"

static int notify_status, sends, ltk_calls, saved, stocks;
const void *sw2_test_attributes;
static unsigned char notified[160],advertised[31],bond[64];
static int notify_length;
static unsigned short notify_handle;
static int (*key_cb)(unsigned short,const u8 *,unsigned short);
static void (*disconnect_cb)(u8,u8 *,int);
int fw_setAdvData(u8 *p,u8 n) {assert(n<=31);memcpy(advertised,p,n);return 0;}
int fw_setScanRspData(u8 *p,u8 n) {(void)p;(void)n;return 0;}
void fw_setAttributeTable(const void *t) {sw2_test_attributes=t;}
int fw_bondCount(void) {return saved;}
void fw_stockReports(void) {stocks++;}
int fw_requestMtu(unsigned short c,unsigned short m) {(void)c;(void)m;return 0;}
void fw_requestParameters(unsigned short a,unsigned short b,unsigned short c,unsigned short d)
{(void)a;(void)b;(void)c;(void)d;}
int fw_notify(unsigned short c,unsigned short h,const u8 *p,int n)
{assert(c==0x40 && n<=160);sends++;notify_handle=h;notify_length=n;memcpy(notified,p,n);return notify_status;}
int fw_ltkReply(unsigned short c,const u8 *k)
{assert(c==0x40);assert(!memcmp(k,STATE->session.ltk,16));ltk_calls++;return 0;}
int fw_ltkNegative(unsigned short c) {(void)c;return 0;}
void fw_registerLtk(int (*cb)(unsigned short,const u8 *,unsigned short)) {key_cb=cb;}
void fw_registerEvent(int e,void (*cb)(u8,u8 *,int)) {assert(e==4);disconnect_cb=cb;}
void fw_stockDisconnect(u8 e,u8 *p,int n) {(void)e;(void)p;(void)n;stocks++;}
void fw_enableAdv(int n) {assert(n==0 || n==1);}
void fw_disconnect(u8 r) {assert(r==0x13);disconnect_cb(4,&r,1);}
void fw_stockPairButton(void) {stocks++;}
u32 fw_loadBond(u8 i,u8 *r) {assert(i==0);memcpy(r,bond,64);return 0x74000;}
u32 fw_saveBond(u8 *r) {memcpy(bond,r,64);saved=1;return 0x74000;}
void fw_compactBonds(void) {}
static int led_calls; static u8 led_state;
void fw_ledState(u8 w,u8 st) {assert(w==4);led_calls++;led_state=st;}
u8 fw_charging(void) {return 0;}
const u8 *fw_l2capReassemble(const u8 *p) {return p;}
static void pdu(unsigned cid,u8 op,u8 handle)
{u8 p[16]={0};p[4]=(u8)cid;p[5]=(u8)(cid>>8);p[6]=op;p[7]=handle;assert(hook_l2cap(p)==p);}
static void write_att(unsigned short h,const u8 *v,unsigned int len)
{
    u8 p[256]={0};assert(len<=244);p[2]=(u8)(len+3);p[3]=(u8)((len+3)>>8);
    p[7]=(u8)h;p[8]=(u8)(h>>8);memcpy(p+9,v,len);sw2_discovery_write(p);
}
static void command(const u8 *h,int n)
{u8 p[128]={0};memcpy(p+33,h,n);write_att(0x16,p,n+33);hook_reports();}
int main(void)
{
    u8 cmd[25]={7,0x91,1,1,0,0,0,0},rand[8]={0},cccd[2]={1,0};
    void *m=mmap((void *)0x840000,0x10000,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);
    assert(m==(void *)0x840000);
    assert(mmap((void *)0x800000,0x1000,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)==(void *)0x800000);
    KEYS=KEY_Y_MASK;memcpy((void *)0x8449e4,"\x35\x66\xbc\xd8\x17\xe4",6);
    hook_set_gatt(0);hook_set_adv(0,0);KEYS=0;
    assert(sw2_active() && key_cb);
    hook_request_mtu(0x40,64);*(u32 *)0x84445c=1;
    /* L2CAP trace during the first connection */
    assert(SW2_DEBUG[T_CONN]==1 && SW2_DEBUG[T_SECS]==255);
    pdu(4,0x02,0);pdu(4,0x10,1);pdu(4,0x08,1);pdu(4,0x12,0x05);pdu(4,0x52,0x16);pdu(4,0x0a,0x07);
    pdu(6,0x01,0);pdu(6,0x05,0);pdu(5,0x13,0);pdu(7,0,0);pdu(4,0x1b,0);
    assert(SW2_DEBUG[T_MTU]==1 && SW2_DEBUG[T_DISC]==2 && SW2_DEBUG[T_READ]==1);
    assert(SW2_DEBUG[T_WREQ]==1 && SW2_DEBUG[T_WCMD]==1 && SW2_DEBUG[T_FIRSTW]==0x05);
    assert(SW2_DEBUG[T_LASTOP]==0x1b && SW2_DEBUG[T_LASTH]==0x07 && SW2_DEBUG[T_OTHER]==1);
    assert(SW2_DEBUG[T_SMP]==2 && SW2_DEBUG[T_SMP1]==0x01 && SW2_DEBUG[T_SIG]==1 && SW2_DEBUG[T_SIG1]==0x13 && SW2_DEBUG[T_CID]==1);
    write_att(0x1f,cccd,2);assert(CCCD[6]==1);
    notify_status=0xb4;command(cmd,8);assert(STATE->queued==8 && notify_length==23);
    notify_status=0;hook_reports();assert(!STATE->queued && notify_handle==0x1e && notified[14]==7);
    /* Largest required canned flash reply and padded request. */
    cmd[0]=2;cmd[3]=4;cmd[5]=8;memcpy(cmd+8,"\x78\x7e\0\0\0\x30\1\0",8);
    command(cmd,16);assert(notify_length==150 && !STATE->queued);
    cmd[0]=0x15;cmd[3]=1;cmd[5]=14;memcpy(cmd+8,"\0\2\1\2\3\4\5\6\0\2\3\4\5\6",14);
    command(cmd,22);assert(STATE->session.stage==1 && notify_length==31);
    cmd[3]=4;cmd[5]=17;memset(cmd+9,0x11,16);command(cmd,25);assert(STATE->session.stage==2);
    cmd[3]=2;memset(cmd+9,0x22,16);command(cmd,25);assert(STATE->session.stage==3);
    cmd[3]=3;cmd[5]=1;command(cmd,9);assert(STATE->session.bonded && !saved);
    assert(key_cb(0x40,rand,0)==1 && ltk_calls==1);
    *(u8 *)0x844c3e=1;hook_reports();assert(saved && STATE->stored);
    cmd[0]=0xc;cmd[3]=2;cmd[5]=4;cmd[8]=0x2f;command(cmd,12);
    write_att(0xf,cccd,2);TICKS=240001;hook_reports();assert(notify_handle==0xe && notify_length==63);
    assert(STATE->session.counter==1);
    notify_status=0xb4;TICKS+=240001;hook_reports();assert(STATE->session.counter==1);
    TICKS=STATE->connected_at+3u*16000000u;
    disconnect_cb(4,rand,1);assert(!*(u32 *)0x84445c && !CCCD[2] && advertised[16]==0x81);
    assert(SW2_DEBUG[T_SECS]==3 && led_calls==1 && led_state==2 && SW2_DEBUG[D_DISC]==0);
    /* Keep-awake: unconnected ticks within 4 min set the stock pairing-mode flag; after that they don't. */
    *(u8 *)0x846013=0;hook_reports();assert(*(u8 *)0x846013==1);
    *(u8 *)0x846013=0;TICKS=STATE->idle_from+0xE4E1C000u;hook_reports();assert(*(u8 *)0x846013==0);
    assert(!memcmp(advertised+17,"\1\2\3\4\5\6",6));
    KEYS=KEY_Y_MASK;hook_set_gatt(0);hook_set_adv(0,0);KEYS=0;
    assert(STATE->session.bonded && STATE->stored && STATE->session.stage==0);
    assert(key_cb(0x40,rand,0)==1 && ltk_calls==2); /* Reconnect without 0x15. */
    *(u8 *)0x846020=1;hook_pair_button();assert(!STATE->session.bonded && advertised[16]==0);
    /* Unencrypted PC session: connect, enable features, subscribe -> input streams
     * (console always encrypts; PC must be able to verify the report before the console test). */
    hook_request_mtu(0x40,64);*(u32 *)0x84445c=1;*(u8 *)0x844c3e=0;notify_status=0;
    /* After the simulated reboot this is connection 1 again (record cleared at boot). */
    assert(SW2_DEBUG[T_CONN]==1 && SW2_DEBUG[T_MTU]==0);pdu(4,0x02,0);assert(SW2_DEBUG[T_MTU]==1);
    /* Second connection: trace frozen, connection count still increments. */
    hook_request_mtu(0x40,64);assert(SW2_DEBUG[T_CONN]==2);pdu(4,0x02,0);pdu(6,0x01,0);
    assert(SW2_DEBUG[T_MTU]==1 && SW2_DEBUG[T_SMP]==0);
    write_att(0x1f,cccd,2);cmd[0]=0xc;cmd[3]=2;cmd[5]=4;cmd[8]=0x2f;command(cmd,12);
    write_att(0xf,cccd,2);TICKS+=240001;hook_reports();
    assert(notify_handle==0xe && notify_length==63 && notified[1]==0x20 && notified[11]==0x38 && notified[14]==0x28);
    puts("PASS: runtime queue/backpressure, 150-byte reply, pairing, key callback, persistence, reboot/reconnect, input gating, unencrypted input, L2CAP trace freeze, LED reset");
    return 0;
}
