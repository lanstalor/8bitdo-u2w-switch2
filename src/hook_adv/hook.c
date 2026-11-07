/* Step-3 test hook: wraps the firmware's bls_ll_setAdvData (FUN_00015894, copies <=31 B into the LL buffer).
 * Copies every AD structure except local names, then appends manufacturer data (test company 0xFFFF) so a scan
 * can prove this code ran. No globals, ~40 B of stack, no library calls. */
typedef unsigned char u8;

extern int fw_setAdvData(u8 *p, u8 len);   /* = 0x15894, from link.ld */

int hook_set_adv(u8 *p, u8 len)
{
    u8 buf[31];
    int n = 0, i = 0, k;
    u8 x = 0;

    while (i + 1 < len) {
        u8 l = p[i];
        if (l == 0 || i + 1 + l > len)
            break;
        if (p[i + 1] != 0x08 && p[i + 1] != 0x09 && n + l + 1 <= 31) {
            for (k = 0; k <= l; k++)
                buf[n + k] = p[i + k];
            n += l + 1;
        }
        i += l + 1;
    }
    if (n + 9 <= 31) {
        buf[n + 0] = 8;      /* AD length */
        buf[n + 1] = 0xFF;   /* manufacturer specific */
        buf[n + 2] = 0xFF;   /* company 0xFFFF = test ID */
        buf[n + 3] = 0xFF;
        buf[n + 4] = 'U';
        buf[n + 5] = '2';
        buf[n + 6] = 'W';
        buf[n + 7] = len;    /* original length passed in (expect 0x1e) */
        for (k = 0; k < n + 8; k++)
            x ^= buf[k];
        buf[n + 8] = x;      /* xor of everything before it: computed at runtime */
        n += 9;
    }
    return fw_setAdvData(buf, (u8)n);
}
