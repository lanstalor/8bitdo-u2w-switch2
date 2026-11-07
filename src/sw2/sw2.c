/* Switch 2 mode selected with Y at boot. Uses the stock LL and bond journal,
 * plus Nintendo command pairing and bounded input reports. Hardware acceptance
 * must still be tested; host simulations cannot prove radio interoperability. */
typedef unsigned char u8;
typedef unsigned int u32;
#include "protocol.h"
#include "session.h"
#include "phy_blob.inc"

extern int fw_setAdvData(u8 *p, u8 len);      /* 0x15894 */
extern int fw_setScanRspData(u8 *p, u8 len);  /* 0x15918 */

#define KEYS        (*(volatile u32 *)0x845fe4)   /* button bitmask the 2.4G init tests at power-on */
#define KEY_Y_MASK  0x20u    /* physical Y, measured on this pad via the boot-keys debug adv (2026-11-07) */

static const u8 adv_sw2[31] = {
    0x02, 0x01, 0x06,                               /* flags */
    0x1b, 0xff,                                     /* manufacturer specific, 26 bytes */
    0x53, 0x05, 0x01, 0x00, 0x03, 0x7e, 0x05, 0x69, 0x20, 0x00, 0x01,
    0x00,                                           /* 0x0B: 0x00 = pairing/discovery (0x81 = wake) */
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,             /* 0x0C: bonded console address (none yet) */
    0x0f, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
};
static const u8 rsp_sw2[16] = { 0x0f, 0x09, 'P','r','o',' ','C','o','n','t','r','o','l','l','e','r' };

static int sw2_mode(void)
{
    return (KEYS & KEY_Y_MASK) != 0;
}

/* Discovery-stage table. The stock dispatcher calls .w instead of copying
 * to .value when a callback exists (0x1821a..0x1823a). */
typedef struct {
    unsigned short count;
    u8 permissions, uuid_len;
    u32 value_len;
    const u8 *uuid, *value;
    int (*write)(void *);
    int (*read)(void *);
} Sw2Attribute;
#ifndef SW2_HOST_TEST
typedef char attribute_size_check[sizeof(Sw2Attribute) == 24 ? 1 : -1];
#endif
extern int fw_notify(unsigned short connection,unsigned short handle,const u8 *data,int length);
/* 31-byte proprietary-radio RX command scratch. References in 1.09:
 * 0xaf0 (2.4G RX), 0xff6c (2.4G init), 0x102d4 (2.4G reply).
 * The BLE mode does not run those paths. First eight bytes are diagnostic only. */
#define SW2_DEBUG ((volatile u8 *)0x846fb8)
/* 15-byte post-mortem record exposed read-only on char 0x26. Cleared ONLY at
 * boot (hook_set_gatt), never on connect/disconnect, so a PC connecting after
 * a failed console attempt reads the console's history. Layout:
 *  0 last command handle (0x14/0x16)   1 last cmd      2 last sub
 *  3 last reply notify status          4 commands accepted (mod 256)
 *  5 replies sent OK (mod 256)         6 last event: 1 bad frame, 2 queued,
 *    3 reply attempted, 0x40 LTK answered, 0x41 bond saved, 0xe1 save failed,
 *    0xe2 command dropped (one already queued), 0xe3 unknown/invalid command
 *  7 last CCCD/descriptor handle written (low byte)
 *  8 LTK request: 1 answered, 2 refused (EDIV/RAND nonzero), 3 refused (not paired)
 *  9 fw_ltkReply return               10 link encryption flag seen (1)
 * 11 bond save: 1 ok, 2 failed        12 effective ATT MTU (low byte) at last command
 * 13 last disconnect reason           14 pairing stage high-water (0..4) */
#define D_HANDLE 0
#define D_CMD 1
#define D_SUB 2
#define D_STATUS 3
#define D_NCMD 4
#define D_NREPLY 5
#define D_EVENT 6
#define D_CCCD 7
#define D_LTK 8
#define D_LTKRET 9
#define D_ENC 10
#define D_SAVE 11
#define D_MTU 12
#define D_DISC 13
#define D_STAGE 14
/* Candidate 12 first-connection trace, same bounded 31-byte allocation.
 * 15 connections,16 duration,17 L2CAP total,18 first CID low,19 first opcode,
 * 20 first length low,21/22 first two parameters,23 negotiated MTU low,24 maxPHY,
 * 25 negotiated MTU high,
 * 26 guard failures (1RX,2TX),27 successful feature enqueues,28 last L2CAP opcode,
 * 29 seen LL classes (feature,length,version,PHY,encryption,other,term,map),
 * 30 layout marker 0xcc. */
#define T_CONN 15
#define T_SECS 16
#define T_L2CAP 17
#define T_FIRST_CID 18
#define T_FIRST_OP 19
#define T_FIRST_LEN 20
#define T_FIRST_ARG0 21
#define T_FIRST_ARG1 22
#define T_MTU_LO 23
#define T_PHY_MAX 24
#define T_MTU_HI 25
#define T_GUARD_FLAGS 26
#define T_TX_OK 27
#define T_LAST_OP 28
#define T_LL_SEEN 29
#define T_LAYOUT 30
#define SW2_DEBUG_LEN 31
#define SW2_ATT_MTU 512u
#define SW2_TRANSPORT_SIZE 520u
#define SW2_RX_BUFFER ((u8 *)0x840d8c)
#define SW2_TX_BUFFER ((u8 *)0x840f9c)
#define SW2_GUARD 0x51a7c0deu
/* These are proprietary 2.4G-only buffers, unused in the BLE physical mode.
 * All literal references audited: RX64 @10050; assembly68 @0xba4.
 * Do not extend either allocation into adjacent stock state. */
typedef struct {
    Sw2Session session;
    u32 last_report;
    u32 idle_from;      /* TICKS at boot / last disconnect: keep-awake window start */
    u8 queued, channel, stored, configured;
    u8 own[6];
    u8 cccd[16];        /* RAM-backed CCCD values for handles b,f,1b,1f,23,27,2f,3b */
    u32 connected_at;   /* TICKS at the start of the current connection */
} Sw2Runtime;
/* Stock key scanner (0xf298) powers the pad off after a fixed count of idle
 * scans while unconnected (threshold u16 @0x845a1c, ~1-2 min) and key presses
 * do NOT reset that count while unconnected. The stock pairing-mode flag
 * @0x846013 zeroes the counter every scan; the stock connect handler clears
 * the flag. Hold it for 4 min after boot/disconnect so a failed console attempt
 * leaves time to read the post-mortem record with tools/sw2_diag.py. */
#define KEEP_AWAKE (*(volatile u8 *)0x846013)
#define KEEP_AWAKE_TICKS 0xE4E1C000u   /* 240 s at 16 MHz (u32 tick wraps at 268 s) */
typedef char state_size_check[sizeof(Sw2Runtime)<=68?1:-1];
#define STATE ((Sw2Runtime *)0x84710c)
#define QUEUE ((u8 *)0x84618c)
/* CCCDs live inside the 68-byte runtime block (fixed offset 46, checked below)
 * so the whole 31-byte scratch at 0x846fb8 is the readable post-mortem record.
 * Only the CCCD bytes are exposed by GATT, never the session/LTK. */
#define CCCD ((u8 *)(0x84710c + 46))
typedef char cccd_offset_check[__builtin_offsetof(Sw2Runtime,cccd)==46?1:-1];
#define TICKS (*(volatile u32 *)0x800740)
extern int fw_ltkReply(unsigned short,const u8 *);
extern int fw_ltkNegative(unsigned short);
extern void fw_registerLtk(int (*)(unsigned short,const u8 *,unsigned short));
extern void fw_registerEvent(int,void (*)(u8,u8 *,int));
extern void fw_stockDisconnect(u8,u8 *,int);
extern void fw_enableAdv(int);
extern void fw_disconnect(u8);
extern void fw_stockPairButton(void);
extern u32 fw_loadBond(u8, u8 *);
extern int fw_bondCount(void);
extern u32 fw_saveBond(u8 *);
extern void fw_compactBonds(void);
static int sw2_active(void);
static void copy(u8 *d,const u8 *s,int n) { while(n--) *d++=*s++; }
static void zero(u8 *d,int n) { while(n--) *d++=0; }
static int cccd_index(u32 handle)
{
    static const u8 handles[]={0xb,0xf,0x1b,0x1f,0x23,0x27,0x2f,0x3b};
    int i; for(i=0;i<8;++i) if(handle==handles[i]) return i;
    return -1;
}
static void advertise(void)
{
    u8 b[31]; copy(b,adv_sw2,31);
    if(STATE->session.bonded) { b[16]=0x81; copy(b+17,STATE->session.host,6); }
    fw_setAdvData(b,31);
}
static int ltk_request(unsigned short conn,const u8 *rand,unsigned short ediv)
{
    int i;
    if(ediv || (STATE->session.stage!=4 && !STATE->session.bonded)) {
        fw_ltkNegative(conn); SW2_DEBUG[D_LTK]=ediv?2:3; return 1;
    }
    for(i=0;i<8;++i) if(rand[i]) { fw_ltkNegative(conn); SW2_DEBUG[D_LTK]=2; return 1; }
    SW2_DEBUG[D_EVENT]=0x40; SW2_DEBUG[D_LTK]=1;
    SW2_DEBUG[D_LTKRET]=(u8)fw_ltkReply(conn,STATE->session.ltk);
    return 1;
}
extern void fw_ledState(u8 which,u8 state);   /* 0xf60c: (4,1) connected solid, (4,2) searching blink */
extern u8 fw_charging(void);                  /* 0x10e6c: stock disconnect skips the LED change when set */
/* configured bit 0 = event callback registered; bit 1 = usable Nintendo input.
 * A raw BLE connection (including a diagnostic PC) is not Nintendo readiness. */
static void input_led(int ready)
{
    if(ready) STATE->configured|=2;
    else STATE->configured&=(u8)~2;
    /* Reassert against other stock LED writers; f60c is a no-op if unchanged. */
    if(!fw_charging()) fw_ledState(4,ready?1:2);
}
static void bump(int i) { if(SW2_DEBUG[i]!=255) SW2_DEBUG[i]++; }
static void disconnected(u8 event,u8 *p,int n)
{
    u32 d,s;
    if(!sw2_active()) { fw_stockDisconnect(event,p,n); return; }
    if(p && n>0) SW2_DEBUG[D_DISC]=p[0];
    if(SW2_DEBUG[T_CONN]==1) {
        /* No libgcc division helper is linked: count whole seconds (16 MHz ticks). */
        d=TICKS-STATE->connected_at; s=0;
        while(d>=16000000u && s<254) { d-=16000000u; ++s; }
        SW2_DEBUG[T_SECS]=(u8)s;
    }
    /* Stock disconnect (0xd4e0) returns the LED to the searching pattern;
     * without this the LED stayed solid after the console dropped the link. */
    if(!fw_charging()) fw_ledState(4,2);
    STATE->configured&=(u8)~2;
    *(volatile u32 *)0x84445c=0;
    STATE->queued=0; STATE->session.stage=0;
    STATE->session.features=0; STATE->session.counter=0; zero(CCCD,16);
    STATE->idle_from=TICKS;
    advertise(); fw_enableAdv(1);
}
static void load_bond(void)
{
    u8 record[64]; int i;
    for(i=fw_bondCount()-1;i>=0;--i) {
        if(fw_loadBond((u8)i,record) && record[48]=='S' && record[49]=='W' &&
           record[50]=='2' && record[51]=='Y' && record[52]==1) {
            copy(STATE->session.host,record+2,6);
            copy(STATE->session.ltk,record+16,16);
            STATE->session.bonded=1; STATE->stored=1; break;
        }
    }
}
static void save_bond(void)
{
    u8 record[64]; int i;
    for(i=0;i<64;++i) record[i]=0xff;
    record[0]=*(volatile u8 *)0x844f45 | 0x10;
    record[1]=0; copy(record+2,STATE->session.host,6);
    record[8]=0; record[9]=0xff;
    copy(record+16,STATE->session.ltk,16);
    record[48]='S'; record[49]='W'; record[50]='2'; record[51]='Y'; record[52]=1;
    /* Use the stock bond journal, never an invented flash region. */
    fw_compactBonds();
    STATE->stored=fw_saveBond(record)?1:2; /* Failed saves never spin/write repeatedly. */
    SW2_DEBUG[D_SAVE]=STATE->stored;
    SW2_DEBUG[D_EVENT]=STATE->stored==1?0x41:0xe1;
}
static int sw2_discovery_write(void *packet)
{
    const u8 *p=(const u8 *)packet;
    u32 length=(u32)p[2]|((u32)p[3]<<8);
    u32 handle=(u32)p[7]|((u32)p[8]<<8);
    const u8 *h;
    u32 skip,n;
    int idx;
    if(length<3 || length>SW2_ATT_MTU) return 0;
    idx=cccd_index(handle);
    if(idx>=0) { if(length==5) copy(CCCD+2*idx,p+9,2); SW2_DEBUG[D_CCCD]=(u8)handle; return 0; }
    if(handle!=0x14 && handle!=0x16) { SW2_DEBUG[D_CCCD]=(u8)handle; return 0; }
    skip=handle==0x16?33:0;
    if(length<3+skip+8) { SW2_DEBUG[D_EVENT]=1; return 0; }
    h=p+9+skip; n=8+h[5];
    if(h[1]!=0x91 || h[2]!=1 || h[6] || h[7] || n>length-3-skip || n>64) { SW2_DEBUG[D_EVENT]=1; return 0; }
    if(STATE->queued) { SW2_DEBUG[D_EVENT]=0xe2; return 0; }
    copy(QUEUE,h,n); STATE->channel=(u8)handle; STATE->queued=(u8)n;
    SW2_DEBUG[D_HANDLE]=(u8)handle; SW2_DEBUG[D_CMD]=h[0]; SW2_DEBUG[D_SUB]=h[3];
    SW2_DEBUG[D_NCMD]++; SW2_DEBUG[D_MTU]=*(volatile u8 *)0x844d8e;
    SW2_DEBUG[D_EVENT]=2;
    return 0;
}
#include "gatt.inc"
extern void fw_setAttributeTable(const void *table);
extern void fw_resetConnPhy(void *state);
static void install_transport(void)
{
    u8 irq=*(volatile u8 *)0x800643;
    *(volatile u8 *)0x800643=0;
    /* 2.4G-only code overlays; same d9ba mode-transition guard as PHY.
     * 520-byte usable buffers plus two canary words each, ending8411ac. */
    zero(SW2_RX_BUFFER,SW2_TRANSPORT_SIZE);
    zero(SW2_TX_BUFFER,SW2_TRANSPORT_SIZE);
    *(volatile u32 *)(SW2_RX_BUFFER+520)=SW2_GUARD;
    *(volatile u32 *)(SW2_RX_BUFFER+524)=SW2_GUARD;
    *(volatile u32 *)(SW2_TX_BUFFER+520)=SW2_GUARD;
    *(volatile u32 *)(SW2_TX_BUFFER+524)=SW2_GUARD;
    *(volatile u32 *)0x844dd4=(u32)(unsigned long)SW2_RX_BUFFER;
    *(volatile u32 *)0x844dd8=(u32)(unsigned long)SW2_TX_BUFFER;
    *(volatile unsigned short *)0x844ddc=SW2_TRANSPORT_SIZE;
    *(volatile unsigned short *)0x844dde=SW2_TRANSPORT_SIZE;
    *(volatile unsigned short *)0x844d8c=SW2_ATT_MTU;
    *(volatile u8 *)0x800643=irq;
}
static void install_phy(void)
{
    unsigned int i;
    volatile u8 *destination=(volatile u8 *)0x840c04;
    u8 irq=*(volatile u8 *)0x800643;
    *(volatile u8 *)0x800643=0;
    /* Overlay only the 2.4G parser's RAM body, preserving its literal pool.
     * The flash original reloads on reset; d9ba is guarded during mode debounce. */
    for(i=0;i<sizeof(sw2_phy_blob);++i) destination[i]=sw2_phy_blob[i];
    fw_resetConnPhy((void *)0x844b7c);
    *(volatile u8 *)0x844d34=1;
    *(volatile u32 *)0x844d3c=SW2_RADIO_PHY_ADDR;
    *(volatile u32 *)0x844b88=SW2_PHY_INSTANT_ADDR;
    *(volatile u32 *)0x844b8c=SW2_PHY_START_ADDR;
    /* Publish LE2M only after all executable code and callbacks are ready. */
    *(volatile u32 *)0x844a04|=0x100;
    *(volatile u8 *)0x800643=irq;
}
void hook_set_gatt(const void *stock)
{
    int i;
    if(sw2_mode()) {
        for(i=0;i<31;++i) SW2_DEBUG[i]=0;
        SW2_DEBUG[T_LAYOUT]=0xcc;
        install_phy();
        install_transport();
        zero((u8 *)STATE,sizeof(*STATE));
        /* Read actual initialized public identity, not factory assumptions. */
        copy(STATE->own,(const u8 *)0x8449e4,6);
    }
    fw_setAttributeTable(sw2_mode() ? sw2_attributes : stock);
}

/* The replaced stock function at 0xfcb8 is a no-op. Its argument is the
 * stack-local address used by BOTH subsequent LL and advertising init calls.
 * Derive a stable, separate mode identity from this unit's factory MAC; no
 * factory/config flash is written and normal mode retains the stock address. */
void hook_prepare_address(u8 *address, int length)
{
    const volatile u8 *factory = (const volatile u8 *)0x7c000;
    int i;
    if (sw2_mode() && length == 6) {
        for (i = 0; i < 6; ++i) address[i] = factory[i];
        /* Candidate8: fresh test identity; candidate7 used xor0x80.
         * Factory address and bond journal remain untouched. */
        address[0] ^= 0x40;
    }
}

extern int fw_bondCount(void);
int hook_bond_count(void)
{
    /* Discovery mode must never target the last stock Windows bond. */
    return sw2_mode() ? 0 : fw_bondCount();
}

extern void fw_stockReports(void);
extern u8 fw_getTxFifoNumber(void);
static void trace_phy_progress(void)
{
    u8 phy;
    if(SW2_DEBUG[T_CONN]!=1 ||
       !*(volatile u32 *)0x84445c) return;
    phy=*(volatile u8 *)0x844b7d;
    if(phy>SW2_DEBUG[T_PHY_MAX]) SW2_DEBUG[T_PHY_MAX]=phy;
    SW2_DEBUG[T_MTU_LO]=*(volatile u8 *)0x844d8e;
    SW2_DEBUG[T_MTU_HI]=*(volatile u8 *)0x844d8f;
    if(*(volatile u32 *)(SW2_RX_BUFFER+520)!=SW2_GUARD ||
       *(volatile u32 *)(SW2_RX_BUFFER+524)!=SW2_GUARD) SW2_DEBUG[T_GUARD_FLAGS]|=1;
    if(*(volatile u32 *)(SW2_TX_BUFFER+520)!=SW2_GUARD ||
       *(volatile u32 *)(SW2_TX_BUFFER+524)!=SW2_GUARD) SW2_DEBUG[T_GUARD_FLAGS]|=2;
}
static int sw2_active(void)
{
    /* Runtime mode is the registered table, not the current button state. */
#ifdef SW2_HOST_TEST
    extern const void *sw2_test_attributes;
    return sw2_test_attributes == sw2_attributes;
#else
    return *(const void * volatile *)0x844d6c == sw2_attributes;
#endif
}
extern void fw_stockRadioLoop(void);
void hook_stock_radio_loop(void)
{
    /* Physical switch is live before stock debounce resets. Do not execute
     * the overwritten 2.4G parser during that brief transition. */
    if(*(volatile u32 *)0x844d3c!=SW2_RADIO_PHY_ADDR) fw_stockRadioLoop();
}
void hook_reports(void)
{
    u8 response[160]; int n,prefix,status;
    const volatile u32 *controls=(const volatile u32 *)0x846d44;
    if (!sw2_active()) { fw_stockReports(); return; }
    trace_phy_progress();
    if(!(STATE->configured&1)) {
        fw_registerEvent(4,disconnected); STATE->configured|=1;
    }
    if(!*(volatile u32 *)0x84445c) {
        input_led(0);
        if((u32)(TICKS-STATE->idle_from)<KEEP_AWAKE_TICKS) KEEP_AWAKE=1;
        return;
    }
    input_led((STATE->configured&2)!=0 && STATE->session.bonded &&
              *(volatile u8 *)0x844c3e && (CCCD[2]&1) && (STATE->session.features&3));
    if(STATE->queued) {
        prefix=STATE->channel==0x16?14:0;
        if(!(CCCD[STATE->channel==0x16?6:4]&1)) return;
        zero(response,prefix);
        n=sw2_session_reply(&STATE->session,STATE->own,QUEUE,STATE->queued,
                             response+prefix,sizeof(response)-prefix);
        if(!n) { STATE->queued=0; SW2_DEBUG[D_EVENT]=0xe3; return; }
        n+=prefix;
        status=fw_notify(0x40,STATE->channel==0x16?0x1e:0x1a,response,n);
        SW2_DEBUG[D_STATUS]=(u8)status; SW2_DEBUG[D_EVENT]=3;
        if(STATE->session.stage>SW2_DEBUG[D_STAGE]) SW2_DEBUG[D_STAGE]=STATE->session.stage;
        if(status==0) {
            SW2_DEBUG[D_NREPLY]++;
            if(QUEUE[0]==0x15 && QUEUE[3]==1) STATE->stored=0;
            if(QUEUE[0]==0x15 && QUEUE[3]==3) STATE->session.bonded=1;
            STATE->queued=0;
        }
        return; /* Retain the request through busy/FIFO-full errors. */
    }
    if(*(volatile u8 *)0x844c3e) SW2_DEBUG[D_ENC]=1;
    if(STATE->session.bonded && !STATE->stored && *(volatile u8 *)0x844c3e) save_bond();
    /* Input is gated on the CCCD and enabled features only, NOT on link
     * encryption: the console always encrypts, and a PC (which cannot use the
     * Nintendo LTK) must be able to verify report framing and button/stick
     * mapping before the console test. */
    if(!(CCCD[2]&1) || !(STATE->session.features&3)) return;
    if((u32)(TICKS-STATE->last_report)<240000) return;
    sw2_input(response,STATE->session.counter,STATE->session.features,
              controls[0],controls[1],controls[2],controls[3]);
    if(!fw_notify(0x40,0xe,response,63)) {
        STATE->session.counter++; STATE->last_report=TICKS;
        input_led(STATE->session.bonded && *(volatile u8 *)0x844c3e);
    }
}

void hook_pair_button(void)
{
    if(!sw2_active()) { fw_stockPairButton(); return; }
    if(!*(volatile u8 *)0x846020) return;
    *(volatile u8 *)0x846020=0;
    STATE->session.bonded=0; STATE->session.stage=0; STATE->queued=0;
    STATE->session.features=0; STATE->session.counter=0; input_led(0);
    zero(CCCD,16);
    /* The stock path changes the Bluetooth identity. Keep the same identity
     * and return to Nintendo discovery instead. Existing flash bond remains
     * available if pairing is cancelled by a power cycle. */
    if(*(volatile u32 *)0x84445c) fw_disconnect(0x13);
    else { fw_enableAdv(0); advertise(); fw_enableAdv(1); }
}

extern int fw_requestMtu(unsigned short connection, unsigned short mtu);
int hook_request_mtu(unsigned short connection, unsigned short mtu)
{
    if (!sw2_active()) return fw_requestMtu(connection, mtu);
    /* Both transport buffers were expanded at boot before advertising. */
    *(volatile unsigned short *)0x844d8c = SW2_ATT_MTU;
    /* ATT+0x28: server data-pending time in 10 ms units. Stock notify
     * (0x188b0) returns 0xB4 while now-tick <= 10000*byte*16 after the last
     * discovery PDU (ATT opcodes 0x04/0x06/0x08/0x10 stamp ATT+0x1c at
     * 0x17d30/0x17d8a/0x17e60/0x17f0a). Zero means no hold-off, so replies
     * are never delayed ~300 ms after the console's service discovery. */
    *(volatile u8 *)0x844d94 = 0;
    STATE->queued=0; zero(CCCD,16); STATE->session.stage=0;
    STATE->session.features=0; STATE->session.counter=0;
    STATE->configured&=(u8)~2;
    /* Stock connect already lit the LED solid at 0xd454. Override it until
     * encrypted Nintendo input has actually been submitted successfully. */
    if(!fw_charging()) fw_ledState(4,2);
    bump(T_CONN); STATE->connected_at=TICKS;
    if(SW2_DEBUG[T_CONN]==1) SW2_DEBUG[T_SECS]=255;   /* overwritten at disconnect */
    return 0;
}

/* Every reassembled L2CAP PDU passes through 0x18bb8 on its way to the
 * dispatcher 0x18f50 (call site 0x18f5e; r0 = packet, returns packet or 0).
 * Packet: [2..3] L2CAP length, [4..5] CID, [6] opcode/code, [7..8] ATT handle. */
extern const u8 *fw_l2capReassemble(const u8 *p);
const u8 *hook_l2cap(const u8 *p)
{
    const u8 *r=fw_l2capReassemble(p);
    u32 length;
    if(!r || !sw2_active() || SW2_DEBUG[T_CONN]!=1) return r;
    length=(u32)r[2]|((u32)r[3]<<8);
    if(!SW2_DEBUG[T_L2CAP]) {
        SW2_DEBUG[T_FIRST_CID]=r[4];
        SW2_DEBUG[T_FIRST_LEN]=r[2];
        if(length>0) SW2_DEBUG[T_FIRST_OP]=r[6];
        if(length>1) SW2_DEBUG[T_FIRST_ARG0]=r[7];
        if(length>2) SW2_DEBUG[T_FIRST_ARG1]=r[8];
    }
    if(length>0) SW2_DEBUG[T_LAST_OP]=r[6];
    bump(T_L2CAP);
    return r;
}

/* Stock wrapper 0x17264 calls 0x16c04 at 0x17270 with r0 = DMA packet.
 * Preserve the handler and return exactly; trace only plaintext control PDUs,
 * never encrypted data or LTK material. No allocation, logging or radio calls. */
extern int fw_llReceive(const u8 *p);
int hook_ll_receive(const u8 *p)
{
    u8 op,flag;
    if(sw2_active() && SW2_DEBUG[T_CONN]==1 && *(volatile u32 *)0x84445c &&
       !*(volatile u8 *)0x844c3e && (p[4]&3)==3 && p[5]) {
        op=p[6];flag=32;
        if(op==8 || op==9 || op==14) flag=1;
        else if(op==20 || op==21) flag=2;
        else if(op==12) flag=4;
        else if(op>=22 && op<=24) flag=8;
        else if(op>=3 && op<=6) flag=16;
        else if(op==2) flag=64;
        else if(op==1) flag=128;
        SW2_DEBUG[T_LL_SEEN]|=flag;
    }
    return fw_llReceive(p);
}
/* Only the FEATURE_RSP call at 0x1705a is patched. r0=queue flags,
 * r1=stock packet [LL header,length,opcode,features[8]]. Preserve both
 * arguments, packet bytes and stock return value. No retry behavior yet. */
extern int fw_llEnqueue(u32 flags,const u8 *packet);
int hook_feature_response(u32 flags,const u8 *p)
{
    int result;
    int trace=sw2_active() && SW2_DEBUG[T_CONN]==1 &&
              *(volatile u32 *)0x84445c && p[1]==9 && p[2]==9;
    result=fw_llEnqueue(flags,p);
    if(trace) {
        if(result) {
            bump(T_TX_OK);
        }
    }
    return result;
}

extern void fw_requestParameters(unsigned short, unsigned short, unsigned short, unsigned short);
void hook_request_parameters(unsigned short min, unsigned short max,
                             unsigned short latency, unsigned short timeout)
{
    if (!sw2_active()) fw_requestParameters(min, max, latency, timeout);
}

static int copy_and_call(const u8 *src, int n, int (*fn)(u8 *, u8))
{
    u8 b[31];
    int i;
    for (i = 0; i < n; i++)
        b[i] = src[i];
    return fn(b, (u8)n);
}

int hook_set_adv(u8 *p, u8 len)
{
    /* Normal mode: stock advertisement untouched. (The earlier debug variant
     * that stripped the name and appended the boot key bitmask is gone.) */
    if (!sw2_mode())
        return fw_setAdvData(p, len);
    /* Stock blc_smp_configSecurityRequestSending state: low/high nibbles
     * select new/reconnect requests; +1 is pending. Both paths are read by
     * 0x19d94/0x19ea8. Nintendo uses application pairing instead of SMP. */
    *(volatile u8 *)0x844f28=0;
    *(volatile u8 *)0x844f29=0;
    fw_registerLtk(ltk_request);
    STATE->idle_from=TICKS;
    load_bond(); advertise(); return 0;
}

int hook_set_scanrsp(u8 *p, u8 len)
{
    if (!sw2_mode())
        return fw_setScanRspData(p, len);
    return copy_and_call(rsp_sw2, sizeof rsp_sw2, fw_setScanRspData);
}
