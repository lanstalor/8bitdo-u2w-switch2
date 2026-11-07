    .section .patch_d5b2, "ax"
    .code 16
    tjl hook_set_adv
    .section .patch_d5ba, "ax"
    .code 16
    tjl hook_set_scanrsp
    .section .patch_d768, "ax"
    .code 16
    tjl hook_set_gatt
    .section .patch_d570, "ax"
    .code 16
    tjl hook_prepare_address
    .section .patch_d5be, "ax"
    .code 16
    tjl hook_bond_count
    .section .patch_d74c, "ax"
    .code 16
    tjl hook_reports
    .section .patch_d750, "ax"
    .code 16
    tjl hook_pair_button
    .section .patch_d48a, "ax"
    .code 16
    tjl hook_request_mtu
    .section .patch_d496, "ax"
    .code 16
    tjl hook_request_parameters
