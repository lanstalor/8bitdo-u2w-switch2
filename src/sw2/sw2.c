/* Switch 2 mode, step 1: advertising only.
 * Hooks the BLE init's two calls (bls_ll_setAdvData @0xd5b2, bls_ll_setScanRspData @0xd5ba).
 * Normal power-on: pass-through (stock behaviour). Y held at power-on: advertise like a Pro Controller 2.
 * No globals, small stack, no library calls. */
typedef unsigned char u8;
typedef unsigned int u32;

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

static int copy_and_call(const u8 *src, int n, int (*fn)(u8 *, u8))
{
    u8 b[31];
    int i;
    for (i = 0; i < n; i++)
        b[i] = src[i];
    return fn(b, (u8)n);
}

/* Debug (normal mode): stock AD structures minus local names, plus test manufacturer data
 * FF FF 'K' <KEYS u32 LE> = raw button bitmask sampled at power-on, so the trigger mask can be read by a scan. */
static int adv_with_keys(u8 *p, u8 len)
{
    u8 b[31];
    int n = 0, i = 0, k;
    u32 keys = KEYS;
    while (i + 1 < len) {
        u8 l = p[i];
        if (l == 0 || i + 1 + l > len)
            break;
        if (p[i + 1] != 0x08 && p[i + 1] != 0x09 && n + l + 1 <= 31) {
            for (k = 0; k <= l; k++)
                b[n + k] = p[i + k];
            n += l + 1;
        }
        i += l + 1;
    }
    if (n + 9 <= 31) {
        b[n++] = 8; b[n++] = 0xFF; b[n++] = 0xFF; b[n++] = 0xFF; b[n++] = 'K';
        b[n++] = (u8)keys; b[n++] = (u8)(keys >> 8); b[n++] = (u8)(keys >> 16); b[n++] = (u8)(keys >> 24);
    }
    return fw_setAdvData(b, (u8)n);
}

int hook_set_adv(u8 *p, u8 len)
{
    if (!sw2_mode())
        return adv_with_keys(p, len);
    return copy_and_call(adv_sw2, sizeof adv_sw2, fw_setAdvData);
}

int hook_set_scanrsp(u8 *p, u8 len)
{
    if (!sw2_mode())
        return fw_setScanRspData(p, len);
    return copy_and_call(rsp_sw2, sizeof rsp_sw2, fw_setScanRspData);
}
