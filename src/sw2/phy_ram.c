/* B80 1M/2M radio support adapted from Telink B80 SDK phy.o and
 * ll_conn_phy.o (Apache-2.0). Stock 1.09 state layout differs from SDK.
 * Entire image executes from RAM: no calls to flash or compiler helpers. */
typedef unsigned char phy_u8;
typedef unsigned short phy_u16;
typedef unsigned int phy_u32;
#define PHY8(a) (*(volatile phy_u8 *)(a))
#define PHY16(a) (*(volatile phy_u16 *)(a))
#define PHY32(a) (*(volatile phy_u32 *)(a))
#define PHY_STATE ((volatile phy_u8 *)0x844d30)
#define CONN_PHY ((volatile phy_u8 *)0x844b7c)

void sw2_radio_phy(phy_u8 phy)
{
    if(phy!=1 && phy!=2) return;
    PHY_STATE[4]=phy;
    if(phy==2) {
        PHY32(0x801220)=0x06432a04;
        PHY8(0x800402)=0x4c;
        PHY8(0x800404)=0xe5;
        PHY32(0x800460)=0x61514636;
        PHY16(0x800464)=0x786d;
        PHY_STATE[7]=4;
        PHY16(0x844d38)=24;
    } else {
        PHY32(0x801220)=0x23200a16;
        PHY8(0x800402)=0x46;
        PHY8(0x800404)=0xf5;
        PHY32(0x800460)=0x5f4f4434;
        PHY16(0x800464)=0x766b;
        PHY_STATE[7]=8;
        PHY16(0x844d38)=40;
    }
}

void sw2_phy_instant(void)
{
    phy_u8 next=CONN_PHY[2];
    if(next!=1 && next!=2) return;
    if(CONN_PHY[1]!=next) PHY32(0x8449e0)|=0x80;
    CONN_PHY[1]=next;
    if(PHY_STATE[4]!=next) {
        sw2_radio_phy(next);
        /* Stock table is already adjusted: no SDK '-1' here. */
        PHY16(0x800f04)=((volatile phy_u8 *)0x844d48)[next];
    }
}

void sw2_phy_start(void)
{
    phy_u8 phy=CONN_PHY[1];
    if(PHY_STATE[4]!=phy) sw2_radio_phy(phy);
}
