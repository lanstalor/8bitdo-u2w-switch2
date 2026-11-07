#define _GNU_SOURCE
#include <sys/mman.h>
#include <assert.h>
#include <stdio.h>
#include "../sw2/phy_ram.c"
int main(void)
{
    assert(mmap((void *)0x800000,0x2000,PROT_READ|PROT_WRITE,
                MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)==(void *)0x800000);
    assert(mmap((void *)0x840000,0x10000,PROT_READ|PROT_WRITE,
                MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)==(void *)0x840000);
    PHY8(0x844d49)=0x52;PHY8(0x844d4a)=0x59;
    sw2_radio_phy(1);
    assert(PHY32(0x801220)==0x23200a16 && PHY8(0x800402)==0x46 && PHY8(0x800404)==0xf5);
    assert(PHY32(0x800460)==0x5f4f4434 && PHY16(0x800464)==0x766b);
    assert(PHY_STATE[4]==1 && PHY_STATE[7]==8 && PHY16(0x844d38)==40);
    CONN_PHY[1]=1;CONN_PHY[2]=2;CONN_PHY[3]=8;PHY32(0x8449e0)=0x400;
    sw2_phy_instant();
    assert(CONN_PHY[1]==2 && CONN_PHY[3]==8 && PHY32(0x8449e0)==0x480);
    assert(PHY_STATE[4]==2 && PHY_STATE[7]==4 && PHY16(0x844d38)==24);
    assert(PHY32(0x801220)==0x06432a04 && PHY8(0x800402)==0x4c && PHY8(0x800404)==0xe5);
    assert(PHY32(0x800460)==0x61514636 && PHY16(0x800464)==0x786d);
    assert(PHY16(0x800f04)==0x59); /* Stock table already adjusted. */
    sw2_radio_phy(1);sw2_phy_start();assert(PHY_STATE[4]==2);
    CONN_PHY[2]=1;sw2_phy_instant();assert(PHY_STATE[4]==1 && PHY16(0x800f04)==0x52);
    CONN_PHY[2]=3;sw2_phy_instant();sw2_radio_phy(0);
    assert(CONN_PHY[1]==1 && PHY_STATE[4]==1);
    puts("PASS: SDK radio register vectors, PHY instant event/settle, connection-start restore, invalid PHY guard");
    return 0;
}
