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
void fw_stockRadioLoop(void) {stocks++;}
void fw_resetConnPhy(void *p) {assert(p==(void *)0x844b7c);((u8 *)p)[1]=1;((u8 *)p)[3]=8;}
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
static int ll_calls,enqueue_result,enqueue_calls;
static u8 tx_depth;
u8 fw_getTxFifoNumber(void) {return tx_depth;}
static const u8 feature_packet[]={3,9,9,0x3d,0,0,0,0,0,0,0};
int fw_llEnqueue(u32 flags,const u8 *p)
{assert(flags==0x8040 && p==feature_packet);enqueue_calls++;return enqueue_result;}
int fw_llReceive(const u8 *p) {(void)p;ll_calls++;return 37;}
static void ll_pdu(u8 op,u8 arg)
{u8 p[8]={0,0,0,0,3,2,op,arg};assert(hook_ll_receive(p)==37);}
const u8 *fw_l2capReassemble(const u8 *p) {return p;}
static void pdu(unsigned cid,u8 op,u8 handle)
{u8 p[16]={0};p[2]=3;p[4]=(u8)cid;p[5]=(u8)(cid>>8);p[6]=op;p[7]=handle;assert(hook_l2cap(p)==p);}
static void write_att(unsigned short h,const u8 *v,unsigned int len)
{
    u8 p[518]={0};assert(len<=509);p[2]=(u8)(len+3);p[3]=(u8)((len+3)>>8);
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
    assert(mmap((void *)0x7c000,0x1000,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)==(void *)0x7c000);
    {u8 address[6]={0};
     memcpy((void *)0x7c000,"\xb6\x66\xbc\xd8\x17\xe4",6);
     KEYS=KEY_Y_MASK;hook_prepare_address(address,6);
     assert(!memcmp(address,"\xf6\x66\xbc\xd8\x17\xe4",6));
     KEYS=0;memset(address,0x55,6);hook_prepare_address(address,6);
     assert(!memcmp(address,"\x55\x55\x55\x55\x55\x55",6));}
    KEYS=KEY_Y_MASK;memcpy((void *)0x8449e4,"\x35\x66\xbc\xd8\x17\xe4",6);
    hook_set_gatt(0);hook_set_adv(0,0);KEYS=0;
    assert(sw2_active() && key_cb);
    assert(!memcmp((void *)0x840c04,sw2_phy_blob,sizeof(sw2_phy_blob)));
    assert(*(u32 *)0x844d3c==SW2_RADIO_PHY_ADDR && *(u32 *)0x844b88==SW2_PHY_INSTANT_ADDR);
    assert(*(u32 *)0x844b8c==SW2_PHY_START_ADDR && (*(u32 *)0x844a04&0x100));
    assert(*(u32 *)0x844dd4==0x840d8c && *(u32 *)0x844dd8==0x840f9c);
    assert(*(unsigned short *)0x844ddc==520 && *(unsigned short *)0x844dde==520);
    assert(*(unsigned short *)0x844d8c==512);
    {int before=stocks;hook_stock_radio_loop();assert(stocks==before);
     sw2_test_attributes=0;hook_stock_radio_loop();assert(stocks==before);
     *(u32 *)0x844d3c=0;hook_stock_radio_loop();assert(stocks==before+1);
     *(u32 *)0x844d3c=SW2_RADIO_PHY_ADDR;sw2_test_attributes=sw2_attributes;}
    hook_request_mtu(0x40,64);*(u32 *)0x84445c=1;
    assert(led_state==2); /* A bare BLE link must not look ready. */
    /* L2CAP trace during the first connection */
    assert(SW2_DEBUG[T_CONN]==1 && SW2_DEBUG[T_SECS]==255);
    {u8 mtu[9]={0,0,3,0,4,0,2,0,2};assert(hook_l2cap(mtu)==mtu);}
    pdu(4,0x10,1);pdu(4,0x08,1);pdu(4,0x12,0x05);pdu(4,0x52,0x16);pdu(4,0x0a,0x07);
    pdu(6,0x01,0);pdu(6,0x05,0);pdu(5,0x13,0);pdu(7,0,0);pdu(4,0x1b,0);
    assert(SW2_DEBUG[T_LAYOUT]==0xcc && SW2_DEBUG[T_L2CAP]==11);
    assert(SW2_DEBUG[T_FIRST_CID]==4 && SW2_DEBUG[T_FIRST_OP]==2 && SW2_DEBUG[T_FIRST_LEN]==3);
    assert(SW2_DEBUG[T_FIRST_ARG0]==0 && SW2_DEBUG[T_FIRST_ARG1]==2);
    ll_pdu(8,0);ll_pdu(12,0);ll_pdu(20,0);ll_pdu(22,0);
    assert(SW2_DEBUG[T_LL_SEEN]==15 && ll_calls==4);
    {u8 empty[6]={0,0,0,0,3,0};assert(hook_ll_receive(empty)==37);}
    *(u8 *)0x844c3e=1;ll_pdu(0xff,0xff);assert(SW2_DEBUG[T_LL_SEEN]==15);
    *(u8 *)0x844c3e=0;
    enqueue_result=0;assert(hook_feature_response(0x8040,feature_packet)==0);
    assert(SW2_DEBUG[T_TX_OK]==0 && enqueue_calls==1);
    *(u8 *)0x8448f6=3;*(u8 *)0x8448f7=2;
    enqueue_result=1;assert(hook_feature_response(0x8040,feature_packet)==1);
    assert(enqueue_calls==2 && SW2_DEBUG[T_TX_OK]==1);
    *(unsigned short *)0x844d8e=512;trace_phy_progress();
    assert(SW2_DEBUG[T_MTU_LO]==0 && SW2_DEBUG[T_MTU_HI]==2 && SW2_DEBUG[T_GUARD_FLAGS]==0);
    *(u32 *)(SW2_RX_BUFFER+520)=0;trace_phy_progress();assert(SW2_DEBUG[T_GUARD_FLAGS]==1);
    *(u32 *)(SW2_RX_BUFFER+520)=SW2_GUARD;
    *(u32 *)(SW2_TX_BUFFER+524)=0;trace_phy_progress();assert(SW2_DEBUG[T_GUARD_FLAGS]==3);
    *(u32 *)(SW2_TX_BUFFER+524)=SW2_GUARD;SW2_DEBUG[T_GUARD_FLAGS]=0;
    *(u8 *)0x844b7d=2;trace_phy_progress();assert(SW2_DEBUG[T_PHY_MAX]==2);
    *(u8 *)0x844b7d=1;trace_phy_progress();assert(SW2_DEBUG[T_PHY_MAX]==2);
    write_att(0x1f,cccd,2);assert(CCCD[6]==1);
    notify_status=0xb4;command(cmd,8);assert(STATE->queued==8 && notify_length==23);
    notify_status=0;hook_reports();assert(!STATE->queued && notify_handle==0x1e && notified[14]==7);
    {u8 boundary[509]={0};memcpy(boundary+33,cmd,8);write_att(0x16,boundary,sizeof(boundary));
     assert(STATE->queued==8);hook_reports();assert(!STATE->queued && notified[14]==7);}
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
    assert(led_state==1); /* Encrypted, paired, subscribed, input sent. */
    notify_status=0xb4;TICKS+=240001;hook_reports();assert(STATE->session.counter==1);
    TICKS=STATE->connected_at+3u*16000000u;
    disconnect_cb(4,rand,1);assert(!*(u32 *)0x84445c && !CCCD[2] && advertised[16]==0x81);
    assert(SW2_DEBUG[T_SECS]==3 && led_state==2 && SW2_DEBUG[D_DISC]==0);
    assert(!STATE->session.features && !STATE->session.counter);
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
    assert(SW2_DEBUG[T_CONN]==1 && SW2_DEBUG[T_L2CAP]==0);pdu(4,0x02,0);assert(SW2_DEBUG[T_L2CAP]==1);
    ll_pdu(8,1);assert(SW2_DEBUG[T_LL_SEEN]==1);
    /* Second connection: trace frozen, connection count still increments. */
    hook_request_mtu(0x40,64);assert(SW2_DEBUG[T_CONN]==2);pdu(4,0x02,0);pdu(6,0x01,0);
    ll_pdu(0x0c,9);
    hook_feature_response(0x8040,feature_packet);assert(SW2_DEBUG[T_TX_OK]==0);
    ll_pdu(7,9);
    assert(SW2_DEBUG[T_L2CAP]==1 && SW2_DEBUG[T_LL_SEEN]==1);
    write_att(0x1f,cccd,2);cmd[0]=0xc;cmd[3]=2;cmd[5]=4;cmd[8]=0x2f;command(cmd,12);
    write_att(0xf,cccd,2);TICKS+=240001;hook_reports();
    assert(notify_handle==0xe && notify_length==63 && notified[1]==0x20 && notified[11]==0x38 && notified[14]==0x28);
    assert(led_state==2); /* PC reports alone must not light the ready LED. */
    STATE->session.bonded=1;*(u8 *)0x844c3e=1;
    notify_status=0xb4;TICKS+=240001;hook_reports();assert(led_state==2);
    notify_status=0;hook_reports();assert(led_state==1);
    {u8 disabled[2]={0};write_att(0xf,disabled,2);hook_reports();assert(led_state==2);}
    write_att(0xf,cccd,2);TICKS+=240001;hook_reports();assert(led_state==1);
    *(u8 *)0x844c3e=0;hook_reports();assert(led_state==2);
    STATE->session.features=0x2f;STATE->session.counter=9;
    hook_request_mtu(0x40,64);
    assert(!STATE->session.features && !STATE->session.counter && led_state==2);
    puts("PASS: runtime queue/backpressure, 150-byte reply, pairing, key callback, persistence, reboot/reconnect, input gating, unencrypted input, L2CAP trace freeze, Nintendo-ready LED, session reset");
    return 0;
}
